#include <cmath>
#include <memory>
#include <string>

#include "can_msgs/msg/frame.hpp"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "geometry_msgs/msg/twist_with_covariance_stamped.hpp"
#include "kanga_core_microcontroller/can_ids.hpp"
#include "kanga_core_microcontroller/can_protocol.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "std_msgs/msg/float64.hpp"

namespace kanga_core_microcontroller
{

namespace
{

void setUnavailableDiagonal(double * covariance, const size_t index)
{
  covariance[index] = -1.0;
}

}  // namespace

class CoreCanBridge final : public rclcpp::Node
{
public:
  CoreCanBridge()
  : Node("core_can_bridge")
  {
    body_pose_frame_id_ = this->declare_parameter<std::string>(
      "body_pose_frame_id", "body_origin");
    body_twist_frame_id_ = this->declare_parameter<std::string>(
      "body_twist_frame_id", "base_link");
    imu_frame_id_ = this->declare_parameter<std::string>(
      "imu_frame_id", "base_link");
    diff_bar_encoder_zero_count_ = this->declare_parameter<int>(
      "diff_bar_encoder_zero_count", 0);
    diff_bar_encoder_counts_per_rad_ = this->declare_parameter<double>(
      "diff_bar_encoder_counts_per_rad", 1000.0);
    orientation_variance_ = this->declare_parameter<double>(
      "orientation_variance", 0.01);
    angular_velocity_variance_ = this->declare_parameter<double>(
      "angular_velocity_variance", 0.001);
    linear_acceleration_variance_ = this->declare_parameter<double>(
      "linear_acceleration_variance", 0.01);

    body_pose_publisher_ =
      this->create_publisher<geometry_msgs::msg::PoseWithCovarianceStamped>(
      "body/pose", rclcpp::SensorDataQoS());
    body_twist_publisher_ =
      this->create_publisher<geometry_msgs::msg::TwistWithCovarianceStamped>(
      "body/twist", rclcpp::SensorDataQoS());
    diff_bar_angle_publisher_ = this->create_publisher<std_msgs::msg::Float64>(
      "diff_bar_angle", rclcpp::SensorDataQoS());
    imu_publisher_ = this->create_publisher<sensor_msgs::msg::Imu>(
      "imu/data", rclcpp::SensorDataQoS());

    can_subscription_ = this->create_subscription<can_msgs::msg::Frame>(
      "from_can_bus", rclcpp::SensorDataQoS(),
      [this](const can_msgs::msg::Frame::SharedPtr message) {
        this->handleCanFrame(*message);
      });

    RCLCPP_INFO(
      this->get_logger(),
      "Core CAN bridge listening on from_can_bus (IDs 812, 820-822)");
  }

private:
  void handleCanFrame(const can_msgs::msg::Frame & frame)
  {
    if (frame.is_extended || frame.is_rtr || frame.is_error) {
      return;
    }

    switch (frame.id) {
      case CAN_ID_DIFF_BAR_ENCODER:
        handleDiffBarEncoder(frame);
        break;
      case CAN_ID_IMU_ORIENTATION:
        handleImuOrientation(frame);
        break;
      case CAN_ID_IMU_ANGULAR_VEL:
        handleImuAngularVelocity(frame);
        break;
      case CAN_ID_IMU_LINEAR_ACCEL:
        handleImuLinearAcceleration(frame);
        break;
      default:
        break;
    }
  }

  void handleDiffBarEncoder(const can_msgs::msg::Frame & frame)
  {
    DiffBarEncoderFrame payload{};
    if (!decodeFrame(frame.data.data(), frame.dlc, payload)) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring short diff-bar encoder frame (dlc=%u)", frame.dlc);
      return;
    }

    std_msgs::msg::Float64 message;
    message.data = diffBarCountToRadians(
      payload.count,
      diff_bar_encoder_zero_count_,
      diff_bar_encoder_counts_per_rad_);
    diff_bar_angle_publisher_->publish(message);
  }

  void handleImuOrientation(const can_msgs::msg::Frame & frame)
  {
    ImuOrientationFrame payload{};
    if (!decodeFrame(frame.data.data(), frame.dlc, payload)) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring short IMU orientation frame (dlc=%u)", frame.dlc);
      return;
    }

