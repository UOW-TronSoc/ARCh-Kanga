# kanga_drive

Drive-domain control for the Kanga rover.

## Owns

- Wheel configuration and geometry
- Chassis-to-wheel velocity mapping
- Drive limits and command validation
- Drive feedback interpretation and ROS node glue

## Does not own

- SocketCAN or `kanga_odrive` endpoint state management
- General joystick policy
- Top-level rover bringup

The wheel mapping mathematics should live in a ROS-independent library with
unit tests. Permanent source names must not use suffixes such as `_new` or
`_working`.
