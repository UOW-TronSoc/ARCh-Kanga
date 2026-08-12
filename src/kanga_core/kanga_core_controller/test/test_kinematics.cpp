/*
 * Offline unit tests for kinematics (ROS messages, but no nodes or motors).
 *
 * Run:
 *   colcon test --packages-select kanga_core_controller --event-handlers console_direct+
 *
 * These checks catch math regressions (e.g. wrong wheel order or scaling).
 */

#include "kanga_core_controller/acceleration_limiter.hpp"
#include "kanga_core_controller/control_time_step.hpp"
#include "kanga_core_controller/kinematics.hpp"

#include <cmath>
#include <gtest/gtest.h>

using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::ControlTimeStep;
using kanga_core_controller::desaturate_wheel_velocities;
using kanga_core_controller::limit_body_velocity_change;
using kanga_core_controller::limit_wheel_acceleration;
using kanga_core_controller::twist_to_wheels;
using geometry_msgs::msg::Twist;
using kanga_interfaces::msg::WheelVelocityCommand;

namespace
{

constexpr double kEps = 1e-6;

ChassisGeometry test_geometry()
{
  ChassisGeometry geom;
  geom.grouser_angle_deg = 45.0;
  geom.half_length = 0.5;
  geom.half_width = 0.4;
  geom.effective_wheel_radius_m = 0.1;
  return geom;
}

WheelVelocityCommand wheel_command(double fl, double bl, double br, double fr)
{
  WheelVelocityCommand command;
  command.front_left_rad_s = fl;
  command.back_left_rad_s = bl;
  command.back_right_rad_s = br;
  command.front_right_rad_s = fr;
  return command;
}

}  // namespace

TEST(Kinematics, ForwardOnlySymmetric)
{
  // Drive straight forward: every wheel should get the same positive speed.
  const auto geom = test_geometry();
  Twist tw;
  tw.linear.x = 1.0;
  const auto w = twist_to_wheels(tw, geom);

  EXPECT_NEAR(w.front_left_rad_s, w.front_right_rad_s, kEps);
  EXPECT_NEAR(w.back_left_rad_s, w.back_right_rad_s, kEps);
  EXPECT_NEAR(w.front_left_rad_s, w.back_left_rad_s, kEps);
  EXPECT_GT(w.front_left_rad_s, 0.0);
}

TEST(Kinematics, SpinInPlaceOppositeSides)
{
  // Spin in place (yaw only): left wheels one way, right wheels the other.
  const auto geom = test_geometry();
  Twist tw;
  tw.angular.z = 1.0;
  const auto w = twist_to_wheels(tw, geom);

  EXPECT_LT(w.front_left_rad_s, 0.0);
  EXPECT_LT(w.back_left_rad_s, 0.0);
  EXPECT_GT(w.front_right_rad_s, 0.0);
  EXPECT_GT(w.back_right_rad_s, 0.0);
}

TEST(Kinematics, DesaturatesAllWheelsUniformly)
{
  const auto input = wheel_command(1.0, -2.0, 4.0, -0.5);
  const auto output = desaturate_wheel_velocities(input, 2.0);
  EXPECT_NEAR(output.front_left_rad_s, 0.5, kEps);
  EXPECT_NEAR(output.back_left_rad_s, -1.0, kEps);
  EXPECT_NEAR(output.back_right_rad_s, 2.0, kEps);
  EXPECT_NEAR(output.front_right_rad_s, -0.25, kEps);
}

TEST(Kinematics, DesaturateZeroMaxGivesZeros)
{
  // max_abs <= 0 means "allow nothing" → all zeros.
  const auto input = wheel_command(1.0, 2.0, 3.0, 4.0);
  const auto output = desaturate_wheel_velocities(input, 0.0);
  EXPECT_NEAR(output.front_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.front_right_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_right_rad_s, 0.0, kEps);
}

