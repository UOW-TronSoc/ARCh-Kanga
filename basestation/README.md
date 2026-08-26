# Basestation (operator UI / API)

Ground-station HTTP services that participate in the ROS 2 graph via `rclpy`.
This tree is **not** a colcon package domain; keep it beside `src/`, not under it.

## Current status

**Phase 1 is done for laptop development.** One service — `basestation-server` —
runs the FastAPI app in `server/` on port 8000, embeds a single rclpy node, and
serves the built React operator UI from the same port.

Verified against Gazebo core simulation and physical core bringup with rover
motors and sensors on CAN (developer laptop, shared `ROS_DOMAIN_ID`).

| Piece | What it does |
| ----- | ------------ |
| `server/main.py` | Routes, health, WebSockets, static files |
| `server/ros.py` | `/cmd_vel`, telemetry, drive REST service clients |
| `frontend/` | React operator UI (Vite); builds into `server/static/` |
| `server/static/` | Production UI bundle (rebuild with `./scripts/build_frontend.bash`) |

### Drive dashboard (implemented)

- Drivestop assert/release (release requires confirmation modal)
- ODrive closed loop / idle, clear faults
- Drive input via dashboard button, **B0**, or **Space** — arms closed loop
  first when idle; gamepad cannot release drivestop
- WASD + gamepad sticks; D-pad **B12–B15** full forward/back/rotate
- Speed max slider (0–90% maps to full scale; 90–100% plateau)
- `/ws/control` dead-man + `/ws/telemetry` at 5 Hz

### Not yet

- Live cameras (placeholders) — Phase 2 in [CAMERAS.md](CAMERAS.md)
- Arm / science pages (hidden)
- Per-wheel calibrate button (API exists)
- Live battery telemetry

## Prerequisites

1. Build the ROS workspace at least once (Path A) so `install/setup.bash` exists.
2. Docker Engine + Compose plugin on the host.

## Start / stop

From the repository root:

```bash
./scripts/basestation_up.bash    # builds frontend, then starts the container
./scripts/basestation_down.bash
```

Rebuild the UI only (Docker Node 20 by default — no host Node needed):

```bash
./scripts/build_frontend.bash
```

Local UI iteration on the host (needs Node 18+; Vite proxy to `:8000`):

```bash
cd basestation/frontend && npm ci && npm run dev
# or force a host build: USE_HOST_NPM=1 ./scripts/build_frontend.bash
```

## Environment (optional)

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `BASESTATION_MAX_LINEAR_MPS` | `0.3` | Forward speed cap at 100% slider |
| `BASESTATION_MAX_YAW_RAD_S` | `0.3` | Yaw rate cap at 100% slider |
| `BASESTATION_SECRET_KEY` | dev placeholder | Session cookie signing (set on rover) |
| `ROS_DOMAIN_ID` | `0` | Must match robot stack |

## Rover deployment (later)

Systemd unit: `deploy/kanga-basestation.service` and
`scripts/basestation_install_service.bash`. Competition Jetson setup (PIN,
secret, paths, retiring the legacy four-service stack) is documented in
[REDESIGN_PLAN.md](REDESIGN_PLAN.md) task 8 — not required for laptop dev.

## Docs

- [REDESIGN_PLAN.md](REDESIGN_PLAN.md) — architecture and task checklist
- [CAMERAS.md](CAMERAS.md) — Phase 2 camera pipeline
- [Basestation install](../docs/install/basestation.md)
- [Basestation migration](../docs/migration/basestation.md)
