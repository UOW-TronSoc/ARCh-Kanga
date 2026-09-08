# kanga_manipulator_microcontroller

Firmware and communication protocol for the Kanga manipulator microcontroller.

## Owns

- The `.ino` firmware that runs on the manipulator microcontroller
- Its command, status, and CAN protocol
- Host-side protocol translation where required
- Wrist and tool sensing and actuation that do not belong to the ODrive drive
  boundary

## Boundary

Generated Arduino build output must not be committed.

This is an architecture placeholder; no 2026 implementation has been migrated yet.

Wrist integration is deferred from the initial four-ODrive-joint milestone.
See the [manipulator migration plan](../../../docs/migration/manipulator.md).
