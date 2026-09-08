# kanga_manipulator_description

Robot description for the Kanga manipulator.

## Owns

- Manipulator URDF and xacro
- Manipulator meshes, joints, and TF frames
- Versioned hardware profiles (initial target: `manipulator_2026.yaml`)
- Canonical joint axes, bounds, transmissions, directions, reductions, and
  prescribed startup angles

## Boundary

Whole-rover assembly remains in kanga_description; manipulator control and simulation do not belong here.

This is an architecture placeholder; no 2026 implementation has been migrated
yet.

See the [manipulator migration plan](../../../docs/migration/manipulator.md).
