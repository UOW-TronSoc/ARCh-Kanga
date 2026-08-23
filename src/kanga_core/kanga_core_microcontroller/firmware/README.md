# Rover-base ESP32 firmware

Sketch path:

```text
firmware/kanga_core_esp32/kanga_core_esp32.ino
```

Firmware-only headers and C++ sources live beside the sketch. The firmware
owns ESP32 peripherals and the device-side CAN protocol; it must not depend on
ROS or encode URDF geometry and suspension kinematics.

## Toolchain

| Item | Value |
|---|---|
| Board | ESP32 (Arduino core) |
| Build system | [PlatformIO](https://platformio.org/) (`firmware/kanga_core_esp32/platformio.ini`) |
| Library | [ESP32-TWAI-CAN](https://github.com/handmade0octopus/ESP32-TWAI-CAN) |
| CAN bitrate | 250 kbit/s (`can_core` policy) |
| CAN pins | TX = GPIO 5, RX = GPIO 4 |

```bash
cd src/kanga_core/kanga_core_microcontroller/firmware/kanga_core_esp32
pio run                  # build
pio run -t upload        # flash (set upload_port in platformio.ini if needed)
pio device monitor       # serial log at 115200 baud
```

Future BNO086 support will use SPI (pins not assigned yet). The bench IMU is an
MPU6050-compatible HW-123 on I2C (GPIO 21/22). Servo PWM and encoder pins are
placeholders (`-1` in `pin_config.h`).

## RTOS layout

| Task | Core | Direction | Status |
|---|---|---|---|
| `can_read` | 0 | Host → ESP32 commands | Active |
| `gimbal` | 1 | CAN gimbal command placeholder | Inactive (logs only) |
| `servo_pwm` | 1 | CAN auxiliary servo placeholder | Inactive (logs only) |
| `imu` | 1 | ESP32 → CAN body IMU samples | MPU6050 DMP when I2C configured |
| `encoder` | 1 | ESP32 → CAN diff-bar count | Emulated |

`ros2_socketcan` on the host will bridge these frames to ROS topics. The future
`core_can_bridge` executable in this package will decode them into typed
messages (`body/pose`, `body/twist`, `diff_bar_angle`, and so on).

## CAN protocol (preliminary)

All frames use 11-bit standard identifiers. Shared protocol headers live in
`include/kanga_core_microcontroller/can_ids.hpp` and `can_protocol.hpp` (used
by both firmware and `core_can_bridge`).

Most payloads include a wrapping sequence byte so the host bridge can detect
drops. The orientation frame is an exception: four int16 quaternion components
fill the 8-byte CAN limit, so sequence is carried only on the gyro and accel
frames published in the same IMU cycle.

### Host → ESP32

| ID | Name | Payload |
|---|---|---|
| 813 | `CAN_ID_GIMBAL_CMD` | `sequence`, `pan_cdeg` (int16), `tilt_cdeg` (int16) |
| 814 | `CAN_ID_SERVO_PWM_CMD` | `sequence`, `servo_a_us` (int16 offset from 1500 µs), `servo_b_us` (int16) |

### ESP32 → host

| ID | Name | Payload |
|---|---|---|
| 812 | `CAN_ID_DIFF_BAR_ENCODER` | `sequence`, `count` (int32, device units TBD) |
| 820 | `CAN_ID_IMU_ORIENTATION` | `qw/qx/qy/qz` (int16, scale 1/16384; no sequence byte) |
| 821 | `CAN_ID_IMU_ANGULAR_VEL` | `sequence`, `wx/wy/wz` (int16, 0.001 rad/s per LSB) |
| 822 | `CAN_ID_IMU_LINEAR_ACCEL` | `sequence`, `ax/ay/az` (int16, 0.001 m/s² per LSB) |

Legacy decimal IDs 810 (ROO release) and 811 (status LED) are reserved from
last year's firmware but are not transmitted yet.

## Source map

| File | Role |
|---|---|
| `kanga_core_esp32.ino` | Setup, task startup order |
| `pin_config.h` | GPIO assignments (`-1` = not wired) |
| `../../include/kanga_core_microcontroller/can_ids.hpp` | CAN identifier constants (shared) |
| `../../include/kanga_core_microcontroller/can_protocol.hpp` | Payload structs, scales (shared) |
| `can_bus.*` | TWAI init and read/write wrapper |
| `tasks_can.*` | Core 0 command ingress |
| `tasks_servos.*` | Gimbal + PWM servo placeholders |
| `tasks_imu.*` | MPU6050 DMP publisher (emulated when I2C unset) |
| `tasks_encoder.*` | Encoder publisher (emulated until wired) |

## Planned BNO086 mode

For competition operation, configure the BNO086 as a six-axis device:

- enable only the Game Rotation Vector for fused orientation;
- use calibrated gyroscope and accelerometer reports as required;
- do not enable Rotation Vector, Geomagnetic Rotation Vector, or magnetic-field
  reports; and
- disable magnetometer calibration with the SH-2 calibration command after
  every reset, because the setting is not persistent.

Game Rotation Vector provides gravity-referenced roll/pitch and relative yaw.
Yaw will drift because there is deliberately no magnetic heading correction.
Record the chosen report interval, axis remapping, units, tare/reference
behaviour, and CAN representation beside the firmware implementation.

## Planned body feedback output

The ESP32, rather than the ROS computer, owns BNO086 orientation processing.
Each body-state sample sent over CAN should contain or identify:

- one ESP32 measurement timestamp;
- body position in metres, if provided by a valid non-IMU source;
- body orientation as a normalized `x/y/z/w` quaternion;
- body linear velocity in m/s, if provided by a valid estimator;
- body angular velocity in rad/s; and
- accuracy/covariance information sufficient for the ROS bridge to describe
  unavailable or uncertain components honestly.

The host CAN bridge will publish the sample as matching `body/pose` and
`body/twist` messages with the same timestamp. Do not send only Euler angles
when the BNO086 Game Rotation Vector already provides a quaternion.
