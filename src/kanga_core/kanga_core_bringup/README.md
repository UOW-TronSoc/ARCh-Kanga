# kanga_core_bringup

Standalone launch entry points for the physical Kanga rover base (no payload).

This package only **composes** other core packages. It does not own drive math,
Fibre configs, or battery logic.

## Production rover bringup

`rover.launch.py` is the stable, headless entry point for the physical rover.
It starts WHS asserted, the physical drive/controller stack, the shared
SocketCAN and ESP32 bridges, the AS5600 differential-bar encoder to suspension
JointState pipeline, robot-state publishing, and the IMU orientation
`body_origin -> base_link` visualization transform. It deliberately excludes
RViz, GUI joint sliders, and onboard gamepad control:

```bash
ros2 launch kanga_core_bringup rover.launch.py
```

The ESP32 bridge publishes `imu/data` in `base_link` by default. The IMU frame
is a separate launch argument so a measured fixed `base_link -> imu_link`
transform can be added later without changing the CAN bridge:

```bash
ros2 launch kanga_core_bringup rover.launch.py imu_frame_id:=imu_link
```

Do not run the IMU-derived `body_origin -> base_link` broadcaster alongside a
localisation system that also parents `base_link`. The future localisation
bringup must pass `use_body_pose_tf:=false` and replace this non-authoritative
visualization transform.

## Unified development bringup

`core.launch.py` is the development and testing entry point for the available
core stack. It currently composes:

- the `core_2026` description and `robot_state_publisher`;
- the sole `kanga_whs` software motion-inhibit authority;
- the physical ODrive stack;
- the `/cmd_vel` wheel controller;
- differential-bar suspension state mapping;
- optional visualization of ESP32 `body/pose` as TF;
- optional wheel/suspension JointState aggregation;
- optional joint sliders and RViz; and
- the existing bench gamepad launch as provisional onboard control.

The shared SocketCAN bridge and ESP32 core CAN bridge are included. Battery
remains deferred. Use `rover.launch.py` for the separate, lightweight
production profile; keep this file useful as a diagnostic and integration
surface.

The ordinary hardware-oriented defaults start WHS in its asserted state, the
shared CAN and ESP32 bridges, drive, controller, description, and suspension
mapping. Joint-state aggregation, its GUI, RViz, and onboard gamepad control
default to off:

```bash
ros2 launch kanga_core_bringup core.launch.py
```

Release the software motion inhibit deliberately after checking the rover is
safe to enable:

```bash
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: false}"
```

`initial_drivestop:=false` is available for controlled hardware-free
development, but should not be used for normal physical bringup.

For a hardware-free suspension/RViz test:

```bash
ros2 launch kanga_core_bringup core.launch.py \
  use_drive:=false \
  use_controller:=false \
  use_joint_state_publisher:=true \
  use_rviz:=true
```

Then publish a simulated +70° differential-bar angle from another sourced
shell:

```bash
ros2 topic pub /diff_bar_angle std_msgs/msg/Float64 \
  "{data: 1.2217304763960306}" --once
```

The headless joint-state publisher merges `wheel_joint_states` and
`suspension_joint_states` into the visualization-only `/joint_states` topic at
50 Hz. `robot_state_publisher` publishes dynamic TF at up to the same rate.
Subsystem controllers and estimators continue to consume their owning feedback
topics at whatever rate each system requires. To use manual sliders instead,
also pass `use_gui:=true`. The GUI option is ignored when
`use_joint_state_publisher:=false`.

To visualize preliminary ESP32 body pose, start the pose-to-TF adapter. The
core RViz configuration permanently uses `body_origin` as its fixed frame:

```bash
ros2 launch kanga_core_bringup core.launch.py \
  use_drive:=false \
  use_controller:=false \
  use_joint_state_publisher:=true \
  use_body_pose_tf:=true \
  use_rviz:=true
```

The adapter consumes `body/pose`; `body/twist` remains published by the future
CAN bridge but is intentionally unused for now. Do not enable
`use_body_pose_tf` alongside a localisation system that also parents
`base_link`.

