#include "tasks_encoder.h"

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

constexpr uint32_t kEncoderPublishPeriodMs = 20;  // 50 Hz

// Full-scale emulated sweep used until a real encoder driver is added.
constexpr int32_t kEmulatedCountAmplitude = 2000;

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

void vEncoderTask(void *pvParameters)
{
  (void)pvParameters;

  if (kDiffBarEncoderPinA < 0 || kDiffBarEncoderPinB < 0)
  {
    Serial.println("Diff-bar encoder pins not configured; publishing emulated counts");
  }
  else
  {
    Serial.println("Encoder task placeholder (driver not implemented yet)");
  }

  uint8_t sequence = 0;
  const uint32_t startMs = millis();

  for (;;)
  {
    const float t = (millis() - startMs) / 1000.0f;

    // TODO: replace with quadrature or absolute encoder reads.
    const int32_t count = generateEmulatedEncoderCount(t, kEmulatedCountAmplitude);
    publishDiffBarEncoder(sequence, count);

    sequence++;
    vTaskDelay(pdMS_TO_TICKS(kEncoderPublishPeriodMs));
  }
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
