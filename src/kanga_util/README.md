# Kanga utilities

Structure folder for named cross-cutting support packages. This folder is not
itself a ROS package and must not become a miscellaneous code dump.

## Packages

- `kanga_canbus`: optional Kanga-facing CAN helpers only; not ODrive transport.
  Club-owned devices should use `ros2socketcan_bridge`.
- `kanga_onboard_control`: control from a controller connected directly to the
  onboard computer.
- `kanga_joy`: shared ROS 2 joystick interfaces and integration.

New utility packages require a clear reusable responsibility and must not own
domain-specific drive, manipulator, excavator, science, or autonomy behaviour.
