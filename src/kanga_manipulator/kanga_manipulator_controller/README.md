# kanga_manipulator_controller

Control system for the Kanga manipulator.

## Owns

- Manipulator control and command processing
- Manipulator kinematics, sequencing, limits, and feedback interpretation

## Boundary

Hardware transport, description assets, launch composition, and simulation bridges remain outside this package.

Motion commands must be rejected while the shared `kanga_whs`
motion-inhibit state is active or unavailable.

This is an architecture placeholder; no 2026 implementation has been migrated yet.
