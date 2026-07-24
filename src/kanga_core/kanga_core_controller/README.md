# kanga_core_controller

Turns “drive the robot this way” into “spin each wheel at this speed”.

If you are new to ROS: this package is a **node** that listens on a **topic**
(`/cmd_vel`) and publishes commands on other topics
(`/wheel_fl/control_message`, …). The motors themselves are started by
`kanga_core_drive` — this package only sends speed setpoints.

```text
  /cmd_vel  --->  wheel_command_mapper  --->  /wheel_*/control_message
   (Twist)         (this package)              (picked up by ODrive nodes)
```

## What lives where

| Package | Job |
|---------|-----|
| `kanga_core_drive` | Start ODrive nodes, calibrate/save motors, enter CLOSED_LOOP, publish wheel JointState |
| `kanga_core_controller` (here) | Map `/cmd_vel` → four wheel speeds and keep streaming them |

## How the mapper behaves

1. **Subscribe** to `/cmd_vel` (`geometry_msgs/Twist`).
2. On a **timer** (~10 Hz), convert that twist to four wheel speeds (kinematics).
3. **Publish** a `ControlMessage` to each wheel **only if** that wheel’s
   `controller_status.axis_state` is `8` (CLOSED_LOOP).
4. If `/cmd_vel` stops for longer than `cmd_vel_timeout_s`, treat the command
   as zero (stop). We still stream zeros while CLOSED_LOOP so the motor
   watchdog does not trip.

This node does **not** invert wheel signs, change axis state, or handle e-stop —
those are single-owner elsewhere (`invert_direction` only in `drive.launch.py`,
`set_closed_loop` on `drive_manager`, `/drivestop`).

## Try it (on the rover)

```bash
ros2 launch kanga_core_drive drive.launch.py
ros2 launch kanga_core_controller controller.launch.py

ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}}" --rate 10
```

Useful beginner checks:

```bash
ros2 topic list | grep -E 'cmd_vel|control_message|controller_status'
ros2 topic echo /wheel_fl/control_message --once
ros2 topic echo /wheel_fl/controller_status --once
```

## Edit the robot size / limits

Defaults are in [`config/controller.yaml`](config/controller.yaml):

- Footprint: **110 cm long × 89 cm wide** → `half_length: 0.55`, `half_width: 0.445`
- `max_wheel_velocity`: safety clamp per wheel (**22 turns/s = 44π rad/s**)
- `cmd_vel_timeout_s`: how long before a quiet `/cmd_vel` becomes “stop”
- `publish_rate_hz`: how often we stream setpoints (keep ≥ ~10 with a 1 s watchdog)

## Code map (for reading the source)

| File | What it is |
|------|------------|
| `include/.../kinematics.hpp` + `src/kinematics.cpp` | Pure math, no ROS |
| `include/.../wheel_command_mapper.hpp` + `src/wheel_command_mapper.cpp` | The ROS node |
| `launch/controller.launch.py` | Starts the node with the YAML params |
| `test/test_kinematics.cpp` | Offline checks of the math (no hardware) |

## Offline tests (no rover needed)

```bash
./scripts/docker_shell.bash
# inside the container:
./scripts/build_workspace.bash
source install/setup.bash
colcon test --packages-select kanga_core_controller --event-handlers console_direct+
```

## Provenance

Math shape comes from the previous competition `kanga_drive` mapper (roller
angle 51°). Footprint: current chassis 110×89 cm. Old mapper also inverted
and auto-requested CLOSED_LOOP — **do not put those back here**; invert is only
`invert_direction` in drive launch, CLOSED_LOOP is only `drive_manager`.
