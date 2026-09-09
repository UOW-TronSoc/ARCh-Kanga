# kanga_interfaces

Shared ROS messages and services used across Kanga packages.

- `WheelVelocityCommand` carries one timestamped, atomic four-wheel joint
  velocity command from `kanga_core_controller` to `kanga_core_drive`.
- Wheel velocity fields are in rad/s before gearbox conversion.
- `ManagedLaunchStatus`, `ListManagedLaunches`, and `ChangeManagedLaunch`
  form the typed boundary between the basestation and the separate onboard
  launch agent. Requests contain only an allowlisted system id and action,
  never a command or launch argument.

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

Core body feedback intentionally uses standard interfaces rather than a custom
Kanga message: `geometry_msgs/PoseWithCovarianceStamped` on `body/pose` and
`geometry_msgs/TwistWithCovarianceStamped` on `body/twist`. Their shared sample
timestamp, frame conventions, and unavailable-component rules are documented
in `kanga_core_microcontroller`.

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
