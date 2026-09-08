# Kanga manipulator

Structure folder for the manipulator software stack. This folder is not itself
a ROS package.

## Packages

| Package | Responsibility |
| --- | --- |
| `kanga_manipulator_description` | URDF, meshes, joint conventions, initial pose, hardware profiles |
| `kanga_manipulator_controller` | V1 joint-velocity relay and input timeout; later Servo and end-effector modes |
| `kanga_manipulator_drive` (planned) | ODrive lifecycle, core-style commissioning, conversion, joint protections, explicit timeout zero, watchdog path, joint feedback |
| `kanga_manipulator_bringup` | Configuration selection and subsystem composition |
| `kanga_manipulator_simulation` | Simulated hardware, timeout, and watchdog behaviour |
| `kanga_manipulator_microcontroller` | ESP32 firmware and wrist/tool protocol |

`kanga_manipulator_utils` is reserved for future utility packages. Do not place
miscellaneous code there without a clear package boundary.

Shared joystick acquisition remains in `kanga_joy`; arm-specific input meaning
stays in the controller. Operator display and reference requests remain in
`basestation/`.

Historical reference: `ARCH2026-Kanga` branch `feat/arm-simulation` at commit
`8b0c0537823fac7aaac26c1bea8bd4f3763bdc06`.

The authoritative architecture, interfaces, staged plan, and migration evidence
are in [`docs/migration/manipulator.md`](../../docs/migration/manipulator.md).
