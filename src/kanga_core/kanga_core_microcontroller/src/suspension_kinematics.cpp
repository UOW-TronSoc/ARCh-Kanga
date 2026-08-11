#include "kanga_core_microcontroller/suspension_kinematics.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace kanga_core_microcontroller
{

LinearSuspensionKinematics::LinearSuspensionKinematics(
  const double diff_bar_limit_rad,
  const double suspension_limit_rad)
: diff_bar_limit_rad_(diff_bar_limit_rad),
  suspension_limit_rad_(suspension_limit_rad)
{
  if (!std::isfinite(diff_bar_limit_rad_) || diff_bar_limit_rad_ <= 0.0) {
    throw std::invalid_argument("diff_bar_limit_rad must be finite and > 0");
  }
  if (!std::isfinite(suspension_limit_rad_) || suspension_limit_rad_ <= 0.0) {
    throw std::invalid_argument("suspension_limit_rad must be finite and > 0");
  }
}

SuspensionJointPositions LinearSuspensionKinematics::map_diff_bar_angle(
  const double diff_bar_angle_rad) const
{
  if (!std::isfinite(diff_bar_angle_rad)) {
    throw std::invalid_argument("diff_bar_angle_rad must be finite");
  }

  const double bounded_diff_bar_angle = std::clamp(
    diff_bar_angle_rad, -diff_bar_limit_rad_, diff_bar_limit_rad_);
  const double suspension_angle =
    -1.0 * bounded_diff_bar_angle * suspension_limit_rad_ / diff_bar_limit_rad_;

  return {
    bounded_diff_bar_angle,
    suspension_angle,
    suspension_angle,
    bounded_diff_bar_angle != diff_bar_angle_rad,
  };
}

}  // namespace kanga_core_microcontroller