With no ESP32 connected, bringup starts in a neutral visual state: the body
transform is identity and the differential-bar and suspension joint positions
are zero. After the first valid body pose, the visualization adapter republishes
that last accepted pose so its dynamic TF does not expire. This is visual state,
not proof that fresh IMU data is arriving; use the source topic timestamp for
freshness and fault handling.

To enable the current local controller test path, connect the gamepad and pass
`use_onboard_control:=true`. This presently includes
`kanga_joy/bench_teleop.launch.py`; it will switch to
`kanga_onboard_control` when that package gains its production implementation.

## Drive-only bringup

`core_drive.launch.py` starts:

1. `kanga_core_drive` `drive.launch.py` — ODrive nodes, `drive_manager`, wheel JointState
2. `kanga_core_controller` `controller.launch.py` — `/cmd_vel` → wheel setpoints

Host must bring up `can_core` first. CLOSED_LOOP is still manual via
`drive_manager`.

```bash
./scripts/docker_shell.bash
# inside:
./scripts/build_workspace.bash
source install/setup.bash

ros2 launch kanga_core_bringup core_drive.launch.py

# then enter CLOSED_LOOP when ready:
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
```

The bringup selects one versioned physical profile and one editable operating
limit config, then passes the same validated effective values to controller,
drive, feedback, and commissioning:

```bash
ros2 launch kanga_core_bringup core_drive.launch.py \
  drivetrain_profile:=drivetrain_2025 \
  motor_limits:=core
```

Add/select a new profile in `kanga_core_description` when the physical
drivetrain changes; do not duplicate its dimensions, reduction, or motor TPS
hard limits in consumer YAML files. Lower normal operating limits in
`kanga_core_description/config/motor_limits/core.yaml`, then rebuild/relaunch
the core stack. Recommission affected motors when their saved ODrive limits
must also change.

---

## Rover test procedure (core drive)

Use this checklist the next time you are at the rover. Work **top to bottom**.
Stop and fix before continuing if a step fails.

**Safety**

- Keep the e-stop / `/drivestop` path in mind.
- **Calibrate with that wheel off the ground** (FULL_CALIBRATION moves the motor).
- Start with small `/cmd_vel` values.
- Prefer jack stands / clear space before CLOSED_LOOP + motion.

### 0. Once per machine (skip if already done)

```bash
# Host — vendor pin (only if custom_ros_odrive is missing under src/vendor/)
vcs import src/vendor < src/vendor/kanga_vendor.repos
# see also: src/vendor/README.md
```

### 1. Host — CAN

```bash
./scripts/setup_can.bash can_core 250000
./scripts/check_can.bash can_core
# optional: candump can_core   # should see ODrive traffic when powered
```

Pass criteria: `can_core` is UP at 250 kbit/s; dump shows activity when drives are on.

### 2. Container — build and source

```bash
./scripts/docker_shell.bash
# inside:
./scripts/build_workspace.bash
source install/setup.bash
```

Pass criteria: build finishes; `ros2 pkg prefix kanga_core_bringup` works.

### 3. First-time Fibre (apply + save configs)

Only when motors are new, configs changed, or NVM was wiped. Sequential; takes a while.

```bash
ros2 run kanga_core_drive commission_wheels -- \
  --wheels all --can can_core --save
```

Pass criteria: each wheel exits 0; no Fibre/serial errors.

### 4. Calibrate (one wheel at a time, off the ground)

CLI:

```bash
ros2 run kanga_core_drive commission_wheels -- \
  --wheels fl --can can_core --calibrate --save
# repeat bl, br, fr as needed
```

Or after bringup is running, via services. Calling a calibration service is the
off-ground acknowledgement for that exact wheel; verify it before pressing
Enter. The service applies config, calibrates, saves to NVRAM, and leaves that
motor disabled:

```bash
ros2 service call /drive_manager/calibrate_fl std_srvs/srv/Trigger "{}"
# calibrate_bl / calibrate_br / calibrate_fr
```

