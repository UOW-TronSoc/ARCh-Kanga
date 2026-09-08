# Manipulator architecture and migration plan

This document is the authoritative foundation for rebuilding the Kanga
manipulator in the permanent `kanga_manipulator_*` packages. It defines the
architectural agreement, behavioural interfaces, staged delivery, migration
evidence, and review criteria for PR1.

The work lands through small, dependent feature branches and pull requests
rather than one migration branch. PR1 delivers documentation and review criteria
only. Package creation, message definitions, configuration files, firmware,
controller code, and simulation implementation belong to subsequent PRs.

The historical implementation remains a reference:

```text
Repository: https://github.com/UOW-TronSoc/ARCH2026-Kanga
Branch:     feat/arm-simulation
Commit:     8b0c0537823fac7aaac26c1bea8bd4f3763bdc06
Paths:      kanga_arm/* and kanga_description/urdf/payloads/arm/*
```

Do not create an in-tree legacy arm package or bulk-copy the old controller.
Import only verified geometry, hardware values, protocol behaviour, and other
requirements that remain applicable. The old calculated kinematics, duplicated
sign inversions, ambiguous limits, and old ODrive integration are not part of
the new architecture.

## Goals and initial scope

The initial system controls the four ODrive-powered arm joints. It provides:

- individual joint-velocity control through a literal controller relay;
- joint position and measured joint velocity feedback in model coordinates;
- drive-side joint-position and actuator protections;
- an arm-specific stopping path with separate input, drive-command, and
  firmware watchdog timeouts; and
- the shared Kanga motion-inhibit behaviour.

Operators place the arm in the prescribed initial pose before powering the
ODrives. The description profile supplies the corresponding initial joint
angles so startup-relative motor feedback maps into model coordinates. The
historical candidates for the first four joints are `[0.0, -1.5708,
1.0471975512, -1.5708]` rad; PR2 must review them against last year's starting
configuration and physical arm before making them authoritative.

Base rotation plus planar end-effector forward/back, up/down, and pitch control
through MoveIt Servo is a subsequent controller capability. Operator-assisted
startup jogging and reference capture are also later quality-of-life work.

Wrist-roll feedback and control are a later slice. Until then, the description
must represent the wrist at a verified fixed orientation and the controller
must not claim full five-axis collision checking. Support only tools intended
for the new system. The old scoop configuration remains historical unless the
physical tool is brought back into service and validated.

Nothing depends on the old controller remaining operational during this work,
so there is no temporary `lkanga_arm` bridge, no temporary port of the old
inverse kinematics, and no unused scoop configuration in supported bringup.

## Architecture

Follow the established core flow where it applies:

```text
operator input
  -> kanga_manipulator_controller (v1 joint-velocity relay; later MoveIt Servo)
  -> desired joint velocity command
  -> kanga_manipulator_drive
  -> custom_odrive / manipulator microcontroller

motor and sensor feedback
  -> drive or microcontroller adapter
  -> manipulator JointState
  -> controller, robot_state_publisher, and operator telemetry
```

The separation is behavioural rather than a requirement that the core and arm
use identical message types. The arm has bounded, coordinated joints; the core
has continuously rotating wheels and a fixed four-wheel command. The
manipulator drive package should be structurally very similar to
`kanga_core_drive`. The v1 controller is a literal joint-velocity relay; MoveIt
Servo is added later for end-effector control without changing the drive
boundary.

### Core conventions and manipulator requirements

| Area | Follow core | Manipulator requirement |
| --- | --- | --- |
| Controller boundary | Produce joint-space commands without motor units or gearing | V1 relays joint velocities unchanged; MoveIt Servo later generates coordinated commands |
| Drive boundary | Own conversion, final actuator clamps, motor management, and feedback | Also enforce normal joint-position bounds; later add reference offsets and alignment eligibility |
| Configuration | Select one validated hardware profile and operating-limit set | Pair last year's arm URDF with `manipulator_2026.yaml` for per-joint coordinates, limits, directions, and reductions |
| Motor identity | Derive launch and feedback mappings from one motor specification | Per-joint motor Fibre overlays because J1/J5 and J2–J4 use different motors |
| Direction | Configure mounting inversion once through `custom_odrive` | Verify positive motion and feedback against every model joint axis |
| Feedback | Publish standard joint positions and velocities | Require observable freshness for all controlled joints; do not republish stale samples with new stamps |
| Stopping | Controller converts stale operator input to a zero stream; drive independently handles stale controller output | Drive sends an explicit zero before stopping setpoints; enabled firmware watchdog then provides the device fallback |
| Simulation | Substitute the hardware boundary while retaining controller interfaces | Reproduce drive timeout, watchdog, inhibition, and joint feedback behaviour |

