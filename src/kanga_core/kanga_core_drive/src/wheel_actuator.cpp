#include "kanga_core_drive/wheel_actuator.hpp"

#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

#include "kanga_core_drive/transmission.hpp"

// Configure the joint-to-motor adapter and create all wheel ROS interfaces.
WheelActuator::WheelActuator(const rclcpp::NodeOptions & options)
: Node("wheel_actuator", options)
{
  // Declare the parameters.
  this->declare_parameter<std::vector<std::string>>(
    "wheel_ids", {"fl", "bl", "br", "fr"});
  // Selected drivetrain profile supplies the physical actuator parameters.
  this->declare_parameter<double>("motor_revolutions_per_wheel_revolution");
  this->declare_parameter<double>("motor_velocity_limit_tps");
  this->declare_parameter<double>("joint_command_timeout_s", 0.5);
  this->declare_parameter<double>("publish_rate_hz", 10.0);

  wheel_ids_ = this->get_parameter("wheel_ids").as_string_array();
  gear_ratio_ = this->get_parameter(
    "motor_revolutions_per_wheel_revolution").as_double();
  motor_velocity_limit_tps_ =
    this->get_parameter("motor_velocity_limit_tps").as_double();
  joint_command_timeout_s_ =
    this->get_parameter("joint_command_timeout_s").as_double();
  const double publish_rate_hz =
    this->get_parameter("publish_rate_hz").as_double();

  // Check the parameters are valid
  if (wheel_ids_.size() != wheel_joint_velocity_commands_.size()) {
    throw std::runtime_error("wheel_ids must have exactly 4 entries");
  }
  if (!std::isfinite(gear_ratio_) || gear_ratio_ <= 0.0) {
    throw std::runtime_error(
            "motor_revolutions_per_wheel_revolution must be finite and > 0");
  }
  if (!std::isfinite(motor_velocity_limit_tps_) ||
    motor_velocity_limit_tps_ <= 0.0)
  {
    throw std::runtime_error("motor_velocity_limit_tps must be finite and > 0");
  }
  if (!std::isfinite(joint_command_timeout_s_) ||
    joint_command_timeout_s_ <= 0.0)
  {
    throw std::runtime_error("joint_command_timeout_s must be finite and > 0");
  }
  if (!std::isfinite(publish_rate_hz) || publish_rate_hz <= 0.0) {
    throw std::runtime_error("publish_rate_hz must be finite and > 0");
  }

  // Calculate the maximum motor velocity
  max_motor_velocity_rad_s_ =
    kanga_core_drive::max_motor_velocity_rad_s(motor_velocity_limit_tps_);

  // One message carries the complete wheel vector, so it cannot arrive partially.
  wheel_velocity_command_subscription_ =
    this->create_subscription<kanga_interfaces::msg::WheelVelocityCommand>(
    "/wheel_joint_velocity_command", 10,
    std::bind(
      &WheelActuator::on_wheel_velocity_command, this,
      std::placeholders::_1));

  // Subscribe to the status of each wheel
  rclcpp::QoS controller_status_qos(10);
  controller_status_qos.best_effort();
  for (size_t wheel_index = 0; wheel_index < wheel_ids_.size(); ++wheel_index) {
    const std::string wheel_namespace = "/wheel_" + wheel_ids_[wheel_index];
    controller_status_subscriptions_.push_back(
      this->create_subscription<custom_odrive::msg::ControllerStatus>(
        wheel_namespace + "/controller_status", controller_status_qos,
        // Humble requires a lambda when each subscription binds an index.
        [this, wheel_index](
          const custom_odrive::msg::ControllerStatus::SharedPtr msg) {
          this->on_controller_status(wheel_index, msg);
        }));
    motor_command_publishers_.push_back(
      this->create_publisher<custom_odrive::msg::ControlMessage>(
        wheel_namespace + "/control_message", 10));
  }

  // Create a timer to publish the motor commands
  const auto publish_period =
    std::chrono::duration<double>(1.0 / publish_rate_hz);
  motor_command_publish_timer_ = this->create_wall_timer(
    std::chrono::duration_cast<std::chrono::nanoseconds>(publish_period),
    std::bind(&WheelActuator::publish_motor_commands, this));

  RCLCPP_INFO(
    this->get_logger(),
    "wheel_actuator ready (ratio %.3f:1, motor limit %.3f TPS / %.3f rad/s, timeout %.2f s)",
    gear_ratio_, motor_velocity_limit_tps_,
    max_motor_velocity_rad_s_,
    joint_command_timeout_s_);
}

