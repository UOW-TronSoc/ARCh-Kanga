# Docker Dev/Build Setup (Initial)

This is the **initial** Docker development/build setup for the Kanga rover. It is
**not** a full rover runtime setup yet. The goal right now is to get a reproducible
ROS 2 Humble build environment and to verify that CAN works inside a container
before we move on to hardware bring-up.

## Responsibility split

### Docker currently handles

- ROS 2 Humble (`ros:humble-ros-base-jammy`)
- `colcon` and the colcon common extensions
- `rosdep`
- Build tools (`build-essential`, etc.)
- Core ROS message/lib packages used by Kanga (`rclcpp`, `rclpy`, `std_msgs`,
  `geometry_msgs`, `sensor_msgs`, `nav_msgs`, `tf2`, `tf2_ros`, ...)
- CAN debugging tools (`can-utils`, `iproute2`, `net-tools`)

### The host still handles

- JetPack / NVIDIA drivers
- Docker itself (engine + compose plugin)
- USB-CAN adapter detection
- CAN interface setup (`can0` / `can1` creation + bitrate)
- udev rules
- Networking and SSH
- ZED SDK (initially, until added to the image later)
- All physical hardware access

The host creates the CAN interfaces; Docker uses `network_mode: host` to reach
them through SocketCAN. Docker is **not** responsible for creating CAN interfaces
yet.

## First validation steps

Run from the repo root **on the host**:

```bash
./scripts/check_devices.bash
./scripts/setup_can.bash can0 500000
./scripts/check_can.bash can0

docker compose -f docker/compose.can-test.yaml build
docker compose -f docker/compose.can-test.yaml run --rm can-test
```

Inside the container:

```bash
ip -details link show type can
candump can0 -n 10
```

Then build the workspace (inside the container):

```bash
./scripts/build_workspace.bash
```

## Opening a general dev shell

```bash
./scripts/docker_shell.bash
# equivalent to:
# docker compose -f docker/compose.dev.yaml run --rm kanga-dev
```

## Important

If CAN does not work **on the host**, Docker is **not** the issue yet. Always get
a native `candump` working before debugging the container. See
[`can.md`](can.md) for CAN-specific troubleshooting.
