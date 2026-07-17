# Kanga manipulator

Structure folder for the manipulator software stack. This folder is not itself
a ROS package.

## Packages

- `kanga_manipulator_description`: manipulator URDF, xacro, meshes, joints, and
  frames.
- `kanga_manipulator_controller`: manipulator control, kinematics, limits, and
  operator command handling.
- `kanga_manipulator_bringup`: manipulator-specific launch composition and
  configuration selection.
- `kanga_manipulator_simulation`: manipulator simulation bridges and launch
  files.
- `kanga_manipulator_microcontroller`: communication with the manipulator
  microcontroller.

`kanga_manipulator_utils` is reserved as an empty structure folder for future
manipulator utility packages. Do not put miscellaneous code there without a
clear package boundary.

The primary historical reference is `ARCH2026-Kanga` branch
`feat/arm-simulation` at commit
`8b0c0537823fac7aaac26c1bea8bd4f3763bdc06`.
