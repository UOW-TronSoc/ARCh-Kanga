# System startup and launch-manager plan

This is the canonical plan for starting, stopping, restarting, and monitoring
reviewed Kanga ROS 2 subsystems from the basestation. It records both the work
already implemented and the remaining roadmap.

## Goal and operator workflow

Routine operation should not require SSH or manually maintained ROS terminals:

```text
Power or activate rover
  -> host performs CAN, device, udev and permission setup
  -> onboard ROS container and launch agent start
  -> separate basestation container starts
  -> operator opens System Startup
  -> operator starts reviewed subsystems as required
  -> process state and, later, ROS health are displayed
```

The launch manager owns subsystem lifecycle and status only. ROS launch files
compose their nodes, while WHS/drivestop remains independent safety authority.

## Deployment architecture

```text
Basestation container                    ROS runtime container
React UI -> FastAPI                      kanga_launch_agent
             |                                  |
             +------ typed ROS services --------+
                                                |
                                         reviewed ros2 launch
                                                |
                                          rover subsystems
```

Kanga uses one ROS runtime plus one basestation container:

| Use | ROS runtime | Basestation | Total |
| --- | --- | --- | --- |
| Development or local simulation | persistent `kanga-dev` | `basestation-server` | 2 |
| Rover production | headless `kanga-onboard` | `basestation-server` | 2 |

`kanga-dev` and `kanga-onboard` are alternatives and must not run as
simultaneous ROS runtimes. The web container never owns ROS processes or
receives `/var/run/docker.sock`; the onboard agent is the sole process owner.

### Development and simulation

```bash
# Terminal 1: create/reuse kanga-dev, then run the agent
./scripts/docker_shell.bash
ros2 launch kanga_launch_agent launch_agent.launch.py

# Terminal 2: enter that same container for diagnostics or simulation
./scripts/docker_shell.bash

# Host terminal: start only the web/API container
./scripts/basestation_up.bash
```

`docker_shell.bash` builds the image when creating the persistent container,
but does not build the ROS workspace. Later calls enter the same container. Use
`docker_dev_down.bash` to stop it. GPU selection on graphical Linux hosts is
made at creation using `KANGA_GPU=auto`, `nvidia`, or `none`.

Simulation can also be started from System Startup as the reviewed `core_sim`
profile. If those or Core sentinel nodes already exist from a manual launch,
the agent reports the overlapping stack as `UNMANAGED` and never controls it.

### Rover production

At boot, the host performs hardware setup and systemd starts the onboard
runtime, then the basestation. `kanga-onboard.service` starts the launch agent.
The agent initially owns no subsystem; Core stays stopped until an allowlisted
request is accepted.

## Trust and command boundary

The browser and FastAPI may submit only a known system id and one fixed action:
`start`, `stop`, or `restart`. They cannot supply an executable, shell command,
launch file, launch argument, environment override, or signal target.

The allowlist in `kanga_launch_agent/profiles.py` owns each complete command and
its external-stack sentinels. Processes start in their own process group.
Shutdown escalates from `SIGINT` to `SIGTERM`, then to `SIGKILL` only after
bounded timeouts.

## Current Core profile

The managed physical profile is `core`. It runs this fixed, headless
production launch:

```text
ros2 launch kanga_core_bringup rover.launch.py
can_interface:=can_core
drivetrain_profile:=drivetrain_2025
motor_limits:=core
initial_drivestop:=true
body_pose_parent_frame:=body_origin
body_pose_child_frame:=base_link
imu_frame_id:=base_link
```

It includes SocketCAN on `can_core`, initially asserted WHS/drivestop, physical
drive and controller nodes, ESP32 `core_can_bridge`, suspension state, headless
joint-state aggregation, `robot_state_publisher`, and the IMU body-pose TF
broadcaster. It excludes RViz, GUI sliders, onboard gamepad control, and all
browser-provided options.

### Suspension encoder and TF

```text
AS5600 suspension encoder
  -> ESP32 CAN frame 812
  -> core_can_bridge
  -> /diff_bar_angle
  -> suspension_joint_state_publisher
  -> /suspension_joint_states
  -> joint_state_publisher
  -> /joint_states
  -> robot_state_publisher
  -> suspension and wheel transforms
```

