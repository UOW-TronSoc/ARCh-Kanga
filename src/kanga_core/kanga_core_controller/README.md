# kanga_core_controller

Turns “drive the robot this way” into “spin each wheel at this speed”.

If you are new to ROS: this package is a **node** that listens on `/cmd_vel`
and publishes one atomic four-wheel command on
`/wheel_joint_velocity_command`. `kanga_core_drive` converts those joint
speeds for the physical motors.

```text
  /cmd_vel  --->  wheel_command_mapper  --->  /wheel_joint_velocity_command
   (Twist)         (this package)              (four wheel-joint rad/s values)
```

## What lives where

| Package | Job |
|---------|-----|
| `kanga_core_drive` | Apply the selected reduction and motor safety limit, start ODrives, calibrate/save, enter CLOSED_LOOP, publish wheel JointState |
| `kanga_core_controller` (here) | Map `/cmd_vel` → four wheel speeds, proportionally desaturate them, and keep streaming them |

## How the mapper behaves

1. **Subscribe** to `/cmd_vel` (`geometry_msgs/Twist`).
2. On a **timer** (~50 Hz), convert that twist to four wheel speeds (kinematics).
3. **Uniformly desaturate** the four-wheel vector if any wheel would exceed the
   selected drivetrain's joint-speed capability. Ratios are preserved: a
   `[50%, 150%]` mix becomes `[33.3%, 100%]`, not `[50%, 100%]`.
4. **Publish** all four results together as one `WheelVelocityCommand`. The
   controller does not perform gearbox conversion or know ODrive/CAN units.
5. If `/cmd_vel` stops for longer than `cmd_vel_timeout_s`, keep publishing
   zero wheel-joint speed. The drive layer then keeps stopped CLOSED_LOOP axes
   fed without masking a failed controller process.

This node does **not** invert wheel signs, change axis state, or handle e-stop —
those are single-owner elsewhere (`invert_direction` only in `drive.launch.py`,
`set_closed_loop` on `drive_manager`, `/drivestop`).

Physical inputs come from the selected `kanga_core_description` drivetrain
profile. The current profile uses a nominal **0.230 m** wheel diameter to the
bottom of the grousers. The loader derives wheel radius and wheel-centre
geometry from the measured outside wheel envelope. Field testing may later
refine the loaded rolling radius through an explicit profile override.

The wheels are not mecanum wheels. The current transform preserves the legacy
51° angled-grouser model, which provides only limited holonomic behaviour. A
future controller mode must allow lateral/holonomic mixing to be disabled for
normal skid-steer-style operation.

Body velocity changes use one shared transition fraction before conversion to
wheel speeds, so forward and yaw mixing cannot outrun each other. The initial
limits are `0.5 m/s²` for translation and `0.75 rad/s²` for yaw. The resulting
wheel vector is also limited uniformly by the joint acceleration derived from
the selected drivetrain's motor ramp and reduction. A complete stop bypasses
both software ramps, and an overall reversal commands zero before accelerating
in the opposite direction.

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
ros2 topic echo /wheel_joint_velocity_command --once  # four joint rad/s values
ros2 topic echo /wheel_fl/control_message --once      # FL motor rad/s from drive
```

## Configuration

Controller behaviour is in [`config/controller.yaml`](config/controller.yaml):

- `cmd_vel_timeout_s`: how long before a quiet `/cmd_vel` becomes “stop”
- `max_linear_acceleration_m_s2`: traction limit for increasing body speed
- `max_angular_acceleration_rad_s2`: traction limit for increasing yaw speed
- `publish_rate_hz`: how often wheel-joint commands are published

Do not add physical geometry or drivetrain limits there. Those live once in a
versioned profile under `kanga_core_description/config/drivetrains/` and are
injected by `controller.launch.py`.

## Code map (for reading the source)

| File | What it is |
|------|------------|
| `include/.../kinematics.hpp` + `src/kinematics.cpp` | Testable math using standard ROS messages |
| `include/.../wheel_command_mapper.hpp` + `src/wheel_command_mapper.cpp` | The ROS node |
| `launch/controller.launch.py` | Loads the selected drivetrain profile and starts the node |
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

Math shape comes from the previous competition `kanga_drive` mapper (empirical
grouser angle 51°). The wheels are regular 230 mm × 180 mm wheels with angled
grousers, not mecanum wheels. Old mapper also inverted and auto-requested
CLOSED_LOOP — **do not put those back here**; invert is only
`invert_direction` in drive launch, CLOSED_LOOP is only `drive_manager`.
