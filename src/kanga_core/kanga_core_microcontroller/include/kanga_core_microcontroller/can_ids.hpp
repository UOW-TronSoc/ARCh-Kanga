#pragma once

// Shared CAN identifier assignments for the rover-base ESP32 and host bridge.
//
// All frames use 11-bit standard identifiers. Decimal values follow last year's
// Core_RTOS sketch where possible. Packed layouts and scaling live in
// can_protocol.hpp.

#include <cstdint>

namespace kanga_core_microcontroller
{

// Host -> ESP32 commands
constexpr uint32_t CAN_ID_GIMBAL_CMD = 813;
constexpr uint32_t CAN_ID_SERVO_PWM_CMD = 814;

// ESP32 -> host telemetry
constexpr uint32_t CAN_ID_DIFF_BAR_ENCODER = 812;
constexpr uint32_t CAN_ID_IMU_ORIENTATION = 820;
constexpr uint32_t CAN_ID_IMU_ANGULAR_VEL = 821;
constexpr uint32_t CAN_ID_IMU_LINEAR_ACCEL = 822;

// Reserved (legacy Core_RTOS IDs; not transmitted yet)
constexpr uint32_t CAN_ID_ROO_RELEASE = 810;
constexpr uint32_t CAN_ID_STATUS_LED = 811;

}  // namespace kanga_core_microcontroller