Encoder zero and scale remain in `core_can_bridge.yaml`.

| Joint | Transform |
| --- | --- |
| `diff_bar_joint` | `kanga_core -> diff_bar` |
| `left_suspension_joint` | `kanga_core -> left_suspension` |
| `right_suspension_joint` | `kanga_core -> right_suspension` |

Wheel transforms remain beneath their respective suspension links.

### IMU topics and TF

```text
ESP32 IMU
  -> CAN frames 820-822
  -> core_can_bridge
       -> /imu/data
       -> /body/pose
       -> /body/twist
```

- `/imu/data` has `frame_id: base_link`.
- `/body/pose` has `frame_id: body_origin`.
- `/body/twist` has `frame_id: base_link`.
- `body_pose_tf_broadcaster` publishes `body_origin -> base_link` orientation.
- Translation is zero because the IMU provides no reliable position.
- TF is identity until the first valid sample, then the last valid orientation
  is republished so it does not expire.

This is a non-authoritative visualization transform. A future localization
system must disable it before owning an authoritative transform to `base_link`,
such as `odom -> base_link`. `imu_frame_id` is separate from
`body_pose_child_frame`, allowing a future measured `base_link -> imu_link`
URDF transform and `imu_frame_id:=imu_link` without changing the CAN bridge.

## Lifecycle contract

| State | Meaning |
| --- | --- |
| `STOPPED` | No owned process and no profile sentinel nodes. |
| `UNMANAGED` | Sentinel nodes exist without an agent-owned process. |
| `STARTING` | Process is within its three-second startup window. |
| `RUNNING` | Owned process is alive; sensor data may still be absent. |
| `STOPPING` | Graceful process-group shutdown is underway. |
| `FAILED` | Launch failed or an owned process exited unexpectedly. |

Rules:

- Start from `STOPPED`, or retry from `FAILED`.
- Stop from `STARTING` or `RUNNING`.
- Restart only from `RUNNING`.
- Reject requests during transitions.
- Never start over, stop, or restart an `UNMANAGED` stack.
- Intentional shutdown becomes `STOPPED`; unexpected exit becomes `FAILED`.

Core sentinels are:

```text
/whs_node
/drive_manager
/wheel_command_mapper
/core_can_bridge
/suspension_joint_state_publisher
/body_pose_tf_broadcaster
```

## Current Core Simulation profile

`core_sim` starts the reviewed Gazebo composition in the ROS container:

```text
ros2 launch kanga_sim core_simulation.launch.py
world:=sand_dunes.sdf
```

Defaults from that launch file remain in force, including the Gazebo GUI. Core
Simulation sentinels are:

```text
/simulation_clock_bridge
/whs_node
/suspension_joint_state_publisher
/body_pose_tf_broadcaster
```

Shared sentinels with `core` prevent starting the physical stack over a running
simulation, and the reverse.

Process state and sensor health stay separate. Health remains `NOT_CHECKED`
until monitoring is implemented, including while a process is `RUNNING`.

## ROS and HTTP interfaces

The onboard agent exposes typed interfaces from `kanga_interfaces`:

- `/launch_manager/list` (`ListManagedLaunches`)
- `/launch_manager/change` (`ChangeManagedLaunch`)

FastAPI exposes only:

```text
GET  /api/systems
POST /api/systems/{system_id}/start
POST /api/systems/{system_id}/stop
POST /api/systems/{system_id}/restart
```

Actions have no command or argument body. All routes use the operator PIN
session when a PIN is configured. An unavailable ROS node/agent returns HTTP
503; an unknown system or rejected transition returns HTTP 409. Polling is the
initial status mechanism. A WebSocket may be added later only if useful.

## React System Startup page

The protected `/systems` page consumes the fixed API. It shows, for every
returned profile:

- label, process state, and independent health state;
- controls derived only from `allowed_actions`;
- transition progress, last error, and connection errors;
- a clear `UNMANAGED` explanation with no controls.

