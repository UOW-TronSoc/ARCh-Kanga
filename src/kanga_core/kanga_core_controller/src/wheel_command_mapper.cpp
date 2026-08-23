#include "kanga_core_controller/wheel_command_mapper.hpp"
#include "kanga_core_controller/acceleration_limiter.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>

#include "rclcpp/create_timer.hpp"

using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::desaturate_wheel_velocities;
using kanga_core_controller::limit_body_velocity_change;
using kanga_core_controller::limit_wheel_acceleration;
using kanga_core_controller::twist_to_wheels;

// Configure the mapper and create its command subscription and wheel publishers.
WheelCommandMapper::WheelCommandMapper(const rclcpp::NodeOptions & options)
: Node("wheel_command_mapper", options)
{
  // Behaviour parameters come from controller.yaml. Physical parameters have
  // no hardware-specific defaults and are injected by the selected profile.
  this->declare_parameter<double>("publish_rate_hz", 50.0);
  this->declare_parameter<double>("cmd_vel_timeout_s", 0.5);
  this->declare_parameter<double>("max_linear_acceleration_m_s2", 0.5);
  this->declare_parameter<double>("max_angular_acceleration_rad_s2", 0.75);
  this->declare_parameter<double>("grouser_angle_deg");
  this->declare_parameter<double>("half_length");
  this->declare_parameter<double>("half_width");
  this->declare_parameter<double>("effective_wheel_radius_m");
  this->declare_parameter<double>("max_wheel_joint_velocity_rad_s");
  this->declare_parameter<double>("max_wheel_joint_acceleration_rad_s2");

  cmd_vel_timeout_s_ = this->get_parameter("cmd_vel_timeout_s").as_double();
  max_linear_acceleration_m_s2_ =
    this->get_parameter("max_linear_acceleration_m_s2").as_double();
  max_angular_acceleration_rad_s2_ =
    this->get_parameter("max_angular_acceleration_rad_s2").as_double();
  const double publish_rate_hz =
    this->get_parameter("publish_rate_hz").as_double();
  chassis_geometry_.grouser_angle_deg =
    this->get_parameter("grouser_angle_deg").as_double();
  chassis_geometry_.half_length = this->get_parameter("half_length").as_double();
  chassis_geometry_.half_width = this->get_parameter("half_width").as_double();
  chassis_geometry_.effective_wheel_radius_m =
    this->get_parameter("effective_wheel_radius_m").as_double();
  max_wheel_joint_velocity_rad_s_ =
    this->get_parameter("max_wheel_joint_velocity_rad_s").as_double();
  max_wheel_joint_acceleration_rad_s2_ =
    this->get_parameter("max_wheel_joint_acceleration_rad_s2").as_double();

  // Check that all parameters are valid before creating ROS interfaces.
  if (!std::isfinite(publish_rate_hz) || publish_rate_hz <= 0.0) {
    throw std::runtime_error("publish_rate_hz must be finite and > 0");
  }
  if (!std::isfinite(cmd_vel_timeout_s_) || cmd_vel_timeout_s_ <= 0.0) {
    throw std::runtime_error("cmd_vel_timeout_s must be finite and > 0");
  }
  if (!std::isfinite(max_linear_acceleration_m_s2_) ||
    max_linear_acceleration_m_s2_ <= 0.0)
  {
    throw std::runtime_error("max_linear_acceleration_m_s2 must be finite and > 0");
  }
  if (!std::isfinite(max_angular_acceleration_rad_s2_) ||
    max_angular_acceleration_rad_s2_ <= 0.0)
  {
    throw std::runtime_error("max_angular_acceleration_rad_s2 must be finite and > 0");
  }
  if (!std::isfinite(chassis_geometry_.grouser_angle_deg) ||
    std::abs(std::cos(chassis_geometry_.grouser_angle_deg * M_PI / 180.0)) < 1e-9)
  {
    throw std::runtime_error(
            "grouser_angle_deg must be finite with non-zero cosine");
  }
  if (!std::isfinite(chassis_geometry_.half_length) ||
    chassis_geometry_.half_length <= 0.0 ||
    !std::isfinite(chassis_geometry_.half_width) ||
    chassis_geometry_.half_width <= 0.0)
  {
    throw std::runtime_error("half_length and half_width must be finite and > 0");
  }
  if (!std::isfinite(chassis_geometry_.effective_wheel_radius_m) ||
    chassis_geometry_.effective_wheel_radius_m <= 0.0)
  {
    throw std::runtime_error("effective_wheel_radius_m must be finite and > 0");
  }
  if (!std::isfinite(max_wheel_joint_velocity_rad_s_) ||
    max_wheel_joint_velocity_rad_s_ <= 0.0)
  {
    throw std::runtime_error("max_wheel_joint_velocity_rad_s must be finite and > 0");
  }
  if (!std::isfinite(max_wheel_joint_acceleration_rad_s2_) ||
    max_wheel_joint_acceleration_rad_s2_ <= 0.0)
  {
    throw std::runtime_error(
            "max_wheel_joint_acceleration_rad_s2 must be finite and > 0");
  }

  // Publish all four joint velocities together so drive receives one vector.
  wheel_velocity_command_publisher_ =
    this->create_publisher<kanga_interfaces::msg::WheelVelocityCommand>(
    "/wheel_joint_velocity_command", 10);

  // Chassis command from teleop / Nav2 / basestation.
  cmd_vel_subscription_ =
    this->create_subscription<geometry_msgs::msg::Twist>(
    "/cmd_vel", 10,
    std::bind(
      &WheelCommandMapper::on_cmd_vel, this,
      std::placeholders::_1));

  // ROS-clock publish rate (default 50 times per simulated or real second).
  const double publish_period_s = 1.0 / publish_rate_hz;
  // Five missed publications is treated as a clock discontinuity rather than
  // a large acceleration interval. Keep a 250 ms floor for slower profiles.
  control_time_step_ = std::make_unique<kanga_core_controller::ControlTimeStep>(
    std::max(5.0 * publish_period_s, 0.25));
  wheel_command_publish_timer_ = rclcpp::create_timer(
    this, this->get_clock(), rclcpp::Duration::from_seconds(publish_period_s),
    std::bind(&WheelCommandMapper::publish_wheel_velocity_command, this));

  RCLCPP_INFO(
    this->get_logger(),
    "wheel_command_mapper ready (%.1f Hz, body acceleration %.2f m/s² and %.2f rad/s², joint acceleration %.3f rad/s²)",
    publish_rate_hz, max_linear_acceleration_m_s2_,
    max_angular_acceleration_rad_s2_, max_wheel_joint_acceleration_rad_s2_);
}

