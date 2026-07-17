# Kanga excavator

Structure folder for the excavation software stack. This folder is not itself
a ROS package.

## Packages

- `kanga_excavator_description`: excavator URDF, xacro, meshes, joints, and
  frames.
- `kanga_excavator_controller`: excavation control, sequencing, limits, and
  operator command handling.
- `kanga_excavator_bringup`: excavator-specific launch composition and
  configuration selection.
- `kanga_excavator_simulation`: excavator simulation bridges and launch files.
- `kanga_excavator_microcontroller`: `.ino` firmware and protocol for the
  excavator microcontroller.

`kanga_excavator_utils` is reserved as an empty structure folder for future
excavator utility packages. Do not put miscellaneous code there without a clear
package boundary.

The previous manipulator and excavation systems shared implementation. The new
systems are independent; do not preserve the old sharing without a current,
validated requirement.
