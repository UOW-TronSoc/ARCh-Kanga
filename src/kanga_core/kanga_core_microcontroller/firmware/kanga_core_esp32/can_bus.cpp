#include "can_bus.h"

#include <Arduino.h>

#include "pin_config.h"

namespace
{

constexpr uint32_t kCanErrorLogIntervalMs = 5000;
uint32_t gLastCanErrorLogMs = 0;

void logCanErrorThrottled(const char *message)
{
  const uint32_t nowMs = millis();
  if (nowMs - gLastCanErrorLogMs < kCanErrorLogIntervalMs)
  {
    return;
  }

  gLastCanErrorLogMs = nowMs;
  Serial.println(message);
}

}  // namespace

bool canBusBegin()
{
  // TX/RX queue depth of 10 matches last year's Core_RTOS defaults.
  return ESP32Can.begin(
    ESP32Can.convertSpeed(kCanBitrateKbps),
    kCanTxPin,
    kCanRxPin,
    10,
    10);
}

bool canBusWrite(CanFrame &frame, uint32_t timeoutMs)
{
  if (ESP32Can.writeFrame(frame, timeoutMs) == 1)
  {
    return true;
  }

  // Expected on the bench when no transceiver or bus termination is present.
  logCanErrorThrottled("CAN write failed (no ACK / bus offline?)");
  return false;
}

bool canBusRead(CanFrame &frame, uint32_t timeoutMs)
{
  return ESP32Can.readFrame(frame, timeoutMs);
}
