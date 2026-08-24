// Rover-base ESP32 firmware entry point.
//
// Initializes TWAI (CAN) and starts FreeRTOS tasks defined in tasks_*.cpp:
//   Core 0 — CAN command reception (gimbal + auxiliary servos)
//   Core 1 — MPU6050 IMU + AS5600 encoder publishers, inactive servo actuation
//
// Hardware pin assignments live in pin_config.h. CAN identifiers and payload
// layouts live in include/kanga_core_microcontroller/can_{ids,protocol}.hpp.
// by ros2_socketcan and the core_can_bridge node in this package.

#include <Arduino.h>

#include "can_bus.h"
#include "i2c_bus.h"
#include "tasks_can.h"
#include "tasks_encoder.h"
#include "tasks_imu.h"
#include "tasks_servos.h"

void setup()
{
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("kanga_core_esp32 RTOS firmware");

  if (!canBusBegin())
  {
    Serial.println("CAN bus failed to start");
    while (true)
    {
      delay(1000);
    }
  }

  Serial.println("CAN bus started at 250 kbit/s");

  i2cBusBegin();

  // Command ingress must start before consumers that block on its queues.
  startCanTasks();
  startGimbalTask();
  startServoPwmTask();
  startImuTask();
  startEncoderTask();

  Serial.println("RTOS tasks started");
}

void loop()
{
  // All periodic work runs in FreeRTOS tasks; loop() stays idle.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
