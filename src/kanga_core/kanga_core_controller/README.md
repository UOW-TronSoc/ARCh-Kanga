# kanga_core_controller

Turns “drive the robot this way” into “spin each wheel at this speed”.

If you are new to ROS: this package is a **node** that listens on a **topic**
(`/cmd_vel`) and publishes wheel-joint commands on other topics
(`/wheel_fl/joint_velocity_command`, …). `kanga_core_drive` converts those
joint speeds for the physical motors.

```text
  /cmd_vel  --->  wheel_command_mapper  --->  /wheel_*/joint_velocity_command
   (Twist)         (this package)              (wheel-joint rad/s to drive)
```

## What lives where

| Package | Job |
|---------|-----|
| `kanga_core_drive` | Apply 50:1 reduction/limits, start ODrives, calibrate/save, enter CLOSED_LOOP, publish wheel JointState |
| `kanga_core_controller` (here) | Map `/cmd_vel` → four wheel speeds and keep streaming them |

## How the mapper behaves

1. **Subscribe** to `/cmd_vel` (`geometry_msgs/Twist`).
2. On a **timer** (~10 Hz), convert that twist to four wheel speeds (kinematics).
3. **Publish** each result as wheel-joint rad/s. The controller has no motor,
   gearbox, ODrive-state, or motor-limit knowledge.
4. If `/cmd_vel` stops for longer than `cmd_vel_timeout_s`, keep publishing
   zero wheel-joint speed. The drive layer then keeps stopped CLOSED_LOOP axes
   fed without masking a failed controller process.

This node does **not** invert wheel signs, change axis state, or handle e-stop —
those are single-owner elsewhere (`invert_direction` only in `drive.launch.py`,
`set_closed_loop` on `drive_manager`, `/drivestop`).

> **Current limitation:** wheel radius is not implemented yet. Directional
> mixing is testable, but `/cmd_vel` linear values are not yet a calibrated
> physical m/s command. The command/limit chain is recorded in the
> [software architecture](../../../docs/architecture/README.md#drive-command-and-limit-model).

## Try it (on the rover)

```bash
ros2 launch kanga_core_drive drive.launch.py
ros2 launch kanga_core_controller controller.launch.py

ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}}" --rate 10
```

Useful beginner checks:

```bash
ros2 topic list | grep -E 'cmd_vel|joint_velocity_command|control_message'
ros2 topic echo /wheel_fl/joint_velocity_command --once  # joint rad/s
ros2 topic echo /wheel_fl/control_message --once          # motor rad/s from drive
```

## Edit the robot size / limits

Defaults are in [`config/controller.yaml`](config/controller.yaml):

- Footprint: **110 cm long × 89 cm wide** → `half_length: 0.55`, `half_width: 0.445`
- `cmd_vel_timeout_s`: how long before a quiet `/cmd_vel` becomes “stop”
- `publish_rate_hz`: how often wheel-joint commands are published

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
