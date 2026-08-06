#include "kanga_core_drive/transmission.hpp"

#include <cmath>
#include <gtest/gtest.h>

namespace
{

constexpr double kRatio = 50.0;
constexpr double kMotorLimitTps = 22.0;
constexpr double kEps = 1e-9;

}  // namespace

TEST(Transmission, ConvertsJointVelocityToMotorVelocity)
{
  EXPECT_NEAR(
    kanga_core_drive::motor_velocity_from_joint(0.314, kRatio),
    15.7, kEps);
}

TEST(Transmission, ConvertsMotorFeedbackToJointUnits)
{
  EXPECT_NEAR(
    kanga_core_drive::joint_velocity_from_motor(15.7, kRatio),
    0.314, kEps);
  EXPECT_NEAR(
    kanga_core_drive::joint_position_from_motor(100.0, kRatio),
    2.0, kEps);
}

TEST(Transmission, DerivesJointLimitFromMotorTps)
{
  const double expected = kMotorLimitTps * 2.0 * M_PI / kRatio;
  EXPECT_NEAR(
    kanga_core_drive::max_joint_velocity(kMotorLimitTps, kRatio),
    expected, kEps);
}

TEST(Transmission, DerivesMotorLimitInRadiansPerSecond)
{
  EXPECT_NEAR(
    kanga_core_drive::max_motor_velocity_rad_s(kMotorLimitTps),
    kMotorLimitTps * 2.0 * M_PI, kEps);
}

TEST(Transmission, ClampsEachMotorIndependently)
{
  EXPECT_NEAR(kanga_core_drive::clamp_motor_velocity(1.0, 2.0), 1.0, kEps);
  EXPECT_NEAR(kanga_core_drive::clamp_motor_velocity(4.0, 2.0), 2.0, kEps);
  EXPECT_NEAR(kanga_core_drive::clamp_motor_velocity(-4.0, 2.0), -2.0, kEps);
}

TEST(Transmission, InvalidMotorLimitReturnsStop)
{
  EXPECT_DOUBLE_EQ(kanga_core_drive::clamp_motor_velocity(NAN, 2.0), 0.0);
  EXPECT_DOUBLE_EQ(kanga_core_drive::clamp_motor_velocity(1.0, 0.0), 0.0);
}