Pass criteria: service/CLI succeeds; wheel completes calibration without faulting.

### 5. Bring up the stack (idle)

```bash
ros2 launch kanga_core_bringup core_drive.launch.py
```

In another container shell (`docker_shell` + `source install/setup.bash`):

```bash
ros2 node list
# expect: drive_manager, wheel_actuator, wheel_command_mapper, wheel_*/can_node, …

ros2 topic list | grep -E 'controller_status|joint_velocity_command|control_message|wheel_joint|cmd_vel'

ros2 topic echo /wheel_fl/controller_status --once
# note axis_state (expect IDLE = 1 before CLOSED_LOOP)
```

Pass criteria: four wheel namespaces alive; status messages flowing; `axis_state` idle.

### 6. Enter CLOSED_LOOP (no motion yet)

Wheels may be on the ground for this step if you are not commanding motion yet.

```bash
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"

ros2 topic echo /wheel_fl/controller_status --once
# axis_state should be 8 (CLOSED_LOOP)
```

Pass criteria: service `success: true`; all four `axis_state == 8`.

If this fails: check CAN, clear faults, retry; do not proceed to motion.

### 7. Confirm mapper streams (still may be zero cmd)

With CLOSED_LOOP on, the controller publishes zero joint commands when
`/cmd_vel` is quiet; drive converts them to motor commands for the watchdog.

```bash
ros2 topic echo /wheel_joint_velocity_command  # all four wheel-joint rad/s values
ros2 topic echo /wheel_fl/control_message      # FL motor-shaft rad/s
# the joint vector and each closed-loop motor command should be ≈0 at ~50 Hz
```

Pass criteria: steady `control_message` on each wheel while CLOSED_LOOP.

### 8. Motion smoke test

Clear space / prefer elevated wheels for first try.

```bash
# small forward pulse (~0.1 m/s chassis twist), then Ctrl-C
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" \
  --rate 10
```

Watch:

```bash
ros2 topic echo /wheel_fl/control_message    # input_vel should leave 0
ros2 topic echo /wheel_joint_velocity_command
ros2 topic echo /wheel_joint_states          # estimates should move
```

Also spot-check invert: left wheels (`fl`/`bl`) use `invert_direction` in
`drive.launch.py` — robot should not fight itself going forward.

Pass criteria: robot (or free wheels) respond in the expected direction; JointState updates.

### 9. Stale `/cmd_vel` → stop

Stop publishing `/cmd_vel` (Ctrl-C the pub). Within ~0.5 s (`cmd_vel_timeout_s`):

```bash
ros2 topic echo /wheel_fl/control_message
# input_vel should return to ~0 while still streaming
```

Pass criteria: commanded velocity goes to zero without leaving CLOSED_LOOP.

### 10. Idle / stop paths

```bash
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: false}"

ros2 topic echo /wheel_fl/controller_status --once
# axis_state back toward IDLE (1)

# control_message should stop (actuator only publishes while CLOSED_LOOP)
```

Also verify global stop if you use it in the field:

```bash
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: true}"
# Confirm every wheel stops, then explicitly release when the area is safe:
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: false}"
```

Pass criteria: idle service succeeds; setpoint stream stops when not CLOSED_LOOP.

### 11. Quick failure log (fill in on the bench)

| Step | Pass? | Notes |
|------|-------|-------|
| 1 CAN | | |
| 2 Build | | |
| 3 Commission save | | |
| 4 Calibrate | | |
| 5 Bringup idle | | |
| 6 CLOSED_LOOP | | |
| 7 Zero stream | | |
| 8 Motion + invert | | |
| 9 Stale stop | | |
| 10 Idle / drivestop | | |

---

## Later

Add battery and the ESP32 CAN bridge to the unified development launch once
those packages have launchable implementations. Keep `core_drive.launch.py`
available for focused drivetrain testing.

## Boundary

`kanga_bringup` composes core + cameras + payload + optional autonomy for the
full rover.
