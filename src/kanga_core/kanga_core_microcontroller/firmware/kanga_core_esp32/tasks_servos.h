#pragma once

// Servo actuation tasks (inactive until pin_config.h PWM pins are assigned).
//
// Each task blocks on its command queue from tasks_can.cpp. When pins are
// configured, replace the Serial logging stubs with ledcWrite() or equivalent.

void startGimbalTask();
void startServoPwmTask();
