# Kanga science

Structure folder for the science payload software stack. This folder is not
itself a ROS package.

## Packages

- `kanga_science_description`: science payload URDF, xacro, meshes, joints, and
  frames.
- `kanga_science_controller`: science payload control, sequencing, and limits.
- `kanga_science_bringup`: science-specific launch composition and
  configuration selection.
- `kanga_science_simulation`: science payload simulation and launch files.
- `kanga_science_microcontroller`: communication with the science payload
  microcontroller.

`kanga_science_utils` is reserved as an empty structure folder for future
science utility packages. Do not put miscellaneous code there without a clear
package boundary.
