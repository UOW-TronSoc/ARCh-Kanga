#include "kanga_core_microcontroller/suspension_kinematics.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace kanga_core_microcontroller
{
namespace
{

constexpr double kTwoPi = 6.28318530717958647693;

// Small tolerance used when checking the inverse-cosine argument.
constexpr double kAcosTolerance = 1e-12;

}  // namespace

LinearSuspensionKinematics::LinearSuspensionKinematics(
  const double diff_bar_limit_rad,
  const double suspension_limit_rad,
  const SuspensionLinkageGeometry geometry)
: diff_bar_limit_rad_(diff_bar_limit_rad),
  suspension_limit_rad_(suspension_limit_rad),
  geometry_(geometry)
{
  if (!std::isfinite(diff_bar_limit_rad_) || diff_bar_limit_rad_ <= 0.0) {
    throw std::invalid_argument("diff_bar_limit_rad must be finite and > 0");
  }
  if (!std::isfinite(suspension_limit_rad_) || suspension_limit_rad_ <= 0.0) {
    throw std::invalid_argument("suspension_limit_rad must be finite and > 0");
  }
  if (!std::isfinite(geometry_.l1_mm) || geometry_.l1_mm <= 0.0 ||
    !std::isfinite(geometry_.l2_mm) || geometry_.l2_mm <= 0.0 ||
    !std::isfinite(geometry_.l3_mm) || geometry_.l3_mm <= 0.0)
  {
    throw std::invalid_argument("suspension linkage lengths must be finite and > 0");
  }
  if (!std::isfinite(geometry_.theta_at_beta_zero_rad)) {
    throw std::invalid_argument("theta_at_beta_zero_rad must be finite");
  }
}

SuspensionJointPositions LinearSuspensionKinematics::map_diff_bar_angle(
  const double diff_bar_angle_rad) const
{
  if (!std::isfinite(diff_bar_angle_rad)) {
    throw std::invalid_argument("diff_bar_angle_rad must be finite");
  }

  // beta: differential-bar angle, bounded to the configured mechanical limit.
  const double beta = std::clamp(
    diff_bar_angle_rad, -diff_bar_limit_rad_, diff_bar_limit_rad_);
  const bool diff_bar_was_clamped = beta != diff_bar_angle_rad;

  // The 3-D linkage closure equation reduces to
  //   p*cos(theta) + q*sin(theta) + r = 0
  // where q and r are functions of beta.
  const double sin_theta_0 = std::sin(geometry_.theta_at_beta_zero_rad);
  const double cos_theta_0 = std::cos(geometry_.theta_at_beta_zero_rad);
  const double sin_beta = std::sin(beta);
  const double cos_beta = std::cos(beta);

  const double offset = geometry_.l2_mm - geometry_.l1_mm * sin_theta_0;

  const double p = -geometry_.l1_mm * cos_theta_0;
  const double q = offset - geometry_.l3_mm * sin_beta;
  const double r =
    (geometry_.l1_mm * geometry_.l1_mm *
    (1.0 + cos_theta_0 * cos_theta_0) +
    geometry_.l3_mm * geometry_.l3_mm *
    (cos_beta - 1.0) * (cos_beta - 1.0) +
    q * q - geometry_.l2_mm * geometry_.l2_mm) /
    (2.0 * geometry_.l1_mm);

  // Combine p*cos(theta) + q*sin(theta) into
  //   magnitude*cos(theta - phi),
  // with magnitude = sqrt(p^2 + q^2) and phi = atan2(q, p).
  const double magnitude = std::hypot(p, q);
  double phi = std::atan2(q, p);
  if (phi < 0.0) {
    phi += kTwoPi;
  }

  // Solve
  //   cos(theta - phi) = -r / magnitude.
  // The minus branch corresponds to the physical assembly configuration and
  // gives the configured theta reference when beta = 0.
  const double raw_acos_argument = -r / magnitude;
  if (raw_acos_argument < -1.0 - kAcosTolerance ||
    raw_acos_argument > 1.0 + kAcosTolerance)
  {
    throw std::domain_error(
            "suspension linkage has no real solution for the requested diff bar angle");
  }

  const double acos_argument = std::clamp(raw_acos_argument, -1.0, 1.0);
  const double theta = phi - std::acos(acos_argument);

  // The existing API uses zero suspension angle at beta = 0 and the opposite
  // sign convention to the geometric theta angle. Preserve that convention by
  // returning the negative displacement from the configured physical reference.
  const double suspension_angle_unbounded =
    -(theta - geometry_.theta_at_beta_zero_rad);
  const double suspension_angle = std::clamp(
    suspension_angle_unbounded, -suspension_limit_rad_, suspension_limit_rad_);
  const bool suspension_was_clamped = suspension_angle != suspension_angle_unbounded;

  return {
    beta,
    suspension_angle,
    suspension_angle,
    diff_bar_was_clamped || suspension_was_clamped,
  };
}

double LinearSuspensionKinematics::suspension_angle_derivative(
  const double diff_bar_angle_rad) const
{
  if (!std::isfinite(diff_bar_angle_rad)) {
    throw std::invalid_argument("diff_bar_angle_rad must be finite");
  }

  // A small bounded finite difference is deliberately used here instead of
  // duplicating the derivative of the nonlinear closure equation. The mapping
  // remains the single source of truth, including future profile changes.
  constexpr double kDerivativeStepRad = 1e-6;
  const double beta = std::clamp(
    diff_bar_angle_rad, -diff_bar_limit_rad_, diff_bar_limit_rad_);
  const double beta_lower = std::max(-diff_bar_limit_rad_, beta - kDerivativeStepRad);
  const double beta_upper = std::min(diff_bar_limit_rad_, beta + kDerivativeStepRad);
  if (beta_upper <= beta_lower) {
    return 0.0;
  }

  const double suspension_lower =
    map_diff_bar_angle(beta_lower).left_suspension_rad;
  const double suspension_upper =
    map_diff_bar_angle(beta_upper).left_suspension_rad;
  return (suspension_upper - suspension_lower) / (beta_upper - beta_lower);
}

}  // namespace kanga_core_microcontroller