TEST(Kinematics, ConvertsPhysicalForwardVelocity)
{
  // A physical 1 m/s command must be converted to joint rad/s by radius.
  const auto geom = test_geometry();
  constexpr double deg2rad = M_PI / 180.0;
  const double theta = geom.grouser_angle_deg * deg2rad;
  const double s = std::sin(theta);
  const double c = std::cos(theta);
  const double alpha = 1.0 / c;
  const double expected = alpha * (s * 1.0) / geom.effective_wheel_radius_m;

  Twist tw;
  tw.linear.x = 1.0;
  const auto w = twist_to_wheels(tw, geom);
  EXPECT_NEAR(w.front_left_rad_s, expected, kEps);
  EXPECT_NEAR(w.front_right_rad_s, expected, kEps);
  EXPECT_NEAR(w.back_left_rad_s, expected, kEps);
  EXPECT_NEAR(w.back_right_rad_s, expected, kEps);
}

TEST(Kinematics, LateralPhysicalVelocityUsesWheelRadius)
{
  const auto geom = test_geometry();
  Twist tw;
  tw.linear.y = 1.0;
  const auto w = twist_to_wheels(tw, geom);
  const double expected = 1.0 / geom.effective_wheel_radius_m;

  EXPECT_NEAR(w.front_left_rad_s, expected, kEps);
  EXPECT_NEAR(w.back_left_rad_s, -expected, kEps);
  EXPECT_NEAR(w.back_right_rad_s, expected, kEps);
  EXPECT_NEAR(w.front_right_rad_s, -expected, kEps);
}

TEST(Kinematics, YawUsesWheelCentreGeometryAndRadius)
{
  const auto geom = test_geometry();
  Twist tw;
  tw.angular.z = 1.0;
  const auto w = twist_to_wheels(tw, geom);
  constexpr double deg2rad = M_PI / 180.0;
  const double expected =
    (geom.half_length + geom.half_width) /
    (std::cos(geom.grouser_angle_deg * deg2rad) *
    geom.effective_wheel_radius_m);

  EXPECT_NEAR(w.front_left_rad_s, -expected, kEps);
  EXPECT_NEAR(w.back_left_rad_s, -expected, kEps);
  EXPECT_NEAR(w.back_right_rad_s, expected, kEps);
  EXPECT_NEAR(w.front_right_rad_s, expected, kEps);
}

