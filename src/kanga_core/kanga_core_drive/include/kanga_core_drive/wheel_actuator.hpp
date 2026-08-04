#pragma once

/*
 * WheelActuator is the Kanga-specific boundary between wheel joints and motors.
 *
 * Input:  /wheel_<id>/joint_velocity_command (wheel-joint rad/s)
 * Output: /wheel_<id>/control_message (motor-shaft rad/s for custom_odrive)
 *
 * It owns the 50:1 reduction, motor velocity limit, command timeout, uniform
 * four-wheel desaturation, and CLOSED_LOOP gating. A stale/partial command
 * vector stops motor transmission so the ODrive watchdog can disarm the axes.
 * Direction inversion remains in each custom_odrive node because it is part of
 * the physical motor mounting.
 */

#include <array>
#include <mutex>
#include <string>
#include <vector>

#include "custom_odrive/msg/control_message.hpp"
#include "custom_odrive/msg/controller_status.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float64.hpp"

class WheelActuator : public rclcpp::Node
{
public:
    explicit WheelActuator(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    static constexpr uint8_t kAxisClosedLoop = 8;
    static constexpr uint32_t kControlModeVelocity = 2;
    static constexpr uint32_t kInputModeVelRamp = 2;

    void on_joint_command(size_t index, const std_msgs::msg::Float64 & msg);
    void on_status(size_t index, const custom_odrive::msg::ControllerStatus & msg);
    void publish_timer();

    std::vector<std::string> wheel_ids_;
    double gear_ratio_{50.0};
    double motor_velocity_limit_tps_{22.0};
    double max_joint_velocity_rad_s_{0.0};
    double joint_command_timeout_s_{0.5};

    std::mutex mutex_;
    std::array<double, 4> joint_commands_{};
    std::array<rclcpp::Time, 4> command_stamps_{
        rclcpp::Time(0, 0, RCL_ROS_TIME),
        rclcpp::Time(0, 0, RCL_ROS_TIME),
        rclcpp::Time(0, 0, RCL_ROS_TIME),
        rclcpp::Time(0, 0, RCL_ROS_TIME)};
    std::array<bool, 4> have_command_{};
    std::array<uint8_t, 4> axis_states_{{1, 1, 1, 1}};

    std::vector<rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr> joint_subs_;
    std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr> status_subs_;
    std::vector<rclcpp::Publisher<custom_odrive::msg::ControlMessage>::SharedPtr> motor_pubs_;
    rclcpp::TimerBase::SharedPtr timer_;
};
