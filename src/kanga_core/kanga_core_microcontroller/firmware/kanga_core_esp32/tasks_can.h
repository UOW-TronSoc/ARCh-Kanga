#pragma once

// CAN command ingress.
//
// Runs on core 0. Receives host command frames and forwards the latest command
// to each servo queue via xQueueOverwrite (only the most recent command is
// kept when the actuator task falls behind).

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "kanga_core_microcontroller/can_protocol.hpp"

extern QueueHandle_t gGimbalCommandQueue;
extern QueueHandle_t gServoPwmCommandQueue;

void startCanTasks();
