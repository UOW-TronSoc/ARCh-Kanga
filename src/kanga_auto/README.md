# Kanga autonomy

Structure folder for localisation, perception, and navigation packages. This
folder is not itself a ROS package.

## Packages

- `kanga_slam`: RTAB-Map odometry, localisation, mapping, sensor remapping, and
  related configuration.
- `kanga_cube_detection`: RGBW cube detection.
- `kanga_nav2`: Kanga's Nav2 navigation pipeline and configuration.
- `kanga_placard_detection`: placard perception and detection outputs.

Packages in this domain should depend on stable drive, sensor, and transform
interfaces rather than hardware implementation details.
