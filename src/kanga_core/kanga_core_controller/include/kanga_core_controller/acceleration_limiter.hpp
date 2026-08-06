#pragma once

#include "geometry_msgs/msg/twist.hpp"
#include "kanga_interfaces/msg/wheel_velocity_command.hpp"

namespace kanga_core_controller
{

// Move the complete body command toward its target by one shared fraction.
geometry_msgs::msg::Twist limit_body_velocity_change(
  const geometry_msgs::msg::Twist & current,
  const geometry_msgs::msg::Twist & target,
  double max_linear_acceleration_m_s2,
  double max_angular_acceleration_rad_s2,
  double elapsed_time_s);

// Move all wheel commands together without exceeding joint acceleration.
kanga_interfaces::msg::WheelVelocityCommand limit_wheel_acceleration(
  const kanga_interfaces::msg::WheelVelocityCommand & current,
  const kanga_interfaces::msg::WheelVelocityCommand & target,
  double max_wheel_joint_acceleration_rad_s2,
  double elapsed_time_s);

}  // namespace kanga_core_controller
