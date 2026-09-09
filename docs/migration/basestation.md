# Basestation migration

## Status

**Phase 1 complete for development** (2026-08-24). The legacy four-service stack
(Django :8000, arm FastAPI :8001, cmd_vel FastAPI :8080, Vite :3000) is replaced
in this repository by a single `basestation-server` on port **8000**.

| Legacy | Replacement |
| ------ | ----------- |
| Django + PIN + logs | `basestation/server/operator.py`, `pin_auth.py`, log buffer |
| cmd_vel FastAPI | `/ws/control` + `server/ros.py` (one rclpy node) |
| Arm FastAPI | Not migrated — arm/science UI hidden until payload packages land |
| Vite dev server :3000 | Built React app in `basestation/server/static/` |

Drive, drivestop, closed-loop management, telemetry, PIN, and logs are
implemented and verified against **Gazebo core simulation** and **physical
core bringup** (laptop dev with rover CAN hardware connected).

Still outstanding (not migration blockers):

- **Phase 2 cameras** — placeholders on the Drive page; see
  [basestation/CAMERAS.md](../../basestation/CAMERAS.md).
- **Rover boot deployment** — systemd unit and compose restart policy exist;
  PIN, session secret, and legacy stack retirement on the competition Jetson
  are manual follow-ups.
- **Motor commissioning integration** — a frontend-only mockup now previews the
  config editor and sequential workflow, but it does not change files or
  contact ROS/motors. The per-wheel calibration REST endpoint exists; the full
  save/calibration backend remains planned. See
  [the commissioning page plan](../../basestation/COMMISSIONING_PAGE_PLAN.md).
- **Live battery** — widget present; `kanga_core_battery` not wired through yet.

## Primary reference (legacy application code)

```text
Previous live stack (retire on rover after parity check):
  /home/kanga/kanga/basestation/basestationproject/

  Django          8000
  Arm FastAPI     8001
  cmd_vel FastAPI 8080
  Vite frontend   3000
```

Do **not** migrate unused `process_manager/` or `robot_controller/` trees from
the old repo.

## Design and task list

[basestation/REDESIGN_PLAN.md](../../basestation/REDESIGN_PLAN.md) — architecture,
WebSocket contracts, and Phase 1/2 checklist.

[basestation/COMMISSIONING_PAGE_PLAN.md](../../basestation/COMMISSIONING_PAGE_PLAN.md)
— follow-on motor config, save, and sequential calibration design.

## Validation

Run Path A (ROS workspace + core bringup or sim) and Path B (basestation) on
the **same machine** with the same `ROS_DOMAIN_ID`:

```bash
# Terminal 1 — robot stack (example: physical core on can0)
ros2 launch kanga_core_bringup core.launch.py can_interface:=can0 ...

# Terminal 2 — operator server
./scripts/basestation_up.bash
```

Open http://localhost:8000/ — PIN → Drive. Release drivestop from the dashboard,
arm with **B0** or **Space** (closed loop, then drive input), drive with WASD /
gamepad / D-pad buttons B12–B15.

## Interface rule

`src/kanga_interfaces` is the single source of truth. Basestation containers
must source `/workspace/install/setup.bash`; do not vendor generated Python
message modules under `basestation/`.