### Manipulator drive parity with core drive

`kanga_manipulator_drive` should mirror the proven `kanga_core_drive` layout:

| Core piece | Manipulator equivalent |
| --- | --- |
| `launch/drive.launch.py` | Multi-axis `custom_odrive_node` launch from one joint specification table |
| `config/motors/shared_motor_config.py` | Shared S1 Fibre settings including **enabled** firmware watchdog |
| `config/motors/wheel_*_motor_config.py` | Per-joint overlays: `joint_j1_motor_config.py`, `joint_j2_motor_config.py`, … |
| `commission_wheels` | `commission_joints` — merge shared + individual, call `custom_odrive commission` |
| `drive_manager` | CLOSED_LOOP / IDLE, per-joint calibrate/save services |
| `wheel_actuator` | Joint actuator — joint rad/s → motor rad/s, normal position-bound enforcement, CLOSED_LOOP gating, command timeout and explicit zero on timeout |
| `wheel_joint_state_publisher` | Joint feedback publisher — motor estimates → joint `JointState` with freshness |

Commissioning should be almost identical to core drive: shared baseline plus
per-joint overlays merged at commission time. J2, J3, and J4 use different
motors from J1 (and later J5), so motor parameters such as pole pairs, torque
constant, and calibration currents belong in the individual joint files, not
only in the shared file.

The target S1 watchdog policy is **enabled** with a timeout of **0.5 s or 1.0 s**
(bench validation chooses the final value). This is the intended production
behaviour for the manipulator. The core stack currently ships with watchdog
disabled and must be brought into alignment separately.

### Observations from the current core implementation

**Stale feedback must not appear fresh.** The core wheel feedback publisher
caches the latest converted motor estimate per wheel and republishes it on a
fixed timer with a new `header.stamp`, without checking whether a new CAN
sample arrived since the last publication:

From `src/kanga_core/kanga_core_drive/src/wheel_joint_state_publisher.cpp`
(lines 102–106):

```cpp
void WheelJointStatePublisher::publish_wheel_joint_states()
{
  sensor_msgs::msg::JointState joint_state_message;
  joint_state_message.header.stamp = this->get_clock()->now();
```

The manipulator joint feedback publisher must not copy this pattern.

**Core watchdog is currently disabled and must be resolved.** The committed
shared motor configuration disables the firmware watchdog:

From `src/kanga_core/kanga_core_drive/config/motors/shared_motor_config.py`
(lines 49–51):

```python
odrv.axis0.config.enable_watchdog = False
odrv.axis0.config.watchdog_timeout = 1
```

Core drive already documents that stale command transmission relies on an
enabled watchdog to disarm CLOSED_LOOP. The manipulator commissioning path must
enable the watchdog at 0.5–1.0 s. Treat the disabled watchdog as a known gap in
the current core pin, not as the target manipulator policy.

### Operator-provided joint mechanical behaviour

The current operator provided the following hardware information. It informs
the expected behaviour but does not replace powered bench validation:

| Joint | Mechanical note | Expected IDLE / watchdog behaviour |
| --- | --- | --- |
| J1 (base) | Operator reports that gravity does not meaningfully drive this axis | Position is expected to remain substantially unchanged in IDLE; verify on the arm |
| J2–J4 | Operator reports that these transmissions are non-backdrivable | They hold position in CLOSED_LOOP; verify their loaded behaviour when the watchdog disarms to IDLE |
| J5 (wrist roll, later) | Operator reports that gravity does not meaningfully drive this axis | Apply the same validation as J1 when wrist control is added |