    pending_orientation_ = payload;
    have_pending_orientation_ = true;
  }

  void handleImuAngularVelocity(const can_msgs::msg::Frame & frame)
  {
    ImuAngularVelocityFrame payload{};
    if (!decodeFrame(frame.data.data(), frame.dlc, payload)) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring short IMU gyro frame (dlc=%u)", frame.dlc);
      return;
    }

    pending_gyro_ = payload;
    have_pending_gyro_ = true;
  }

  void handleImuLinearAcceleration(const can_msgs::msg::Frame & frame)
  {
    ImuLinearAccelFrame payload{};
    if (!decodeFrame(frame.data.data(), frame.dlc, payload)) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "Ignoring short IMU accel frame (dlc=%u)", frame.dlc);
      return;
    }

    if (!have_pending_orientation_ || !have_pending_gyro_) {
      return;
    }
    if (pending_gyro_.sequence != payload.sequence) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "IMU accel sequence %u does not match gyro sequence %u",
        payload.sequence, pending_gyro_.sequence);
      return;
    }

    publishImuSample(pending_orientation_, pending_gyro_, payload);
    have_pending_orientation_ = false;
    have_pending_gyro_ = false;
  }

  void publishImuSample(
    const ImuOrientationFrame & orientation,
    const ImuAngularVelocityFrame & gyro,
    const ImuLinearAccelFrame & accel)
  {
    const auto stamp = this->get_clock()->now();

    const double qw = int16ToFloat(orientation.qw, kQuatScale);
    const double qx = int16ToFloat(orientation.qx, kQuatScale);
    const double qy = int16ToFloat(orientation.qy, kQuatScale);
    const double qz = int16ToFloat(orientation.qz, kQuatScale);

    const double wx = int16ToFloat(gyro.wx, kGyroScale);
    const double wy = int16ToFloat(gyro.wy, kGyroScale);
    const double wz = int16ToFloat(gyro.wz, kGyroScale);

    const double ax = int16ToFloat(accel.ax, kAccelScale);
    const double ay = int16ToFloat(accel.ay, kAccelScale);
    const double az = int16ToFloat(accel.az, kAccelScale);

    geometry_msgs::msg::PoseWithCovarianceStamped pose;
    pose.header.stamp = stamp;
    pose.header.frame_id = body_pose_frame_id_;
    pose.pose.pose.position.x = 0.0;
    pose.pose.pose.position.y = 0.0;
    pose.pose.pose.position.z = 0.0;
    pose.pose.pose.orientation.x = qx;
    pose.pose.pose.orientation.y = qy;
    pose.pose.pose.orientation.z = qz;
    pose.pose.pose.orientation.w = qw;
    pose.pose.covariance.fill(0.0);
    setUnavailableDiagonal(pose.pose.covariance.data(), 0);
    setUnavailableDiagonal(pose.pose.covariance.data(), 7);
    setUnavailableDiagonal(pose.pose.covariance.data(), 14);
    pose.pose.covariance[21] = orientation_variance_;
    pose.pose.covariance[28] = orientation_variance_;
    pose.pose.covariance[35] = orientation_variance_;
    body_pose_publisher_->publish(pose);

    geometry_msgs::msg::TwistWithCovarianceStamped twist;
    twist.header.stamp = stamp;
    twist.header.frame_id = body_twist_frame_id_;
    twist.twist.twist.linear.x = 0.0;
    twist.twist.twist.linear.y = 0.0;
    twist.twist.twist.linear.z = 0.0;
    twist.twist.twist.angular.x = wx;
    twist.twist.twist.angular.y = wy;
    twist.twist.twist.angular.z = wz;
    twist.twist.covariance.fill(0.0);
    setUnavailableDiagonal(twist.twist.covariance.data(), 0);
    setUnavailableDiagonal(twist.twist.covariance.data(), 7);
    setUnavailableDiagonal(twist.twist.covariance.data(), 14);
    twist.twist.covariance[21] = angular_velocity_variance_;
    twist.twist.covariance[28] = angular_velocity_variance_;
    twist.twist.covariance[35] = angular_velocity_variance_;
    body_twist_publisher_->publish(twist);

    sensor_msgs::msg::Imu imu;
    imu.header.stamp = stamp;
    imu.header.frame_id = imu_frame_id_;
    imu.orientation.x = qx;
    imu.orientation.y = qy;
    imu.orientation.z = qz;
    imu.orientation.w = qw;
    imu.angular_velocity.x = wx;
    imu.angular_velocity.y = wy;
    imu.angular_velocity.z = wz;
    imu.linear_acceleration.x = ax;
    imu.linear_acceleration.y = ay;
    imu.linear_acceleration.z = az;
    imu.orientation_covariance[0] = orientation_variance_;
    imu.orientation_covariance[4] = orientation_variance_;
    imu.orientation_covariance[8] = orientation_variance_;
    imu.angular_velocity_covariance[0] = angular_velocity_variance_;
    imu.angular_velocity_covariance[4] = angular_velocity_variance_;
    imu.angular_velocity_covariance[8] = angular_velocity_variance_;
    imu.linear_acceleration_covariance[0] = linear_acceleration_variance_;
    imu.linear_acceleration_covariance[4] = linear_acceleration_variance_;
    imu.linear_acceleration_covariance[8] = linear_acceleration_variance_;
    imu_publisher_->publish(imu);
  }

  std::string body_pose_frame_id_;
  std::string body_twist_frame_id_;
  std::string imu_frame_id_;
  int diff_bar_encoder_zero_count_;
  double diff_bar_encoder_counts_per_rad_;
  double orientation_variance_;
  double angular_velocity_variance_;
  double linear_acceleration_variance_;

  bool have_pending_orientation_{false};
  bool have_pending_gyro_{false};
  ImuOrientationFrame pending_orientation_{};
  ImuAngularVelocityFrame pending_gyro_{};

  rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr
  body_pose_publisher_;
  rclcpp::Publisher<geometry_msgs::msg::TwistWithCovarianceStamped>::SharedPtr
  body_twist_publisher_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr diff_bar_angle_publisher_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_publisher_;
  rclcpp::Subscription<can_msgs::msg::Frame>::SharedPtr can_subscription_;
};

}  // namespace kanga_core_microcontroller

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<kanga_core_microcontroller::CoreCanBridge>());
  rclcpp::shutdown();
  return 0;
}
