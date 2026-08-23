# Docker Dev/Build Setup

This is the reproducible ROS 2 Humble development, hardware integration, and
Gazebo Fortress simulation environment for the Kanga rover.

Fortress is intentionally pinned with ROS 2 Humble on Ubuntu Jammy and is
supported through May 2027. Treat a future ROS/Gazebo migration as one stack
upgrade; do not mix an unsupported Gazebo release into this image. See the
[Gazebo Fortress installation guidance](https://gazebosim.org/docs/fortress/getstarted/).

## Responsibility split

### Docker currently handles

- ROS 2 Humble (`ros:humble-ros-base-jammy`)
- `colcon` and the colcon common extensions
- `rosdep`
- Build tools (`build-essential`, etc.)
- Core ROS message/lib packages used by Kanga (`rclcpp`, `rclpy`, `std_msgs`,
  `geometry_msgs`, `sensor_msgs`, `nav_msgs`, `tf2`, `tf2_ros`, ...)
- CAN debugging tools (`can-utils`, `iproute2`, `net-tools`)
- Gazebo Fortress, its development libraries, and `ros_gz`

### The host still handles

- JetPack / NVIDIA drivers and NVIDIA Container Toolkit
- Docker itself (engine + compose plugin)
- USB-CAN adapter detection
- stable CAN interface naming (`can_core` / `can_payload`) and bitrate setup
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
./scripts/setup_can.bash can_core 250000
./scripts/setup_can.bash can_payload 250000
./scripts/check_can.bash can_core
./scripts/check_can.bash can_payload

docker compose -f docker/compose.can-test.yaml build
docker compose -f docker/compose.can-test.yaml run --rm can-test
```

Inside the container:

```bash
ip -details link show type can
candump can_core -n 10
candump can_payload -n 10
```

Then build the workspace (inside the container):

```bash
./scripts/build_workspace.bash
```

## Opening a general dev shell

```bash
./scripts/docker_shell.bash
# equivalent to:
# docker compose -f docker/compose.dev.yaml run --rm --build kanga-dev
```

The shell helper checks the image build before starting. Docker reuses cached
layers when `Dockerfile.dev` and `apt-packages.txt` have not changed.

From a graphical Linux desktop, the helper also applies
`docker/compose.gui.yaml` automatically. It forwards the current X11 display
and Xauthority cookie so RViz and other Qt applications can open on the host.
Headless and SSH sessions without a usable `DISPLAY` continue with the base
development Compose file only.

The same GUI overlay supports Gazebo. For a headless core simulation, no
display forwarding is required:

```bash
ros2 launch kanga_sim core_simulation.launch.py gui:=false
```

### NVIDIA-accelerated Gazebo GUI

The GUI overlay permits hardware rendering and the NVIDIA overlay selects the
discrete GPU on PRIME / hybrid-graphics laptops. `docker_shell.bash` applies
`docker/compose.nvidia.yaml` automatically when the host driver is working and
Docker has registered the NVIDIA runtime. It no longer forces Mesa's software
renderer.

The NVIDIA driver remains a host responsibility. Install and register NVIDIA
Container Toolkit once on the host:

```bash
./scripts/setup_nvidia_container_toolkit.bash
```

The helper intentionally does not restart Docker because a restart interrupts
all running containers. After closing them, either run
`sudo systemctl restart docker`, or install and restart in one operation with
`./scripts/setup_nvidia_container_toolkit.bash --restart`.

Open a fresh development shell and verify both device passthrough and the
actual OpenGL renderer:

```bash
./scripts/docker_shell.bash
nvidia-smi -L
glxinfo -B | grep -E 'direct rendering|OpenGL vendor|OpenGL renderer'
```

The renderer should contain `NVIDIA`, not `llvmpipe` or `softpipe`. Use
`KANGA_GPU=nvidia ./scripts/docker_shell.bash` to require NVIDIA and fail early
if it is unavailable. Use `KANGA_GPU=none` to disable the NVIDIA overlay and
allow the host/Mesa renderer to be selected instead.

NVIDIA's setup follows the
[official Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),
and the Compose overlay follows Docker's
[GPU access guidance](https://docs.docker.com/compose/how-tos/gpu-support/).

The image uses a non-root `kanga` user whose UID and GID are matched to the host
by `docker_shell.bash`. This prevents colcon's bind-mounted `build/`, `install/`,
and `log/` directories from becoming root-owned. When building the image
directly on a host whose UID/GID are not `1000`, pass them explicitly:

```bash
KANGA_UID="$(id -u)" KANGA_GID="$(id -g)" \
  docker compose -f docker/compose.dev.yaml build
```

Reusable operating-system dependencies are listed in
`docker/apt-packages.txt`. Add a package there and rebuild the image.

Python packages used inside the dev container (e.g. `odrive` for Fibre-over-CAN
commissioning) are listed in `docker/pip-packages.txt` and installed during the
image build. Rebuild after changing either file:

```bash
docker compose -f docker/compose.dev.yaml build
```

Declare ROS package dependencies in the relevant `package.xml` so rosdep can
resolve them.

## ODrive Fibre commissioning

`commission_wheels` and `custom_odrive commission` run inside the dev container
like the rest of the stack.

`docker_shell.bash` bind-mounts the host odrivetool cache at
`/home/kanga/.cache/odrivetool`. Without it, each disposable `docker compose run
--rm` shell must re-download the firmware device descriptor over CAN; on a busy
bus that can look like a serial discovery failure.

```bash
# default: ~/.cache/odrivetool on the host
./scripts/docker_shell.bash

# optional override:
KANGA_ODRIVE_CACHE=/path/to/odrivetool-cache ./scripts/docker_shell.bash
```

Inside the container:

```bash
ros2 run kanga_core_drive commission_wheels -- --wheels fl --can can0 --save
# with drive.launch running (parks /wheel_fl via ROS):
ros2 run kanga_core_drive commission_wheels -- --wheels fl --can can0 --save
# drive.launch stopped:
ros2 run kanga_core_drive commission_wheels -- --wheels fl --can can0 --save --bench
```

## Important

If CAN does not work **on the host**, Docker is **not** the issue yet. Always get
a native `candump` working before debugging the container. See
[`can.md`](can.md) for CAN-specific troubleshooting.