J2–J4 may behave differently from the rover wheels when torque is removed. Bench
validation in physical bringup must record the measured outcome; do not assume
wheel-like coasting.

### Package ownership

| Component | Owns |
| --- | --- |
| `kanga_manipulator_controller` | V1 joint-velocity relay, operator-input timeout and continuous zero stream; later MoveIt Servo integration and end-effector mapping |
| `kanga_manipulator_drive` (planned) | Motor lifecycle, transmission conversion, joint-position and actuator clamps, controller-output timeout/watchdog path, joint feedback conversion, and later reference state |
| `kanga_manipulator_description` | Physical geometry, joint axes and bounds, prescribed initial pose, `manipulator_2026.yaml` hardware profile, reductions, and physical capability ceilings |
| `kanga_manipulator_microcontroller` | ESP32 protocol, sensor acquisition, and wrist/tool device control |
| `kanga_manipulator_bringup` | Select and distribute configuration; compose subsystem nodes |
| `kanga_manipulator_simulation` | Provide equivalent simulated hardware and operating-state behaviour |
| `basestation/` | Display authoritative onboard state and request operations |
| `kanga_joy` | Acquire and normalise shared joystick device input |

`kanga_manipulator_drive` does not exist yet and will be added in its own PR.
ODrive protocol and SocketCAN internals remain in the external `custom_odrive`
package. Arm-specific input meaning stays with the manipulator controller; the
shared joystick package only delivers device-level axes and buttons. Whole-rover
composition remains in the top-level bringup, description, and simulation
packages.

### ODrive electrical calibration versus arm pose referencing

These are separate operations and must not be conflated:

- **ODrive electrical calibration** establishes motor/encoder electrical
  parameters and axis readiness inside `custom_odrive`. It does not define the
  arm's physical joint angles in the robot model.
- **Initial pose mapping** adds the configured initial joint angle to
  startup-relative motor motion. It is required for v1 and assumes the operator
  placed the arm in the prescribed pose before ODrive power-up.
- **Arm pose referencing** (planned QOL) captures motor readings against a
  known model reference pose and computes joint offsets so feedback stays
  aligned when startup pose is uncertain.

Commissioning requires electrical calibration. V1 requires initial pose
mapping. Interactive startup jogging and reference capture remain optional
until the later stages land.

## Hardware profile: `manipulator_2026.yaml`

Follow the `kanga_core_description` drivetrain-profile pattern. Last year's arm
URDF/xacro is paired with a versioned YAML profile, initially
`kanga_manipulator_description/config/manipulators/manipulator_2026.yaml`.

Like `drivetrain_2025.yaml`, the profile is flattened into one shared ROS
parameter dictionary. Bringup selects one profile and passes the same validated
physical values to description consumers, controller, drive, joint feedback,
and commissioning. Consumer YAML and node defaults must not duplicate those
values.

The profile owns per-joint model-facing data:

- joint names and canonical order;
- `lower` / `upper` joint limits;
- the prescribed startup pose and initial joint angles;
- positive reduction (`motor_revolutions_per_joint_revolution` or equivalent);
- `invert_direction` eligibility per joint (applied once in `custom_odrive`
  launch, not again in the controller);
- motor identity (`node_id`, serial number reference, namespace);
- commissioned motor velocity and acceleration ceilings; and
- reference-pose joint angles reused by the later startup-jogging workflow.

Controller configuration holds behaviour only: v1 operator-input timeout and
publish rate, followed later by Servo rates, collision checking, operator mode
limits, and command shaping. It must not re-encode physical joint data that
already lives in the profile.

## Command and feedback contracts

V1 establishes a direct joint-velocity path before MoveIt Servo is introduced:

```text
JointTrajectory input -> controller relay -> JointTrajectory output -> drive
```

For every valid, fresh motion input, the relay preserves the joint names,
ordering, velocities, header, and trajectory point without modifying the data.
It performs no kinematics, gearing, direction inversion, smoothing, or Servo
processing. Its only active behaviours are whole-message validation, WHS
inhibition, operator-input timeout, and explicit zero-command publication.