// Cache the newest chassis command for the fixed-rate publisher.
void WheelCommandMapper::on_cmd_vel(
  const geometry_msgs::msg::Twist::SharedPtr msg)
{
  // Store the latest command; the fixed-rate callback publishes it later.
  std::lock_guard<std::mutex> lock(twist_mutex_);
  latest_twist_ = *msg;
  latest_twist_time_ = this->get_clock()->now();
  twist_received_ = true;
}

// Return the newest command while it is valid, otherwise return a zero Twist.
geometry_msgs::msg::Twist WheelCommandMapper::get_active_twist_locked()
{
  // Prevent the subscription callback changing the command during this copy.
  std::lock_guard<std::mutex> lock(twist_mutex_);
  geometry_msgs::msg::Twist active_twist;    // Default construction means stop.
  if (twist_received_) {
    const double command_age =
      (this->get_clock()->now() - latest_twist_time_).seconds();
    if (command_age <= cmd_vel_timeout_s_) {
      active_twist = latest_twist_;
    }
  }
  return active_twist;
}

// Publish the latest four-wheel command at the configured ROS-clock rate.
void WheelCommandMapper::publish_wheel_velocity_command()
{
  const auto publish_time = this->get_clock()->now();
  const auto elapsed_time_s = control_time_step_->update(publish_time.nanoseconds());

  // The first tick and all clock discontinuities publish a deterministic stop.
  // Also discard the cached Twist so a pre-reset command cannot resume motion.
  if (!elapsed_time_s.has_value()) {
    {
      std::lock_guard<std::mutex> lock(twist_mutex_);
      twist_received_ = false;
      latest_twist_ = geometry_msgs::msg::Twist();
    }
    previous_limited_twist_ = geometry_msgs::msg::Twist();
    previous_wheel_command_ =
      kanga_interfaces::msg::WheelVelocityCommand();
    previous_wheel_command_.header.stamp = publish_time;
    wheel_velocity_command_publisher_->publish(previous_wheel_command_);
    return;
  }

  // Get a stable local copy; new /cmd_vel messages cannot alter it afterwards.
  const auto active_twist = get_active_twist_locked();

  const auto limited_twist = limit_body_velocity_change(
    previous_limited_twist_, active_twist,
    max_linear_acceleration_m_s2_, max_angular_acceleration_rad_s2_,
    elapsed_time_s.value());
  previous_limited_twist_ = limited_twist;

  const auto target_wheel_command = desaturate_wheel_velocities(
    twist_to_wheels(limited_twist, chassis_geometry_),
    max_wheel_joint_velocity_rad_s_);
  auto command = limit_wheel_acceleration(
    previous_wheel_command_, target_wheel_command,
    max_wheel_joint_acceleration_rad_s2_, elapsed_time_s.value());
  previous_wheel_command_ = command;
  command.header.stamp = this->get_clock()->now();
  wheel_velocity_command_publisher_->publish(command);
}
