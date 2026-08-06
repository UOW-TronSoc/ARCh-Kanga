#include "kanga_core_controller/wheel_command_mapper.hpp"

#include <chrono>
#include <cmath>
#include <stdexcept>

using namespace std::chrono_literals;
using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::desaturate_wheel_velocities;
using kanga_core_controller::twist_to_wheels;

// Configure the mapper and create its command subscription and wheel publishers.
WheelCommandMapper::WheelCommandMapper(const rclcpp::NodeOptions &options)
    : Node("wheel_command_mapper", options)
{
    // Behaviour parameters come from controller.yaml. Physical parameters have
    // no hardware-specific defaults and are injected by the selected profile.
    this->declare_parameter<double>("publish_rate_hz", 10.0);
    this->declare_parameter<double>("cmd_vel_timeout_s", 0.5);
    this->declare_parameter<double>("grouser_angle_deg");
    this->declare_parameter<double>("half_length");
    this->declare_parameter<double>("half_width");
    this->declare_parameter<double>("effective_wheel_radius_m");
    this->declare_parameter<double>("max_wheel_joint_velocity_rad_s");

    cmd_vel_timeout_s_ = this->get_parameter("cmd_vel_timeout_s").as_double();
    const double rate = this->get_parameter("publish_rate_hz").as_double();
    geom_.grouser_angle_deg = this->get_parameter("grouser_angle_deg").as_double();
    geom_.half_length = this->get_parameter("half_length").as_double();
    geom_.half_width = this->get_parameter("half_width").as_double();
    geom_.effective_wheel_radius_m = this->get_parameter("effective_wheel_radius_m").as_double();
    max_wheel_joint_velocity_rad_s_ = this->get_parameter("max_wheel_joint_velocity_rad_s").as_double();

	// Check if the parameters are valid
    if (!std::isfinite(rate) || rate <= 0.0)
    {
        throw std::runtime_error("publish_rate_hz must be finite and > 0");
    }
    if (!std::isfinite(cmd_vel_timeout_s_) || cmd_vel_timeout_s_ <= 0.0)
    {
        throw std::runtime_error("cmd_vel_timeout_s must be finite and > 0");
    }
    if (!std::isfinite(geom_.grouser_angle_deg) || std::abs(std::cos(geom_.grouser_angle_deg * M_PI / 180.0)) < 1e-9)
    {
        throw std::runtime_error(
            "grouser_angle_deg must be finite with non-zero cosine");
    }
    if (!std::isfinite(geom_.half_length) || geom_.half_length <= 0.0 || !std::isfinite(geom_.half_width) || geom_.half_width <= 0.0)
    {
        throw std::runtime_error("half_length and half_width must be finite and > 0");
    }
    if (!std::isfinite(geom_.effective_wheel_radius_m) || geom_.effective_wheel_radius_m <= 0.0)
    {
        throw std::runtime_error("effective_wheel_radius_m must be finite and > 0");
    }
    if (!std::isfinite(max_wheel_joint_velocity_rad_s_) || max_wheel_joint_velocity_rad_s_ <= 0.0)
    {
        throw std::runtime_error("max_wheel_joint_velocity_rad_s must be finite and > 0");
    }

    // Publish all four joint velocities together so drive receives one vector.
    joint_command_pub_ =
        this->create_publisher<kanga_interfaces::msg::WheelVelocityCommand>(
            "/wheel_joint_velocity_command", 10);

    // Chassis command from teleop / Nav2 / basestation.
    cmd_sub_ = this->create_subscription<geometry_msgs::msg::Twist>(
        "/cmd_vel", 10,
        std::bind(&WheelCommandMapper::on_cmd_vel, this, std::placeholders::_1));

    // Steady publish rate (default 10 times per second).
    const auto period = std::chrono::duration<double>(1.0 / rate);
    timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelCommandMapper::on_timer, this));

    RCLCPP_INFO(
        this->get_logger(),
        "wheel_command_mapper ready (%.1f Hz, timeout %.2f s, joint limit %.3f rad/s)",
        rate, cmd_vel_timeout_s_, max_wheel_joint_velocity_rad_s_);
}

// Cache the newest chassis command for the fixed-rate publisher.
void WheelCommandMapper::on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg)
{
    // Just store the latest command. Publishing happens in on_timer().
    std::lock_guard<std::mutex> lock(mutex_);
    last_twist_ = *msg;
    last_cmd_stamp_ = this->get_clock()->now();
    have_cmd_ = true;
}

// Return the newest command while it is valid, otherwise return a zero Twist.
geometry_msgs::msg::Twist WheelCommandMapper::get_active_twist_locked()
{
    // Prevent on_cmd_vel() from changing the command while this copy is made.
    std::lock_guard<std::mutex> lock(mutex_);
    geometry_msgs::msg::Twist active_twist; // Default construction means stop.
    if (have_cmd_)
    {
        const double age = (this->get_clock()->now() - last_cmd_stamp_).seconds();
        if (age <= cmd_vel_timeout_s_)
        {
            active_twist = last_twist_;
        }
    }
    return active_twist;
}

// Publish the latest four-wheel command at the configured steady rate.
void WheelCommandMapper::on_timer()
{
    // Get a stable local copy; on_cmd_vel() cannot alter active_twist afterwards.
    const auto active_twist = get_active_twist_locked();

    auto command = desaturate_wheel_velocities(
        twist_to_wheels(active_twist, geom_), max_wheel_joint_velocity_rad_s_);
    command.header.stamp = this->get_clock()->now();
    joint_command_pub_->publish(command);
}