MoveIt Servo becomes a later producer of the same drive-facing velocity
contract for constrained end-effector control. The drive boundary therefore
does not change when Servo is added.

### Normal command stream

Use `trajectory_msgs/msg/JointTrajectory` for both v1 relay input and output.
It accommodates named joints and is also a standard Servo output for the later
controller stage. Core's `WheelVelocityCommand` remains unchanged.

The v1 receiver is a streaming velocity interface:

- one point containing velocities for the complete active joint set;
- values in joint rad/s before transmission conversion;
- joint names determine correspondence; missing, duplicate, or unexpected names
  invalidate the complete command;
- position, effort, and acceleration arrays must be empty, and multi-point
  messages are rejected;
- a valid motion command is published unchanged by the relay;
- both relay and drive validate the complete vector before accepting it;
- the drive uses fresh model-coordinate feedback, configured joint bounds, and
  the commissioned deceleration capability to define a stopping margin; it
  replaces an outward velocity with zero at that margin while still permitting
  motion back toward the allowed range;
- protection is applied to a complete validated command before any motor
  setpoint is sent, so one callback cannot leave axes with a mixture of old and
  new setpoints; and
- normal motion requires fresh feedback, permitted motor states, and released
  inhibition for the controlled arm.

The later startup-jogging path is the only planned mode allowed to bypass these
position bounds. It uses its own low velocity ceilings and command source.

#### Timestamp and timeout semantics

