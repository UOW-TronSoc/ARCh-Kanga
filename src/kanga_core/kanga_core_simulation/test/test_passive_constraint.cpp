#include "kanga_core_simulation/passive_constraint.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

#include <gtest/gtest.h>

namespace
{

kanga_core_microcontroller::LinearSuspensionKinematics kinematics()
{
  return kanga_core_microcontroller::LinearSuspensionKinematics(
    70.0 * M_PI / 180.0, 30.0 * M_PI / 180.0,
    {545.5, 287.75, 194.7375, 30.0 * M_PI / 180.0});
}

TEST(PassiveConstraint, IsZeroOnTheKinematicManifold)
{
  kanga_core_simulation::PassiveSuspensionConstraint constraint(
    {1200.0, 80.0, 250.0}, kinematics());
  const double beta = 0.3;
  const double beta_velocity = -0.2;
  const auto mapped = kinematics().map_diff_bar_angle(beta);
  const double theta_velocity =
    kinematics().suspension_angle_derivative(beta) * beta_velocity;
  const auto output = constraint.calculate(
    beta, beta_velocity,
    mapped.left_suspension_rad, theta_velocity,
    mapped.right_suspension_rad, theta_velocity);
  EXPECT_NEAR(output.diff_bar_nm, 0.0, 1e-8);
  EXPECT_NEAR(output.left_suspension_nm, 0.0, 1e-8);
  EXPECT_NEAR(output.right_suspension_nm, 0.0, 1e-8);
}

TEST(PassiveConstraint, ReactionTorqueIsBalancedAndUniformlyCapped)
{
  kanga_core_simulation::PassiveSuspensionConstraint constraint(
    {2000.0, 100.0, 12.0}, kinematics());
  const double beta = 0.2;
  const double derivative =
    kinematics().suspension_angle_derivative(beta);
  const auto output = constraint.calculate(beta, 0.0, 0.3, 0.0, -0.2, 0.0);
  EXPECT_LE(std::abs(output.diff_bar_nm), 12.0);
  EXPECT_LE(std::abs(output.left_suspension_nm), 12.0);
  EXPECT_LE(std::abs(output.right_suspension_nm), 12.0);
  EXPECT_NEAR(
    output.diff_bar_nm +
    derivative * (output.left_suspension_nm + output.right_suspension_nm),
    0.0, 1e-9);
}

TEST(PassiveConstraint, RejectsInvalidState)
{
  kanga_core_simulation::PassiveSuspensionConstraint constraint(
    {1200.0, 80.0, 250.0}, kinematics());
  EXPECT_THROW(
    constraint.calculate(
      std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0, 0.0, 0.0, 0.0),
    std::invalid_argument);
}

}  // namespace
