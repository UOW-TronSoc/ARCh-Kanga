/*
 * Offline unit tests for kinematics (no ROS, no motors).
 *
 * Run:
 *   colcon test --packages-select kanga_core_controller --event-handlers console_direct+
 *
 * These checks catch math regressions (e.g. wrong wheel order or clamp).
 */

#include "kanga_core_controller/kinematics.hpp"

#include <cmath>
#include <gtest/gtest.h>

using kanga_core_controller::ChassisGeometry;
using kanga_core_controller::Twist2D;
using kanga_core_controller::clamp_wheels;
using kanga_core_controller::twist_to_wheels;

namespace
{

constexpr double kEps = 1e-6;

}  // namespace

TEST(Kinematics, ForwardOnlySymmetric)
{
    // Drive straight forward: every wheel should get the same positive speed.
    ChassisGeometry geom;
    Twist2D tw;
    tw.vx = 1.0;
    const auto w = twist_to_wheels(tw, geom);

    EXPECT_NEAR(w.fl, w.fr, kEps);
    EXPECT_NEAR(w.bl, w.br, kEps);
    EXPECT_NEAR(w.fl, w.bl, kEps);
    EXPECT_GT(w.fl, 0.0);
}

TEST(Kinematics, SpinInPlaceOppositeSides)
{
    // Spin in place (yaw only): left wheels one way, right wheels the other.
    ChassisGeometry geom;
    Twist2D tw;
    tw.omega = 1.0;
    const auto w = twist_to_wheels(tw, geom);

    EXPECT_LT(w.fl, 0.0);
    EXPECT_LT(w.bl, 0.0);
    EXPECT_GT(w.fr, 0.0);
    EXPECT_GT(w.br, 0.0);
}

TEST(Kinematics, ClampSymmetric)
{
    // Huge forward command must be cut down to ±max.
    ChassisGeometry geom;
    Twist2D tw;
    tw.vx = 100.0;
    const auto raw = twist_to_wheels(tw, geom);
    const auto clamped = clamp_wheels(raw, 5.0);
    EXPECT_NEAR(clamped.fl, 5.0, kEps);
    EXPECT_NEAR(clamped.fr, 5.0, kEps);
    EXPECT_NEAR(clamped.bl, 5.0, kEps);
    EXPECT_NEAR(clamped.br, 5.0, kEps);
}

TEST(Kinematics, ClampZeroMaxGivesZeros)
{
    // max_abs <= 0 means "allow nothing" → all zeros.
    ChassisGeometry geom;
    Twist2D tw;
    tw.vx = 1.0;
    const auto clamped = clamp_wheels(twist_to_wheels(tw, geom), 0.0);
    EXPECT_NEAR(clamped.fl, 0.0, kEps);
    EXPECT_NEAR(clamped.fr, 0.0, kEps);
    EXPECT_NEAR(clamped.bl, 0.0, kEps);
    EXPECT_NEAR(clamped.br, 0.0, kEps);
}

TEST(Kinematics, MatchesDefaultGeometryForward)
{
    // Sanity: library result matches the formula for default geometry.
    ChassisGeometry geom;
    constexpr double deg2rad = M_PI / 180.0;
    const double theta = geom.theta_deg * deg2rad;
    const double s = std::sin(theta);
    const double c = std::cos(theta);
    const double alpha = 1.0 / c;
    const double expected = alpha * (s * 1.0);

    Twist2D tw;
    tw.vx = 1.0;
    const auto w = twist_to_wheels(tw, geom);
    EXPECT_NEAR(w.fl, expected, kEps);
    EXPECT_NEAR(w.fr, expected, kEps);
    EXPECT_NEAR(w.bl, expected, kEps);
    EXPECT_NEAR(w.br, expected, kEps);
}
