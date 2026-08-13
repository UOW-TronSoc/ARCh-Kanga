#include "tasks_imu.h"

#include <Arduino.h>
#include <math.h>
#include <string.h>

#include "can_bus.h"
#include "kanga_core_microcontroller/can_ids.hpp"
#include "kanga_core_microcontroller/can_protocol.hpp"
#include "pin_config.h"

using namespace kanga_core_microcontroller;

namespace
{

constexpr uint32_t kImuPublishPeriodMs = 20;  // 50 Hz

void publishImuOrientation(float qw, float qx, float qy, float qz)
{
  ImuOrientationFrame payload = {};
  payload.qw = floatToInt16(qw, kQuatScale);
  payload.qx = floatToInt16(qx, kQuatScale);
  payload.qy = floatToInt16(qy, kQuatScale);
  payload.qz = floatToInt16(qz, kQuatScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_ORIENTATION;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

void publishImuAngularVelocity(uint8_t sequence, float wx, float wy, float wz)
{
  ImuAngularVelocityFrame payload = {};
  payload.sequence = sequence;
  payload.wx = floatToInt16(wx, kGyroScale);
  payload.wy = floatToInt16(wy, kGyroScale);
  payload.wz = floatToInt16(wz, kGyroScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_ANGULAR_VEL;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

void publishImuLinearAccel(uint8_t sequence, float ax, float ay, float az)
{
  ImuLinearAccelFrame payload = {};
  payload.sequence = sequence;
  payload.ax = floatToInt16(ax, kAccelScale);
  payload.ay = floatToInt16(ay, kAccelScale);
  payload.az = floatToInt16(az, kAccelScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_LINEAR_ACCEL;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

// Generates deterministic sine-based motion for bench testing without hardware.
void generateEmulatedImuSample(
  float t,
  float &qw, float &qx, float &qy, float &qz,
  float &wx, float &wy, float &wz,
  float &ax, float &ay, float &az)
{
  const float yaw = 0.35f * sinf(t * 0.25f);
  const float pitch = 0.10f * sinf(t * 0.50f);
  const float roll = 0.05f * sinf(t * 0.33f);

  const float cy = cosf(yaw * 0.5f);
  const float sy = sinf(yaw * 0.5f);
  const float cp = cosf(pitch * 0.5f);
  const float sp = sinf(pitch * 0.5f);
  const float cr = cosf(roll * 0.5f);
  const float sr = sinf(roll * 0.5f);

  qw = cr * cp * cy + sr * sp * sy;
  qx = sr * cp * cy - cr * sp * sy;
  qy = cr * sp * cy + sr * cp * sy;
  qz = cr * cp * sy - sr * sp * cy;

  wx = 0.20f * cosf(t * 0.40f);
  wy = 0.15f * sinf(t * 0.55f);
  wz = 0.10f * cosf(t * 0.30f);

  ax = 0.30f * sinf(t * 0.80f);
  ay = 0.20f * cosf(t * 0.60f);
  az = 9.81f + 0.10f * sinf(t * 0.45f);
}

void vImuTask(void *pvParameters)
{
  (void)pvParameters;

  if (kBno086SpiCsPin < 0)
  {
    Serial.println("BNO086 SPI not configured; publishing emulated IMU samples");
  }
  else
  {
    Serial.println("BNO086 SPI task placeholder (driver not implemented yet)");
  }

  uint8_t sequence = 0;
  const uint32_t startMs = millis();

  for (;;)
  {
    const float t = (millis() - startMs) / 1000.0f;

    float qw = 0.0f;
    float qx = 0.0f;
    float qy = 0.0f;
    float qz = 0.0f;
    float wx = 0.0f;
    float wy = 0.0f;
    float wz = 0.0f;
    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    // TODO: replace with BNO086 Game Rotation Vector + gyro + accel reads.
    generateEmulatedImuSample(t, qw, qx, qy, qz, wx, wy, wz, ax, ay, az);

    publishImuOrientation(qw, qx, qy, qz);
    publishImuAngularVelocity(sequence, wx, wy, wz);
    publishImuLinearAccel(sequence, ax, ay, az);

    sequence++;
    vTaskDelay(pdMS_TO_TICKS(kImuPublishPeriodMs));
  }
}

}  // namespace

void startImuTask()
{
  xTaskCreatePinnedToCore(
    vImuTask,
    "imu",
    4096,
    nullptr,
    2,
    nullptr,
    1);
}
