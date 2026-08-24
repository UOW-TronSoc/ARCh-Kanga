#pragma once

// Board pin assignments for the rover-base ESP32.
//
// Set each constant to a valid GPIO number when the peripheral is wired.
// A value of -1 means "not configured"; tasks that depend on the pin will
// stay in emulation or log-only mode until it is updated.

// -----------------------------------------------------------------------------
// TWAI / CAN transceiver (active)
// -----------------------------------------------------------------------------

constexpr int kCanTxPin = 4;
constexpr int kCanRxPin = 5;

// Bitrate in kbit/s. Must match can_core on the host (250 kbit/s).
constexpr int kCanBitrateKbps = 250;

// -----------------------------------------------------------------------------
// Shared I2C bus (MPU6050 IMU + AS5600 diff-bar encoder)
// -----------------------------------------------------------------------------

constexpr int kI2cSdaPin = 21;
constexpr int kI2cSclPin = 22;
constexpr int kMpu6050I2cAddress = 0x68;
constexpr int kAs5600I2cAddress = 0x36;

// -----------------------------------------------------------------------------
// BNO086 IMU over SPI (planned production IMU; not used while MPU6050 is wired)
// -----------------------------------------------------------------------------

constexpr int kBno086SpiCsPin = -1;
constexpr int kBno086SpiSckPin = -1;
constexpr int kBno086SpiMosiPin = -1;
constexpr int kBno086SpiMisoPin = -1;
constexpr int kBno086IntPin = -1;
constexpr int kBno086RstPin = -1;

// -----------------------------------------------------------------------------
// Camera gimbal + auxiliary PWM servos (planned; tasks_servos.cpp is inactive)
// -----------------------------------------------------------------------------

constexpr int kGimbalPanPwmPin = -1;
constexpr int kGimbalTiltPwmPin = -1;
constexpr int kServoAPwmPin = -1;
constexpr int kServoBPwmPin = -1;