// Cache one complete four-wheel command and its local arrival time.
void WheelActuator::on_wheel_velocity_command(
  const kanga_interfaces::msg::WheelVelocityCommand::SharedPtr msg)
{
  std::lock_guard<std::mutex> lock(actuator_state_mutex_);
  wheel_joint_velocity_commands_ = {
    msg->front_left_rad_s,
    msg->back_left_rad_s,
    msg->back_right_rad_s,
    msg->front_right_rad_s,
  };
  last_joint_command_time_ = this->get_clock()->now();
  wheel_command_received_ = true;
}

// Cache one ODrive axis state for CLOSED_LOOP output gating.
void WheelActuator::on_controller_status(
  size_t wheel_index,
  const custom_odrive::msg::ControllerStatus::SharedPtr msg)
{
  if (wheel_index >= wheel_axis_states_.size()) {
    return;
  }
  std::lock_guard<std::mutex> lock(actuator_state_mutex_);
  wheel_axis_states_[wheel_index] = msg->axis_state;
}

// Convert fresh joint commands and publish safe motor commands while closed loop.
void WheelActuator::publish_motor_commands()
{
  std::array<double, 4> wheel_joint_velocity_commands{};
  std::array<uint8_t, 4> wheel_axis_states{};
  bool command_is_fresh = false;
  const auto now = this->get_clock()->now();

  {
    std::lock_guard<std::mutex> lock(actuator_state_mutex_);
    wheel_joint_velocity_commands = wheel_joint_velocity_commands_;
    wheel_axis_states = wheel_axis_states_;
    command_is_fresh = wheel_command_received_ &&
      (now - last_joint_command_time_).seconds() <=
      joint_command_timeout_s_;
  }

  // A stale four-wheel vector means the controller path has failed.
  // Send nothing so an enabled firmware watchdog can disarm CLOSED_LOOP.
  // Normal stale /cmd_vel is different: the live controller keeps publishing
  // joint zeros.
  if (!command_is_fresh) {
    return;
  }

  // Check if the joint commands are valid
  for (const double command : wheel_joint_velocity_commands) {
    if (!std::isfinite(command)) {
      return;
    }
  }

  custom_odrive::msg::ControlMessage motor_command_message;
  motor_command_message.control_mode = kControlModeVelocity;
  motor_command_message.input_mode = kInputModeVelRamp;
  motor_command_message.input_pos = 0.0F;
  motor_command_message.input_torque = 0.0F;

  // Publish the motor commands
  for (size_t wheel_index = 0;
    wheel_index < motor_command_publishers_.size(); ++wheel_index)
  {
    if (wheel_axis_states[wheel_index] != kAxisClosedLoop) {
      continue;
    }
    const double requested_motor_rad_s =
      kanga_core_drive::motor_velocity_from_joint(
      wheel_joint_velocity_commands[wheel_index],
      gear_ratio_);
    const double limited_motor_rad_s =
      kanga_core_drive::clamp_motor_velocity(
      requested_motor_rad_s, max_motor_velocity_rad_s_);
    if (limited_motor_rad_s != requested_motor_rad_s) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 2000,
        "Motor safety clamp active; controller joint command exceeds profile limit");
    }
    motor_command_message.input_vel = static_cast<float>(limited_motor_rad_s);
    motor_command_publishers_[wheel_index]->publish(motor_command_message);
  }
}
