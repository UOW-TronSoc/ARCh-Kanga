#include "kanga_core_drive/wheel_actuator.hpp"

#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

#include "kanga_core_drive/transmission.hpp"

// Configure the joint-to-motor adapter and create all wheel ROS interfaces.
WheelActuator::WheelActuator(const rclcpp::NodeOptions & options)
: Node("wheel_actuator", options)
{
    // Declare the parameters
    this->declare_parameter<std::vector<std::string>>("wheel_ids", {"fl", "bl", "br", "fr"});
    // Selected drivetrain profile supplies the physical actuator parameters.
    this->declare_parameter<double>("motor_revolutions_per_wheel_revolution");
    this->declare_parameter<double>("motor_velocity_limit_tps");
    this->declare_parameter<double>("joint_command_timeout_s", 0.5);
    this->declare_parameter<double>("publish_rate_hz", 10.0);

    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    gear_ratio_ = this->get_parameter("motor_revolutions_per_wheel_revolution").as_double();
    motor_velocity_limit_tps_ = this->get_parameter("motor_velocity_limit_tps").as_double();
    joint_command_timeout_s_ = this->get_parameter("joint_command_timeout_s").as_double();
    const double publish_rate_hz = this->get_parameter("publish_rate_hz").as_double();

    // Check the parameters are valid
    if (wheel_ids_.size() != joint_commands_.size()) {
        throw std::runtime_error("wheel_ids must have exactly 4 entries");
    }
    if (!std::isfinite(gear_ratio_) || gear_ratio_ <= 0.0) {
        throw std::runtime_error("motor_revolutions_per_wheel_revolution must be finite and > 0");
    }
    if (!std::isfinite(motor_velocity_limit_tps_) || motor_velocity_limit_tps_ <= 0.0) {
        throw std::runtime_error("motor_velocity_limit_tps must be finite and > 0");
    }
    if (!std::isfinite(joint_command_timeout_s_) || joint_command_timeout_s_ <= 0.0) {
        throw std::runtime_error("joint_command_timeout_s must be finite and > 0");
    }
    if (!std::isfinite(publish_rate_hz) || publish_rate_hz <= 0.0) {
        throw std::runtime_error("publish_rate_hz must be finite and > 0");
    }

    // Calculate the maximum motor velocity
    max_motor_velocity_rad_s_ = kanga_core_drive::max_motor_velocity_rad_s(motor_velocity_limit_tps_);

    // One message carries the complete wheel vector, so it cannot arrive partially.
    joint_command_sub_ =
        this->create_subscription<kanga_interfaces::msg::WheelVelocityCommand>(
            "/wheel_joint_velocity_command", 10,
            std::bind(
                &WheelActuator::on_joint_command, this,
                std::placeholders::_1));

    // Subscribe to the status of each wheel
    rclcpp::QoS status_qos(10);
    status_qos.best_effort();
    for (size_t i = 0; i < wheel_ids_.size(); ++i) {
        const std::string ns = "/wheel_" + wheel_ids_[i];
        status_subs_.push_back(
            this->create_subscription<custom_odrive::msg::ControllerStatus>(
                ns + "/controller_status", status_qos,
                // Humble requires a lambda when each subscription binds an index.
                [this, i](const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
                    this->on_status(i, msg);
                }));
        motor_pubs_.push_back(
            this->create_publisher<custom_odrive::msg::ControlMessage>(
                ns + "/control_message", 10));
    }

    // Create a timer to publish the motor commands
    const auto period = std::chrono::duration<double>(1.0 / publish_rate_hz);
    timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelActuator::publish_timer, this));

    RCLCPP_INFO(
        this->get_logger(),
        "wheel_actuator ready (ratio %.3f:1, motor limit %.3f TPS / %.3f rad/s, timeout %.2f s)",
        gear_ratio_, motor_velocity_limit_tps_, max_motor_velocity_rad_s_,
        joint_command_timeout_s_);
}

// Cache one complete four-wheel command and its local arrival time.
void WheelActuator::on_joint_command(
    const kanga_interfaces::msg::WheelVelocityCommand::SharedPtr msg)
{
    std::lock_guard<std::mutex> lock(mutex_);
    joint_commands_ = {
        msg->front_left_rad_s,
        msg->back_left_rad_s,
        msg->back_right_rad_s,
        msg->front_right_rad_s,
    };
    command_stamp_ = this->get_clock()->now();
    have_command_ = true;
}

// Cache one ODrive axis state for CLOSED_LOOP output gating.
void WheelActuator::on_status(
    size_t index, const custom_odrive::msg::ControllerStatus::SharedPtr msg)
{
    if (index >= axis_states_.size()) {
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    axis_states_[index] = msg->axis_state;
}

// Convert fresh joint commands and publish safe motor commands while closed loop.
void WheelActuator::publish_timer()
{
    std::array<double, 4> joint_commands{};
    std::array<uint8_t, 4> axis_states{};
    bool command_is_fresh = false;
    const auto now = this->get_clock()->now();

    {
        std::lock_guard<std::mutex> lock(mutex_);
        joint_commands = joint_commands_;
        axis_states = axis_states_;
        command_is_fresh = have_command_ && (now - command_stamp_).seconds() <= joint_command_timeout_s_;
    }

    // A stale four-wheel vector means the controller path has failed.
    // Send nothing so an enabled firmware watchdog can disarm CLOSED_LOOP.
    // Normal stale /cmd_vel is different: the live controller keeps publishing
    // joint zeros.
    if (!command_is_fresh) {
        return;
    }

    // Check if the joint commands are valid
    for (const double command : joint_commands) {
        if (!std::isfinite(command)) {
            return;
        }
    }

    custom_odrive::msg::ControlMessage control;
    control.control_mode = kControlModeVelocity;
    control.input_mode = kInputModeVelRamp;
    control.input_pos = 0.0F;
    control.input_torque = 0.0F;

    // Publish the motor commands
    for (size_t i = 0; i < motor_pubs_.size(); ++i) {
        if (axis_states[i] != kAxisClosedLoop) {
            continue;
        }
        const double requested_motor_rad_s = kanga_core_drive::motor_velocity_from_joint(joint_commands[i], gear_ratio_);
        const double limited_motor_rad_s = kanga_core_drive::clamp_motor_velocity(requested_motor_rad_s, max_motor_velocity_rad_s_);
        if (limited_motor_rad_s != requested_motor_rad_s) {
            RCLCPP_WARN_THROTTLE(
                this->get_logger(), *this->get_clock(), 2000,
                "Motor safety clamp active; controller joint command exceeds profile limit");
        }
        control.input_vel = static_cast<float>(limited_motor_rad_s);
        motor_pubs_[i]->publish(control);
    }
}
