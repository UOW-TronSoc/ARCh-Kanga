# kanga_core_simulation

Gazebo Fortress hardware boundary for the Kanga rover base. The top-level
`kanga_sim` package provides the standalone world/spawn launch. This package
deliberately replaces `kanga_core_drive`, while preserving
the shared controller, WHS, description, joint-state aggregation, and ROS API:

```text
rover:      kanga_core_controller -> kanga_core_drive      -> ODrive
simulation: kanga_core_controller -> kanga_core_simulation -> Gazebo
```

It does not use `ros2_control`. `CoreHardwareSystem` reads and writes Gazebo
entity/component state directly, and `ros_gz` provides the process, spawn, and
`/clock` integration in the top-level launch. Body orientation follows the same
path as the real robot: the plugin publishes the Game-Rotation-Vector contract
on `/body/pose`, and `body_pose_tf_broadcaster` converts that into
`body_origin -> base_link` for RViz. Suspension feedback is the same: the
plugin publishes only `/diff_bar_angle`, and `suspension_joint_state_publisher`
maps it through the shared kinematics into `/suspension_joint_states`. Gazebo's
`PassiveSuspensionSystem` still uses that kinematics library for physics
constraint torques; it does not own the ROS joint-state topic.

## Run

Build and enter the development image, then build the workspace:

```bash
docker compose -f docker/compose.dev.yaml build
./scripts/docker_shell.bash
./scripts/build_workspace.bash
source install/setup.bash
```

Launch the flat world with the GUI:

```bash
ros2 launch kanga_sim core_simulation.launch.py
```

Headless validation-course examples:

```bash
ros2 launch kanga_sim core_simulation.launch.py \
  gui:=false world:=core_validation.sdf

ros2 launch kanga_sim core_simulation.launch.py \
  gui:=false paused:=true use_rviz:=false
```

The system always starts IDLE. Clear WHS and explicitly enable it before
commanding motion:

```bash
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: false}"
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.25}, angular: {z: 0.0}}" -r 10
```

The launch accepts `world`, `gui`, `paused`, `drivetrain_profile`,
`surface_preset`, `spawn_{x,y,z,roll,pitch,yaw}`, `use_controller`, `use_whs`,
and `use_rviz`. The default settling clearance is 0.02 m.

With a headless simulation running, exercise the graph, QoS, frame, ordering,
50 Hz publication, controller direction mapping, IDLE isolation, forward
motion, drivestop, no-op management services, and explicit IDLE transition.
The checker commands a short forward movement, so use the flat world or clear
space around the spawn pose:

```bash
ros2 run kanga_sim core_simulation_contract_check
```

## Operational interface contract

| Direction | ROS interface | Simulation behaviour |
|---|---|---|
| Input | `/wheel_joint_velocity_command` (`kanga_interfaces/WheelVelocityCommand`) | Atomic FL, BL, BR, FR wheel-joint rad/s |
| Input | `/drivestop` (`std_msgs/Bool`) | Reliable/transient-local; true immediately returns to IDLE; false never re-enables |
| Service | `/drive_manager/set_closed_loop` (`std_srvs/SetBool`) | Explicit IDLE/CLOSED_LOOP transition; enable is rejected while stopped |
| Service | `/drive_manager/clear_errors` (`std_srvs/Trigger`) | Deterministic successful no-op |
| Services | `/drive_manager/calibrate_{fl,bl,br,fr}` (`std_srvs/Trigger`) | Successful no-op; simulation needs no calibration |
| Output | `/wheel_joint_states` (`sensor_msgs/JointState`) | Actual Gazebo positions/velocities in FL, BL, BR, FR order at 50 Hz |
| Output | `/suspension_joint_states` (`sensor_msgs/JointState`) | Produced by `suspension_joint_state_publisher` from `/diff_bar_angle` |
| Output | `/diff_bar_angle` (`std_msgs/Float64`) | Actual Gazebo differential-bar joint angle |
| Output | `/body/pose`, `/body/twist` | IMU-contract stand-in: orientation and angular velocity only; translation/linear marked unavailable |
| Output | `/odom` | Privileged Gazebo ground truth for diagnostics; not used for visualization TF |
| Shared | `/joint_states`, `/robot_description`, `/tf`, `/tf_static` | Aggregator, `robot_state_publisher`, and `body_pose_tf_broadcaster` (`body_origin -> base_link`) |
| Simulation only | `/clock` and Gazebo transport topics | Never required by control or autonomy code directly |

