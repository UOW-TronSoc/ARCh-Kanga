#pragma once

// Differential-bar encoder publisher.
//
// When the AS5600 I2C address in pin_config.h is unset, or the magnet is not
// detected, publishes an emulated triangle-wave count at 50 Hz. When configured,
// publishes the 12-bit RAW ANGLE (unwrapped across 0/4095) as the CAN count.
// Host-side zero_count and counts_per_rad convert that to diff_bar_angle.

void startEncoderTask();
