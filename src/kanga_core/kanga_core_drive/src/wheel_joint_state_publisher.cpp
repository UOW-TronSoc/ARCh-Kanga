#include "kanga_core_drive/wheel_joint_state_publisher.hpp"

#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

#include "kanga_core_drive/transmission.hpp"

using namespace std::chrono_literals;

// Configure feedback conversion and create the per-wheel status subscriptions.
WheelJointStatePublisher::WheelJointStatePublisher(const rclcpp::NodeOptions & options)
: Node("wheel_joint_state_publisher", options)
{
    // wheel_ids ↔ joint_names are parallel arrays from launch; names must match
    // the URDF when robot_state_publisher / controllers consume this topic.
    this->declare_parameter<std::vector<std::string>>(
        "wheel_ids", {"fl", "bl", "br", "fr"});
    this->declare_parameter<std::vector<std::string>>(
        "joint_names",
        {"wheel_fl_joint", "wheel_bl_joint", "wheel_br_joint", "wheel_fr_joint"});
    this->declare_parameter<double>("publish_rate_hz", 50.0);
    this->declare_parameter<double>("motor_revolutions_per_wheel_revolution");

    const double publish_rate_hz =
        this->get_parameter("publish_rate_hz").as_double();
    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    gear_ratio_ = this->get_parameter(
        "motor_revolutions_per_wheel_revolution").as_double();
    const auto joint_names = this->get_parameter("joint_names").as_string_array();

    // Check the parameters are valid
    if (joint_names.size() != wheel_ids_.size()) {
        throw std::runtime_error("joint_names length must match wheel_ids");
    }
    if (!std::isfinite(gear_ratio_) || gear_ratio_ <= 0.0) {
        throw std::runtime_error(
            "motor_revolutions_per_wheel_revolution must be finite and > 0");
    }
    if (!std::isfinite(publish_rate_hz) || publish_rate_hz <= 0.0) {
        throw std::runtime_error("publish_rate_hz must be finite and > 0");
    }

    // Initialize the joint states
    for (size_t i = 0; i < wheel_ids_.size(); ++i) {
        joint_name_by_wheel_id_[wheel_ids_[i]] = joint_names[i];
        joint_position_by_wheel_id_[wheel_ids_[i]] = 0.0;
        joint_velocity_by_wheel_id_[wheel_ids_[i]] = 0.0;
        status_received_by_wheel_id_[wheel_ids_[i]] = false;
    }

    // One subscription per custom_odrive_node controller_status stream.
    // Estimates already include invert_direction from that node — do not negate.
    // QoS must match custom_odrive_node (KeepLast(10), best_effort).
    rclcpp::QoS status_qos(10);
    status_qos.best_effort();
    for (const auto & wheel_id : wheel_ids_) {
        const std::string topic = "/wheel_" + wheel_id + "/controller_status";
        controller_status_subscriptions_.push_back(
            this->create_subscription<custom_odrive::msg::ControllerStatus>(
                topic, status_qos,
                // Humble requires a lambda when each subscription binds a wheel id.
                [this, wheel_id](
                    const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
                    this->on_controller_status(wheel_id, msg);
                }));
    }

    const auto period = std::chrono::duration<double>(1.0 / publish_rate_hz);

    // Create a publisher to publish the joint states
    wheel_joint_state_publisher_ =
        this->create_publisher<sensor_msgs::msg::JointState>("wheel_joint_states", 10);
    joint_state_publish_timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelJointStatePublisher::publish_wheel_joint_states, this));

    RCLCPP_INFO(
        this->get_logger(), "Publishing wheel_joint_states (%zu wheels, ratio %.3f:1)",
        wheel_ids_.size(), gear_ratio_);
}

// Convert and cache one motor's feedback in wheel-joint units.
void WheelJointStatePublisher::on_controller_status(
    const std::string & wheel_id,
    const custom_odrive::msg::ControllerStatus::SharedPtr msg)
{
    // Callback and timer may run concurrently on a multi-threaded executor if
    // remapped later; guard the caches.
    std::lock_guard<std::mutex> lock(joint_feedback_mutex_);
    joint_position_by_wheel_id_[wheel_id] =
        kanga_core_drive::joint_position_from_motor(
            msg->pos_estimate, gear_ratio_);
    joint_velocity_by_wheel_id_[wheel_id] =
        kanga_core_drive::joint_velocity_from_motor(
            msg->vel_estimate, gear_ratio_);
    status_received_by_wheel_id_[wheel_id] = true;
}

// Publish all wheel-joint feedback that has been received at least once.
void WheelJointStatePublisher::publish_wheel_joint_states()
{
    sensor_msgs::msg::JointState out;
    out.header.stamp = this->get_clock()->now();

    {
        std::lock_guard<std::mutex> lock(joint_feedback_mutex_);
        // Only include wheels that have reported at least once (partial OK).
        for (const auto & wheel_id : wheel_ids_) {
            if (!status_received_by_wheel_id_[wheel_id]) {
                continue;
            }
            out.name.push_back(joint_name_by_wheel_id_.at(wheel_id));
            out.position.push_back(joint_position_by_wheel_id_.at(wheel_id));
            out.velocity.push_back(joint_velocity_by_wheel_id_.at(wheel_id));
        }
    }

    // Stay quiet until at least one wheel has reported (avoids empty frames).
    if (!out.name.empty()) {
        wheel_joint_state_publisher_->publish(out);
    }
}
