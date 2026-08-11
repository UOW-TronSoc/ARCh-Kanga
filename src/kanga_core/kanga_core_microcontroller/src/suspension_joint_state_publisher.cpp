#include <memory>
#include <stdexcept>
#include <string>

#include "kanga_core_microcontroller/suspension_kinematics.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/float64.hpp"

namespace kanga_core_microcontroller
{

class SuspensionJointStatePublisher final : public rclcpp::Node
{
public:
  SuspensionJointStatePublisher()
  : Node("suspension_joint_state_publisher"),
    kinematics_(
      this->declare_parameter<double>("diff_bar_limit_rad", 1.2217304763960306),
      this->declare_parameter<double>("suspension_limit_rad", 0.5235987755982988))
  {
    diff_bar_joint_name_ = this->declare_parameter<std::string>(
      "diff_bar_joint_name", "diff_bar_joint");
    left_suspension_joint_name_ = this->declare_parameter<std::string>(
      "left_suspension_joint_name", "left_suspension_joint");
    right_suspension_joint_name_ = this->declare_parameter<std::string>(
      "right_suspension_joint_name", "right_suspension_joint");

    joint_state_publisher_ = this->create_publisher<sensor_msgs::msg::JointState>(
      "suspension_joint_states", 10);
    diff_bar_angle_subscription_ = this->create_subscription<std_msgs::msg::Float64>(
      "diff_bar_angle", rclcpp::SensorDataQoS(),
      [this](const std_msgs::msg::Float64::SharedPtr message) {
        this->publish_joint_state(message->data);
      });

    RCLCPP_INFO(
      this->get_logger(),
      "Mapping diff_bar_angle to %s, %s, and %s on suspension_joint_states",
      diff_bar_joint_name_.c_str(),
      left_suspension_joint_name_.c_str(),
      right_suspension_joint_name_.c_str());
  }

private:
  void publish_joint_state(const double diff_bar_angle_rad)
  {
    SuspensionJointPositions positions;
    try {
      positions = kinematics_.map_diff_bar_angle(diff_bar_angle_rad);
    } catch (const std::invalid_argument & error) {
      RCLCPP_ERROR(this->get_logger(), "Ignoring encoder angle: %s", error.what());
      return;
    }

    if (positions.input_was_clamped) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Diff-bar angle %.6f rad exceeds its configured range; clamping to %.6f rad",
        diff_bar_angle_rad, positions.diff_bar_rad);
    }

    sensor_msgs::msg::JointState joint_state;
    joint_state.header.stamp = this->get_clock()->now();
    joint_state.name = {
      diff_bar_joint_name_,
      left_suspension_joint_name_,
      right_suspension_joint_name_,
    };
    joint_state.position = {
      positions.diff_bar_rad,
      positions.left_suspension_rad,
      positions.right_suspension_rad,
    };
    joint_state_publisher_->publish(joint_state);
  }

  LinearSuspensionKinematics kinematics_;
  std::string diff_bar_joint_name_;
  std::string left_suspension_joint_name_;
  std::string right_suspension_joint_name_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr joint_state_publisher_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr
    diff_bar_angle_subscription_;
};

}  // namespace kanga_core_microcontroller

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(
    std::make_shared<kanga_core_microcontroller::SuspensionJointStatePublisher>());
  rclcpp::shutdown();
  return 0;
}
