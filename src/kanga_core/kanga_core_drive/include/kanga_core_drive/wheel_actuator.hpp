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

  void on_wheel_velocity_command(
    const kanga_interfaces::msg::WheelVelocityCommand::SharedPtr msg);
  void on_controller_status(
    size_t wheel_index,
    const custom_odrive::msg::ControllerStatus::SharedPtr msg);
  void publish_motor_commands();

  std::vector<std::string> wheel_ids_;
  double gear_ratio_{0.0};
  double motor_velocity_limit_tps_{0.0};
  double max_motor_velocity_rad_s_{0.0};
  double joint_command_timeout_s_{0.5};

  std::mutex actuator_state_mutex_;
  std::array<double, 4> wheel_joint_velocity_commands_{};
  rclcpp::Time last_joint_command_time_{0, 0, RCL_ROS_TIME};
  bool wheel_command_received_{false};
  std::array<uint8_t, 4> wheel_axis_states_{{1, 1, 1, 1}};

  rclcpp::Subscription<kanga_interfaces::msg::WheelVelocityCommand>::SharedPtr
    wheel_velocity_command_subscription_;
  std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr>
  controller_status_subscriptions_;
  std::vector<rclcpp::Publisher<custom_odrive::msg::ControlMessage>::SharedPtr>
  motor_command_publishers_;
  rclcpp::TimerBase::SharedPtr motor_command_publish_timer_;
};
