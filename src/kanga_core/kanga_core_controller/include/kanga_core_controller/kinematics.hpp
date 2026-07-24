#pragma once

/*
 * Kinematics = the math that turns "how the robot should move" into
 * "how fast each wheel should spin".
 *
 * Input:  chassis velocity (forward, sideways, spin) — same idea as /cmd_vel
 * Output: four wheel speeds (front-left, back-left, back-right, front-right)
 *
 * This file has NO ROS code. It is plain C++ so we can unit-test the math
 * without launching nodes or needing motors.
 *
 * Sign flip for left-side wheels is NOT done here. That is handled by
 * invert_direction on each custom_odrive node in wheels.launch.py.
 */

#include <array>
#include <cmath>

namespace kanga_core_controller
{

// Physical size of the rover base (metres). Used by twist_to_wheels().
//
// Measure overall length / width of the wheel footprint, then halve them:
//   110 cm long  → half_length = 0.55
//    89 cm wide  → half_width  = 0.445
struct ChassisGeometry
{
    // Mecanum roller angle on the wheel (degrees). Keep unless hardware changes.
    double theta_deg{51.0};
    // Distance from robot centre to a wheel axle, along the length (front/back).
    double half_length{0.55};
    // Distance from robot centre to a wheel, along the width (left/right).
    double half_width{0.445};
};

// Robot motion in the robot frame (matches geometry_msgs/Twist fields we use).
struct Twist2D
{
    double vx{0.0};     // forward (+) / backward (−), metres per second
    double vy{0.0};     // left (+) / right (−), metres per second
    double omega{0.0};  // spin left (+) / right (−), radians per second
};

// One speed command per wheel. Order matches drive: fl, bl, br, fr.
// Units: rad/s when ODrive nodes run with control_message_in_radians: true.
struct WheelVelocities
{
    double fl{0.0};  // front left
    double bl{0.0};  // back left
    double br{0.0};  // back right
    double fr{0.0};  // front right

    // Handy for looping fl → bl → br → fr in the same order as wheel_ids.
    std::array<double, 4> as_array() const
    {
        return {fl, bl, br, fr};
    }
};

// Convert chassis twist → four wheel speeds (Kanga mecanum / roller map).
WheelVelocities twist_to_wheels(const Twist2D & twist, const ChassisGeometry & geom);

// Limit each wheel to ±max_abs. If max_abs is 0 or negative, return all zeros.
WheelVelocities clamp_wheels(const WheelVelocities & in, double max_abs);

}  // namespace kanga_core_controller
