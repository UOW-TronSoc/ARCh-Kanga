#include <cmath>
#include <stdexcept>

#include "gtest/gtest.h"
#include "kanga_core_microcontroller/suspension_kinematics.hpp"

namespace
{

constexpr double kPi = 3.14159265358979323846;
constexpr double kDiffBarLimitRad = 70.0 * kPi / 180.0;
constexpr double kSuspensionLimitRad = 30.0 * kPi / 180.0;

TEST(SuspensionKinematics, MapsZeroToZero)
{
  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad);
  const auto positions = kinematics.map_diff_bar_angle(0.0);

  EXPECT_DOUBLE_EQ(positions.diff_bar_rad, 0.0);
  EXPECT_DOUBLE_EQ(positions.left_suspension_rad, 0.0);
  EXPECT_DOUBLE_EQ(positions.right_suspension_rad, 0.0);
  EXPECT_FALSE(positions.input_was_clamped);
}

TEST(SuspensionKinematics, MapsBothSidesEquallyAcrossRange)
{
  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad);

  for (const double diff_bar_angle : {-kDiffBarLimitRad, -0.5, 0.5, kDiffBarLimitRad}) {
    const auto positions = kinematics.map_diff_bar_angle(diff_bar_angle);
    const double expected = diff_bar_angle * 3.0 / 7.0;
    EXPECT_NEAR(positions.left_suspension_rad, expected, 1e-12);
    EXPECT_NEAR(positions.right_suspension_rad, expected, 1e-12);
    EXPECT_FALSE(positions.input_was_clamped);
  }
}

TEST(SuspensionKinematics, ClampsAnglesOutsidePhysicalRange)
{
  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad);

  const auto positive = kinematics.map_diff_bar_angle(2.0);
  EXPECT_NEAR(positive.diff_bar_rad, kDiffBarLimitRad, 1e-12);
  EXPECT_NEAR(positive.left_suspension_rad, kSuspensionLimitRad, 1e-12);
  EXPECT_NEAR(positive.right_suspension_rad, kSuspensionLimitRad, 1e-12);
  EXPECT_TRUE(positive.input_was_clamped);

  const auto negative = kinematics.map_diff_bar_angle(-2.0);
  EXPECT_NEAR(negative.diff_bar_rad, -kDiffBarLimitRad, 1e-12);
  EXPECT_NEAR(negative.left_suspension_rad, -kSuspensionLimitRad, 1e-12);
  EXPECT_NEAR(negative.right_suspension_rad, -kSuspensionLimitRad, 1e-12);
  EXPECT_TRUE(negative.input_was_clamped);
}

TEST(SuspensionKinematics, RejectsInvalidConfigurationAndInput)
{
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      0.0, kSuspensionLimitRad),
    std::invalid_argument);
  EXPECT_THROW(
    kanga_core_microcontroller::LinearSuspensionKinematics(
      kDiffBarLimitRad, -1.0),
    std::invalid_argument);

  const kanga_core_microcontroller::LinearSuspensionKinematics kinematics(
    kDiffBarLimitRad, kSuspensionLimitRad);
  EXPECT_THROW(kinematics.map_diff_bar_angle(NAN), std::invalid_argument);
}

}  // namespace
