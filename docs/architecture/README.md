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

- `kanga_core_drive` owns ODrive multi-motor launch, Fibre commissioning
  (apply / calibrate / save), closed-loop trigger, and wheel `JointState` from
  ODrive estimates. Invert direction is configured in launch only.
- `kanga_core_controller` owns chassis-to-wheel velocity mapping, drive limits,
  and the continuous `/cmd_vel` setpoint stream. The selected physical or
  simulated drive boundary owns CLOSED_LOOP gating.
  Optional low-confidence wheel odometry remains deferred. `robot_state_publisher`
  generates link transforms from the robot description. A visual, inertial,
  SLAM, or fused estimator owns the authoritative `odom` to `base_link`
  transform.
- `kanga_core_description` owns chassis, wheel, suspension, and other base
  geometry and frame naming. It also owns versioned drivetrain hardware
  profiles consumed by description, controller, drive, and commissioning.
- `kanga_core_bringup` composes the physical core so it can run without a
  payload.
- `kanga_core_microcontroller` owns the rover-base microcontroller firmware and
  its protocol, including ROO release, drive lock, differential-bar encoder
  sampling, IMU and servo interfaces, core internal status, and host-side
  suspension JointState mapping. CAN translation and suspension kinematics are
  separate executables within that package. Its preliminary body-pose TF is a
  non-authoritative visualization adapter; future controllers may consume the
  timestamped pose/twist topics, while a fused estimator owns the authoritative
  `odom` to `base_link` transform. The stop switch connects directly to the
  Jetson and is owned by `kanga_whs`.
- `kanga_core_battery` owns Daly BMS communication and battery diagnostics.
- `kanga_core_simulation` provides standalone simulated hardware and launch
  integration for the rover base. It exposes the same operational drive and
  state interfaces as the physical boundary and is the authoritative simulated
  odometry/TF source.

Transport and device-state management for ODrive live in the vendor
`custom_odrive` package (opened from `kanga_core_drive` launch). Mission policy
remains above the battery and microcontroller packages.

### Drive command and limit model

The drive actuator boundary and nominal wheel-radius conversion are
implemented. The operator `0–100%` mapping and Twist-domain shaping remain
future work.

The operator's `0–100%` speed setting is a UI-level scale, not a motor unit.
The basestation should map it onto configurable maximum chassis linear and
angular speeds and publish a `geometry_msgs/Twist`: linear components in m/s
and yaw in rad/s.

The planned path is:

```text
operator speed scale (0–100%)
  → chassis command limits / shaping (Twist: m/s and rad/s)
  → angled-grouser wheel kinematics using chassis geometry and effective radius
  → wheel-joint velocity (rad/s)
  → Kanga drive actuator boundary (50:1 reduction)
  → motor-shaft velocity (rad/s)
  → generic custom_odrive node / CAN Simple
```

`kanga_core_controller` owns the Twist-domain behaviour: configurable linear
and yaw limits, command timeout, and basic acceleration/deceleration or slew
limiting. It also owns chassis geometry, effective loaded wheel radius, and the
angled-grouser wheel transform calculations; their measured physical inputs
live in the selected description profile. Its output is wheel-joint rad/s. It
consumes a derived maximum joint velocity from that hardware profile so it can
uniformly desaturate wheel mixing, but it does not perform motor/gearbox
conversion or use ODrive/CAN units. A later feedback controller may use an
authoritative chassis velocity estimate, but that is separate from the initial
command shaper.

Kanga uses regular wheels with angled grousers, not mecanum wheels. The legacy
51° transform retains the rover's limited lateral capability, but that motion
is inefficient and is not the normal operating mode. Controller configuration
must later provide an explicit holonomic enable/disable mode; disabled mode
must ignore lateral commands and use the appropriate non-holonomic wheel mix.
Nominal measured geometry is a 230 mm wheel diameter, 180 mm wheel width, and
an outside wheel envelope of 1.10 m long by 0.89 m wide. Wheel-centre values are
derived rather than independently configured.

