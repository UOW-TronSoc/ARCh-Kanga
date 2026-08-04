#include "kanga_core_drive/wheel_actuator.hpp"

#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

#include "kanga_core_drive/transmission.hpp"

WheelActuator::WheelActuator(const rclcpp::NodeOptions & options)
: Node("wheel_actuator", options)
{
    this->declare_parameter<std::vector<std::string>>(
        "wheel_ids", {"fl", "bl", "br", "fr"});
    this->declare_parameter<double>("gear_ratio", 50.0);
    this->declare_parameter<double>("motor_velocity_limit_tps", 22.0);
    this->declare_parameter<double>("joint_command_timeout_s", 0.5);
    this->declare_parameter<double>("publish_rate_hz", 10.0);

    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    gear_ratio_ = this->get_parameter("gear_ratio").as_double();
    motor_velocity_limit_tps_ =
        this->get_parameter("motor_velocity_limit_tps").as_double();
    joint_command_timeout_s_ =
        this->get_parameter("joint_command_timeout_s").as_double();
    const double publish_rate_hz = this->get_parameter("publish_rate_hz").as_double();

    if (wheel_ids_.size() != joint_commands_.size()) {
        throw std::runtime_error("wheel_ids must have exactly 4 entries");
    }
    if (!std::isfinite(gear_ratio_) || gear_ratio_ <= 0.0) {
        throw std::runtime_error("gear_ratio must be finite and > 0");
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

    max_joint_velocity_rad_s_ =
        kanga_core_drive::max_joint_velocity(motor_velocity_limit_tps_, gear_ratio_);

    rclcpp::QoS status_qos(10);
    status_qos.best_effort();
    for (size_t i = 0; i < wheel_ids_.size(); ++i) {
        const std::string ns = "/wheel_" + wheel_ids_[i];
        joint_subs_.push_back(
            this->create_subscription<std_msgs::msg::Float64>(
                ns + "/joint_velocity_command", 10,
                [this, i](const std_msgs::msg::Float64::SharedPtr msg) {
                    this->on_joint_command(i, *msg);
                }));
        status_subs_.push_back(
            this->create_subscription<custom_odrive::msg::ControllerStatus>(
                ns + "/controller_status", status_qos,
                [this, i](const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
                    this->on_status(i, *msg);
                }));
        motor_pubs_.push_back(
            this->create_publisher<custom_odrive::msg::ControlMessage>(
                ns + "/control_message", 10));
    }

    const auto period = std::chrono::duration<double>(1.0 / publish_rate_hz);
    timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelActuator::publish_timer, this));

    RCLCPP_INFO(
        this->get_logger(),
        "wheel_actuator ready (ratio %.3f:1, motor limit %.3f TPS, joint limit %.3f rad/s, timeout %.2f s)",
        gear_ratio_, motor_velocity_limit_tps_, max_joint_velocity_rad_s_,
        joint_command_timeout_s_);
}

void WheelActuator::on_joint_command(size_t index, const std_msgs::msg::Float64 & msg)
{
    if (index >= joint_commands_.size()) {
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    joint_commands_[index] = msg.data;
    command_stamps_[index] = this->get_clock()->now();
    have_command_[index] = true;
}

void WheelActuator::on_status(
    size_t index, const custom_odrive::msg::ControllerStatus & msg)
{
    if (index >= axis_states_.size()) {
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    axis_states_[index] = msg.axis_state;
}

void WheelActuator::publish_timer()
{
    std::array<double, 4> joint_commands{};
    std::array<uint8_t, 4> axis_states{};
    bool all_commands_fresh = true;
    const auto now = this->get_clock()->now();

    {
        std::lock_guard<std::mutex> lock(mutex_);
        joint_commands = joint_commands_;
        axis_states = axis_states_;
        for (size_t i = 0; i < have_command_.size(); ++i) {
            if (!have_command_[i] ||
                (now - command_stamps_[i]).seconds() > joint_command_timeout_s_)
            {
                all_commands_fresh = false;
                break;
            }
        }
    }

    // A partial/stale four-wheel vector means the controller path has failed.
    // Send nothing so the firmware watchdog disarms CLOSED_LOOP. Normal stale
    // /cmd_vel is different: the live controller keeps publishing joint zeros.
    if (!all_commands_fresh) {
        return;
    }
    for (const double command : joint_commands) {
        if (!std::isfinite(command)) {
            return;
        }
    }
    const auto limited = kanga_core_drive::desaturate_joint_velocities(
        joint_commands, max_joint_velocity_rad_s_);

    custom_odrive::msg::ControlMessage control;
    control.control_mode = kControlModeVelocity;
    control.input_mode = kInputModeVelRamp;
    control.input_pos = 0.0F;
    control.input_torque = 0.0F;

    for (size_t i = 0; i < motor_pubs_.size(); ++i) {
        if (axis_states[i] != kAxisClosedLoop) {
            continue;
        }
        control.input_vel = static_cast<float>(
            kanga_core_drive::motor_velocity_from_joint(limited[i], gear_ratio_));
        motor_pubs_[i]->publish(control);
    }
}
