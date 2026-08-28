# Basestation (operator UI / API)

Ground-station HTTP services that participate in the ROS 2 graph via `rclpy`.
This tree is **not** a colcon package domain; keep it beside `src/`, not under it.

## Current status

**Phase 1 is complete for development.** One service — `basestation-server` —
runs the FastAPI app in `server/` on port 8000, embeds a single rclpy node, and
serves the built React operator UI from the same port.

Verified against Gazebo core simulation and physical core bringup with rover
motors and sensors on CAN (developer laptop, shared `ROS_DOMAIN_ID`).

| Piece | What it does |
| ----- | ------------ |
| `server/main.py` | Routes, health, WebSockets, static files |
| `server/ros.py` | `/cmd_vel`, telemetry, drive REST service clients |
| `server/commissioning_catalog.py` | Allowed subsystems, motors, paths, namespaces, and order |
| `server/commissioning_config.py` | Safe config/default reads, validation, revisions, atomic writes |
| `server/commissioning_jobs.py` | Sequential save/calibration jobs and drive interlock |
| `server/commissioning_api.py` | Authenticated commissioning HTTP routes |
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
- Motor calibration browser controls — `/commissioning` now edits real backend
  configs and runs individual or sequential motor Save jobs with live progress.
  Calibration remains disabled pending the final Step 4 slice in
  [COMMISSIONING_PAGE_PLAN.md](COMMISSIONING_PAGE_PLAN.md).
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

Rebuild the UI only:

```bash
./scripts/build_frontend.bash
```

Local UI iteration (Vite proxy to `:8000`):

```bash
cd basestation/frontend && npm ci && npm run dev
```

## Environment (optional)

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `BASESTATION_MAX_LINEAR_MPS` | `0.3` | Forward speed cap at 100% slider |
| `BASESTATION_MAX_YAW_RAD_S` | `0.3` | Yaw rate cap at 100% slider |
| `BASESTATION_SECRET_KEY` | dev placeholder | Session cookie signing (set on rover) |
| `BASESTATION_WORKSPACE_ROOT` | repository root | Override catalog file root for tests/deployment |
| `ROS_DOMAIN_ID` | `0` | Must match robot stack |

## Commissioning backend

The commissioning API accepts subsystem and motor IDs from its fixed catalog;
clients cannot provide paths, ROS namespaces, CAN node IDs, or shell arguments.
When a PIN is configured, every route below requires the existing authenticated
session.

| Method | Route | Purpose |
| ------ | ----- | ------- |
| `GET` | `/api/commissioning/catalog` | Core/Arm/Payload availability and ordered motors |
| `GET`, `PUT` | `/api/commissioning/configs/{subsystem}/{scope}` | Shared file (`scope=shared`) or motor overlay (`scope=fl`, `bl`, `br`, `fr`) |
| `GET`, `PUT` | `/api/commissioning/soft-limits/{subsystem}` | Editable limits, immutable defaults, and hard maxima |
| `POST` | `/api/commissioning/jobs` | Start one save or calibration job |
| `GET` | `/api/commissioning/jobs/{job_id}` | Poll overall and per-motor state |
| `POST` | `/api/commissioning/jobs/{job_id}/confirm` | Confirm the current calibration motor is free to spin |
| `POST` | `/api/commissioning/jobs/{job_id}/retry` | Retry the failed motor in the same job |
| `POST` | `/api/commissioning/jobs/{job_id}/skip` | Skip a failed motor in a multi-motor job |
| `POST` | `/api/commissioning/jobs/{job_id}/cancel` | Cancel while waiting for confirmation or a failure decision |

Config reads return complete `content`, `default_content`, and a SHA-256
`revision`. A PUT must send the last loaded revision; stale edits receive HTTP
409 instead of overwriting another change. Motor Python is parsed as inert
declarative assignments and is never executed by the server. Imports, calls,
control flow, protected velocity/ramp assignments, changed CAN node IDs, and
duplicate/empty serials are rejected. Soft-limit YAML must remain positive and
at or below the unchanged drivetrain-profile maxima.

Only one hardware job may exist at a time. Requested motors are normalized to
catalog order (`fl -> bl -> br -> fr`), and a failure pauses the job for Retry,
Skip, or Cancel. Save jobs proceed sequentially. Calibration jobs ask whether
the named motor is free to spin before every motor. Save and confirmed
calibration operations temporarily release drivestop for one motor, then attempt
to reassert it after success, failure, exception, or timeout. WHS
release/restoration failures fail the job and are shown to the operator. While a job is active, non-zero
browser motion, closed-loop enable, ordinary drivestop release, error clearing,
and config writes are blocked; asserting drivestop and requesting IDLE remain
available.

Run the backend tests without ROS hardware:

```bash
python3 -m unittest discover -s basestation/server -t basestation
```

## Rover deployment

Systemd unit: `deploy/kanga-basestation.service` and
`scripts/basestation_install_service.bash`. The scaffold is present; final
competition Jetson setup still requires a PIN, a production session secret,
verified unit paths/startup ordering, and retirement of the legacy stack. See
[the install guide](../docs/install/basestation.md).

## Docs

- [REDESIGN_PLAN.md](REDESIGN_PLAN.md) — architecture and task checklist
- [COMMISSIONING_PAGE_PLAN.md](COMMISSIONING_PAGE_PLAN.md) — planned motor
  config, save, and sequential calibration page
- [CAMERAS.md](CAMERAS.md) — Phase 2 camera pipeline
- [Basestation install](../docs/install/basestation.md)
- [Basestation migration](../docs/migration/basestation.md)
