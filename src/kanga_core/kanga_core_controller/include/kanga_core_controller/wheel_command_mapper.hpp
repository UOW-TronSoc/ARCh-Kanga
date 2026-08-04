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
 *   /wheel_fl/joint_velocity_command   … same for bl, br, fr
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
 * 3. Output is wheel-joint rad/s. This node does not know the motor, gearbox,
 *    ODrive state, or motor limit; those belong to kanga_core_drive.
 *
 * This node does NOT:
 *   - flip left/right signs (see invert_direction in drive.launch.py)
 *   - call request_axis_state / set_enabled
 *   - own the emergency stop topic /drivestop
 */

#include <mutex>
#include <string>
#include <vector>

#include "geometry_msgs/msg/twist.hpp"
#include "kanga_core_controller/kinematics.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float64.hpp"

class WheelCommandMapper : public rclcpp::Node
{
public:
    explicit WheelCommandMapper(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    // Called whenever someone publishes to /cmd_vel.
    void on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg);
    // Called on a fixed timer (~10 Hz) to send joint velocities to drive.
    void on_timer();

    // Build the four desired wheel speeds from the last /cmd_vel (or zeros
    // if timed out). Caller must already hold mutex_.
    kanga_core_controller::WheelVelocities desired_locked();

    std::vector<std::string> wheel_ids_;
    kanga_core_controller::ChassisGeometry geom_;
    double cmd_vel_timeout_s_{0.5};

    // Shared state touched by topic callbacks and the timer. Lock before use.
    std::mutex mutex_;
    kanga_core_controller::Twist2D last_twist_;
    rclcpp::Time last_cmd_stamp_{0, 0, RCL_ROS_TIME};
    bool have_cmd_{false};

    // ROS interfaces (one chassis subscription + four joint publishers).
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
    std::vector<rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr> joint_pubs_;
    rclcpp::TimerBase::SharedPtr timer_;
};
