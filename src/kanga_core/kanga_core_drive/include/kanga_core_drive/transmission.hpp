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
#include <array>
#include <cmath>
#include <cstddef>

namespace kanga_core_drive
{

inline double motor_velocity_from_joint(double joint_rad_s, double gear_ratio)
{
    return joint_rad_s * gear_ratio;
}

inline double joint_velocity_from_motor(double motor_rad_s, double gear_ratio)
{
    return motor_rad_s / gear_ratio;
}

inline double joint_position_from_motor(double motor_rad, double gear_ratio)
{
    return motor_rad / gear_ratio;
}

inline double max_joint_velocity(double motor_velocity_limit_tps, double gear_ratio)
{
    constexpr double two_pi = 6.28318530717958647692;
    return motor_velocity_limit_tps * two_pi / gear_ratio;
}

// Scale the complete four-wheel vector when any joint exceeds the actuator
// capability. Uniform scaling preserves the requested mecanum motion direction.
inline std::array<double, 4> desaturate_joint_velocities(
    const std::array<double, 4> & input,
    double max_abs_joint_rad_s)
{
    if (!std::isfinite(max_abs_joint_rad_s) || max_abs_joint_rad_s <= 0.0) {
        return {};
    }

    double largest = 0.0;
    for (const double value : input) {
        if (!std::isfinite(value)) {
            return {};
        }
        largest = std::max(largest, std::abs(value));
    }

    if (largest <= max_abs_joint_rad_s) {
        return input;
    }

    const double scale = max_abs_joint_rad_s / largest;
    std::array<double, 4> output{};
    for (std::size_t i = 0; i < input.size(); ++i) {
        output[i] = input[i] * scale;
    }
    return output;
}

}  // namespace kanga_core_drive
