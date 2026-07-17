# kanga_canbus

Interface between SocketCAN and ROS-facing Kanga code.

## Owns

- Reusable SocketCAN helpers
- CAN frame conversion and common ROS-facing CAN abstractions

## Boundary

The host creates and configures CAN interfaces. Device-specific protocols remain in their owning hardware or payload packages.

This is an architecture placeholder; no 2026 implementation has been migrated yet.
