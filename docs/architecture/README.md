# Software architecture

## Goals

The source tree groups related ROS packages by rover domain while keeping each
buildable package responsible for one coherent capability. Structure folders
provide navigation and ownership documentation; they are not ROS packages.

The new tree preserves useful subsystem grouping from the 2026 repository
without automatically preserving duplicated packages or competition-time
shortcuts.

## Composition

```text
kanga_bringup                         Whole-rover composition
├── kanga_description                 Core model and payload assembly
├── kanga_drive
├── kanga_hardware/*
├── kanga_manipulator/kanga_manipulator_bringup
├── kanga_excavator/kanga_excavator_bringup
├── kanga_science/kanga_science_bringup
└── kanga_auto/*                      Autonomous operating modes

Payload bringup
├── kanga_<payload>_controller
├── kanga_<payload>_description
└── kanga_<payload>_microcontroller

Simulation uses the same controllers and descriptions, replacing physical
hardware with kanga_<payload>_simulation or whole-rover kanga_sim components.
```

A package should declare only dependencies it actually uses. Dependency arrows
must point toward lower-level interfaces and transport, not from transport back
into control or mission behaviour.

## Shared foundations

### Interfaces

`kanga_interfaces` contains shared `.msg`, `.srv`, and `.action` definitions and
their build metadata. It must not contain nodes, launch files, or hardware code.

### Core description

`kanga_description` owns the rover core URDF/xacro, core meshes and frames, and
whole-rover assembly of selected payload descriptions. Manipulator, excavator,
and science geometry belongs in each payload's description package.

### Drive and whole-rover packages

`kanga_drive` owns wheel configuration, chassis-to-wheel mapping, drive limits,
and drive-domain control. Its mathematical mapping should be usable without ROS
or ODrive where practical.

`kanga_bringup` composes real whole-rover operating modes. `kanga_sim` owns
whole-rover simulation integration, while `kanga_rviz` owns reviewed RViz
layouts.

## Hardware domain

`kanga_hardware` is a structure folder containing:

- `kanga_cameras` for Kanga-specific integration of ROS-compatible cameras;
- `kanga_battery` for Daly BMS communication;
- `kanga_core` for the ROO release, drive lock, and differential encoder;
- `kanga_odrive` for ODrive transport, state, status, errors, and setpoints;
- `kanga_microcontroller` for internal rover microcontroller communication.

`kanga_cameras` is provisional. If upstream ROS camera packages plus launch
configuration cover the requirement, avoid maintaining an unnecessary wrapper.

The modified ODrive implementation is first-party Kanga code. Its README must
record its upstream origin, the reason for the fork, all Kanga modifications,
and why it must not be casually replaced.

## Autonomy domain

`kanga_auto` is a structure folder containing separate SLAM, cube detection,
Nav2, and placard detection packages. RTAB-Map and Nav2 remain external ROS
dependencies; these packages own only Kanga-specific configuration,
integration, and behaviour.

## Utility domain

`kanga_util` contains named cross-cutting packages for CAN/ROS integration,
direct onboard control, and shared joystick integration. It must not become a
miscellaneous dumping ground. Domain-specific behaviour stays in its domain.

## Payload domains

Manipulator, excavator, and science are independent structure folders. Each
owns separate description, controller, bringup, simulation, and microcontroller
packages.

The manipulator and excavator shared control and launch code previously, but
the current systems do not. Do not preserve the old shared implementation by
default. Extract a common library only when current, tested requirements prove
that an abstraction is genuinely shared.

Each payload also has an empty `kanga_<payload>_utils` structure folder reserved
for future packages. It must not receive miscellaneous implementation directly.

## Cross-cutting decisions

- ROS 2 Humble on Ubuntu 22.04 is the initial supported environment.
- The host creates and configures SocketCAN; containers consume it through host
  networking.
- ROS dependencies are declared in `package.xml` and resolved with rosdep.
- Common operating-system dependencies may also be preinstalled through
  `docker/apt-packages.txt` for a fast, repeatable container.
- Platform SDKs such as ZED are treated separately from ordinary ROS package
  dependencies.
- Tests should target pure calculations below ROS nodes whenever practical.
