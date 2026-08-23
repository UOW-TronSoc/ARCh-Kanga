# Basestation install

The basestation is one HTTP server that joins the ROS 2 graph via `rclpy`. It
lives under `basestation/` (not under `src/`) and shares the host network /
`ROS_DOMAIN_ID` with the ROS dev container. Everything — operator page, API,
and ROS node — runs from a single service on port 8000. Design and progress:
[basestation/REDESIGN_PLAN.md](../../basestation/REDESIGN_PLAN.md).

## Responsibility split

### Docker handles

- Basestation Python image (`ros:humble-ros-base-jammy` + pip deps)
- Sourcing `/opt/ros/humble` and `/workspace/install` in the entrypoint

### The host still handles

- Docker Engine + Compose
- Building the ROS workspace (`install/`) via Path A
- SocketCAN / drivers when testing against hardware (see [docker.md](docker.md)
  and [can.md](can.md))

## Prerequisites

Docker access on the host: your user must be able to talk to the Docker engine
(typically membership in the `docker` group, then a fresh login).

From the repository root, build the workspace at least once:

```bash
docker compose -f docker/compose.dev.yaml build
./scripts/docker_shell.bash
# inside the container:
./scripts/build_workspace.bash
```

`./scripts/basestation_up.bash` exits with an error if `install/setup.bash` is
missing.

## Start basestation

```bash
./scripts/basestation_up.bash
```

| URL | What you get |
| --- | --- |
| http://localhost:8000/ | React operator UI (PIN → Drive, Logs) |
| http://localhost:8000/health | Server + ROS node status as JSON |

Stop:

```bash
./scripts/basestation_down.bash
```

## Workflows

- **Path A (ROS only):** `docker_shell.bash` + `build_workspace.bash`
- **Path B (basestation):** `basestation_up.bash` after `install/` exists
- **Path C (control test):** Path A with nodes running, then Path B on the same
  machine and `ROS_DOMAIN_ID`

Basestation services are ROS participants. “Path B” only means you do not need
an interactive ROS shell open; the containers still use Humble and `install/`.

## Shared contract

Do not copy generated message code into `basestation/`. Message definitions live
in `src/kanga_interfaces`, become importable after `colcon build`, and are
exposed to basestation containers by sourcing `install/setup.bash`.
