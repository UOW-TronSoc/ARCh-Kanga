# Kanga core

Structure folder for packages that make up the rover base independently of any
payload. This folder is not itself a ROS package.

## Packages

- `kanga_core_drive`: ODrive launch, Fibre commissioning, closed-loop trigger,
  wheel JointState from motor estimates.
- `kanga_core_controller`: chassis-to-wheel mapping and `/cmd_vel` setpoint
  stream (Alternative A; CLOSED_LOOP only).
- `kanga_core_description`: chassis, wheel, and core rover geometry.
- `kanga_core_bringup`: standalone physical rover-base composition.
- `kanga_core_microcontroller`: `.ino` firmware and protocol for core
  mechanisms, encoders, and status.
- `kanga_core_battery`: Daly BMS communication and battery diagnostics.
- `kanga_core_simulation`: standalone simulation of the rover base.

Whole-rover description, bringup, and simulation packages compose this domain
with a selected payload. Payload-specific behaviour does not belong here.
