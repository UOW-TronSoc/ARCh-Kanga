# kanga_manipulator_bringup

Bringup and configuration for the Kanga manipulator.

## Owns

- Manipulator-specific launch composition
- Manipulator configuration selection
- Composition of the selected description, controller, physical drive, and
  microcontroller adapters

## Boundary

Whole-rover launch composition remains in kanga_bringup. Control algorithms do not belong in launch files.

This is an architecture placeholder; no 2026 implementation has been migrated yet.

See the [manipulator migration plan](../../../docs/migration/manipulator.md).
