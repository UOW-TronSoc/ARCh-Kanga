# Basestation (operator UI / API)

Ground-station HTTP services that participate in the ROS 2 graph via `rclpy`.
This tree is **not** a colcon package domain; keep it beside `src/`, not under it.

## Current status

Scaffold only: health-stub services on the production ports so Docker and the
`install/` coupling can be validated before real application code is migrated.

| Service (compose)       | Port | Stub role                                      |
| ----------------------- | ---- | ---------------------------------------------- |
| `basestation-django`    | 8000 | HTTP health (placeholder for future Django)    |
| `basestation-fastapi`   | 8080 | HTTP health + optional `/cmd_vel` Twist pub    |
| `basestation-arm-fastapi` | 8001 | HTTP health (placeholder for arm FastAPI)    |
| `basestation-frontend`  | 3000 | Static page linking to the health endpoints    |

## Prerequisites

1. Build the ROS workspace at least once (Path A) so `install/setup.bash` exists.
2. Docker Engine + Compose plugin on the host.

## Start / stop

From the repository root:

```bash
./scripts/basestation_up.bash
./scripts/basestation_down.bash
```

See [Basestation install](../docs/install/basestation.md) and
[Basestation migration](../docs/migration/basestation.md).

## Redesign (future work)

- [REDESIGN_PLAN.md](REDESIGN_PLAN.md) — full two-phase plan: consolidate the
  four legacy services into one FastAPI backend (WebSocket teleop/telemetry,
  built static frontend, single systemd bringup chain), then the camera
  pipeline rework.
- [CAMERAS.md](CAMERAS.md) — camera deep-dive: latency diagnosis,
  MediaMTX/WebRTC design, and the Orin NX vs Orin Nano encoder comparison.
