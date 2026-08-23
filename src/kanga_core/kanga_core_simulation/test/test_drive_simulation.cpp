#include "kanga_core_simulation/drive_simulation.hpp"

#include <cmath>
#include <limits>
#include <string>

#include <gtest/gtest.h>

namespace
{

using kanga_core_simulation::SimDriveMode;
using kanga_core_simulation::SimDriveState;
using kanga_core_simulation::VelocityControllerConfig;
using kanga_core_simulation::WheelVector;
using kanga_core_simulation::WheelVelocityController;

TEST(WheelCommandContract, PreservesCanonicalFieldOrder)
{
  EXPECT_EQ(
    kanga_core_simulation::wheel_vector(1.0, 2.0, 3.0, 4.0),
    WheelVector({1.0, 2.0, 3.0, 4.0}));
}

TEST(SimDriveState, StartsIdleAndRequiresFreshCommand)
{
  SimDriveState state(0.5);
  std::string message;
  EXPECT_EQ(state.mode(), SimDriveMode::kIdle);
  EXPECT_TRUE(state.request_closed_loop(true, message));
  EXPECT_FALSE(state.actuation_enabled(1000000000LL));

  EXPECT_TRUE(state.accept_command({1.0, 2.0, 3.0, 4.0}, 1000000000LL));
  EXPECT_TRUE(state.actuation_enabled(1500000000LL));
  EXPECT_FALSE(state.actuation_enabled(1500000001LL));
  EXPECT_EQ(state.mode(), SimDriveMode::kIdle);
  EXPECT_EQ(state.command(), WheelVector({0.0, 0.0, 0.0, 0.0}));
}

TEST(SimDriveState, DrivestopLatchesIdleUntilExplicitEnable)
{
  SimDriveState state(0.5);
  std::string message;
  ASSERT_TRUE(state.request_closed_loop(true, message));
  ASSERT_TRUE(state.accept_command({1.0, 1.0, 1.0, 1.0}, 0));

  state.set_drivestop(true);
  EXPECT_FALSE(state.actuation_enabled(1));
  EXPECT_FALSE(state.request_closed_loop(true, message));
  EXPECT_EQ(message, "drivestop is active");
  state.set_drivestop(false);
  EXPECT_EQ(state.mode(), SimDriveMode::kIdle);
  EXPECT_FALSE(state.actuation_enabled(2));

  EXPECT_TRUE(state.request_closed_loop(true, message));
  EXPECT_TRUE(state.accept_command({2.0, 2.0, 2.0, 2.0}, 3));
  EXPECT_TRUE(state.actuation_enabled(3));
  EXPECT_TRUE(state.request_closed_loop(false, message));
  EXPECT_FALSE(state.actuation_enabled(4));
}

TEST(SimDriveState, RejectsNonFiniteAndDisarmsOnBackwardTime)
{
  SimDriveState state(0.5);
  std::string message;
  ASSERT_TRUE(state.request_closed_loop(true, message));
  EXPECT_FALSE(state.accept_command(
      {1.0, std::numeric_limits<double>::quiet_NaN(), 3.0, 4.0}, 100));
  ASSERT_TRUE(state.accept_command({1.0, 2.0, 3.0, 4.0}, 100));
  EXPECT_TRUE(state.actuation_enabled(200));
  EXPECT_FALSE(state.actuation_enabled(99));
  EXPECT_EQ(state.mode(), SimDriveMode::kIdle);
}

TEST(WheelVelocityController, ClampsVelocityAccelerationAndTorque)
{
  WheelVelocityController controller(VelocityControllerConfig{
      100.0, 0.0, 0.0, 1.0, 5.0, 2.0, 4.0});
  const auto effort = controller.update(
    {10.0, -10.0, 1.0, -1.0}, {0.0, 0.0, 0.0, 0.0}, 0.25, true);
  EXPECT_EQ(controller.limited_targets(), WheelVector({1.0, -1.0, 1.0, -1.0}));
  EXPECT_EQ(effort, WheelVector({5.0, -5.0, 5.0, -5.0}));

  controller.update(
    {10.0, -10.0, 1.0, -1.0}, {0.0, 0.0, 0.0, 0.0}, 0.25, true);
  EXPECT_EQ(controller.limited_targets(), WheelVector({2.0, -2.0, 1.0, -1.0}));
  EXPECT_EQ(
    controller.update({}, {}, 0.1, false),
    WheelVector({0.0, 0.0, 0.0, 0.0}));
  EXPECT_EQ(controller.limited_targets(), WheelVector({0.0, 0.0, 0.0, 0.0}));
}

}  // namespace