Per-wheel `custom_odrive` telemetry, currents, temperatures, and raw faults are
not emulated. They are hardware-operation details outside the v1 operational
boundary.

## Drive and reset behaviour

The drive system clamps targets to the selected shared drivetrain profile and
uses conservative simulation-only velocity PID gains and an 8 N.m torque cap.
Zero commands actively hold zero velocity in CLOSED_LOOP. IDLE and drivestop
apply no motor effort, so the configured wheel bearing damping determines
coast-down.

A missing four-wheel command for more than 0.5 simulated seconds removes
effort, returns to IDLE, and requires another `set_closed_loop` call. Gazebo
pause freezes the timeout. A backwards clock jump or world reset clears
controller history and unsafe commands.

## Passive suspension

`PassiveSuspensionSystem` reuses the exported nonlinear linkage mapping and its
tested derivative from `kanga_core_microcontroller` for Gazebo physics only. It
enforces `theta_left/right - f(beta)` with stiffness and damping torques and
applies the Jacobian-scaled reaction to `diff_bar_joint`. Torque saturation
scales all three reactions together, preserving virtual-work balance. It never
writes joint positions, has no centring spring, and does not publish ROS
suspension joint states.

The canonical limits remain +/-70 degrees on the differential bar and +/-30
degrees on both suspension pivots. Starting gains, damping, bearing losses, and
torque caps live in `config/core_simulation.yaml`; tune them against the closure
targets of less than 1 degree steady-state and 3 degrees transient error.

## Terrain presets and calibration

`hard_ground`, `compacted_sand`, and `loose_sand` tune friction, contact, and
longitudinal/lateral wheel-slip compliance. They are effective rigid-terrain
models through Fortress's
[WheelSlip system](https://gazebosim.org/api/gazebo/6/WheelSlip_8hh.html), not
deformable soil. `kanga_sim` owns the flat smoke-test world and the course
containing alternating wheel blocks, a berm, incline, and primitive rocks.

`loose_sand` is the project default for every world. Its preliminary values
assume the wheel-local first friction direction is parallel to the axle. The
model uses lateral `mu=0.20`, longitudinal `mu=0.55`, lateral compliance
`0.90`, and longitudinal compliance `0.20`. This deliberately makes lateral
scrub easier than longitudinal slip so the nearly square differential-drive
footprint can turn without unrealistic tyre binding. The flat and validation
world planes also use an isotropic `mu=0.55`; wheel-local settings provide the
directional behaviour at rover contacts.

These are plausible starting values, not measured soil parameters. In
Fortress, higher slip compliance reduces the pre-saturation force slope; it
does not model sinkage, bulldozing, ruts, or displaced soil. The other presets
remain available only as explicit diagnostic overrides.

The smooth cylinder collision is sufficient for basic differential turning,
where wheel spin supplies longitudinal force and lateral compliance permits
scrub. It cannot reproduce the 51-degree physical grousers' discrete soil
engagement or their lateral-force generation. Grouser collision geometry is
therefore important for believable holonomic strafing and obstacle bite, but
adding the detailed CAD mesh would increase contact count without making DART's
rigid surface behave like loose sand. If that fidelity is needed, prefer a
small compound collision made from repeated primitive grouser bars rather than
the full visual mesh.

Before claiming physical fidelity, record and reproduce:

1. incline sliding angle (`mu` starts near `tan(angle)`);
2. drawbar pull and longitudinal wheel slip;
3. lateral drag; and
4. traversal speed and articulation over a measured block or berm.

Change one named preset at a time and retain the raw rover and simulation
measurements. The smooth collision remains 0.125 m radius while the shared
controller currently uses a 0.115 m effective rolling radius. Treat that as a
visible calibration difference. Do not change canonical geometry merely to
hide it. Primitive compound grousers are a later option if obstacle engagement
is demonstrably unrealistic.

Noise, latency, cameras, battery/BMS, payloads, raw IMU diagnostics, low-level
ODrive telemetry, sinkage, ruts, and displaced soil are intentionally deferred.
Body and odometry covariance is zero until measured noise and latency exist.
