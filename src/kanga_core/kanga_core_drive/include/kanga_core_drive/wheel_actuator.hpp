#pragma once

/*
 * WheelActuator is the Kanga-specific boundary between wheel joints and motors.
 *
 * Input:  /wheel_joint_velocity_command (one atomic four-wheel command)
 * Output: /wheel_<id>/control_message (motor-shaft rad/s for custom_odrive)
 *
 * It owns the selected reduction, the final per-motor safety limit, command
 * timeout, and CLOSED_LOOP gating. Proportional four-wheel desaturation is a
 * control decision and therefore happens in kanga_core_controller. A
 * stale command vector stops motor transmission so the ODrive watchdog
 * can disarm the axes.
 * Direction inversion remains in each custom_odrive node because it is part of
 * the physical motor mounting.
 */

#include <array>
#include <mutex>
#include <string>
#include <vector>

#include "custom_odrive/msg/control_message.hpp"
#include "custom_odrive/msg/controller_status.hpp"
#include "kanga_interfaces/msg/wheel_velocity_command.hpp"
#include "rclcpp/rclcpp.hpp"

class WheelActuator : public rclcpp::Node
{
public:
    explicit WheelActuator(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    static constexpr uint8_t kAxisClosedLoop = 8;
    static constexpr uint32_t kControlModeVelocity = 2;
    static constexpr uint32_t kInputModeVelRamp = 2;

    void on_joint_command(
        const kanga_interfaces::msg::WheelVelocityCommand::SharedPtr msg);
    void on_status(
        size_t index, const custom_odrive::msg::ControllerStatus::SharedPtr msg);
    void publish_timer();

    std::vector<std::string> wheel_ids_;
    double gear_ratio_{0.0};
    double motor_velocity_limit_tps_{0.0};
    double max_motor_velocity_rad_s_{0.0};
    double joint_command_timeout_s_{0.5};

    std::mutex mutex_;
    std::array<double, 4> joint_commands_{};
    rclcpp::Time command_stamp_{0, 0, RCL_ROS_TIME};
    bool have_command_{false};
    std::array<uint8_t, 4> axis_states_{{1, 1, 1, 1}};

    rclcpp::Subscription<kanga_interfaces::msg::WheelVelocityCommand>::SharedPtr
        joint_command_sub_;
    std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr> status_subs_;
    std::vector<rclcpp::Publisher<custom_odrive::msg::ControlMessage>::SharedPtr> motor_pubs_;
    rclcpp::TimerBase::SharedPtr timer_;
};
