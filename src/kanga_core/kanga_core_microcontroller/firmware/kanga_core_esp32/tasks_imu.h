#pragma once

// MPU6050 IMU publisher.
//
// When the shared I2C pins in pin_config.h are unset, publishes emulated orientation,
// angular velocity, and linear acceleration at 50 Hz. When configured, reads
// quaternion, gyro, and gravity-compensated acceleration from the DMP.

void startImuTask();
