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
 *            |  every ~0.1 s, if that wheel is in CLOSED_LOOP
 *            v
 *   /wheel_fl/control_message   … same for bl, br, fr
 *            |
 *            v
 *   custom_odrive_node     (talks CAN to the real ODrive)
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
 * 3. We only publish to a wheel while its axis_state is CLOSED_LOOP (8).
 *    Enter CLOSED_LOOP via drive_manager (set_closed_loop). This node does
 *    not change axis state itself.
 *
 * 4. While CLOSED_LOOP we keep publishing even when the command is zero.
 *    The ODrive firmware has a watchdog (~1 s): if setpoints stop arriving
 *    it faults. Streaming zeros = "still alive, please stay stopped".
 *
 * This node does NOT:
 *   - flip left/right signs (see invert_direction in drive.launch.py)
 *   - call request_axis_state / set_enabled
 *   - own the emergency stop topic /drivestop
 */

#include <array>
#include <cmath>
#include <mutex>
#include <string>
#include <vector>

#include "custom_odrive/msg/control_message.hpp"
#include "custom_odrive/msg/controller_status.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "kanga_core_controller/kinematics.hpp"
#include "rclcpp/rclcpp.hpp"

class WheelCommandMapper : public rclcpp::Node
{
public:
    explicit WheelCommandMapper(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    // ODrive axis_state value meaning "ready to accept velocity commands".
    static constexpr uint8_t kAxisClosedLoop = 8;
    // Numbers the ODrive expects for "velocity control with ramped input".
    // See ODrive docs / custom_odrive ControlMessage — do not change casually.
    static constexpr uint32_t kControlModeVelocity = 2;
    static constexpr uint32_t kInputModeVelRamp = 2;

    // Called whenever someone publishes to /cmd_vel.
    void on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg);
    // Called whenever an ODrive node publishes controller_status.
    void on_status(size_t index, const custom_odrive::msg::ControllerStatus & msg);
    // Called on a fixed timer (~10 Hz) to send ControlMessage to the wheels.
    void on_timer();

    // Build the four desired wheel speeds from the last /cmd_vel (or zeros
    // if timed out). Caller must already hold mutex_.
    kanga_core_controller::WheelVelocities desired_locked();

    std::vector<std::string> wheel_ids_;
    kanga_core_controller::ChassisGeometry geom_;
    double max_wheel_velocity_{44.0 * M_PI};  // 22 turns/s in rad/s
    double cmd_vel_timeout_s_{0.5};

    // Shared state touched by topic callbacks and the timer. Lock before use.
    std::mutex mutex_;
    kanga_core_controller::Twist2D last_twist_;
    rclcpp::Time last_cmd_stamp_{0, 0, RCL_ROS_TIME};
    bool have_cmd_{false};
    std::array<uint8_t, 4> axis_state_{{1, 1, 1, 1}};  // 1 = IDLE until we hear status

    // ROS interfaces (one subscription + four status subs + four publishers).
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
    std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr> status_subs_;
    std::vector<rclcpp::Publisher<custom_odrive::msg::ControlMessage>::SharedPtr> ctrl_pubs_;
    rclcpp::TimerBase::SharedPtr timer_;
};
