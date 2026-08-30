# Basestation install

The basestation is one HTTP server that joins the ROS 2 graph via `rclpy`. It
lives under `basestation/` (not under `src/`) and shares the host network /
`ROS_DOMAIN_ID` with the ROS dev container. Everything — operator page, API,
and ROS node — runs from a single service on port 8000. Design and progress:
[basestation/REDESIGN_PLAN.md](../../basestation/REDESIGN_PLAN.md).

## Responsibility split

### Docker handles

- Basestation Python image (`ros:humble-ros-base-jammy` + pip deps)
- Frontend UI build (`node:20` via `./scripts/build_frontend.bash`, and the
  Node stage in `Dockerfile.basestation-python`)
- Sourcing `/opt/ros/humble` and `/workspace/install` in the entrypoint

### The host still handles

- Docker Engine + Compose (no host Node/npm required for Path B)
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

On Linux, `basestation_up.bash` also applies host networking so the server
joins the same ROS graph as other host processes. Docker Desktop on macOS and
Windows runs Linux containers in a VM, so host networking is **not** your
browser's localhost; the default compose file publishes `8000:8000` instead.

| URL | What you get |
| --- | --- |
| http://localhost:8000/ | React operator UI (PIN, Drive, and Logs) |
| http://localhost:8000/health | Server + ROS node status as JSON |

Drive arming on the dashboard: release drivestop (confirmed), then **B0**,
**Space**, or the Drive Input button — closed loop first, then drive input.
Gamepad cannot release drivestop.

Stop:

```bash
./scripts/basestation_down.bash
```

For frontend-only iteration, keep the backend running and start Vite from
`basestation/frontend/` with `npm ci && npm run dev`. Vite normally listens on
port 5173 and proxies API and WebSocket traffic to port 8000.

## Rover (systemd)

After workspace build and a one-time frontend build on the rover:

```bash
./scripts/build_frontend.bash          # or SKIP_FRONTEND_BUILD=1 if already built
sudo ./scripts/basestation_install_service.bash
sudo systemctl enable --now kanga-basestation
```

The compose service uses `restart: unless-stopped`. Boot-time starts skip
frontend rebuild (`SKIP_FRONTEND_BUILD=1`). Edit the unit if the repo path or
robot bringup unit name differs:

```bash
sudo systemctl edit kanga-basestation
```

## Workflows

- **Path A (ROS only):** `docker_shell.bash` + `build_workspace.bash`
- **Path B (basestation):** `basestation_up.bash` after `install/` exists
- **Path C (control test):** Path A with nodes running, then Path B on the same
  machine and `ROS_DOMAIN_ID`

Basestation services are ROS participants. “Path B” only means you do not need
an interactive ROS shell open; the containers still use Humble and `install/`.

## Commissioning mockup

A frontend-only preview is available at `/commissioning`. Its editors, action
buttons, confirmation dialogs, and progress queue use mock data and do not
change files or contact ROS/motors. The agreed backend and hardware behavior is
documented in
[the commissioning page plan](../../basestation/COMMISSIONING_PAGE_PLAN.md).
Until that integration is implemented, use the `kanga_core_drive`
commissioning CLI and per-wheel ROS services documented in that package.

## Shared contract

Do not copy generated message code into `basestation/`. Message definitions live
in `src/kanga_interfaces`, become importable after `colcon build`, and are
exposed to basestation containers by sourcing `install/setup.bash`.
