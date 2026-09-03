# Basestation install

The basestation is one HTTP server that joins the ROS 2 graph via `rclpy`. It
lives under `basestation/` (not under `src/`) and shares the host network /
`ROS_DOMAIN_ID` with the ROS dev container. Everything — operator page, API,
and ROS node — runs from a single service on port 8000. Design and progress:
[basestation/REDESIGN_PLAN.md](../../basestation/REDESIGN_PLAN.md).

Rover launch processes do not run in this container. The active ROS runtime
(`kanga-dev` during development or `kanga-onboard` in production) runs
`kanga_launch_agent`, and FastAPI talks to it over ROS services. The basestation
has neither a local launch subprocess nor launch ownership via the Docker
socket. It does mount the host Docker socket **read-only** so the Logs page
can follow PID-1 `docker logs` of `basestation-server` and the onboard
runtime. That is log follow only; FastAPI does not compose, run, or exec
containers. See [the logs plan](../logging/README.md).

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
./scripts/docker_shell.bash
# inside the container:
./scripts/build_workspace.bash
```

`docker_shell.bash` builds/updates the Docker image when creating the runtime.
`build_workspace.bash` is the separate colcon workspace build.

`./scripts/basestation_up.bash` exits with an error if `install/setup.bash` is
missing.

## Start basestation

```bash
./scripts/basestation_up.bash
```

This command starts only the basestation. During development, start the launch
agent inside the existing `kanga-dev` container. On the rover, systemd starts
the separate production `kanga-onboard` container before the basestation.

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
./scripts/onboard_up.bash              # builds the no-simulation image once
sudo ./scripts/onboard_install_service.bash
sudo ./scripts/basestation_install_service.bash
sudo systemctl enable --now kanga-onboard kanga-basestation
```

The compose service uses `restart: unless-stopped`. Boot-time starts skip
image and frontend rebuilds. The host configures `can_core` before starting the
agent, but a missing adapter does not prevent the agent and UI from coming up.
Edit the units if the repo path differs:

```bash
sudo systemctl edit kanga-basestation
```

Stable `can_core` naming remains a host udev responsibility. The unit only
applies bitrate and queue configuration to the already named interface.

## Workflows

- **Path A (ROS only):** `docker_shell.bash` + `build_workspace.bash`. Repeated
  `docker_shell.bash` calls enter the same persistent `kanga-dev` container.
- **Path B (basestation):** `basestation_up.bash` after `install/` exists
- **Path C (control test):** Path A with nodes running, then Path B on the same
  machine and `ROS_DOMAIN_ID`

Basestation services are ROS participants. “Path B” only means you do not need
an interactive ROS shell open; the containers still use Humble and `install/`.

### Development and simulation

Use `kanga-dev` and `basestation-server`; do not also start `kanga-onboard`:

```bash
# Terminal 1: persistent ROS runtime and launch agent
./scripts/docker_shell.bash
ros2 launch kanga_launch_agent launch_agent.launch.py

# Terminal 2: same ROS runtime, for diagnostics or a manually managed sim
./scripts/docker_shell.bash

# Host terminal: separate web/API container
./scripts/basestation_up.bash
```

Running `docker_shell.bash` again never creates another development container.
If more than one legacy `kanga-dev` container is detected, the helper stops with
an error instead of selecting one. Use `./scripts/docker_dev_down.bash` when the
persistent runtime is no longer needed.

### Rover production

Use `kanga-onboard` and `basestation-server`; do not run `kanga-dev` as another
rover runtime. Systemd starts the onboard agent first, then the basestation. The
agent initially owns no subsystem process: Core remains stopped until an
allowlisted start request arrives.

## System Startup

The operator page is `/systems`. It lists allowlisted profiles from the onboard
launch agent and offers only the actions the agent currently allows. Process
state and health are shown separately; health stays `NOT_CHECKED` until
monitoring exists. An externally started stack is shown as `UNMANAGED` and
cannot be started, stopped, or restarted from the page.

The backend exposes only fixed lifecycle operations:

```text
GET  /api/systems
POST /api/systems/{system_id}/start
POST /api/systems/{system_id}/stop
POST /api/systems/{system_id}/restart
```

Action requests have no command or launch-argument body. FastAPI forwards the
system id and fixed action to the onboard ROS agent, which applies its own
profile allowlist and lifecycle rules. When a PIN is configured, all four
routes require the authenticated operator session. An unreachable agent returns
HTTP 503; a rejected transition, including an `UNMANAGED` stack, returns 409.

The full lifecycle contract and remaining roadmap live in
[the launch-manager plan](../launch-manager/README.md).

## Commissioning mockup

A frontend-only preview is available at `/commissioning`. Its editors, action
buttons, confirmation dialogs, and progress queue use mock data and do not
change files or contact ROS/motors. The agreed backend and hardware behavior is
documented in
[the commissioning page plan](../../basestation/COMMISSIONING_PAGE_PLAN.md).
Until that integration is implemented, use the `kanga_core_drive`
commissioning CLI and per-wheel ROS services documented in that package.

## Logs

`/logs` is a folder tree: live ROS `/rosout`, HTTP uvicorn buffer, Docker
PID-1 `docker logs` (Basestation and Onboard), and a launch-stdout stub.
Recording stays on the server; the browser paints only while the page is
open. Details in [the logs plan](../logging/README.md).

## Shared contract

Do not copy generated message code into `basestation/`. Message definitions live
in `src/kanga_interfaces`, become importable after `colcon build`, and are
exposed to basestation containers by sourcing `install/setup.bash`.
