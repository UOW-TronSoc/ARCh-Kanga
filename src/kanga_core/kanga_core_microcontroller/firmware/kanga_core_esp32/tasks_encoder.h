#pragma once

// Differential-bar encoder publisher.
//
// When encoder pins in pin_config.h are unset, publishes an emulated triangle-
// wave count at 50 Hz. Raw counts are calibrated to diff_bar_angle on the host.

void startEncoderTask();
