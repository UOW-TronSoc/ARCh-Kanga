#include "kanga_core_controller/kinematics.hpp"

#include <algorithm>
#include <cmath>

namespace kanga_core_controller
{

WheelVelocities twist_to_wheels(const Twist2D & twist, const ChassisGeometry & geom)
{
    // Convert roller angle to radians for sin/cos.
    constexpr double deg2rad = M_PI / 180.0;
    const double theta = geom.theta_deg * deg2rad;
    const double s = std::sin(theta);
    const double c = std::cos(theta);

    // 1/cos(theta) scales the mix of forward/sideways for this roller angle.
    // If cos is ~0 the geometry is invalid — refuse to divide by zero.
    const double alpha = (std::abs(c) < 1e-9) ? 0.0 : (1.0 / c);

    // Turning contribution grows with how far the wheels sit from centre.
    const double r = geom.half_length + geom.half_width;

    const double vx = twist.vx;
    const double vy = twist.vy;
    const double omega = twist.omega;

    // Same closed-form map as the previous competition mapper.
    // Each line: mix of drive forward, strafe, and yaw for that corner.
    WheelVelocities out;
    out.fl = alpha * (s * vx + c * vy - r * omega);
    out.fr = alpha * (s * vx - c * vy + r * omega);
    out.bl = alpha * (s * vx - c * vy - r * omega);
    out.br = alpha * (s * vx + c * vy + r * omega);
    return out;
}

WheelVelocities clamp_wheels(const WheelVelocities & in, double max_abs)
{
    // Safety cap so a huge /cmd_vel cannot ask for an impossible wheel speed.
    if (max_abs <= 0.0) {
        return {};
    }
    auto clamp_one = [max_abs](double v) {
        return std::clamp(v, -max_abs, max_abs);
    };
    WheelVelocities out;
    out.fl = clamp_one(in.fl);
    out.bl = clamp_one(in.bl);
    out.br = clamp_one(in.br);
    out.fr = clamp_one(in.fr);
    return out;
}

}  // namespace kanga_core_controller
