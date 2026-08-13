#include "tasks_servos.h"

#include <Arduino.h>

#include "kanga_core_microcontroller/can_protocol.hpp"
#include "pin_config.h"
#include "tasks_can.h"

using namespace kanga_core_microcontroller;

namespace
{

// Two-axis camera gimbal. CAN_ID_GIMBAL_CMD -> gGimbalCommandQueue.
void vGimbalTask(void *pvParameters)
{
  (void)pvParameters;
  Serial.println("Gimbal task started (inactive placeholder)");

  GimbalCommandFrame latestCommand = {};

  for (;;)
  {
    if (gGimbalCommandQueue != nullptr &&
        xQueueReceive(gGimbalCommandQueue, &latestCommand, pdMS_TO_TICKS(100)) == pdTRUE)
    {
      // TODO: drive kGimbalPanPwmPin / kGimbalTiltPwmPin when configured.
      Serial.printf(
        "Gimbal command seq=%u pan=%.2f deg tilt=%.2f deg (not applied)\n",
        latestCommand.sequence,
        latestCommand.pan_cdeg / 100.0f,
        latestCommand.tilt_cdeg / 100.0f);
    }
  }
}

// Two auxiliary PWM servos. CAN_ID_SERVO_PWM_CMD -> gServoPwmCommandQueue.
void vServoPwmTask(void *pvParameters)
{
  (void)pvParameters;
  Serial.println("Servo PWM task started (inactive placeholder)");

  ServoPwmCommandFrame latestCommand = {};

  for (;;)
  {
    if (gServoPwmCommandQueue != nullptr &&
        xQueueReceive(gServoPwmCommandQueue, &latestCommand, pdMS_TO_TICKS(100)) == pdTRUE)
    {
      // TODO: drive kServoAPwmPin / kServoBPwmPin when configured.
      Serial.printf(
        "Servo PWM command seq=%u A=%d us B=%d us (not applied)\n",
        latestCommand.sequence,
        1500 + latestCommand.servo_a_us,
        1500 + latestCommand.servo_b_us);
    }
  }
}

}  // namespace

void startGimbalTask()
{
  if (kGimbalPanPwmPin < 0 || kGimbalTiltPwmPin < 0)
  {
    Serial.println("Gimbal PWM pins not configured; task will log commands only");
  }

  xTaskCreatePinnedToCore(
    vGimbalTask,
    "gimbal",
    3072,
    nullptr,
    2,
    nullptr,
    1);
}

void startServoPwmTask()
{
  if (kServoAPwmPin < 0 || kServoBPwmPin < 0)
  {
    Serial.println("Auxiliary servo PWM pins not configured; task will log commands only");
  }

  xTaskCreatePinnedToCore(
    vServoPwmTask,
    "servo_pwm",
    3072,
    nullptr,
    2,
    nullptr,
    1);
}
