# Basestation install (scaffold)

Operator HTTP services that join the ROS 2 graph via `rclpy`. They live under
`basestation/` (not under `src/`) and share the host network / `ROS_DOMAIN_ID`
with the ROS dev container.

This is the **initial** basestation Docker setup: health stubs on the production
ports. Real Django / FastAPI / Vite code will replace the stubs later.

## Responsibility split

### Docker handles

- Basestation Python image (`ros:humble-ros-base-jammy` + pip deps)
- Static scaffold frontend (nginx on port 3000)
- Sourcing `/opt/ros/humble` and `/workspace/install` in Python entrypoints

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

| URL | Service |
| --- | --- |
| http://localhost:3000/ | Scaffold frontend |
| http://localhost:8000/health | Django-port stub |
| http://localhost:8001/health | Arm FastAPI stub |
| http://localhost:8080/health | cmd_vel FastAPI stub |

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
