#pragma once

#include "kanga_core_microcontroller/suspension_kinematics.hpp"

namespace kanga_core_simulation
{

struct PassiveConstraintConfig
{
  double stiffness_nm_rad{0.0};
  double damping_nm_s_rad{0.0};
  double maximum_torque_nm{0.0};
};

struct PassiveConstraintTorques
{
  double diff_bar_nm{0.0};
  double left_suspension_nm{0.0};
  double right_suspension_nm{0.0};
  double left_error_rad{0.0};
  double right_error_rad{0.0};
};

// Penalty constraint for theta_left/right = f(beta). The differential-bar
// torque is derived with the kinematic Jacobian, so the three torques remain
// balanced under virtual work. Saturation scales all three together.
class PassiveSuspensionConstraint
{
public:
  PassiveSuspensionConstraint(
    PassiveConstraintConfig config,
    kanga_core_microcontroller::LinearSuspensionKinematics kinematics);

  PassiveConstraintTorques calculate(
    double diff_bar_position_rad,
    double diff_bar_velocity_rad_s,
    double left_position_rad,
    double left_velocity_rad_s,
    double right_position_rad,
    double right_velocity_rad_s) const;

private:
  PassiveConstraintConfig config_;
  kanga_core_microcontroller::LinearSuspensionKinematics kinematics_;
};

}  // namespace kanga_core_simulation
