#pragma once

/*
 * WheelCommandMapper — the ROS node that drives the wheels from /cmd_vel.
 *
 * Big picture (read this first):
 *
 *   Joystick / autonomy / basestation
 *            |
 *            v
 *        /cmd_vel          (geometry_msgs/Twist: go forward, strafe, spin)
 *            |
 *            v
 *   wheel_command_mapper   (this node)
 *            |
 *            |  every ~0.1 s
 *            v
 *   /wheel_joint_velocity_command  (one atomic four-wheel message)
 *            |
 *            v
 *   kanga_core_drive wheel_actuator (applies reduction + motor limit)
 *
 * Important behaviours for beginners:
 *
 * 1. We only *remember* the latest /cmd_vel. A timer does the publishing.
 *    That way motors keep getting a steady stream even if Twist arrives
 *    in bursts.
 *
 * 2. If /cmd_vel goes quiet for longer than cmd_vel_timeout_s, we treat
 *    the command as "stop" (all wheel speeds = 0). Safety: a crashed
 *    teleop client should not leave the rover driving forever.
 *
 * 3. Output is wheel-joint rad/s. The complete four-wheel vector is scaled
 *    uniformly to the selected drivetrain's joint-speed capability, preserving
 *    the requested chassis-motion ratio. Motor/gearbox conversion and the
 *    final motor-side safety limit belong to kanga_core_drive.
 *
 * This node does NOT:
 *   - flip left/right signs (see invert_direction in drive.launch.py)
 *   - call request_axis_state / set_enabled
 *   - own the emergency stop topic /drivestop
 */

#include <mutex>

#include "geometry_msgs/msg/twist.hpp"
#include "kanga_core_controller/kinematics.hpp"
#include "kanga_interfaces/msg/wheel_velocity_command.hpp"
#include "rclcpp/rclcpp.hpp"

class WheelCommandMapper : public rclcpp::Node
{
public:
    explicit WheelCommandMapper(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    // Called whenever someone publishes to /cmd_vel.
    void on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg);
    // Called on a fixed timer (~10 Hz) to send joint velocities to drive.
    void on_timer();

    // Return the latest Twist, or a zero Twist when it has timed out.
    geometry_msgs::msg::Twist get_active_twist_locked();

    // Stored once at startup and reused for every Twist-to-wheel calculation.
    kanga_core_controller::ChassisGeometry geom_;
    double max_wheel_joint_velocity_rad_s_{0.0};
    double cmd_vel_timeout_s_{0.5};

    // Shared state touched by topic callbacks and the timer. Lock before use.
    std::mutex mutex_;
    geometry_msgs::msg::Twist last_twist_;
    rclcpp::Time last_cmd_stamp_{0, 0, RCL_ROS_TIME};
    bool have_cmd_{false};

    // ROS interfaces (one chassis input and one atomic four-wheel output).
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
    rclcpp::Publisher<kanga_interfaces::msg::WheelVelocityCommand>::SharedPtr
        joint_command_pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};
