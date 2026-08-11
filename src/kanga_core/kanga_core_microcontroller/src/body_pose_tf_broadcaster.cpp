#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>

#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tf2_ros/transform_broadcaster.h"

namespace kanga_core_microcontroller
{

class BodyPoseTfBroadcaster final : public rclcpp::Node
{
public:
  BodyPoseTfBroadcaster()
  : Node("body_pose_tf_broadcaster")
  {
    parent_frame_id_ = this->declare_parameter<std::string>(
      "parent_frame_id", "body_origin");
    child_frame_id_ = this->declare_parameter<std::string>(
      "child_frame_id", "base_link");
    quaternion_norm_tolerance_ = this->declare_parameter<double>(
      "quaternion_norm_tolerance", 0.01);

    if (parent_frame_id_.empty() || child_frame_id_.empty()) {
      throw std::invalid_argument("Body pose TF frame names must not be empty");
    }
    if (!std::isfinite(quaternion_norm_tolerance_) ||
      quaternion_norm_tolerance_ <= 0.0)
    {
      throw std::invalid_argument(
              "quaternion_norm_tolerance must be finite and > 0");
    }

    transform_broadcaster_ =
      std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    latest_transform_.header.frame_id = parent_frame_id_;
    latest_transform_.child_frame_id = child_frame_id_;
    latest_transform_.transform.rotation.w = 1.0;
    pose_subscription_ =
      this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
      "body/pose", rclcpp::SensorDataQoS(),
      [this](
        const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr message)
      {
        this->broadcast_pose(*message);
      });
    transform_timer_ = this->create_wall_timer(
      std::chrono::milliseconds(100), [this]() {
        this->broadcast_latest_transform();
      });

    RCLCPP_INFO(
      this->get_logger(), "Broadcasting body/pose as %s -> %s",
      parent_frame_id_.c_str(), child_frame_id_.c_str());
  }

private:
  void broadcast_pose(
    const geometry_msgs::msg::PoseWithCovarianceStamped & message)
  {
    if (!message.header.frame_id.empty() &&
      message.header.frame_id != parent_frame_id_)
    {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring body pose in frame '%s'; expected '%s'",
        message.header.frame_id.c_str(), parent_frame_id_.c_str());
      return;
    }

    const auto & position = message.pose.pose.position;
    const auto & orientation = message.pose.pose.orientation;
    if (!std::isfinite(position.x) || !std::isfinite(position.y) ||
      !std::isfinite(position.z) || !std::isfinite(orientation.x) ||
      !std::isfinite(orientation.y) || !std::isfinite(orientation.z) ||
      !std::isfinite(orientation.w))
    {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring body pose containing non-finite values");
      return;
    }

    const double quaternion_norm = std::sqrt(
      orientation.x * orientation.x + orientation.y * orientation.y +
      orientation.z * orientation.z + orientation.w * orientation.w);
    if (quaternion_norm < 1.0e-12 ||
      std::abs(quaternion_norm - 1.0) > quaternion_norm_tolerance_)
    {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring body pose with quaternion norm %.6f", quaternion_norm);
      return;
    }

    latest_transform_.transform.translation.x = position.x;
    latest_transform_.transform.translation.y = position.y;
    latest_transform_.transform.translation.z = position.z;
    latest_transform_.transform.rotation.x = orientation.x / quaternion_norm;
    latest_transform_.transform.rotation.y = orientation.y / quaternion_norm;
    latest_transform_.transform.rotation.z = orientation.z / quaternion_norm;
    latest_transform_.transform.rotation.w = orientation.w / quaternion_norm;
    broadcast_latest_transform();
  }

  void broadcast_latest_transform()
  {
    latest_transform_.header.stamp = this->get_clock()->now();
    transform_broadcaster_->sendTransform(latest_transform_);
  }

  std::string parent_frame_id_;
  std::string child_frame_id_;
  double quaternion_norm_tolerance_;
  geometry_msgs::msg::TransformStamped latest_transform_;
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr
    pose_subscription_;
  rclcpp::TimerBase::SharedPtr transform_timer_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> transform_broadcaster_;
};

}  // namespace kanga_core_microcontroller

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(
    std::make_shared<kanga_core_microcontroller::BodyPoseTfBroadcaster>());
  rclcpp::shutdown();
  return 0;
}
