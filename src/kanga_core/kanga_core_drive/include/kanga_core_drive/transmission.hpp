#pragma once

/*
 * Pure actuator-boundary calculations for the Kanga wheel drives.
 *
 * Controller side: wheel-joint rad/s.
 * Motor side:      motor-shaft rad/s.
 *
 * gear_ratio = motor motion / wheel-joint motion. For Kanga's 50:1
 * reduction, motor_rad_s = joint_rad_s * 50.
 */

#include <algorithm>
#include <cmath>

namespace kanga_core_drive
{

// Convert a wheel-joint velocity into motor-shaft velocity.
inline double motor_velocity_from_joint(double joint_rad_s, double gear_ratio)
{
  return joint_rad_s * gear_ratio;
}

// Convert motor-shaft velocity feedback into wheel-joint velocity.
inline double joint_velocity_from_motor(double motor_rad_s, double gear_ratio)
{
  return motor_rad_s / gear_ratio;
}

// Convert motor-shaft position feedback into wheel-joint position.
inline double joint_position_from_motor(double motor_rad, double gear_ratio)
{
  return motor_rad / gear_ratio;
}

// Derive the wheel-joint limit from motor TPS and reduction.
inline double max_joint_velocity(double motor_velocity_limit_tps, double gear_ratio)
{
  constexpr double two_pi = 6.28318530717958647692;
  return motor_velocity_limit_tps * two_pi / gear_ratio;
}

// Convert the configured motor limit from turns/s to rad/s.
inline double max_motor_velocity_rad_s(double motor_velocity_limit_tps)
{
  constexpr double two_pi = 6.28318530717958647692;
  return motor_velocity_limit_tps * two_pi;
}

// Independently clamp one motor command as the final actuator-local safety bound.
inline double clamp_motor_velocity(double motor_rad_s, double max_abs_motor_rad_s)
{
  if (!std::isfinite(motor_rad_s) ||
    !std::isfinite(max_abs_motor_rad_s) || max_abs_motor_rad_s <= 0.0)
  {
    return 0.0;
  }
  return std::clamp(motor_rad_s, -max_abs_motor_rad_s, max_abs_motor_rad_s);
}

}  // namespace kanga_core_drive
