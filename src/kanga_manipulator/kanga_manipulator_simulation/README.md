# kanga_manipulator_simulation

Simulation integration for the Kanga manipulator.

## Owns

- Manipulator simulator bridges (planned)
- Manipulator simulation configuration and launch files (planned)
- A simulated actuator, initial-angle feedback mapping, joint protections,
  explicit timeout-zero response, and watchdog boundary matching the physical
  drive interfaces

## Boundary

Reusable control remains in the controller package and canonical geometry
remains in the description package. Optional startup referencing behaviour
follows the late QOL stages in the migration plan.

This is an architecture placeholder; no 2026 implementation has been migrated
yet.

See the [manipulator migration plan](../../../docs/migration/manipulator.md).
