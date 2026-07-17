# kanga_science_controller

Control system for the Kanga science.

## Owns

- Science control and command processing
- Science kinematics, sequencing, limits, and feedback interpretation

## Boundary

Hardware transport, description assets, launch composition, and simulation bridges remain outside this package.

Motor commands must be rejected while the shared `kanga_whs`
motion-inhibit state is active or unavailable.

This is an architecture placeholder; no 2026 implementation has been migrated yet.
