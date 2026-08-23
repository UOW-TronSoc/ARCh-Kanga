#include "tasks_can.h"

#include <Arduino.h>
#include <string.h>

#include "can_bus.h"
#include "kanga_core_microcontroller/can_ids.hpp"
#include "kanga_core_microcontroller/can_protocol.hpp"

using namespace kanga_core_microcontroller;

QueueHandle_t gGimbalCommandQueue = nullptr;
QueueHandle_t gServoPwmCommandQueue = nullptr;

namespace
{

// Route a received frame to the appropriate RTOS queue.
void dispatchReceivedFrame(const CanFrame &frame)
{
  switch (frame.identifier)
  {
    case CAN_ID_GIMBAL_CMD:
    {
      if (frame.data_length_code < sizeof(GimbalCommandFrame))
      {
        return;
      }

      GimbalCommandFrame command;
      memcpy(&command, frame.data, sizeof(command));
      if (gGimbalCommandQueue != nullptr)
      {
        xQueueOverwrite(gGimbalCommandQueue, &command);
      }
      break;
    }

    case CAN_ID_SERVO_PWM_CMD:
    {
      if (frame.data_length_code < sizeof(ServoPwmCommandFrame))
      {
        return;
      }

      ServoPwmCommandFrame command;
      memcpy(&command, frame.data, sizeof(command));
      if (gServoPwmCommandQueue != nullptr)
      {
        xQueueOverwrite(gServoPwmCommandQueue, &command);
      }
      break;
    }

    default:
      break;
  }
}

void vCanReadLoop(void *pvParameters)
{
  (void)pvParameters;
  Serial.println("CAN read task started");

  CanFrame receivedFrame;

  for (;;)
  {
    if (canBusRead(receivedFrame, portMAX_DELAY))
    {
      dispatchReceivedFrame(receivedFrame);
    }
  }
}

}  // namespace

void startCanTasks()
{
  gGimbalCommandQueue = xQueueCreate(1, sizeof(GimbalCommandFrame));
  gServoPwmCommandQueue = xQueueCreate(1, sizeof(ServoPwmCommandFrame));

  xTaskCreatePinnedToCore(
    vCanReadLoop,
    "can_read",
    4096,
    nullptr,
    3,       // Highest priority on core 0 so commands are not starved.
    nullptr,
    0);
}
