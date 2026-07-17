# Kanga hardware

Structure folder for ROS packages that communicate with physical rover
hardware. This folder is not itself a ROS package.

## Packages

- `kanga_cameras`: ROS-compatible ZED, RealSense, and OAK camera integration.
  Keep this package only if Kanga-specific camera management is required beyond
  upstream drivers and launch configuration.
- `kanga_battery`: Daly BMS communication and battery status.
- `kanga_core`: core internal mechanisms including the ROO release, drive lock,
  and differential encoder.
- `kanga_odrive`: Kanga's maintained ODrive communication implementation.
- `kanga_microcontroller`: communication with internal rover
  microcontrollers.

Higher-level drive and payload packages consume these hardware capabilities but
must not embed their transport implementations.