`kanga_core_drive` owns the actuator boundary. It converts wheel-joint rad/s to
motor-shaft rad/s using the selected reduction, applies an independent final
motor-facing safety clamp, and converts motor feedback back to joint units
where required. The reusable
`custom_odrive` API remains in motor-shaft units; its `velocity_ramp_test` must
therefore continue to test motor-shaft rad/s without Kanga gearbox knowledge.

Limits must be enforced at several layers:

- `100%` maps to configurable chassis-speed maxima, not directly to 22 TPS.
- If wheel mixing would exceed a wheel, uniformly desaturate all four wheel
  commands so the requested motion direction is preserved.
- No motor command may exceed the configured, commissioned S1
  `motor_velocity_limit_tps` (currently `22 turns/s`, or
  `44π ≈ 138.23 motor rad/s`). At the current value, 50:1 reduction corresponds
  to about `2.7646 rad/s` at the gearbox output.
- The onboard ODrive velocity limit remains the final hardware-side guard.

The authoritative physical inputs live in a versioned
`kanga_core_description/config/drivetrains/` profile. Core bringup selects one
profile and passes one shared parameter dictionary to controller, drive, and
joint feedback; each node uses only its declared subset. Commissioning
uses that same profile for the saved ODrive velocity limit. Consumer YAML and
C++ defaults must not duplicate the physical values. Hardware profile changes
are launch-time choices, not live parameter changes.

The controller uses a nominal effective radius of 0.115 m, measured to the
bottom of the grousers, so its transform is dimensionally correct in physical
units. Do not treat commanded chassis speed as field-calibrated until the
loaded rolling radius and traction/slip behaviour have been measured.

ODrive motor-shaft torque/current telemetry remains the unmodified logging
source. A Kanga drive-layer output-torque estimate may later add reduction and
measured gearbox efficiency without replacing the raw data.

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
joystick integration, allowlisted launch-process supervision, and only optional
Kanga-facing CAN helpers. `kanga_launch_agent` runs beside the rover nodes and
is the only component allowed to create and signal the process groups for its
fixed profiles. It must not become a miscellaneous dumping ground, and it must
not own SocketCAN for ODrive or other device drivers that should use
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

`basestation/` is the ground-station HTTP stack: one FastAPI server embeds an
`rclpy` node and serves the built React frontend on the same port. It is **not**
a ROS package domain and must not live under `src/`. The server is still a ROS 2
participant: it publishes and subscribes on rover topics and imports message
types from `kanga_interfaces` after a workspace `install/` overlay is sourced.

Docker for basestation is separate from `compose.dev.yaml` so members can work
on ROS packages without starting the operator stack. See
[Basestation install](../install/basestation.md) and
[Basestation migration](../migration/basestation.md). System startup and launch
ownership are documented in the
[launch-manager plan](../launch-manager/README.md). Planned motor config and
calibration behavior is documented in the
[commissioning page plan](../../basestation/COMMISSIONING_PAGE_PLAN.md).
The Logs page (folder tree of ROS, HTTP, and Docker PID-1 logs)
is documented in [the logs plan](../logging/README.md).

The basestation and onboard runtime remain separate deployment units. The
FastAPI process never launches rover nodes locally. It mounts the host
Docker socket only to follow PID-1 `docker logs` for the operator Logs
page (no compose/run/exec). Launch ownership stays on the onboard
`kanga_launch_agent` over the typed `kanga_interfaces` services. The agent
owns the fixed command, checks ROS sentinel nodes, and refuses to control
an externally started stack. This keeps process ownership on the
machine/container where the rover or local simulation actually runs.

Simulation is not an agent-owned profile in the initial release. It may be
started locally in the ROS development environment and uses the same controller
and operator interfaces as hardware. A later simulator deployment can add its
own explicit profile without teaching rover consumers whether their hardware
boundary is physical or simulated.

There is exactly one active ROS runtime container per operating environment.
Development and simulation use persistent `kanga-dev`; rover production uses
headless `kanga-onboard`. Both may run the same launch-agent node, but the two
containers are alternatives and must not be run together. The separate
`basestation-server` is the only other normal runtime container.

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
