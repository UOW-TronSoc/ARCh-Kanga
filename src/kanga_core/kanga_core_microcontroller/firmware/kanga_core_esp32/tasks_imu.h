#pragma once

// BNO086 IMU publisher.
//
// When SPI pins in pin_config.h are unset, publishes emulated orientation,
// angular velocity, and linear acceleration at 50 Hz. Replace the emulation
// loop in tasks_imu.cpp with Game Rotation Vector + gyro + accel reads once
// the BNO086 driver is integrated.

void startImuTask();
