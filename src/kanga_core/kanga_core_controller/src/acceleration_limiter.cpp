#include "kanga_core_controller/acceleration_limiter.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace kanga_core_controller
{
namespace
{

constexpr double kStoppedTolerance = 1e-9;

// Report whether the three body-motion components request a complete stop.
bool is_stopped(const geometry_msgs::msg::Twist & twist)
{
  return std::abs(twist.linear.x) <= kStoppedTolerance &&
         std::abs(twist.linear.y) <= kStoppedTolerance &&
         std::abs(twist.angular.z) <= kStoppedTolerance;
}

// Report whether all four target wheel speeds request a complete stop.
bool is_stopped(const kanga_interfaces::msg::WheelVelocityCommand & command)
{
  return std::abs(command.front_left_rad_s) <= kStoppedTolerance &&
         std::abs(command.back_left_rad_s) <= kStoppedTolerance &&
         std::abs(command.back_right_rad_s) <= kStoppedTolerance &&
         std::abs(command.front_right_rad_s) <= kStoppedTolerance;
}

// Return a zero Twist when a command reverses the overall motion direction.
bool reverses_body_direction(
  const geometry_msgs::msg::Twist & current,
  const geometry_msgs::msg::Twist & target,
  double linear_scale,
  double angular_scale)
{
  const double scaled_dot_product =
    (current.linear.x * target.linear.x + current.linear.y * target.linear.y) /
    (linear_scale * linear_scale) +
    (current.angular.z * target.angular.z) /
    (angular_scale * angular_scale);
  return scaled_dot_product < -kStoppedTolerance;
}

}  // namespace

// Move the complete body command toward its target by one shared fraction.
geometry_msgs::msg::Twist limit_body_velocity_change(
  const geometry_msgs::msg::Twist & current,
  const geometry_msgs::msg::Twist & target,
  double max_linear_acceleration_m_s2,
  double max_angular_acceleration_rad_s2,
  double elapsed_time_s)
{
  geometry_msgs::msg::Twist stopped;
  if (!std::isfinite(current.linear.x) || !std::isfinite(current.linear.y) ||
    !std::isfinite(current.angular.z) || !std::isfinite(target.linear.x) ||
    !std::isfinite(target.linear.y) || !std::isfinite(target.angular.z))
  {
    return stopped;
  }

  // A complete stop, timeout, or overall reversal receives full deceleration.
  if (is_stopped(target) || reverses_body_direction(
      current, target, max_linear_acceleration_m_s2,
      max_angular_acceleration_rad_s2))
  {
    return stopped;
  }

  const double linear_change = std::hypot(
    target.linear.x - current.linear.x,
    target.linear.y - current.linear.y);
  const double angular_change = std::abs(target.angular.z - current.angular.z);
  const double transition_time_s = std::max(
    linear_change / max_linear_acceleration_m_s2,
    angular_change / max_angular_acceleration_rad_s2);
  if (transition_time_s <= elapsed_time_s) {
    return target;
  }

  const double progress = elapsed_time_s / transition_time_s;
  geometry_msgs::msg::Twist limited;
  limited.linear.x = current.linear.x + progress * (target.linear.x - current.linear.x);
  limited.linear.y = current.linear.y + progress * (target.linear.y - current.linear.y);
  limited.angular.z = current.angular.z + progress * (target.angular.z - current.angular.z);
  return limited;
}

// Move all wheel commands together without exceeding joint acceleration.
kanga_interfaces::msg::WheelVelocityCommand limit_wheel_acceleration(
  const kanga_interfaces::msg::WheelVelocityCommand & current,
  const kanga_interfaces::msg::WheelVelocityCommand & target,
  double max_wheel_joint_acceleration_rad_s2,
  double elapsed_time_s)
{
  if (is_stopped(target)) {
    return target;
  }

  const std::array<double, 4> changes = {
    target.front_left_rad_s - current.front_left_rad_s,
    target.back_left_rad_s - current.back_left_rad_s,
    target.back_right_rad_s - current.back_right_rad_s,
    target.front_right_rad_s - current.front_right_rad_s,
  };
  double largest_change = 0.0;
  for (const double change : changes) {
    if (!std::isfinite(change)) {
      return kanga_interfaces::msg::WheelVelocityCommand();
    }
    largest_change = std::max(largest_change, std::abs(change));
  }

  const double maximum_change = max_wheel_joint_acceleration_rad_s2 * elapsed_time_s;
  if (largest_change <= maximum_change) {
    return target;
  }

  const double progress = maximum_change / largest_change;
  kanga_interfaces::msg::WheelVelocityCommand limited;
  limited.front_left_rad_s = current.front_left_rad_s + progress * changes[0];
  limited.back_left_rad_s = current.back_left_rad_s + progress * changes[1];
  limited.back_right_rad_s = current.back_right_rad_s + progress * changes[2];
  limited.front_right_rad_s = current.front_right_rad_s + progress * changes[3];
  return limited;
}

}  // namespace kanga_core_controller