It disables duplicate actions during transitions, periodically refreshes, and
never infers health from process state. Stop and restart ask for confirmation
because they change an owned rover process group. The page never sends a
command, launch file, or argument.

## Adding subsystems

To add Cameras, Manipulator, Science, Sensors, SLAM, Nav2, Autonomy, or another
system:

1. Create and test a reviewed headless high-level ROS launch file.
2. Add one `LaunchProfile` with stable id, label, complete fixed command, and
   distinctive sentinels to `profiles.py` and `PROFILES`.
3. Add manager and launch-contract tests.
4. Verify it appears through the existing ROS service, REST API, and UI.

No new HTTP route, ROS service, or manager code should be needed. Initial
candidates are Core, Cameras, and Manipulator, but a subsystem enters the
allowlist only after its production launch contract is reviewed.

## Dependencies, presets, and health

Dependencies are deferred until multiple profiles exist. The first dependency
implementation should reject a start and list missing prerequisites rather
than automatically starting them.

Later presets may group existing fixed profiles:

- Drive: Core, Battery, Cameras
- Manipulator: Core, Battery, Cameras, Manipulator
- Science: Core, Battery, Cameras, Science
- Autonomous: Core, Sensors, Cameras, localization/SLAM, Nav2, Perception,
  Autonomy
- Full Rover: every required subsystem

Partial-start and rollback semantics must be designed before presets are built.

Health monitoring will independently inspect reviewed nodes, topics, services,
CAN availability, camera streams, sensor heartbeats, and expected rates. It
will distinguish states such as `RUNNING/HEALTHY` and `RUNNING/DEGRADED`
without changing process ownership. Safety reactions belong onboard, not in
the browser.

## Implementation record

This section is the running record of what has actually been added. A checked
item means the code and its hardware-independent validation exist; it does not
claim that the hardware acceptance checks later in this document have passed.

### Completed

- [x] Added the stable physical Core entry point in
  [`rover.launch.py`](../../src/kanga_core/kanga_core_bringup/launch/rover.launch.py).
  It composes SocketCAN, WHS, drive, controller, ESP32 bridge, suspension joint
  states, aggregated joint states, robot state publication, and body-pose TF.
- [x] Added independent `imu_frame_id`, `body_pose_parent_frame`, and
  `body_pose_child_frame` launch arguments while retaining the fixed production
  defaults recorded above.
- [x] Included the suspension encoder path and the differential-bar, left
  suspension, right suspension, and attached wheel transforms in the Core
  launch contract.
- [x] Included the ESP32 IMU topics and the continuously available
  `body_origin -> base_link` visualization transform in the Core contract.
- [x] Added typed launch-manager messages/services to
  [`kanga_interfaces`](../../src/kanga_interfaces/README.md).
- [x] Added the fixed Core profile in
  [`profiles.py`](../../src/kanga_util/kanga_launch_agent/kanga_launch_agent/profiles.py),
  including the reviewed command and external-stack sentinels.
- [x] Added the thread-safe lifecycle/process owner in
  [`manager.py`](../../src/kanga_util/kanga_launch_agent/kanga_launch_agent/manager.py)
  with startup grace, process-group shutdown escalation, unexpected-exit
  monitoring, strict transitions, and `UNMANAGED` protection.
- [x] Added the onboard ROS service node, launch file, executable wrapper, and
  package build/install metadata under
  [`kanga_launch_agent`](../../src/kanga_util/kanga_launch_agent/README.md).
- [x] Added the production systemd unit and onboard Docker/host helpers so the
  launch agent runs inside `kanga-onboard` without exposing the Docker socket to
  the basestation.
- [x] Changed development helpers so repeated `docker_shell.bash` invocations
  enter one persistent `kanga-dev` container rather than creating separate ROS
  runtimes. Added documented `KANGA_GPU` selection.
- [x] Kept `basestation_up.bash` responsible only for the separate web/API
  container.
- [x] Added the basestation ROS clients that list profiles and request only the
  three fixed lifecycle actions.
