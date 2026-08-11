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

class LinearSuspensionKinematics
{
public:
  LinearSuspensionKinematics(
    double diff_bar_limit_rad,
    double suspension_limit_rad);

  SuspensionJointPositions map_diff_bar_angle(double diff_bar_angle_rad) const;

private:
  double diff_bar_limit_rad_;
  double suspension_limit_rad_;
};

}  // namespace kanga_core_microcontroller
