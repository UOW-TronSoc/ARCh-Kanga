#pragma once

// Thin wrapper around ESP32-TWAI-CAN.
//
// Centralizes TWAI init and read/write so tasks do not call the library
// directly. Pin and bitrate settings come from pin_config.h.

#include <ESP32-TWAI-CAN.hpp>

// Start TWAI with the pins and bitrate from pin_config.h.
bool canBusBegin();

// Transmit a standard or extended frame. Returns false on timeout or bus error.
bool canBusWrite(CanFrame &frame, uint32_t timeoutMs = 10);

// Block until a frame is received or timeoutMs elapses. Returns false on timeout.
bool canBusRead(CanFrame &frame, uint32_t timeoutMs);
