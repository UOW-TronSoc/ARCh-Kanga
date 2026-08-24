#include "tasks_encoder.h"

#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <string.h>

#include "can_bus.h"
#include "i2c_bus.h"
#include "kanga_core_microcontroller/can_ids.hpp"
#include "kanga_core_microcontroller/can_protocol.hpp"
#include "pin_config.h"

using namespace kanga_core_microcontroller;

namespace
{

constexpr uint32_t kEncoderPublishPeriodMs = 20;  // 50 Hz

// Full-scale emulated sweep used until a real encoder driver is added.
constexpr int32_t kEmulatedCountAmplitude = 2000;

// AS5600 register map used by the Instructables I2C sketch:
// https://www.instructables.com/AS5600-Magnetic-Angle-Encoder/
constexpr uint8_t kAs5600StatusReg = 0x0B;
constexpr uint8_t kAs5600RawAngleHighReg = 0x0C;
constexpr uint8_t kAs5600MagnetDetectedMask = 0x20;  // STATUS bit 5 (MD)
constexpr uint16_t kAs5600CountsPerTurn = 4096;

void publishDiffBarEncoder(uint8_t sequence, int32_t count)
{
  DiffBarEncoderFrame payload = {};
  payload.sequence = sequence;
  payload.count = count;

  CanFrame frame = {};
  frame.identifier = CAN_ID_DIFF_BAR_ENCODER;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

// Triangle wave in [-amplitude, +amplitude] with a 4 s period.
int32_t generateEmulatedEncoderCount(float t, int32_t amplitude)
{
  const float phase = fmodf(t, 4.0f);
  const float normalized = (phase < 2.0f) ? (phase / 2.0f) : (2.0f - phase / 2.0f);
  return static_cast<int32_t>((normalized * 2.0f - 1.0f) * static_cast<float>(amplitude));
}

bool as5600Configured()
{
  return i2cBusConfigured() && kAs5600I2cAddress >= 0;
}

bool readAs5600Register(uint8_t reg, uint8_t *buffer, uint8_t length)
{
  I2cBusLock lock;

  Wire.beginTransmission(kAs5600I2cAddress);
  Wire.write(reg);
  if (Wire.endTransmission() != 0)
  {
    return false;
  }

  const uint8_t received = Wire.requestFrom(
    static_cast<uint16_t>(kAs5600I2cAddress), length);
  if (received != length)
  {
    return false;
  }

  for (uint8_t i = 0; i < length; ++i)
  {
    buffer[i] = static_cast<uint8_t>(Wire.read());
  }
  return true;
}

bool readAs5600Status(uint8_t &status)
{
  return readAs5600Register(kAs5600StatusReg, &status, 1);
}

bool readAs5600RawAngle(uint16_t &rawAngle)
{
  uint8_t bytes[2] = {0, 0};

  // High nibble at 0x0C, low byte at 0x0D — same registers as the tutorial,
  // fetched as one two-byte transaction because they are consecutive.
  if (!readAs5600Register(kAs5600RawAngleHighReg, bytes, 2))
  {
    return false;
  }

  rawAngle = static_cast<uint16_t>(((bytes[0] & 0x0F) << 8) | bytes[1]);
  return true;
}

bool magnetDetected(uint8_t status)
{
  return (status & kAs5600MagnetDetectedMask) != 0;
}

int32_t unwrapRawAngle(uint16_t rawAngle, uint16_t &previousRaw, int32_t &turns)
{
  const int32_t delta =
    static_cast<int32_t>(rawAngle) - static_cast<int32_t>(previousRaw);
  if (delta > static_cast<int32_t>(kAs5600CountsPerTurn / 2))
  {
    turns -= 1;
  }
  else if (delta < -static_cast<int32_t>(kAs5600CountsPerTurn / 2))
  {
    turns += 1;
  }

  previousRaw = rawAngle;
  return turns * static_cast<int32_t>(kAs5600CountsPerTurn) +
    static_cast<int32_t>(rawAngle);
}

void runEmulatedEncoderTask(const char *reason)
{
  Serial.println(reason);

  uint8_t sequence = 0;
  const uint32_t startMs = millis();

  for (;;)
  {
    const float t = (millis() - startMs) / 1000.0f;
    publishDiffBarEncoder(
      sequence, generateEmulatedEncoderCount(t, kEmulatedCountAmplitude));
    sequence++;
    vTaskDelay(pdMS_TO_TICKS(kEncoderPublishPeriodMs));
  }
}

void waitForAs5600Magnet()
{
  uint8_t status = 0;
  uint32_t lastLogMs = 0;

  Serial.println("Waiting for AS5600 magnet (STATUS MD bit)...");
  while (true)
  {
    if (readAs5600Status(status) && magnetDetected(status))
    {
      Serial.printf("AS5600 magnet detected, STATUS=0x%02X\n", status);
      return;
    }

    const uint32_t nowMs = millis();
    if ((nowMs - lastLogMs) >= 2000)
    {
      Serial.printf("AS5600 waiting for magnet, STATUS=0x%02X\n", status);
      lastLogMs = nowMs;
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

void runAs5600EncoderTask()
{
  waitForAs5600Magnet();

  uint16_t rawAngle = 0;
  while (!readAs5600RawAngle(rawAngle))
  {
    vTaskDelay(pdMS_TO_TICKS(100));
  }

  Serial.printf("AS5600 initial RAW ANGLE=%u\n", rawAngle);

  uint16_t previousRaw = rawAngle;
  int32_t turns = 0;
  uint8_t sequence = 0;
  uint32_t lastFailLogMs = 0;

  for (;;)
  {
    uint8_t status = 0;
    if (!readAs5600Status(status) || !magnetDetected(status))
    {
      const uint32_t nowMs = millis();
      if ((nowMs - lastFailLogMs) >= 2000)
      {
        Serial.printf("AS5600 magnet lost, STATUS=0x%02X\n", status);
        lastFailLogMs = nowMs;
      }
      vTaskDelay(pdMS_TO_TICKS(kEncoderPublishPeriodMs));
      continue;
    }

    if (!readAs5600RawAngle(rawAngle))
    {
      vTaskDelay(pdMS_TO_TICKS(kEncoderPublishPeriodMs));
      continue;
    }

    const int32_t count = unwrapRawAngle(rawAngle, previousRaw, turns);
    publishDiffBarEncoder(sequence, count);
    sequence++;
    vTaskDelay(pdMS_TO_TICKS(kEncoderPublishPeriodMs));
  }
}

void vEncoderTask(void *pvParameters)
{
  (void)pvParameters;

  if (!as5600Configured())
  {
    runEmulatedEncoderTask(
      "AS5600 I2C not configured; publishing emulated counts");
    return;
  }

  runAs5600EncoderTask();
}

}  // namespace

void startEncoderTask()
{
  xTaskCreatePinnedToCore(
    vEncoderTask,
    "encoder",
    3072,
    nullptr,
    2,
    nullptr,
    1);
}
