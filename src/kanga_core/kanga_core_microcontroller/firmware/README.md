# Rover-base ESP32 firmware

Place the rover-base Arduino sketch at:

```text
firmware/kanga_core_esp32/kanga_core_esp32.ino
```

Firmware-only headers and C++ sources should live beside the sketch. The
firmware owns ESP32 peripherals and the device-side CAN protocol; it must not
depend on ROS or encode URDF geometry and suspension kinematics.

When the firmware is added, document its board target, toolchain or Arduino
core version, required libraries, pin assignments, CAN frame definitions, and
flash procedure here. Keep a matching protocol description and host-side
protocol tests in the parent package whenever CAN frames change.

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