The relay preserves a valid input message's header, but neither controller nor
drive uses that header as its freshness clock. Each records local monotonic
reception time at its own boundary. This also supports the later Servo producer:
Humble Servo deliberately emits zero-stamped trajectories to request immediate
execution and can omit position and acceleration fields. In
[`servo_calcs.cpp`](https://github.com/moveit/moveit2/blob/humble/moveit_ros/moveit_servo/src/servo_calcs.cpp)
Servo sets `joint_trajectory.header.stamp = rclcpp::Time(0)` when publishing
velocity commands. The outgoing message stamp therefore cannot be treated as
the publication time or used for drive-side command timeout.

The controller applies its operator-input timeout from its local reception
clock. The drive independently records local reception time for each valid
controller output and applies its controller-output timeout from that clock.
`points[0].time_from_start` describes the single command point; it does not
enable scheduled or multi-point execution in v1.

The later Servo stage must validate its installed version and output against
this same contract.

#### Annotated v1 example

The joint names and reductions below are symbolic placeholders for documentation
only. They are not commissioned defaults.

```yaml
# trajectory_msgs/JointTrajectory — accepted relay input and unchanged motion output
header:
  stamp: {sec: 0, nanosec: 0}          # permitted; local reception clocks own timeout
  frame_id: base_link                   # ignored by the drive for velocity streaming
joint_names:
  - manipulator_j1_joint
  - manipulator_j2_joint
  - manipulator_j3_joint
  - manipulator_j4_joint
points:
  - time_from_start: {sec: 0, nanosec: 40000000}   # Servo publish horizon; not multi-point scheduling
    velocities: [0.10, -0.05, 0.00, 0.20]          # rad/s in model joint coordinates, pre-reduction
```

Interpretation:

- all four active joints are named exactly once;
- positions, accelerations, and effort must be empty or absent;
- the v1 controller emits the valid message with the same names, ordering, and
  velocity values;
- the drive converts each finite velocity through the selected positive
  reduction, applies the final motor-facing clamp, and transmits motor rad/s to
  `custom_odrive` only when CLOSED_LOOP and motion eligibility permit;
- if any name is unknown or any required velocity is missing or non-finite,
  the entire message is rejected with no partial actuator update.

### Stopping and loss of commands

The manipulator uses an explicit zero-command step when controller output goes
stale. This deliberately differs from the current core actuator, which stops
transmitting immediately and depends on an enabled firmware watchdog.

| Event | Owner and required response |
| --- | --- |
| Operator releases motion control | Input source sends a complete zero-velocity command; controller forwards it immediately |
| Operator input becomes stale | Controller replaces the cached motion input with a complete zero command and continuously publishes zeros while healthy |
| Controller output becomes stale | Drive sends one explicit zero motor-velocity command for every eligible active axis, then stops periodic setpoints so the firmware watchdog can disarm |
| Drive process or CAN transmission fails | Enabled firmware watchdog provides the device-side fallback from the last successfully received setpoint |
| Feedback becomes missing or stale | Drive blocks new nonzero motion, publishes operating status, and follows the same explicit-zero/fallback path where communication permits |
| WHS asserts inhibition | Existing `/drivestop` enforcement takes precedence and requests IDLE regardless of either command stream |

Three independent durations must be named and configured:

- `operator_input_timeout_s`, owned by the controller;
- `joint_command_timeout_s`, owned by the drive; and
- the commissioned ODrive `watchdog_timeout`, owned by the motor configuration.

If the operator input source disappears while the controller remains healthy,
a nonzero request may remain until `operator_input_timeout_s`, after which the
controller's zero stream begins. The command response bound is therefore the
input timeout plus controller scheduling, CAN delivery, and physical
deceleration. The drive timeout and watchdog do not add to this healthy path
because the drive continues receiving explicit zeros.

If controller output disappears while the drive and CAN path remain healthy,
the drive attempts zero at `joint_command_timeout_s`; because that final
setpoint feeds the ODrive watchdog, IDLE may occur up to one additional
`watchdog_timeout` later. Its disarm bound is therefore the drive timeout plus
the watchdog timeout, scheduling, and CAN latency. Physical stopping also
includes the commissioned velocity-ramp deceleration. If the drive or CAN path
fails before the explicit zero arrives, the watchdog instead expires from the
last successfully delivered setpoint.

For commissioning, also test the conservative compounded sequence in which the
input remains nonzero for the full operator timeout and controller output is
then lost: the upper bound from last operator input to firmware disarm is
`operator_input_timeout_s + joint_command_timeout_s + watchdog_timeout`, plus
scheduling and CAN latency. This bound is deliberately conservative; a healthy
controller publishes zeros after its own timeout and stops the arm earlier.

The selected timeout values must preserve that ordering and document the
resulting worst-case response before physical operation. The current candidates
are a 0.5 s drive timeout and a 0.5–1.0 s firmware watchdog; they are not final
until bench validation. The operator-input timeout is selected with the input
mapping in the v1 relay stage.

Zero velocity, ODrive IDLE, loss of torque, and a physically stationary arm are
not equivalent states. J2–J4 bench behaviour on watchdog disarm must be measured
during physical bringup.

### Feedback

Normal measured-state interface:

- `sensor_msgs/msg/JointState` is the normal measured-state interface;
- command and feedback directions match `manipulator_2026.yaml` and the URDF;
- v1 positions use the prescribed startup angles from the selected profile;
- joint position and measured velocity are available for all controlled joints
  before normal motion is eligible;
- missing or stale measurements are exposed through operating status rather
  than concealed by refreshed timestamps; and
- one physical or simulated source owns the active feedback interface.

The current `custom_odrive` `ControllerStatus` message has no measurement
timestamp or explicit reboot/session identifier. PR3 must establish the
evidence used for freshness. Do not promise reliable reset detection solely
from an unexplained position jump.

For v1, the operator places the arm in the prescribed pose before ODrive
power-up. With `motor_position` expressed as the direction-normalised motor
displacement in radians since that ODrive startup, the drive publishes:

```text
joint_position = initial_joint_angle + motor_position / reduction
```

`initial_joint_angle` comes from the selected description profile. A ROS node
restart must continue using the same ODrive startup-relative reading; it must
not treat the motor's position at node restart as a new zero. An ODrive reboot
invalidates the prior coordinate mapping and requires the prescribed physical
startup procedure again. PR3 must define how that condition is detected or how
normal motion remains inhibited until the procedure is repeated.

When the optional startup-jogging stage lands, captured motor readings and
reference offsets replace the simple startup mapping through the workflow under
[Startup referencing (planned QOL)](#startup-referencing-planned-qol).

## Migration evidence and dependencies

### Component inventory

Inventory from the pinned historical commit. Competition or hardware validation
status is recorded where known; otherwise it is explicitly unknown.

| Historical component | Source (commit `8b0c053`) | Destination / disposition | Validation status |
| --- | --- | --- | --- |
| Arm and tool URDF/xacro/meshes | `kanga_arm/kanga_arm_description/`, `kanga_description/urdf/payloads/arm/` | Selective import into `kanga_manipulator_description` paired with `manipulator_2026.yaml` in PR2 | Not yet physically validated in the new workspace |
| Mixed arm configuration YAML | `kanga_arm/kanga_arm_description/config/kanga_arm_config.yaml` | Extract physical data, including the historical startup angles, into `manipulator_2026.yaml`; separate controller behaviour | Historical values require PR2 review |
| Motor IDs and reductions | `kanga_arm/kanga_arm_drive/config/odrive_node_ids_arm.yaml` | Per-joint Fibre overlays in PR3; not authoritative commissioned values | Unknown competition compatibility |
| Command mapper | `kanga_arm/kanga_arm_drive/src/arm_command_mapper.cpp` | Replace with core-style joint actuator in PR3 | Superseded integration pattern |
| Feedback bridge | `kanga_arm/kanga_arm_drive/src/arm_feedback_bridge.cpp` | Replace with core-style joint feedback publisher plus freshness rules | Known sign problems (see below) |
| Calculated IK / world-space controller | `kanga_arm/kanga_arm_controller/src/kanga_arm_controller.cpp` | Do not migrate; replace with MoveIt Servo in PR6 | N/A |
| Joint relay and control mux | `joint_control_relay.cpp`, `joint_desired_control_mux.cpp` | Preserve applicable operator requirements in PR5–PR6 | Behaviour reference only |
| ESP32 firmware variants | `kanga_arm/kanga_arm_esp32/Arm_RTOS/` | `kanga_manipulator_microcontroller`; wrist deferred | Wrist sensing not part of initial four-axis milestone |
| Legacy simulation and launch files | `kanga_arm/kanga_arm_simulation/`, bringup launches | Reference requirements for PR4 simulation; no wholesale port | Raisim-based; not competition-validated in this tree |
| Scoop description | `scoop_tool_*` parameters | Excluded from supported configurations | Historical only |

#### Historical sign problem

The old stack applied direction correction in multiple independent places.
Values from those layers cannot be copied into a single `invert_direction`
flag without physical verification.

| Layer | Historical mechanism | Example from `8b0c053` |
| --- | --- | --- |
| Controller | `joint_velocity_invert` per joint | `[true, false, true, false, false]` in `kanga_arm_config.yaml` |
| Command mapper | per-axis `invert` before motor command | `invert: true` on several axes in `odrive_node_ids_arm.yaml` |
| Feedback bridge | separate `encoder_invert`, defaulting to `invert` when omitted | mixed `encoder_invert` overrides in the same file |
| Simulation | `joint_encoder_invert` array | `[true, false, true, false, false]` in `simulation.yaml` |

The new architecture configures mounting inversion once in `custom_odrive`,
records the result in `manipulator_2026.yaml`, and verifies positive motion and
feedback against every model joint axis during PR2 and physical integration.

### Staged branches and pull requests

Each row is a review boundary. **May start** indicates when design or
scaffolding work can begin; **Depends on** lists what must be complete before
that PR can merge.

| Stage | Suggested branch | Deliverable | May start | Depends on | Completion criterion |
| --- | --- | --- | --- | --- | --- |
| 1 | `docs/manipulator-foundation` | Architecture, migration policy, interfaces, state ownership, staged plan, and open validation items | — | — | Agreed, internally consistent foundation with uncertainties assigned to a stage |
| 2 | `feat/manipulator-description` | Arm/tool URDF, `manipulator_2026.yaml`, joint conventions, and profile validation | Stage 1 | Stage 1 | Validated description package with one hardware profile |
| 3 | `feat/manipulator-drive-foundation` | Drive package mirroring core drive: per-joint Fibre configs, commissioning, joint actuator, position-bound enforcement, initial-angle feedback mapping, explicit timeout zero, enabled watchdog, and CLOSED_LOOP gating | Stage 2 | Stage 2 | Four-axis drive launches, commissions, converts units, applies bounds, and publishes fresh model-coordinate joint feedback |
| 4 | `feat/manipulator-simulation` | Simulated drive, feedback, timeout, and watchdog behaviour for controller development | Stages 1–2 | Stages 1–2 | Simulated boundary matches drive interfaces |
| 5 | `feat/manipulator-joint-relay` | Literal velocity-only `JointTrajectory` relay, operator-input timeout, zero stream, WHS handling, and simulated joint control | Stage 4 | Stages 2 and 4 | Valid motion data passes through unchanged and joint-only control works in simulation |
| 6 | `feat/manipulator-tool-control` | MoveIt Servo base-yaw and constrained planar end-effector mode, safe source switching, and collision/singularity validation | Stage 5 | Stage 5 | Servo produces the accepted drive contract and end-effector mode is validated in simulation |
| 7 | `feat/manipulator-physical-bringup` | Physical joint-only composition, measured corrections, timeout/watchdog validation, and supported operating procedure | Stage 3 | Stages 3 and 5 | Literal-relay joint control plus stop, watchdog, IDLE, and CAN-loss behaviour are bench-recorded without requiring Servo |
| 8 | `feat/manipulator-referencing` | Optional startup state machine, offset capture, and referenced `JointState` | Stage 7 | Stage 7 | Reference workflow available when startup pose is uncertain |
| 9 | `feat/manipulator-startup-ui` | Basestation reference workflow and held-enable joystick alignment | Stage 8 | Stage 8 | Operator QOL alignment against simulated or physical drive |

Simulation scaffolding can begin after the model and interface agreement in
Stages 1–2. Joint-only physical bringup depends on the drive and relay, not on
MoveIt Servo or the referencing QOL stages. Servo development can proceed
against simulation and receive its own later physical-validation PR after
Stages 6 and 7. Any necessary generic `custom_odrive` API improvement is a
separate vendor change and pin update.

After the foundation and description merge, simulation and controller work can
proceed while drive commissioning is finalised. Merge each reviewed slice into
`develop`; promote validated milestones from `develop` to `main` through the
repository's normal release process.

Physical Servo validation, wrist encoder feedback and closed-loop wrist
control, additional physical tools, planned trajectory execution, and startup
referencing UI are separate follow-on work. They are not acceptance requirements
for the initial literal-relay four-ODrive-joint system.

### Outstanding evidence and owning stages

| Outstanding evidence | Owning stage | Needed before |
| --- | --- | --- |
| Geometry, axes, reductions, limits, directions, and prescribed initial angles in `manipulator_2026.yaml` | PR2, verified during PR7 | Declaring the physical model supported |
| Per-joint motor identity, Fibre overlays, and commissioning | PR3 | Commissioning the arm |
| Encoder freshness evidence | PR3 | Physical Servo integration |
| Final watchdog timeout (0.5 vs 1.0 s) and IDLE behaviour on J2–J4 | PR3, bench-recorded in PR7 | Declaring supported physical stop behaviour |
| Operator-input timeout and literal relay behaviour | PR5 | Joint-only control acceptance |
| Exact installed Servo version and stream behaviour | PR6 | Servo/drive integration acceptance |
| Joystick selection and held-enable mapping | PR9 | Operator alignment QOL only |
| Reference pose, stationary tolerance, and alignment speeds | PR8–PR9 | Referencing QOL only |
| Wrist sensing and actuation | Later wrist milestone | Five-axis operation |

## Startup referencing (planned QOL)

This section documents the optional startup-jogging workflow. It is not
required for the initial four-joint system because v1 maps feedback from the
prescribed physical power-up pose and configured initial joint angles.

The arm has no absolute multi-turn joint reference across ODrive reboots.
Referencing maps arbitrary startup motor readings to model coordinates when
manual posing is inconvenient.

Normal controller commands and alignment commands must be distinguishable at
the drive boundary when this stage is implemented. The drive selects which
source is eligible. Being referenced does not automatically enable motors or
override WHS.

### State transition table

| Situation | Required behaviour |
| --- | --- |
| Startup-jogging mode requested | Unreferenced; normal commands blocked while the optional workflow is active |
| Operator confirms an already-correct pose | Capture fresh stationary readings and establish reference |
| Operator requests alignment | Accept only the restricted alignment input |
| Alignment control released or input lost | Stop alignment motion; remain unreferenced |
| Alignment cancelled | Return to unreferenced with no active command |
| Alignment confirmed | Capture reference, discard previous commands, restore normal protections |
| Reference continuity lost | Invalidate reference and block normal motion |
| WHS asserted | Inhibit motion regardless of reference or selected mode |

Alignment bypasses position bounds and pose-dependent Servo collision checks
because joint position is not yet trustworthy. It continues to enforce WHS,
ODrive faults and axis eligibility, command freshness, finite-value checks,
alignment velocity ceilings, and the final motor clamp.

Reference confirmation requires neutral operator controls plus fresh,
stationary feedback for every controlled joint. For each joint the drive
captures the current direction-normalised motor position and calculates:

```text
q = q_reference + (motor_position - captured_motor_position) / reduction
```

The reference angle `q_reference` need not be zero. It is the model joint angle
defined for the confirmed pose in `manipulator_2026.yaml`.

### Worked reference-capture example

Assume one joint with `q_reference = 0.30 rad`, `reduction = 50.0`, and a motor
reading of `12.0 rad` when alignment begins. The operator jogs it to the known
reference pose, where the motor reads `13.5 rad`, and confirms there. Capture
records `captured_motor = 13.5 rad`:

```text
q_measured = 0.30 + (13.5 - 13.5) / 50.0 = 0.30 rad
```

The operator does not return the motor to its startup reading. Confirmation
associates the current `13.5 rad` motor reading with the known `0.30 rad` model
angle.

After confirmation, if the motor later reads `14.5 rad`:

```text
q_measured = 0.30 + (14.5 - 13.5) / 50.0 = 0.32 rad
```

## Validation requirements

Offline and simulated tests must establish:

- positive command and feedback directions match every URDF joint axis and
  `manipulator_2026.yaml` entry;
- radians, motor turns/radians, reductions, initial angles, and limits are
  converted exactly once;
- valid v1 motion messages retain identical names, ordering, headers, points,
  and velocity values through the controller relay;
- malformed, partial, non-finite, stale, and unsupported trajectory commands
  produce no partial actuator update;
- stale operator input produces a continuous controller zero stream;
- stale controller output makes drive attempt an explicit zero before stopping
  setpoint transmission and allowing watchdog disarm in simulation;
- simulation and physical drive expose the same controller-facing command,
  feedback, timeout, and inhibit behaviour.

When the referencing QOL stages land, additionally validate:

- normal commands cannot move an unreferenced arm when referencing is enabled;
- alignment moves only its selected joint and stops on held-enable release,
  stale input, joystick loss, WHS, feedback loss, or motor fault;
- reference capture works after arbitrary startup readings and alignment
  movement, and is invalidated after a simulated encoder reset; and
- confirmation and mode changes cannot replay queued motion.

Physical bench testing must validate direction, reduction, initial-angle
mapping, per-joint hard limits, the three timeout layers, CAN-loss recovery,
watchdog timeout, ramped stopping time, and per-joint behaviour when an ODrive
enters IDLE. It must verify the operator-provided information that J2–J4 are
non-backdrivable and gravity does not meaningfully drive J1 or the later J5.

## PR1 review and acceptance

The foundation document contains the detailed agreement. Package READMEs
summarise ownership and link here without duplicating the entire specification.

Before PR1 is ready for review:

- mark future functionality consistently as planned;
- verify each package responsibility has one clear owner;
- check the message example against the literal relay and later Servo output
  contracts;
- walk through command loss, watchdog disarm, and mode switching on paper;
- confirm every hardware-dependent uncertainty has an owning stage and
  acceptance gate;
- verify relative links, historical source references, Markdown formatting, and
  whitespace;
- run the repository's existing `repo-check` checks; no ROS build or hardware
  test is needed to validate documentation-only changes; and
- confirm the diff contains only documentation and preserves the existing
  implementation.

PR1 does not implement manipulator runtime capability or hardware-qualify any
behaviour.
