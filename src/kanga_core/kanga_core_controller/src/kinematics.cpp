#include "kanga_core_controller/kinematics.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace kanga_core_controller
{

// Convert a physical chassis twist into four wheel-joint velocities.
kanga_interfaces::msg::WheelVelocityCommand twist_to_wheels(
    const geometry_msgs::msg::Twist & twist, const ChassisGeometry & geom)
{
    // Convert roller angle to radians for sin/cos.
    constexpr double deg2rad = M_PI / 180.0;
    const double theta = geom.grouser_angle_deg * deg2rad;
    const double s = std::sin(theta);
    const double c = std::cos(theta);

    if (!std::isfinite(geom.grouser_angle_deg) ||
        !std::isfinite(geom.half_length) || geom.half_length <= 0.0 ||
        !std::isfinite(geom.half_width) || geom.half_width <= 0.0 ||
        !std::isfinite(geom.effective_wheel_radius_m) ||
        geom.effective_wheel_radius_m <= 0.0 || std::abs(c) < 1e-9)
    {
        return kanga_interfaces::msg::WheelVelocityCommand();
    }

    // The legacy angled-grouser model scales the mix by 1/cos(theta).
    const double alpha = 1.0 / c;
    const double joint_rad_per_m = 1.0 / geom.effective_wheel_radius_m;

    // Turning contribution grows with how far the wheels sit from centre.
    const double r = geom.half_length + geom.half_width;

    const double vx = twist.linear.x;
    const double vy = twist.linear.y;
    const double omega = twist.angular.z;

    // Same closed-form map as the previous competition mapper.
    // Each line: mix of drive forward, strafe, and yaw for that corner.
    kanga_interfaces::msg::WheelVelocityCommand out;
    out.front_left_rad_s = joint_rad_per_m * alpha * (s * vx + c * vy - r * omega);
    out.front_right_rad_s = joint_rad_per_m * alpha * (s * vx - c * vy + r * omega);
    out.back_left_rad_s = joint_rad_per_m * alpha * (s * vx - c * vy - r * omega);
    out.back_right_rad_s = joint_rad_per_m * alpha * (s * vx + c * vy + r * omega);
    return out;
}

// Uniformly scale an over-limit wheel vector while preserving its ratios.
kanga_interfaces::msg::WheelVelocityCommand desaturate_wheel_velocities(
    const kanga_interfaces::msg::WheelVelocityCommand & in,
    double max_abs_joint_rad_s)
{
    if (!std::isfinite(max_abs_joint_rad_s) || max_abs_joint_rad_s <= 0.0) {
        return kanga_interfaces::msg::WheelVelocityCommand();
    }

    const std::array<double, 4> input{
        in.front_left_rad_s,
        in.back_left_rad_s,
        in.back_right_rad_s,
        in.front_right_rad_s,
    };
    double largest = 0.0;
    for (const double value : input) {
        if (!std::isfinite(value)) {
            return kanga_interfaces::msg::WheelVelocityCommand();
        }
        largest = std::max(largest, std::abs(value));
    }

    if (largest <= max_abs_joint_rad_s) {
        return in;
    }

    const double scale = max_abs_joint_rad_s / largest;
    auto output = in;
    output.front_left_rad_s *= scale;
    output.back_left_rad_s *= scale;
    output.back_right_rad_s *= scale;
    output.front_right_rad_s *= scale;
    return output;
}

}  // namespace kanga_core_controller