TEST(Kinematics, InvalidWheelRadiusReturnsStop)
{
  auto geom = test_geometry();
  geom.effective_wheel_radius_m = 0.0;
  Twist tw;
  tw.linear.x = 1.0;
  const auto w = twist_to_wheels(tw, geom);

  EXPECT_NEAR(w.front_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(w.back_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(w.back_right_rad_s, 0.0, kEps);
  EXPECT_NEAR(w.front_right_rad_s, 0.0, kEps);
}

TEST(Kinematics, DesaturateRejectsNonFiniteInput)
{
  const auto input = wheel_command(1.0, NAN, 2.0, 3.0);
  const auto output = desaturate_wheel_velocities(input, 2.0);
  EXPECT_NEAR(output.front_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_right_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.front_right_rad_s, 0.0, kEps);
}

TEST(AccelerationLimiter, MovesBodyComponentsByOneSharedFraction)
{
  Twist current;
  Twist target;
  target.linear.x = 1.0;
  target.linear.y = -1.0;
  target.angular.z = 2.0;

  const auto output = limit_body_velocity_change(current, target, 0.5, 0.75, 0.1);
  const double progress = 0.1 / (std::sqrt(2.0) / 0.5);
  EXPECT_NEAR(output.linear.x, progress, kEps);
  EXPECT_NEAR(output.linear.y, -progress, kEps);
  EXPECT_NEAR(output.angular.z, 2.0 * progress, kEps);
}

TEST(AccelerationLimiter, CompleteStopBypassesBodyLimit)
{
  Twist current;
  current.linear.x = 1.0;
  current.angular.z = -1.0;
  Twist target;

  const auto output = limit_body_velocity_change(current, target, 0.5, 0.75, 0.1);
  EXPECT_NEAR(output.linear.x, 0.0, kEps);
  EXPECT_NEAR(output.angular.z, 0.0, kEps);
}

TEST(AccelerationLimiter, ReversalStopsBeforeAcceleratingOppositeDirection)
{
  Twist current;
  current.linear.x = 0.5;
  Twist target;
  target.linear.x = -0.5;

  const auto stopped = limit_body_velocity_change(current, target, 0.5, 0.75, 0.1);
  EXPECT_NEAR(stopped.linear.x, 0.0, kEps);

  const auto reversing = limit_body_velocity_change(stopped, target, 0.5, 0.75, 0.1);
  EXPECT_NEAR(reversing.linear.x, -0.05, kEps);
}

TEST(AccelerationLimiter, CombinedForwardAndYawKeepRequestedRatio)
{
  Twist current;
  Twist target;
  target.linear.x = 0.4;
  target.angular.z = 0.3;

  const auto output = limit_body_velocity_change(current, target, 0.5, 0.75, 0.1);
  EXPECT_NEAR(output.linear.x, 0.05, kEps);
  EXPECT_NEAR(output.angular.z, 0.0375, kEps);
  EXPECT_NEAR(output.angular.z / output.linear.x, 0.75, kEps);
}

TEST(AccelerationLimiter, WheelTransitionIsUniform)
{
  const auto current = wheel_command(2.0, 2.0, 0.0, 0.0);
  const auto target = wheel_command(2.0, 2.0, 2.0, 2.0);

  const auto output = limit_wheel_acceleration(current, target, 10.0, 0.1);
  EXPECT_NEAR(output.front_left_rad_s, 2.0, kEps);
  EXPECT_NEAR(output.back_left_rad_s, 2.0, kEps);
  EXPECT_NEAR(output.back_right_rad_s, 1.0, kEps);
  EXPECT_NEAR(output.front_right_rad_s, 1.0, kEps);
}

TEST(AccelerationLimiter, CompleteStopBypassesWheelLimit)
{
  const auto current = wheel_command(2.0, 1.0, -1.0, -2.0);
  const auto target = wheel_command(0.0, 0.0, 0.0, 0.0);

  const auto output = limit_wheel_acceleration(current, target, 10.0, 0.1);
  EXPECT_NEAR(output.front_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_left_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.back_right_rad_s, 0.0, kEps);
  EXPECT_NEAR(output.front_right_rad_s, 0.0, kEps);
}

TEST(ControlTimeStep, UsesOnlyPositiveBoundedNodeClockIntervals)
{
  ControlTimeStep timing(0.25);

  EXPECT_FALSE(timing.update(1'000'000'000).has_value());
  const auto ordinary = timing.update(1'020'000'000);
  ASSERT_TRUE(ordinary.has_value());
  EXPECT_NEAR(ordinary.value(), 0.02, 1e-12);

  // A paused clock produces no controller step.
  EXPECT_FALSE(timing.update(1'020'000'000).has_value());
  // The reset baseline is the repeated timestamp, so normal time can resume.
  const auto after_pause = timing.update(1'040'000'000);
  ASSERT_TRUE(after_pause.has_value());
  EXPECT_NEAR(after_pause.value(), 0.02, 1e-12);
}

TEST(ControlTimeStep, RejectsBackwardsAndOversizedJumps)
{
  ControlTimeStep timing(0.25);
  EXPECT_FALSE(timing.update(2'000'000'000).has_value());
  EXPECT_FALSE(timing.update(1'000'000'000).has_value());
  EXPECT_FALSE(timing.update(2'000'000'000).has_value());

  const auto recovered = timing.update(2'020'000'000);
  ASSERT_TRUE(recovered.has_value());
  EXPECT_NEAR(recovered.value(), 0.02, 1e-12);
}
