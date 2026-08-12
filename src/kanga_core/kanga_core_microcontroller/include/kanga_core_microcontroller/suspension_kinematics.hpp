#pragma once

namespace kanga_core_microcontroller
{

struct SuspensionJointPositions
{
  double diff_bar_rad;
  double left_suspension_rad;
  double right_suspension_rad;
  bool input_was_clamped;
};

struct SuspensionLinkageGeometry
{
  double l1_mm;
  double l2_mm;
  double l3_mm;
  double theta_at_beta_zero_rad;
};

class LinearSuspensionKinematics
{
public:
  LinearSuspensionKinematics(
    double diff_bar_limit_rad,
    double suspension_limit_rad,
    SuspensionLinkageGeometry geometry);

  SuspensionJointPositions map_diff_bar_angle(double diff_bar_angle_rad) const;

  // Derivative of either suspension-joint angle with respect to differential-
  // bar angle. The passive simulation uses this Jacobian to apply the equal
  // and opposite generalized reaction at the differential bar.
  double suspension_angle_derivative(double diff_bar_angle_rad) const;

private:
  double diff_bar_limit_rad_;
  double suspension_limit_rad_;
  SuspensionLinkageGeometry geometry_;
};

}  // namespace kanga_core_microcontroller
