/*
 * Offline unit tests for kinematics (ROS messages, but no nodes or motors).
 *
 * Run:
 *   colcon test --packages-select kanga_core_controller --event-handlers console_direct+
 *
 * These checks catch math regressions (e.g. wrong wheel order or scaling).
 */

#include "kanga_core_controller/kinematics.hpp"

#include <cmath>
#include <gtest/gtest.h>

using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::desaturate_wheel_velocities;
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
