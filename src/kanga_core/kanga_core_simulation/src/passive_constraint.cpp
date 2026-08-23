#include "kanga_core_simulation/passive_constraint.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace kanga_core_simulation
{
namespace
{

void require_positive(const double value, const char * name)
{
  if (!std::isfinite(value) || value <= 0.0) {
    throw std::invalid_argument(std::string(name) + " must be finite and > 0");
  }
}

}  // namespace

PassiveSuspensionConstraint::PassiveSuspensionConstraint(
  const PassiveConstraintConfig config,
  kanga_core_microcontroller::LinearSuspensionKinematics kinematics)
: config_(config), kinematics_(std::move(kinematics))
{
  require_positive(config_.stiffness_nm_rad, "stiffness_nm_rad");
  require_positive(config_.damping_nm_s_rad, "damping_nm_s_rad");
  require_positive(config_.maximum_torque_nm, "maximum_torque_nm");
}

PassiveConstraintTorques PassiveSuspensionConstraint::calculate(
  const double diff_bar_position_rad,
  const double diff_bar_velocity_rad_s,
  const double left_position_rad,
  const double left_velocity_rad_s,
  const double right_position_rad,
  const double right_velocity_rad_s) const
{
  const std::array<double, 6> inputs{
    diff_bar_position_rad, diff_bar_velocity_rad_s,
    left_position_rad, left_velocity_rad_s,
    right_position_rad, right_velocity_rad_s,
  };
  if (!std::all_of(
      inputs.begin(), inputs.end(),
      [](const double value) {return std::isfinite(value);}))
  {
    throw std::invalid_argument("passive constraint state must be finite");
  }

  const auto target = kinematics_.map_diff_bar_angle(diff_bar_position_rad);
  const double jacobian =
    kinematics_.suspension_angle_derivative(diff_bar_position_rad);
  const double left_error = left_position_rad - target.left_suspension_rad;
  const double right_error = right_position_rad - target.right_suspension_rad;
  const double left_error_rate = left_velocity_rad_s -
    jacobian * diff_bar_velocity_rad_s;
  const double right_error_rate = right_velocity_rad_s -
    jacobian * diff_bar_velocity_rad_s;

  PassiveConstraintTorques output;
  output.left_error_rad = left_error;
  output.right_error_rad = right_error;
  output.left_suspension_nm =
    -config_.stiffness_nm_rad * left_error -
    config_.damping_nm_s_rad * left_error_rate;
  output.right_suspension_nm =
    -config_.stiffness_nm_rad * right_error -
    config_.damping_nm_s_rad * right_error_rate;
  output.diff_bar_nm = jacobian * (
    config_.stiffness_nm_rad * (left_error + right_error) +
    config_.damping_nm_s_rad * (left_error_rate + right_error_rate));

  const double largest_torque = std::max({
      std::abs(output.diff_bar_nm),
      std::abs(output.left_suspension_nm),
      std::abs(output.right_suspension_nm),
    });
  if (largest_torque > config_.maximum_torque_nm) {
    const double scale = config_.maximum_torque_nm / largest_torque;
    output.diff_bar_nm *= scale;
    output.left_suspension_nm *= scale;
    output.right_suspension_nm *= scale;
  }
  return output;
}

}  // namespace kanga_core_simulation
