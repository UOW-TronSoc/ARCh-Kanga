#pragma once

// Board pin assignments for the rover-base ESP32.
//
// Set each constant to a valid GPIO number when the peripheral is wired.
// A value of -1 means "not configured"; tasks that depend on the pin will
// stay in emulation or log-only mode until it is updated.

// -----------------------------------------------------------------------------
// TWAI / CAN transceiver (active)
// -----------------------------------------------------------------------------

constexpr int kCanTxPin = 5;
constexpr int kCanRxPin = 4;

// Bitrate in kbit/s. Must match can_core on the host (250 kbit/s).
constexpr int kCanBitrateKbps = 250;

// -----------------------------------------------------------------------------
// BNO086 IMU over SPI (planned; tasks_imu.cpp emulates until configured)
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

// -----------------------------------------------------------------------------
// Differential-bar encoder (planned; tasks_encoder.cpp emulates until chosen)
// -----------------------------------------------------------------------------

constexpr int kDiffBarEncoderPinA = -1;
constexpr int kDiffBarEncoderPinB = -1;