- [x] Added the fixed FastAPI routes in
  [`launch_api.py`](../../basestation/server/launch_api.py), including PIN
  protection, HTTP 503 for an unavailable agent, and HTTP 409 for rejected
  requests.
- [x] Added manager, Core launch-contract, and ASGI API tests. The API was also
  checked to ensure no arbitrary-command route exists.
- [x] Documented the two-container development and production workflows in the
  root, Docker, basestation, architecture, Core bringup, and launch-agent
  documentation.
- [x] Added the protected React System Startup page at `/systems`. It polls
  `/api/systems`, renders process state and independent health, derives controls
  only from `allowed_actions`, explains `UNMANAGED` stacks, and never infers
  health from process state.

### Remaining

- [ ] Exercise the physical encoder, live ESP32 CAN frames, IMU topics, and TF
  acceptance checks on rover hardware or with representative CAN replay.
- [ ] Confirm on the rover that systemd performs host hardware setup, starts
  `kanga-onboard`, and then makes the basestation available as intended.
- [ ] Add Cameras and Manipulator only after each has a reviewed headless launch
  file, fixed command, and reliable sentinels.
- [ ] Add other subsystem profiles incrementally; do not expose unfinished
  entries in the production allowlist.
- [ ] Add ROS health checks while retaining the separate process-state field.
- [ ] Add explicit dependency validation and missing-prerequisite reporting.
- [ ] Define partial-start and rollback semantics, then add operating presets.
- [x] Added the reviewed Core Simulation profile `core_sim` for
  `kanga_sim/core_simulation.launch.py` with `world:=sand_dunes.sdf`.

### Validation completed so far

- Python lint passes for the launch-manager REST boundary.
- Launch-manager unit tests cover allowed transitions, startup failure,
  unexpected exit, shutdown escalation, and unmanaged-stack behavior.
- Core launch-contract tests verify the required nodes, fixed defaults, and
  sensor/TF integration at launch-description level.
- Basestation ASGI tests cover listing, all three fixed actions, PIN access,
  rejection/unavailability mapping, and the absence of a command endpoint.
- Production static serving falls back to the React entrypoint for `/systems`.
- The basestation Python suite passed in its intended container image at the
  implementation checkpoint.
- Repository whitespace validation passes with `git diff --check`.

## Delivery sequence

1. **Core launch contract — implemented.** Drive, WHS, suspension encoder and
   TF, IMU topics and body-pose TF.
2. **Onboard lifecycle agent — implemented.** Allowlist, process groups,
   transitions, unmanaged detection, typed ROS services.
3. **Separate deployment — implemented.** Persistent dev runtime, production
   onboard runtime, basestation-only container, systemd and helpers.
4. **Basestation REST API — implemented.** Fixed lifecycle routes, PIN and
   rejected/unavailable responses.
5. **React System Startup page — implemented.** Polling, status and controls.
6. **Additional reviewed profiles — incremental.**
7. **ROS health monitoring — deferred.**
8. **Dependency validation — deferred.**
9. **Operating presets — deferred.**
10. **Managed simulation profile — implemented.** `core_sim` runs
    `kanga_sim/core_simulation.launch.py` with `world:=sand_dunes.sdf`.

## Acceptance contract

Current Core and lifecycle acceptance requires:

- physical encoder movement updates `/diff_bar_angle`;
- `/suspension_joint_states` contains the differential bar and both suspension
  joints;
- TF moves the differential bar, suspension links, and attached wheels;
- valid IMU frames produce `/imu/data`, `/body/pose`, and `/body/twist`;
- `/imu/data` uses `base_link` and orientation updates
  `body_origin -> base_link`;
- no conflicting parent transform is published for `base_link`;
- owned processes follow the lifecycle and external stacks are never controlled;
- browser/API callers cannot provide commands or arguments;
- health remains independent and `NOT_CHECKED` until monitoring exists.

Hardware-free testing covers profile commands, transitions, unmanaged sentinel
handling, ROS/HTTP serialization, PIN enforcement, and UI states. Live CAN,
encoder, IMU, and physical TF acceptance requires rover hardware or suitable
CAN replay.
