#pragma once

// Shared CAN payload definitions for the rover-base ESP32 and host bridge.
//
// Structs map 1:1 onto CAN data bytes (DLC <= 8). IMU samples are published as
// a triple each cycle (orientation, then gyro, then accel). Gyro and accel
// frames carry a shared sequence byte; orientation omits sequence to fit four
// int16 values in one 8-byte frame.

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace kanga_core_microcontroller
{

constexpr float kQuatScale = 1.0f / 16384.0f;
constexpr float kGyroScale = 0.001f;
constexpr float kAccelScale = 0.001f;

constexpr int16_t kInt16Max = 32767;

inline int16_t floatToInt16(float value, float scale)
{
  const float scaled = value / scale;
  if (scaled > static_cast<float>(kInt16Max)) {
    return kInt16Max;
  }
  if (scaled < static_cast<float>(-kInt16Max)) {
    return -kInt16Max;
  }
  return static_cast<int16_t>(scaled);
}

inline float int16ToFloat(int16_t value, float scale)
{
  return static_cast<float>(value) * scale;
}

#pragma pack(push, 1)

struct GimbalCommandFrame
{
  uint8_t sequence;
  int16_t pan_cdeg;
  int16_t tilt_cdeg;
  uint8_t reserved[2];
};

struct ServoPwmCommandFrame
{
  uint8_t sequence;
  int16_t servo_a_us;
  int16_t servo_b_us;
  uint8_t reserved[2];
};

struct DiffBarEncoderFrame
{
  uint8_t sequence;
  int32_t count;
  uint8_t reserved[2];
};

struct ImuOrientationFrame
{
  int16_t qw;
  int16_t qx;
  int16_t qy;
  int16_t qz;
};

struct ImuAngularVelocityFrame
{
  uint8_t sequence;
  int16_t wx;
  int16_t wy;
  int16_t wz;
};

struct ImuLinearAccelFrame
{
  uint8_t sequence;
  int16_t ax;
  int16_t ay;
  int16_t az;
};

#pragma pack(pop)

template<typename FrameT>
bool decodeFrame(const uint8_t * data, size_t length, FrameT & frame)
{
  if (data == nullptr || length < sizeof(FrameT)) {
    return false;
  }
  std::memcpy(&frame, data, sizeof(FrameT));
  return true;
}

inline double diffBarCountToRadians(
  int32_t count,
  int32_t zero_count,
  double counts_per_radian)
{
  if (counts_per_radian == 0.0) {
    return 0.0;
  }
  return static_cast<double>(count - zero_count) / counts_per_radian;
}

}  // namespace kanga_core_microcontroller
