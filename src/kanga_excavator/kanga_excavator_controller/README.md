# kanga_excavator_controller

Control system for the Kanga excavator.

## Owns

- Excavator control and command processing
- Excavator kinematics, sequencing, limits, and feedback interpretation

## Boundary

Hardware transport, description assets, launch composition, and simulation bridges remain outside this package.

Motion commands must be rejected while the shared `kanga_whs`
motion-inhibit state is active or unavailable.

This is an architecture placeholder; no 2026 implementation has been migrated yet.
