# Software architecture

## Goals

The source tree groups related ROS packages by rover domain while allowing the
rover base and each payload to operate independently. Thin top-level packages
compose those independently testable domains into a complete rover.

Structure folders provide navigation and ownership documentation; they are not
ROS packages.

## Composition

```text
Physical rover
kanga_bringup                         Whole-rover composition
├── kanga_description                 Core and selected payload model
├── kanga_whs                         Whole-robot motion-stop coordination
├── kanga_core/kanga_core_bringup     Physical rover base
├── kanga_cameras                     Shared camera configuration
├── selected payload bringup
└── selected kanga_auto packages      Optional autonomous operating mode

Simulation
kanga_sim                             Whole-rover simulation composition
├── kanga_description
├── kanga_core/kanga_core_simulation
└── selected payload simulation
```

The core and payload bringup or simulation packages remain valid standalone
entry points. The top-level packages select and connect them; they do not
reimplement subsystem behaviour.

A package should declare only dependencies it actually uses. Dependency arrows
must point toward lower-level interfaces and transports, not from transport
back into control or mission behaviour.

## Shared foundations

### Interfaces

`kanga_interfaces` contains shared `.msg`, `.srv`, and `.action` definitions and
their build metadata. It must not contain nodes, launch files, or hardware code.

An independently maintained vendor repository must own any interfaces required
for its generic API rather than depending on Kanga-specific interfaces.

### Cameras

`kanga_cameras` provides shared Kanga-specific configuration and launch
integration for cameras used by the core, payloads, or autonomy. If upstream
ROS camera packages fully cover the requirement, avoid maintaining an
unnecessary wrapper.

### Whole-robot safety

The minimum `kanga_whs` implementation reads a physical switch connected
directly to an NVIDIA Jetson GPIO and publishes a whole-robot software
motion-inhibit state. Core and payload controllers must reject motor commands
while that state is active.

A manual software override exists only as an exceptional mid-competition
recovery mechanism when entering the field would incur a penalty. It bypasses
the GPIO-triggered software inhibit and must be clearly visible to the operator.
No automatic health or fault detection is required for the initial system.

Because the switch is a software input rather than a direct motor-power or
hardware-enable interruption, this initial implementation depends on the
Jetson and motor-control software. It must not be described as a hardwired or
safety-rated emergency stop.

## Core rover domain

`kanga_core` is a structure folder for the rover base:

- `kanga_core_drive` owns wheel configuration, chassis-to-wheel mapping, drive
  limits, and two separate feedback paths. ODrive wheel feedback becomes wheel
  joint states and may optionally produce low-confidence wheel odometry. Raw
  differential-bar encoder feedback from the core microcontroller becomes the
  differential-bar and suspension joint states. `robot_state_publisher`
  generates their link transforms from the robot description. A visual,
  inertial, SLAM, or fused estimator owns the authoritative `odom` to
  `base_link` transform.
- `kanga_core_description` owns chassis, wheel, suspension, and other base
  geometry and frame naming.
- `kanga_core_bringup` composes the physical core so it can run without a
  payload.
- `kanga_core_microcontroller` owns the rover-base microcontroller firmware and
  its protocol, including ROO release, drive lock, differential-bar encoder
  sampling, and core internal status. The stop switch connects directly to the
  Jetson and is owned by `kanga_whs`.
- `kanga_core_battery` owns Daly BMS communication and battery diagnostics.
- `kanga_core_simulation` provides standalone simulated hardware and launch
  integration for the rover base.

Transport and device-state management remain below drive behaviour. Mission
policy remains above the battery and microcontroller packages.

## Whole-rover packages

`kanga_description` assembles `kanga_core_description` and the selected payload
description. It does not duplicate geometry owned by those packages.

`kanga_bringup` composes reviewed physical-rover operating modes from the core,
cameras, selected payload, and optional autonomy packages.

`kanga_sim` owns simulation worlds, spawning, and composition of the core and
selected payload simulations. Simulator adapters specific to a subsystem stay
in that subsystem's simulation package.

`kanga_rviz` owns reviewed whole-rover and general debugging layouts.
Configurations required to operate a subsystem independently may live in that
subsystem's bringup package. For example, manipulator-only RViz configuration
belongs with `kanga_manipulator_bringup`, while a rover-with-manipulator layout
belongs in `kanga_rviz`.

## Vendor repositories

`vendor` is a structure folder for independently maintained ROS repositories.
Dependencies are pinned through a version-controlled `.repos` manifest and
imported with `vcs import`; their source is not copied into this repository.

The reusable ODrive ROS integration is intended to become one such repository.
Its public API should remain generic and independent of Kanga packages so other
club projects can use it. That repository owns its direct SocketCAN access and
any epoll / socket helpers internally; it must not depend on `kanga_canbus`.
Document upstream origin, local modifications, compatibility, and release
process.

## CAN transport

The host creates and configures SocketCAN interfaces. Containers consume them
through host networking.

Use a hybrid model:

- Vendor ODrive nodes open SocketCAN directly (one node per axis).
- Kanga-owned devices (battery, microcontrollers, science, and similar) use
  [ros2_socketcan](https://github.com/autowarefoundation/ros2_socketcan) and
  exchange CAN frames over ROS topics.
- Do not teach or re-home the ODrive epoll stack as a shared Kanga utility.
- Do not migrate `kanga_microcontroller`; prefer `ros2_socketcan`.
- Multiple RAW sockets may share one interface; do not also drive the same
  ODrive axes through the bridge.

## Autonomy domain

`kanga_auto` contains separate SLAM, cube detection, Nav2, and placard detection
packages. RTAB-Map and Nav2 remain external ROS dependencies; these packages own
only Kanga-specific configuration, integration, and behaviour.

Autonomy-specific RViz configuration should stay with the package or launch
flow that requires it unless it becomes a general whole-rover layout.

## Utility domain

`kanga_util` contains named cross-cutting packages for onboard control, shared
joystick integration, and only optional Kanga-facing CAN helpers. It must not
become a miscellaneous dumping ground, and it must not own SocketCAN for ODrive
or other device drivers that should use
[ros2_socketcan](https://github.com/autowarefoundation/ros2_socketcan).
Domain-specific behaviour stays in its domain.

## Payload domains

Manipulator, excavator, and science are independent structure folders. Each
owns separate description, controller, bringup, simulation, and microcontroller
packages so it can run without the core or either other payload.

The manipulator and excavator shared control and launch code previously, but the
current systems do not. Extract a common library only when current, tested
requirements prove that an abstraction is genuinely shared.

Each payload also has an empty `kanga_<payload>_utils` structure folder reserved
for future packages. It must not receive miscellaneous implementation directly.

## Operator UI (basestation)

`basestation/` is the ground-station HTTP stack (Django/FastAPI/frontend). It is
**not** a ROS package domain and must not live under `src/`. Those services are
still ROS 2 participants: they use `rclpy`, publish and subscribe on rover
topics, and import message types from `kanga_interfaces` after a workspace
`install/` overlay is sourced.

Docker for basestation is separate from `compose.dev.yaml` so members can work
on ROS packages without starting the operator stack. See
[Basestation install](../install/basestation.md) and
[Basestation migration](../migration/basestation.md).

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
- Operator UI code stays under `basestation/`; shared ROS interfaces stay in
  `src/kanga_interfaces`.
