# kanga_joy

Shared ROS 2 joystick integration for Kanga.

## Owns

- Shared joystick device integration
- Common joystick input normalisation and mapping interfaces

## Boundary

Manipulator, excavator, science, and drive-specific control policy remains in the owning domain.

This is an architecture placeholder; gamepad teleop will land here later.

## Controller test

The test launch starts ROS 2's standard `joy_node` and a small monitor that
prints changed axes and buttons with their numeric indexes. It is intended for
identifying a controller's layout before adding the final Kanga mapping.

Inside `scripts/docker_shell.bash`, run:

```bash
colcon build --symlink-install --packages-select kanga_joy
source install/setup.bash
ros2 launch kanga_joy controller_test.launch.py
```

The default SDL controller index is `0`. Select another controller when needed:

```bash
ros2 launch kanga_joy controller_test.launch.py device_id:=1
```

Press `Ctrl+C` to finish. Rover runtime must use Linux; Docker development
shells can access the host controller because the development container is
privileged.

## Bench teleop

This launch is deliberately for off-ground development testing. It starts
`joy_node` and maps the Logitech F310 to `/cmd_vel`:

| Input | Command |
|---|---|
| Axis 1 + axis 7 | Forward velocity (`linear.x`) |
| Axis 0 | Sideways velocity (`linear.y`) |
| Axis 3 + axis 6 | Yaw velocity (`angular.z`) |
| Button 0 | Toggle all wheels between CLOSED_LOOP and IDLE |
| Button 1 | Assert the global `/drivestop` latch |
| Button 2 | Release `/drivestop` (does not re-enter CLOSED_LOOP) |
| Button 3 | Clear errors on all four drive wheels |
| Button 7 (hold) | Stop publishing `/cmd_vel` to simulate command loss |

Analogue and D-pad inputs are added and clamped to `-1..1`. The percentages
are scaled by the commented limits in `config/bench_teleop.yaml`.

With `core_drive.launch.py` already running, start the bench controller:

```bash
ros2 launch kanga_joy bench_teleop.launch.py
```

Motion is zero while IDLE, while drivestop is asserted, or if `/joy` becomes
stale. After entering CLOSED_LOOP, all mapped axes must pass through neutral
before motion is enabled. There is intentionally no deadman button in this
bench mapping. Releasing button 7 also requires the axes to pass through
neutral before motion resumes.
