#include <array>
#include <cmath>

#include "gtest/gtest.h"
#include "kanga_core_microcontroller/can_protocol.hpp"

namespace
{

TEST(CanProtocol, DecodesDiffBarEncoderFrame)
{
  const std::array<uint8_t, 7> data = {0x09, 0x87, 0x04, 0x00, 0x00, 0x00, 0x00};

  kanga_core_microcontroller::DiffBarEncoderFrame frame{};
  ASSERT_TRUE(kanga_core_microcontroller::decodeFrame(
      data.data(), data.size(), frame));
  EXPECT_EQ(frame.sequence, 9);
  EXPECT_EQ(frame.count, 1159);

  const double angle = kanga_core_microcontroller::diffBarCountToRadians(
    frame.count, 0, 1000.0);
  EXPECT_NEAR(angle, 1.159, 1e-9);
}

TEST(CanProtocol, DecodesImuOrientationFrame)
{
  const std::array<uint8_t, 8> data = {
    0xB0, 0x3F, 0xC6, 0xFF, 0x2D, 0xFD, 0xA4, 0x05};

  kanga_core_microcontroller::ImuOrientationFrame frame{};
  ASSERT_TRUE(kanga_core_microcontroller::decodeFrame(
      data.data(), data.size(), frame));

  EXPECT_EQ(frame.qw, static_cast<int16_t>(0x3FB0));
  EXPECT_NEAR(
    kanga_core_microcontroller::int16ToFloat(
      frame.qw, kanga_core_microcontroller::kQuatScale),
    16304.0 / 16384.0,
    1e-6);
}

TEST(CanProtocol, RejectsShortFrames)
{
  const std::array<uint8_t, 3> data = {0x01, 0x02, 0x03};

  kanga_core_microcontroller::ImuAngularVelocityFrame frame{};
  EXPECT_FALSE(kanga_core_microcontroller::decodeFrame(
      data.data(), data.size(), frame));
}

}  // namespace
