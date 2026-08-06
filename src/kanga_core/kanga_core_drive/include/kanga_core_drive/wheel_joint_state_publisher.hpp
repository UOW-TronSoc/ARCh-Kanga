#pragma once

/*
 * WheelJointStatePublisher — echo ODrive estimates into sensor_msgs/JointState.
 *
 * Subscribes to each /wheel_<id>/controller_status (custom_odrive) and publishes
 * a combined JointState on /wheel_joint_states (or remapped). Position and
 * ODrive pos_estimate / vel_estimate are motor-shaft rad / rad/s. This node
 * divides both by the configured reduction and publishes wheel-joint rad / rad/s.
 *
 * Invert is already applied inside custom_odrive when invert_direction is set
 * in launch — do not flip signs again here. URDF joint-name alignment is
 * configured via the joint_names parameter in drive.launch.py.
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
  void on_controller_status(
    const std::string & wheel_id,
    const custom_odrive::msg::ControllerStatus::SharedPtr msg);
  void publish_wheel_joint_states();

  std::vector<std::string> wheel_ids_;
  double gear_ratio_{0.0};
  std::unordered_map<std::string, std::string> joint_name_by_wheel_id_;
  std::unordered_map<std::string, double> joint_position_by_wheel_id_;
  std::unordered_map<std::string, double> joint_velocity_by_wheel_id_;
  // Only include a joint once at least one status message has arrived.
  std::unordered_map<std::string, bool> status_received_by_wheel_id_;
  std::mutex joint_feedback_mutex_;

  std::vector<rclcpp::Subscription<custom_odrive::msg::ControllerStatus>::SharedPtr>
  controller_status_subscriptions_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr
    wheel_joint_state_publisher_;
  rclcpp::TimerBase::SharedPtr joint_state_publish_timer_;
};
