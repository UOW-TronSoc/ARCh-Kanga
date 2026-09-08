# kanga_manipulator_controller

Control system for the Kanga manipulator.

## Owns

- Literal velocity-only `JointTrajectory` relay for v1 joint control
- Operator-input timeout and continuous zero-command output while the relay is
  healthy
- Arm-specific input mapping
- Later MoveIt Servo integration and constrained end-effector control

## Boundary

Hardware transport, motor conversion, joint-position and final actuator limits,
description assets, launch composition, simulation bridges, basestation UI, and
shared joystick acquisition remain outside this package. The drive owns its
independent controller-output timeout, explicit motor-zero response, and
firmware-watchdog integration.

The v1 relay preserves valid motion command data unchanged. Whole-message
validation, input timeout, explicit zeros, and rejection while the shared
`kanga_whs` motion-inhibit state is active or unavailable are the only v1
exceptions to forwarding.

This is an architecture placeholder; no 2026 implementation has been migrated
yet.

See the [manipulator migration plan](../../../docs/migration/manipulator.md).
