#pragma once

/*
 * WheelJointStatePublisher — echo ODrive estimates into sensor_msgs/JointState.
 *
 * Subscribes to each /wheel_<id>/controller_status (custom_odrive) and publishes
 * a combined JointState on ~/wheel_joint_states (or remapped). Position and
 * velocity come from pos_estimate / vel_estimate (rad / rad/s when the ODrive
 * nodes run with control_message_in_radians: true).
 *
 * Invert is already applied inside custom_odrive when invert_direction is set
 * in launch — do not flip signs again here. URDF joint-name alignment is
 * configured via the joint_names parameter (see wheels.yaml / launch).
 *
 * Diff-bar / suspension joints are out of scope (separate MCU pipeline later).
 */

#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "custom_odrive/msg/controller_status.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"

class WheelJointStatePublisher : public rclcpp::Node
{
public:
    explicit WheelJointStatePublisher(
        const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
    void on_status(
        const std::string & wheel_id,
        const custom_odrive::msg::ControllerStatus & msg);
    void publish_timer();

    std::vector<std::string> wheel_ids_;
    std::unordered_map<std::string, std::string> joint_by_wheel_;  // id → URDF name
    std::unordered_map<std::string, double> pos_;  // last pos_estimate (rad)
    std::unordered_map<std::string, double> vel_;  // last vel_estimate (rad/s)
    // Only include a joint once at least one status message has arrived.
    std::unordered_map<std::string, bool> have_;
    std::mutex mutex_;  // protects pos_/vel_/have_ across callback + timer

    std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr> subs_;
    rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};
