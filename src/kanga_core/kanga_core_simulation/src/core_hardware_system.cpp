#include "kanga_core_simulation/drive_simulation.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <gz/math/Pose3.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/Joint.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Types.hh>
#include <gz/sim/Util.hh>
#include <sdf/Element.hh>

#include <builtin_interfaces/msg/time.hpp>
#include <geometry_msgs/msg/pose_with_covariance_stamped.hpp>
#include <geometry_msgs/msg/twist_with_covariance_stamped.hpp>
#include <kanga_interfaces/msg/wheel_velocity_command.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/executors/single_threaded_executor.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float64.hpp>
#include <std_srvs/srv/set_bool.hpp>
#include <std_srvs/srv/trigger.hpp>

namespace kanga_core_simulation
{
namespace
{

constexpr std::array<const char *, kWheelCount> kWheelJointNames{
  "wheel_fl_joint", "wheel_bl_joint", "wheel_br_joint", "wheel_fr_joint"};
constexpr const char * kDiffBarJointName = "diff_bar_joint";
// Match the BNO086-only body contract: mark unobservable translation components
// as unavailable rather than publishing privileged Gazebo ground truth there.
constexpr double kUnavailableVariance = 1.0e6;

template<typename T>
T sdf_value(const std::shared_ptr<const sdf::Element> & sdf,
  const std::string & name, const T & default_value)
{
  return sdf->Get<T>(name, default_value).first;
}

builtin_interfaces::msg::Time ros_time(const std::chrono::steady_clock::duration time)
{
  const auto nanoseconds =
    std::chrono::duration_cast<std::chrono::nanoseconds>(time).count();
  builtin_interfaces::msg::Time stamp;
  stamp.sec = static_cast<std::int32_t>(nanoseconds / 1000000000LL);
  stamp.nanosec = static_cast<std::uint32_t>(nanoseconds % 1000000000LL);
  return stamp;
}

bool joint_state(
  const gz::sim::Joint & joint,
  const gz::sim::EntityComponentManager & ecm,
  double & position, double & velocity)
{
  const auto positions = joint.Position(ecm);
  const auto velocities = joint.Velocity(ecm);
  if (!positions.has_value() || positions->empty() ||
    !velocities.has_value() || velocities->empty())
  {
    return false;
  }
  position = positions->front();
  velocity = velocities->front();
  return std::isfinite(position) && std::isfinite(velocity);
}

void set_pose(
  geometry_msgs::msg::Pose & output, const gz::math::Pose3d & pose)
{
  output.position.x = pose.Pos().X();
  output.position.y = pose.Pos().Y();
  output.position.z = pose.Pos().Z();
  output.orientation.x = pose.Rot().X();
  output.orientation.y = pose.Rot().Y();
  output.orientation.z = pose.Rot().Z();
  output.orientation.w = pose.Rot().W();
}

void set_vector(
  geometry_msgs::msg::Vector3 & output, const gz::math::Vector3d & vector)
{
  output.x = vector.X();
  output.y = vector.Y();
  output.z = vector.Z();
}

template<typename Covariance>
void mark_unavailable_translation(Covariance & covariance)
{
  for (double & value : covariance) {
    value = 0.0;
  }
  covariance[0] = kUnavailableVariance;
  covariance[7] = kUnavailableVariance;
  covariance[14] = kUnavailableVariance;
}

}  // namespace

class CoreHardwareSystem final :
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate,
  public gz::sim::ISystemPostUpdate
{
public:
  ~CoreHardwareSystem() override
  {
    if (executor_) {
      executor_->cancel();
    }
    if (ros_context_ && ros_context_->is_valid()) {
      ros_context_->shutdown("Kanga Gazebo hardware system unloaded");
    }
    if (executor_thread_.joinable()) {
      executor_thread_.join();
    }
  }

  void Configure(
    const gz::sim::Entity & entity,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager & ecm,
    gz::sim::EventManager &) override
  {
    model_ = gz::sim::Model(entity);
    if (!model_.Valid(ecm)) {
      throw std::runtime_error("CoreHardwareSystem must be attached to a model");
    }

    for (std::size_t index = 0; index < kWheelCount; ++index) {
      const auto joint_entity = model_.JointByName(ecm, kWheelJointNames[index]);
      wheel_joints_[index] = gz::sim::Joint(joint_entity);
      if (!wheel_joints_[index].Valid(ecm)) {
        throw std::runtime_error(
                std::string("CoreHardwareSystem cannot find ") +
                kWheelJointNames[index]);
      }
      wheel_joints_[index].EnablePositionCheck(ecm);
      wheel_joints_[index].EnableVelocityCheck(ecm);
    }
    {
      const auto joint_entity = model_.JointByName(ecm, kDiffBarJointName);
      diff_bar_joint_ = gz::sim::Joint(joint_entity);
      if (!diff_bar_joint_.Valid(ecm)) {
        throw std::runtime_error(
                std::string("CoreHardwareSystem cannot find ") +
                kDiffBarJointName);
      }
      diff_bar_joint_.EnablePositionCheck(ecm);
      diff_bar_joint_.EnableVelocityCheck(ecm);
    }

    canonical_link_ = gz::sim::Link(model_.CanonicalLink(ecm));
    if (!canonical_link_.Valid(ecm)) {
      throw std::runtime_error("CoreHardwareSystem cannot find the canonical link");
    }
    canonical_link_.EnableVelocityChecks(ecm);
    spawn_pose_ = gz::sim::worldPose(model_.Entity(), ecm);

    const double timeout_s = sdf_value(sdf, "command_timeout_s", 0.5);
    publish_period_ = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
      std::chrono::duration<double>(1.0 / sdf_value(sdf, "publish_rate_hz", 50.0)));
    drive_state_ = std::make_unique<SimDriveState>(timeout_s);
    velocity_controller_ = std::make_unique<WheelVelocityController>(
      VelocityControllerConfig{
        sdf_value(sdf, "velocity_kp", 45.0),
        sdf_value(sdf, "velocity_ki", 4.0),
        sdf_value(sdf, "velocity_kd", 0.3),
        sdf_value(sdf, "integral_limit", 5.0),
        sdf_value(sdf, "torque_limit_nm", 120.0),
        sdf_value(sdf, "wheel_velocity_limit_rad_s", 2.764601535),
        sdf_value(sdf, "wheel_acceleration_limit_rad_s2", 10.05309649),
      });

    initialize_ros();
    RCLCPP_INFO(
      node_->get_logger(),
      "Gazebo core hardware ready in IDLE (%.1f Hz, %.2f s watchdog)",
      1.0 / std::chrono::duration<double>(publish_period_).count(), timeout_s);
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info,
    gz::sim::EntityComponentManager & ecm) override
  {
    if (info.paused) {
      for (auto & joint : wheel_joints_) {
        joint.SetForce(ecm, {0.0});
      }
      return;
    }
    const auto now_ns =
      std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    const double elapsed_s = std::chrono::duration<double>(info.dt).count();

    WheelVector measured_velocity{};
    bool valid_state = true;
    for (std::size_t index = 0; index < kWheelCount; ++index) {
      double unused_position = 0.0;
      valid_state = joint_state(
        wheel_joints_[index], ecm, unused_position, measured_velocity[index]) &&
        valid_state;
    }

    WheelVector efforts{};
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      if (pending_command_sequence_ != applied_command_sequence_) {
        if (drive_state_->accept_command(pending_command_, now_ns)) {
          applied_command_sequence_ = pending_command_sequence_;
        }
      }
      const bool enabled = elapsed_s > 0.0 && valid_state &&
        drive_state_->actuation_enabled(now_ns);
      efforts = velocity_controller_->update(
        drive_state_->command(), measured_velocity, elapsed_s, enabled);
    }

