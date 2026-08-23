# Basestation (operator UI / API)

Ground-station HTTP services that participate in the ROS 2 graph via `rclpy`.
This tree is **not** a colcon package domain; keep it beside `src/`, not under it.

## Current status

One service: `basestation-server` runs the FastAPI app in `server/` on port
8000. It joins the ROS graph as a single `rclpy` node and serves the operator
web page from the same port. The old four health-stub services (ports
3000/8000/8001/8080) were retired when this server landed — see
[REDESIGN_PLAN.md](REDESIGN_PLAN.md) for the full picture and progress.

| Piece              | What it does                                          |
| ------------------ | ----------------------------------------------------- |
| `server/main.py`   | The web app: routes, health endpoint, static serving  |
| `server/ros.py`    | The ROS side: one node, one background spin thread    |
| `frontend/`        | React operator UI (Vite); builds into `server/static/` |
| `server/static/`   | Built UI served at `/` (run `./scripts/build_frontend.bash`) |

## Prerequisites

1. Build the ROS workspace at least once (Path A) so `install/setup.bash` exists.
2. Docker Engine + Compose plugin on the host.

## Start / stop

From the repository root:

```bash
./scripts/basestation_up.bash    # builds frontend, then starts the container
./scripts/basestation_down.bash
```

Rebuild the UI only:

```bash
./scripts/build_frontend.bash
```

Local UI iteration (proxy to `:8000`):

```bash
cd basestation/frontend && npm ci && npm run dev
```

See [Basestation install](../docs/install/basestation.md) and
[Basestation migration](../docs/migration/basestation.md).

## Redesign (in progress)

- [REDESIGN_PLAN.md](REDESIGN_PLAN.md) — full two-phase plan: consolidate the
  four legacy services into one FastAPI backend (WebSocket teleop/telemetry,
  built static frontend, single systemd bringup chain), then the camera
  pipeline rework. The task list at the bottom tracks progress.
- [CAMERAS.md](CAMERAS.md) — camera deep-dive: latency diagnosis,
  MediaMTX/WebRTC design, and the Orin NX vs Orin Nano encoder comparison.
