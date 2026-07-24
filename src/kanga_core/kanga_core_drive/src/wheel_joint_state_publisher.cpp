#include "kanga_core_drive/wheel_joint_state_publisher.hpp"

#include <chrono>
#include <functional>
#include <stdexcept>

using namespace std::chrono_literals;

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

    wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
    const auto joint_names = this->get_parameter("joint_names").as_string_array();
    if (joint_names.size() != wheel_ids_.size()) {
        throw std::runtime_error("joint_names length must match wheel_ids");
    }

    for (size_t i = 0; i < wheel_ids_.size(); ++i) {
        joint_by_wheel_[wheel_ids_[i]] = joint_names[i];
        pos_[wheel_ids_[i]] = 0.0;
        vel_[wheel_ids_[i]] = 0.0;
        have_[wheel_ids_[i]] = false;
    }

    // One subscription per custom_odrive_node controller_status stream.
    // Estimates already include invert_direction from that node — do not negate.
    for (const auto & wid : wheel_ids_) {
        const std::string topic = "/wheel_" + wid + "/controller_status";
        subs_.push_back(
            this->create_subscription<custom_odrive::msg::ControllerStatus>(
                topic, 10,
                [this, wid](const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
                    this->on_status(wid, *msg);
                }));
    }

    const double rate = this->get_parameter("publish_rate_hz").as_double();
    const auto period = std::chrono::duration<double>(rate > 0.0 ? (1.0 / rate) : 0.02);
    // Relative topic; remappable. Default name used by RSP / joint consumers.
    pub_ = this->create_publisher<sensor_msgs::msg::JointState>("wheel_joint_states", 10);
    timer_ = this->create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&WheelJointStatePublisher::publish_timer, this));

    RCLCPP_INFO(
        this->get_logger(), "Publishing wheel_joint_states (%zu wheels)", wheel_ids_.size());
}

void WheelJointStatePublisher::on_status(
    const std::string & wheel_id,
    const custom_odrive::msg::ControllerStatus & msg)
{
    // Callback and timer may run concurrently on a multi-threaded executor if
    // remapped later; guard the caches.
    std::lock_guard<std::mutex> lock(mutex_);
    pos_[wheel_id] = msg.pos_estimate;
    vel_[wheel_id] = msg.vel_estimate;
    have_[wheel_id] = true;
}

void WheelJointStatePublisher::publish_timer()
{
    sensor_msgs::msg::JointState out;
    out.header.stamp = this->get_clock()->now();

    {
        std::lock_guard<std::mutex> lock(mutex_);
        // Only include wheels that have reported at least once (partial OK).
        for (const auto & wid : wheel_ids_) {
            if (!have_[wid]) {
                continue;
            }
            out.name.push_back(joint_by_wheel_.at(wid));
            out.position.push_back(pos_.at(wid));
            out.velocity.push_back(vel_.at(wid));
        }
    }

    // Stay quiet until at least one wheel has reported (avoids empty frames).
    if (!out.name.empty()) {
        pub_->publish(out);
    }
}
