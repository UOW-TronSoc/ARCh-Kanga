# kanga_canbus

Optional Kanga-facing CAN helpers only. This package is not the ODrive
transport and must not own SocketCAN for motor controllers.

## Owns

- Small shared utilities for Kanga packages that already speak ROS CAN frames,
  if such helpers prove necessary

## Does not own

- Direct SocketCAN sockets or epoll event loops for device drivers
- ODrive protocol or ODrive node internals (those stay in the external ODrive
  repository)
- The primary path for Daly BMS, microcontroller, or science CAN traffic

## Boundary

The host creates and configures CAN interfaces. For club-owned devices, use
`ros2socketcan_bridge` so nodes exchange `can_msgs` on ROS topics. Device
protocols remain in their owning hardware or payload packages.

Do not port the 2026 `epoll_event_loop` / `SocketCanIntf` stack here. That
code, if retained, belongs inside the external ODrive repository only.

This is an architecture placeholder; no 2026 implementation has been migrated
yet. Prefer removing this package later if nothing Kanga-specific remains.
