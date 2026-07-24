#include "kanga_core_controller/wheel_command_mapper.hpp"

#include <chrono>
#include <cmath>
#include <stdexcept>

using namespace std::chrono_literals;
using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::Twist2D;
using kanga_core_controller::WheelVelocities;
using kanga_core_controller::clamp_wheels;
using kanga_core_controller::twist_to_wheels;

WheelCommandMapper::WheelCommandMapper(const rclcpp::NodeOptions & options)
: Node("wheel_command_mapper", options)
{
    // Parameters come from config/controller.yaml (or overrides on the CLI).
    // declare_parameter sets the default if nothing else provides a value.
    this->declare_parameter<std::vector<std::string>>(
        "wheel_ids", {"fl", "bl", "br", "fr"});
    this->declare_parameter<double>("publish_rate_hz", 10.0);
    this->declare_parameter<double>("cmd_vel_timeout_s", 0.5);
    this->declare_parameter<double>("max_wheel_velocity", 44.0 * M_PI);  // 22 turns/s
    this->declare_parameter<double>("theta_deg", 51.0);
    this->declare_parameter<double>("half_length", 0.55);
    this->declare_parameter<double>("half_width", 0.445);

    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    if (wheel_ids_.size() != 4) {
        throw std::runtime_error("wheel_ids must have exactly 4 entries (fl,bl,br,fr)");
    }

    cmd_vel_timeout_s_ = this->get_parameter("cmd_vel_timeout_s").as_double();
    max_wheel_velocity_ = this->get_parameter("max_wheel_velocity").as_double();
    geom_.theta_deg = this->get_parameter("theta_deg").as_double();
    geom_.half_length = this->get_parameter("half_length").as_double();
    geom_.half_width = this->get_parameter("half_width").as_double();

    // One publisher + one status subscription per wheel namespace.
    // Example for fl: publish /wheel_fl/control_message
    //                 listen  /wheel_fl/controller_status
    for (size_t i = 0; i < wheel_ids_.size(); ++i) {
        const std::string ns = "/wheel_" + wheel_ids_[i];
        ctrl_pubs_.push_back(
            this->create_publisher<custom_odrive::msg::ControlMessage>(
                ns + "/control_message", 10));
        status_subs_.push_back(
            this->create_subscription<custom_odrive::msg::ControllerStatus>(
                ns + "/controller_status", 10,
                [this, i](const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
                    this->on_status(i, *msg);
                }));
    }

    // Chassis command from teleop / Nav2 / basestation.
    cmd_sub_ = this->create_subscription<geometry_msgs::msg::Twist>(
        "/cmd_vel", 10,
        std::bind(&WheelCommandMapper::on_cmd_vel, this, std::placeholders::_1));

    // Steady publish rate (default 10 times per second).
    const double rate = this->get_parameter("publish_rate_hz").as_double();
    const auto period = std::chrono::duration<double>(rate > 0.0 ? (1.0 / rate) : 0.1);
    timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelCommandMapper::on_timer, this));

    RCLCPP_INFO(
        this->get_logger(),
        "wheel_command_mapper ready (%.1f Hz, timeout %.2f s, max_wheel_vel %.2f)",
        rate > 0.0 ? rate : 10.0, cmd_vel_timeout_s_, max_wheel_velocity_);
}

void WheelCommandMapper::on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg)
{
    // Just store the latest command. Publishing happens in on_timer().
    std::lock_guard<std::mutex> lock(mutex_);
    last_twist_.vx = msg->linear.x;
    last_twist_.vy = msg->linear.y;
    last_twist_.omega = msg->angular.z;
    last_cmd_stamp_ = this->get_clock()->now();
    have_cmd_ = true;
}

void WheelCommandMapper::on_status(
    size_t index, const custom_odrive::msg::ControllerStatus & msg)
{
    // Remember whether this wheel is IDLE (1), CLOSED_LOOP (8), etc.
    if (index >= axis_state_.size()) {
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    axis_state_[index] = msg.axis_state;
}

WheelVelocities WheelCommandMapper::desired_locked()
{
    // Caller already holds mutex_.
    Twist2D twist;  // defaults to all zeros = "stop"
    if (have_cmd_) {
        const double age = (this->get_clock()->now() - last_cmd_stamp_).seconds();
        if (age <= cmd_vel_timeout_s_) {
            twist = last_twist_;
        }
        // else: command is stale → keep twist at zeros
    }
    return clamp_wheels(twist_to_wheels(twist, geom_), max_wheel_velocity_);
}

void WheelCommandMapper::on_timer()
{
    // Snapshot shared state quickly, then publish without holding the lock.
    WheelVelocities desired;
    std::array<uint8_t, 4> states{};
    {
        std::lock_guard<std::mutex> lock(mutex_);
        desired = desired_locked();
        states = axis_state_;
    }

    const auto vels = desired.as_array();  // fl, bl, br, fr
    custom_odrive::msg::ControlMessage ctrl;
    ctrl.control_mode = kControlModeVelocity;
    ctrl.input_mode = kInputModeVelRamp;
    ctrl.input_pos = 0.0F;
    ctrl.input_torque = 0.0F;

    // Skip wheels that are not in CLOSED_LOOP — do not spam IDLE motors.
    // No sign flip here; invert lives only in drive.launch.py → custom_odrive.
    for (size_t i = 0; i < ctrl_pubs_.size(); ++i) {
        if (states[i] != kAxisClosedLoop) {
            continue;
        }
        ctrl.input_vel = static_cast<float>(vels[i]);
        ctrl_pubs_[i]->publish(ctrl);
    }
}
