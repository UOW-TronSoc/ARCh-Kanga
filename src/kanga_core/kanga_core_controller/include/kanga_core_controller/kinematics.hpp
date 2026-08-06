#pragma once

/*
 * Kinematics = the math that turns "how the robot should move" into
 * "how fast each wheel should spin".
 *
 * Input:  chassis velocity (forward, sideways, spin) — same idea as /cmd_vel
 * Output: four wheel speeds (front-left, back-left, back-right, front-right)
 *
 * The functions use standard ROS messages but contain no node, topic, or motor
 * code, so the maths remains directly unit-testable.
 *
 * Sign flip for left-side wheels is NOT done here. That is handled by
 * invert_direction on each custom_odrive node in drive.launch.py.
 */

#include "geometry_msgs/msg/twist.hpp"
#include "kanga_interfaces/msg/wheel_velocity_command.hpp"

namespace kanga_core_controller
{

// One stored set of physical inputs used by every kinematics calculation.
// geom_ in WheelCommandMapper is an instance populated from profile parameters.
struct ChassisGeometry
{
    // Empirical grouser angle used by the legacy limited-holonomic model.
    double grouser_angle_deg{0.0};
    // Distance from rover centre to the front/rear wheel centres.
    double half_length{0.0};
    // Distance from rover centre to the left/right wheel centres.
    double half_width{0.0};
    // Rolling radius used to convert linear wheel speed into angular speed.
    double effective_wheel_radius_m{0.0};
};

// Convert physical chassis twist → wheel-joint rad/s using Kanga's empirical
// angled-grouser limited-holonomic map.
kanga_interfaces::msg::WheelVelocityCommand twist_to_wheels(
    const geometry_msgs::msg::Twist & twist, const ChassisGeometry & geom);

// Scale the complete vector when any wheel exceeds the joint limit. This
// preserves the requested chassis-motion ratio. Invalid input returns stop.
kanga_interfaces::msg::WheelVelocityCommand desaturate_wheel_velocities(
    const kanga_interfaces::msg::WheelVelocityCommand & in,
    double max_abs_joint_rad_s);

}  // namespace kanga_core_controller
