#include "kanga_core_simulation/passive_constraint.hpp"

#include <array>
#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

#include <gz/plugin/Register.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/Joint.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Types.hh>
#include <sdf/Element.hh>

namespace kanga_core_simulation
{
namespace
{

constexpr std::array<const char *, 3> kJointNames{
  "diff_bar_joint", "left_suspension_joint", "right_suspension_joint"};

template<typename T>
T sdf_value(const std::shared_ptr<const sdf::Element> & sdf,
  const std::string & name, const T & default_value)
{
  return sdf->Get<T>(name, default_value).first;
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

}  // namespace

class PassiveSuspensionSystem final :
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate
{
public:
  void Configure(
    const gz::sim::Entity & entity,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager & ecm,
    gz::sim::EventManager &) override
  {
    gz::sim::Model model(entity);
    if (!model.Valid(ecm)) {
      throw std::runtime_error("PassiveSuspensionSystem must be attached to a model");
    }
    for (std::size_t index = 0; index < kJointNames.size(); ++index) {
      joints_[index] = gz::sim::Joint(model.JointByName(ecm, kJointNames[index]));
      if (!joints_[index].Valid(ecm)) {
        throw std::runtime_error(
                std::string("PassiveSuspensionSystem cannot find ") +
                kJointNames[index]);
      }
      joints_[index].EnablePositionCheck(ecm);
      joints_[index].EnableVelocityCheck(ecm);
    }

    const double degrees_to_radians = std::acos(-1.0) / 180.0;
    kanga_core_microcontroller::SuspensionLinkageGeometry geometry{
      sdf_value(sdf, "suspension_linkage_l1_mm", 545.5),
      sdf_value(sdf, "suspension_linkage_l2_mm", 287.75),
      sdf_value(sdf, "suspension_linkage_l3_mm", 194.7375),
      sdf_value(sdf, "suspension_theta_at_beta_zero_deg", 30.0) *
      degrees_to_radians,
    };
    auto kinematics =
      kanga_core_microcontroller::LinearSuspensionKinematics(
      sdf_value(sdf, "diff_bar_limit_deg", 70.0) * degrees_to_radians,
      sdf_value(sdf, "suspension_limit_deg", 30.0) * degrees_to_radians,
      geometry);
    constraint_ = std::make_unique<PassiveSuspensionConstraint>(
      PassiveConstraintConfig{
        sdf_value(sdf, "stiffness_nm_rad", 1200.0),
        sdf_value(sdf, "damping_nm_s_rad", 80.0),
        sdf_value(sdf, "maximum_torque_nm", 250.0),
      },
      std::move(kinematics));
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info,
    gz::sim::EntityComponentManager & ecm) override
  {
    if (info.paused || std::chrono::duration<double>(info.dt).count() <= 0.0) {
      for (auto & joint : joints_) {
        joint.SetForce(ecm, {0.0});
      }
      return;
    }

    std::array<double, 3> position{};
    std::array<double, 3> velocity{};
    for (std::size_t index = 0; index < joints_.size(); ++index) {
      if (!joint_state(joints_[index], ecm, position[index], velocity[index])) {
        return;
      }
    }

    try {
      const auto torques = constraint_->calculate(
        position[0], velocity[0], position[1], velocity[1],
        position[2], velocity[2]);
      joints_[0].SetForce(ecm, {torques.diff_bar_nm});
      joints_[1].SetForce(ecm, {torques.left_suspension_nm});
      joints_[2].SetForce(ecm, {torques.right_suspension_nm});
    } catch (const std::exception &) {
      for (auto & joint : joints_) {
        joint.SetForce(ecm, {0.0});
      }
    }
  }

private:
  std::array<gz::sim::Joint, 3> joints_{
    gz::sim::Joint{gz::sim::kNullEntity},
    gz::sim::Joint{gz::sim::kNullEntity},
    gz::sim::Joint{gz::sim::kNullEntity},
  };
  std::unique_ptr<PassiveSuspensionConstraint> constraint_;
};

}  // namespace kanga_core_simulation

IGNITION_ADD_PLUGIN(
  kanga_core_simulation::PassiveSuspensionSystem,
  gz::sim::System,
  kanga_core_simulation::PassiveSuspensionSystem::ISystemConfigure,
  kanga_core_simulation::PassiveSuspensionSystem::ISystemPreUpdate)

IGNITION_ADD_PLUGIN_ALIAS(
  kanga_core_simulation::PassiveSuspensionSystem,
  "kanga_core_simulation::PassiveSuspensionSystem")
