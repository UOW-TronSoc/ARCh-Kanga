#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "gtest/gtest.h"
#include "kanga_core_microcontroller/suspension_kinematics.hpp"

namespace
{

constexpr double kPi = 3.14159265358979323846;
constexpr double kDiffBarLimitRad = 70.0 * kPi / 180.0;
constexpr double kSuspensionLimitRad = 30.0 * kPi / 180.0;
constexpr double kThetaReferenceDeg = 30.0;
constexpr kanga_core_microcontroller::SuspensionLinkageGeometry k2025Geometry{
  545.5,
  287.75,
  194.7375,
  kThetaReferenceDeg * kPi / 180.0,
};

double degrees_to_radians(const double degrees)
{
  return degrees * kPi / 180.0;
}

double one_percent_tolerance(const double expected_rad)
{
  // The zero case has no meaningful relative tolerance. Use 0.01 degrees,
  // which is stricter than the three-decimal-degree source data.
  return std::max(std::abs(expected_rad) * 0.01, degrees_to_radians(0.01));
}

TEST(SuspensionKinematics, MatchesCalculatedLinkageCasesWithinOnePercent)
{
  struct LinkageCase
  {
    double beta_deg;
    double physical_theta_deg;
    double returned_suspension_deg;
  };

  constexpr LinkageCase cases[] = {
    {0.0, 30.000, 0.000},
    {10.0, 34.097, -4.097},
    {20.0, 38.012, -8.012},
    {30.0, 41.531, -11.531},
    {40.0, 44.438, -14.438},
    {50.0, 46.537, -16.537},
    {60.0, 47.662, -17.662},
  };

  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad, k2025Geometry);

  for (const auto & test_case : cases) {
    SCOPED_TRACE(test_case.beta_deg);
    const double beta_rad = degrees_to_radians(test_case.beta_deg);
    const double expected_suspension_rad =
      degrees_to_radians(test_case.returned_suspension_deg);
    const auto positions = kinematics.map_diff_bar_angle(beta_rad);

    EXPECT_NEAR(positions.diff_bar_rad, beta_rad, 1e-12);
    EXPECT_NEAR(
      positions.left_suspension_rad,
      expected_suspension_rad,
      one_percent_tolerance(expected_suspension_rad));
    EXPECT_NEAR(
      positions.right_suspension_rad,
      expected_suspension_rad,
      one_percent_tolerance(expected_suspension_rad));

    const double physical_theta_rad =
      degrees_to_radians(kThetaReferenceDeg) - positions.left_suspension_rad;
    const double expected_physical_theta_rad =
      degrees_to_radians(test_case.physical_theta_deg);
    EXPECT_NEAR(
      physical_theta_rad,
      expected_physical_theta_rad,
      one_percent_tolerance(expected_physical_theta_rad));
    EXPECT_FALSE(positions.input_was_clamped);
  }
}

TEST(SuspensionKinematics, MapsBothSuspensionJointsEqually)
{
  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad, k2025Geometry);

  for (const double beta_deg : {-70.0, -35.0, 0.0, 35.0, 70.0}) {
    const auto positions =
      kinematics.map_diff_bar_angle(degrees_to_radians(beta_deg));
    EXPECT_DOUBLE_EQ(
      positions.left_suspension_rad, positions.right_suspension_rad);
  }
}

TEST(SuspensionKinematics, ClampsInputToMechanicalRange)
{
  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad, k2025Geometry);

  const auto positive_limit = kinematics.map_diff_bar_angle(kDiffBarLimitRad);
  const auto positive_outside = kinematics.map_diff_bar_angle(2.0);
  EXPECT_NEAR(positive_outside.diff_bar_rad, kDiffBarLimitRad, 1e-12);
  EXPECT_NEAR(
    positive_outside.left_suspension_rad,
    positive_limit.left_suspension_rad,
    1e-12);
  EXPECT_TRUE(positive_outside.input_was_clamped);

  const auto negative_limit = kinematics.map_diff_bar_angle(-kDiffBarLimitRad);
  const auto negative_outside = kinematics.map_diff_bar_angle(-2.0);
  EXPECT_NEAR(negative_outside.diff_bar_rad, -kDiffBarLimitRad, 1e-12);
  EXPECT_NEAR(
    negative_outside.left_suspension_rad,
    negative_limit.left_suspension_rad,
    1e-12);
  EXPECT_TRUE(negative_outside.input_was_clamped);
}

TEST(SuspensionKinematics, AcceptsGeometryFromAnotherDrivetrainProfile)
{
  constexpr kanga_core_microcontroller::SuspensionLinkageGeometry future_geometry{
    550.0,
    290.0,
    200.0,
    35.0 * kPi / 180.0,
  };
  const kanga_core_microcontroller::LinearSuspensionKinematics current(
    kDiffBarLimitRad, kSuspensionLimitRad, k2025Geometry);
  const kanga_core_microcontroller::LinearSuspensionKinematics future(
    kDiffBarLimitRad, kSuspensionLimitRad, future_geometry);

  EXPECT_NEAR(future.map_diff_bar_angle(0.0).left_suspension_rad, 0.0, 1e-12);
  EXPECT_NE(
    future.map_diff_bar_angle(degrees_to_radians(40.0)).left_suspension_rad,
    current.map_diff_bar_angle(degrees_to_radians(40.0)).left_suspension_rad);
}

TEST(SuspensionKinematics, RejectsInvalidConfigurationAndInput)
{
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      0.0, kSuspensionLimitRad, k2025Geometry),
    std::invalid_argument);
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      kDiffBarLimitRad, -1.0, k2025Geometry),
    std::invalid_argument);

  auto invalid_length = k2025Geometry;
  invalid_length.l1_mm = -1.0;
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      kDiffBarLimitRad, kSuspensionLimitRad, invalid_length),
    std::invalid_argument);

  auto invalid_reference = k2025Geometry;
  invalid_reference.theta_at_beta_zero_rad = NAN;
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      kDiffBarLimitRad, kSuspensionLimitRad, invalid_reference),
    std::invalid_argument);

  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad, k2025Geometry);
  EXPECT_THROW(kinematics.map_diff_bar_angle(NAN), std::invalid_argument);
}

}  // namespace