    for (std::size_t index = 0; index < kWheelCount; ++index) {
      wheel_joints_[index].SetForce(ecm, {efforts[index]});
    }
  }

  void PostUpdate(
    const gz::sim::UpdateInfo & info,
    const gz::sim::EntityComponentManager & ecm) override
  {
    if (info.paused) {
      return;
    }
    if (publish_time_initialized_ && info.simTime < last_publish_time_) {
      publish_time_initialized_ = false;
    }
    if (publish_time_initialized_ &&
      info.simTime - last_publish_time_ < publish_period_)
    {
      return;
    }
    last_publish_time_ = info.simTime;
    publish_time_initialized_ = true;

    const auto stamp = ros_time(info.simTime);
    publish_joint_states(stamp, ecm);
    publish_body_state(stamp, ecm);
  }

private:
  void initialize_ros()
  {
    ros_context_ = std::make_shared<rclcpp::Context>();
    rclcpp::InitOptions init_options;
    ros_context_->init(0, nullptr, init_options);

    rclcpp::NodeOptions node_options;
    node_options.context(ros_context_);
    node_options.parameter_overrides({rclcpp::Parameter("use_sim_time", true)});
    node_ = std::make_shared<rclcpp::Node>("drive_manager", node_options);

    command_subscription_ =
      node_->create_subscription<kanga_interfaces::msg::WheelVelocityCommand>(
      "/wheel_joint_velocity_command", rclcpp::QoS(10),
      [this](const kanga_interfaces::msg::WheelVelocityCommand::SharedPtr message) {
        const WheelVector command = wheel_vector(
          message->front_left_rad_s, message->back_left_rad_s,
          message->back_right_rad_s, message->front_right_rad_s);
        if (!std::all_of(
            command.begin(), command.end(),
            [](const double value) {return std::isfinite(value);}))
        {
          RCLCPP_WARN(node_->get_logger(), "Rejected non-finite wheel command");
          return;
        }
        std::lock_guard<std::mutex> lock(state_mutex_);
        pending_command_ = command;
        ++pending_command_sequence_;
      });

    auto drivestop_qos = rclcpp::QoS(rclcpp::KeepLast(1));
    drivestop_qos.reliable().transient_local();
    drivestop_subscription_ = node_->create_subscription<std_msgs::msg::Bool>(
      "/drivestop", drivestop_qos,
      [this](const std_msgs::msg::Bool::SharedPtr message) {
        std::lock_guard<std::mutex> lock(state_mutex_);
        drive_state_->set_drivestop(message->data);
        if (message->data) {
          velocity_controller_->reset();
        }
      });

    set_closed_loop_service_ = node_->create_service<std_srvs::srv::SetBool>(
      "~/set_closed_loop",
      [this](const std_srvs::srv::SetBool::Request::SharedPtr request,
      std_srvs::srv::SetBool::Response::SharedPtr response) {
        std::lock_guard<std::mutex> lock(state_mutex_);
        response->success = drive_state_->request_closed_loop(
          request->data, response->message);
        if (!request->data || !response->success) {
          velocity_controller_->reset();
        }
      });

    clear_errors_service_ = node_->create_service<std_srvs::srv::Trigger>(
      "~/clear_errors",
      [](const std_srvs::srv::Trigger::Request::SharedPtr,
      std_srvs::srv::Trigger::Response::SharedPtr response) {
        response->success = true;
        response->message = "simulation has no persistent drive errors";
      });
    for (const char * wheel_id : {"fl", "bl", "br", "fr"}) {
      save_services_.push_back(
        node_->create_service<std_srvs::srv::Trigger>(
          std::string("~/save_") + wheel_id,
          [](const std_srvs::srv::Trigger::Request::SharedPtr,
          std_srvs::srv::Trigger::Response::SharedPtr response) {
            response->success = true;
            response->message =
              "configuration persistence not required in simulation";
          }));
      calibration_services_.push_back(
        node_->create_service<std_srvs::srv::Trigger>(
          std::string("~/calibrate_") + wheel_id,
          [](const std_srvs::srv::Trigger::Request::SharedPtr,
          std_srvs::srv::Trigger::Response::SharedPtr response) {
            response->success = true;
            response->message = "calibration not required in simulation";
          }));
    }

    wheel_state_publisher_ =
      node_->create_publisher<sensor_msgs::msg::JointState>(
      "/wheel_joint_states", 10);
    // Suspension joint states are owned by suspension_joint_state_publisher,
    // which maps this encoder angle through the shared kinematics.
    diff_bar_publisher_ = node_->create_publisher<std_msgs::msg::Float64>(
      "/diff_bar_angle", 10);
    body_pose_publisher_ = node_->create_publisher<
      geometry_msgs::msg::PoseWithCovarianceStamped>("/body/pose", 10);
    body_twist_publisher_ = node_->create_publisher<
      geometry_msgs::msg::TwistWithCovarianceStamped>("/body/twist", 10);
    odometry_publisher_ =
      node_->create_publisher<nav_msgs::msg::Odometry>("/odom", 10);

    rclcpp::ExecutorOptions executor_options;
    executor_options.context = ros_context_;
    executor_ = std::make_unique<rclcpp::executors::SingleThreadedExecutor>(
      executor_options);
    executor_->add_node(node_);
    executor_thread_ = std::thread([this]() {executor_->spin();});
  }

  void publish_joint_states(
    const builtin_interfaces::msg::Time & stamp,
    const gz::sim::EntityComponentManager & ecm)
  {
    sensor_msgs::msg::JointState wheel_state;
    wheel_state.header.stamp = stamp;
    for (std::size_t index = 0; index < kWheelCount; ++index) {
      double position = 0.0;
      double velocity = 0.0;
      if (!joint_state(wheel_joints_[index], ecm, position, velocity)) {
        return;
      }
      wheel_state.name.emplace_back(kWheelJointNames[index]);
      wheel_state.position.push_back(position);
      wheel_state.velocity.push_back(velocity);
    }
    wheel_state_publisher_->publish(wheel_state);

    double diff_bar_position = 0.0;
    double diff_bar_velocity = 0.0;
    if (!joint_state(
        diff_bar_joint_, ecm, diff_bar_position, diff_bar_velocity))
    {
      return;
    }
    std_msgs::msg::Float64 diff_bar_angle;
    diff_bar_angle.data = diff_bar_position;
    diff_bar_publisher_->publish(diff_bar_angle);
  }

  void publish_body_state(
    const builtin_interfaces::msg::Time & stamp,
    const gz::sim::EntityComponentManager & ecm)
  {
    const gz::math::Pose3d world_pose = gz::sim::worldPose(model_.Entity(), ecm);
    const gz::math::Pose3d relative_pose = spawn_pose_.Inverse() * world_pose;
    const auto canonical_pose = canonical_link_.WorldPose(ecm);
    const auto angular_world = canonical_link_.WorldAngularVelocity(ecm);
    if (!canonical_pose.has_value() || !angular_world.has_value()) {
      return;
    }

    const gz::math::Vector3d base_offset_in_link =
      canonical_pose->Rot().RotateVectorReverse(
      world_pose.Pos() - canonical_pose->Pos());
    const auto linear_world =
      canonical_link_.WorldLinearVelocity(ecm, base_offset_in_link);
    if (!linear_world.has_value()) {
      return;
    }
    const gz::math::Vector3d linear_body =
      world_pose.Rot().RotateVectorReverse(*linear_world);
    const gz::math::Vector3d angular_body =
      world_pose.Rot().RotateVectorReverse(*angular_world);

    // body/pose mirrors the real-robot BNO086 Game Rotation Vector contract:
    // orientation relative to body_origin, with no reliable translation.
    // Visualization TF is owned by body_pose_tf_broadcaster, not this plugin.
    geometry_msgs::msg::PoseWithCovarianceStamped body_pose;
    body_pose.header.stamp = stamp;
    body_pose.header.frame_id = "body_origin";
    body_pose.pose.pose.orientation.x = relative_pose.Rot().X();
    body_pose.pose.pose.orientation.y = relative_pose.Rot().Y();
    body_pose.pose.pose.orientation.z = relative_pose.Rot().Z();
    body_pose.pose.pose.orientation.w = relative_pose.Rot().W();
    mark_unavailable_translation(body_pose.pose.covariance);
    body_pose_publisher_->publish(body_pose);

    geometry_msgs::msg::TwistWithCovarianceStamped body_twist;
    body_twist.header.stamp = stamp;
    body_twist.header.frame_id = "base_link";
    set_vector(body_twist.twist.twist.angular, angular_body);
    mark_unavailable_translation(body_twist.twist.covariance);
    body_twist_publisher_->publish(body_twist);

    // Privileged Gazebo ground truth for sim diagnostics only. Do not broadcast
    // odom -> base_link; that would diverge from the real-robot TF path.
    nav_msgs::msg::Odometry odometry;
    odometry.header.stamp = stamp;
    odometry.header.frame_id = "odom";
    odometry.child_frame_id = "base_link";
    set_pose(odometry.pose.pose, relative_pose);
    set_vector(odometry.twist.twist.linear, linear_body);
    set_vector(odometry.twist.twist.angular, angular_body);
    odometry_publisher_->publish(odometry);
  }

  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Link canonical_link_{gz::sim::kNullEntity};
  std::array<gz::sim::Joint, kWheelCount> wheel_joints_{
    gz::sim::Joint{gz::sim::kNullEntity},
    gz::sim::Joint{gz::sim::kNullEntity},
    gz::sim::Joint{gz::sim::kNullEntity},
    gz::sim::Joint{gz::sim::kNullEntity},
  };
  gz::sim::Joint diff_bar_joint_{gz::sim::kNullEntity};
  gz::math::Pose3d spawn_pose_{};

  std::mutex state_mutex_;
  std::unique_ptr<SimDriveState> drive_state_;
  std::unique_ptr<WheelVelocityController> velocity_controller_;
  WheelVector pending_command_{};
  std::uint64_t pending_command_sequence_{0};
  std::uint64_t applied_command_sequence_{0};

  std::chrono::steady_clock::duration publish_period_{};
  std::chrono::steady_clock::duration last_publish_time_{};
  bool publish_time_initialized_{false};

  std::shared_ptr<rclcpp::Context> ros_context_;
  rclcpp::Node::SharedPtr node_;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread executor_thread_;
  rclcpp::Subscription<kanga_interfaces::msg::WheelVelocityCommand>::SharedPtr
    command_subscription_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr drivestop_subscription_;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr set_closed_loop_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr clear_errors_service_;
  std::vector<rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr>
    save_services_;
  std::vector<rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr>
    calibration_services_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr wheel_state_publisher_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr diff_bar_publisher_;
  rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr
    body_pose_publisher_;
  rclcpp::Publisher<geometry_msgs::msg::TwistWithCovarianceStamped>::SharedPtr
    body_twist_publisher_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odometry_publisher_;
};

}  // namespace kanga_core_simulation

IGNITION_ADD_PLUGIN(
  kanga_core_simulation::CoreHardwareSystem,
  gz::sim::System,
  kanga_core_simulation::CoreHardwareSystem::ISystemConfigure,
  kanga_core_simulation::CoreHardwareSystem::ISystemPreUpdate,
  kanga_core_simulation::CoreHardwareSystem::ISystemPostUpdate)

IGNITION_ADD_PLUGIN_ALIAS(
  kanga_core_simulation::CoreHardwareSystem,
  "kanga_core_simulation::CoreHardwareSystem")
