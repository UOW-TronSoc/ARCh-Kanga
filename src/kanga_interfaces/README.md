# kanga_interfaces

Shared ROS 2 messages, services, and actions for Kanga.

## Owns

- Kanga-specific `.msg`, `.srv`, and `.action` definitions
- Interface generation and interface-only dependencies

## Does not own

- Nodes or executable logic
- Hardware communication
- Launch or parameter files
- ODrive motor contracts (`ControlMessage`, `ControllerStatus`, `ODriveStatus`,
  `AxisState`) — those live in the external ODrive package
- Raw SocketCAN framing — use
  [ros2_socketcan](https://github.com/autowarefoundation/ros2_socketcan)
  instead of a Kanga-local microcontroller frame message

Add an interface only when standard ROS interfaces cannot express the contract
clearly. Keep definitions transport-neutral and document units in field
comments.

## Migrated from ARCH2026-Kanga

| Message | Source path | Merged |
|---------|-------------|--------|
| `BatteryInfo` | `kanga_interfaces/msg/BatteryInfo.msg` | PR #15 |
| `BmsStatus` | `kanga_interfaces/msg/BmsStatus.msg` | PR #15 |

ODrive motor contracts (`ControlMessage`, `ControllerStatus`, `ODriveStatus`,
`AxisState`) were removed from Kanga and live in
[`custom-ros-odrive`](https://github.com/UOW-TronSoc/custom-ros-odrive).

The whole-robot WHS contract may require transport-neutral motion-inhibit state
and explicit override interfaces here. Their fields and override semantics must
be documented before implementation.
