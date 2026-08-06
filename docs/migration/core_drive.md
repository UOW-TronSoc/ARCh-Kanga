# Next steps: core drive + controller

Agreed design for the rover-base ODrive stack. **`kanga_core_drive`** landed on
`feat/drive-system` and its current v1 actuator scope was bench-validated on
the rover on 2026-08-05. **`kanga_core_controller`** is implemented on
`feat/core-controller`; physical m/s calibration and command shaping remain.

Related: [migration overview](README.md),
[`src/vendor/README.md`](../../src/vendor/README.md),
[`custom-ros-odrive`](https://github.com/UOW-TronSoc/custom-ros-odrive).

Old reference (mapper / launch): `ARCH2026-Kanga` → `src/kanga_drive`.

---

## Locked decisions

| Topic | Decision |
|-------|----------|
| Packages | **`kanga_core_drive`** — ODrive launch, Fibre configs, commission, closed-loop trigger, wheel JointState. **`kanga_core_controller`** — twist→wheel + setpoint stream. |
| Branches | **`feat/drive-system`** (vendor pin + drive). **`feat/core-controller`** (mapper). |
| custom_odrive | Do not change the C++ node unless blocked. Apply/calibrate/save via existing `commission` CLI. |
| Calibrate | **One motor at a time.** CLI and/or per-wheel `std_srvs/Trigger` (`~/calibrate_fl` …). |
| Save config | Apply shared+individual, then `--save`. Sequential one-at-a-time in a single CLI command. Command only. |
| Stream | Controller publishes wheel-joint commands at ~10 Hz. Drive publishes motor commands only while CLOSED_LOOP. Stale `/cmd_vel` → continuously streamed zero. |
| Firmware watchdog | Shared Fibre config is authoritative; verify enable/timeout policy before rover operation. |
| Invert | Launch `invert_direction` only. URDF sign check later. |
| Deferred | Synchronised wheel acceleration/deceleration shaping, diff-bar JointState, odom, errors/UX, WHS, and loaded/field qualification. |

```mermaid
flowchart LR
  web["Basestation motor page"] -->|"calibrate one wheel"| drivePkg["kanga_core_drive"]
  cliSave["commission CLI"] --> drivePkg
  trigger["set_closed_loop"] --> nodes["custom_odrive nodes"]
  cmdVel["/cmd_vel"] --> ctrl["kanga_core_controller"]
  ctrl -->|"wheel-joint rad/s"| actuator["wheel_actuator"]
  actuator -->|"motor-shaft rad/s if CLOSED_LOOP"| nodes
  nodes --> status["controller_status"]
  status --> drivePkg
  drivePkg --> js["JointState wheels"]
  nodes --> can["SocketCAN can_core"]
```

---

## Branch 1 — vendor pin + `kanga_core_drive` (this branch)

### Vendor

`custom-ros-odrive` pinned in `kanga_vendor.repos`. Import **once** when setting
up a machine (or after changing the pin) — see
[`src/vendor/README.md`](../../src/vendor/README.md). Everyday builds use the
Docker workspace scripts:

```bash
./scripts/docker_shell.bash          # host → container
./scripts/build_workspace.bash       # inside container
source install/setup.bash
```

### Package owns

| Piece | Role |
|-------|------|
| `launch/drive.launch.py` | 4× `custom_odrive_node` on `can_core`, namespaces `wheel_fl/bl/br/fr`, ids 1–4, left invert (no `start_enabled` override; use `/drivestop` for stop) |
| `config/motors/` | `shared_motor_config.py` + per-wheel overlays |
| `commission_wheels` | Concat shared+individual → call `custom_odrive commission` |
| `drive_manager` | `set_closed_loop` + `calibrate_fl/bl/br/fr` (Trigger) |
| `wheel_joint_state_publisher` | `controller_status` → wheel `JointState` |

### Fibre configs

```text
config/motors/
  shared_motor_config.py      # common odrv.*; baud 250000; watchdog policy
  wheel_fl_motor_config.py    # SERIAL_NUMBER + node_id + per-wheel diffs
  ...
```

Commission merges shared then individual into a temp file before calling
`custom_odrive commission`.

### CLI

```bash
# Apply + save all wheels (sequential)
ros2 run kanga_core_drive commission_wheels -- \
  --wheels all --can can_core --save

# Calibrate one wheel
ros2 run kanga_core_drive commission_wheels -- \
  --wheels fl --can can_core --calibrate
```

### Services (`drive_manager`)

- `~/set_closed_loop` (`std_srvs/SetBool`) — true: clear_errors + CLOSED_LOOP(8) all wheels; false: IDLE(1); no `set_enabled` (use `/drivestop`)
- `~/calibrate_fl`, `~/calibrate_bl`, `~/calibrate_br`, `~/calibrate_fr` (`std_srvs/Trigger`) — one-wheel FULL_CALIBRATION; rejects if busy

---

## Branch 2 — `kanga_core_controller` (`feat/core-controller`)

| Piece | Role |
|-------|------|
| `kinematics` lib | Pure `twist_to_wheels` plus proportional four-wheel desaturation; legacy angled-grouser model |
| `wheel_command_mapper` | `/cmd_vel` → one limited four-wheel joint command; stale `/cmd_vel` → joint zeros |
| `config/controller.yaml` | controller rate and timeout only |
| `launch/controller.launch.py` | loads selected description profile and starts mapper |

No invert; no `request_axis_state` / `set_enabled` from the mapper. Enter CLOSED_LOOP via `drive_manager`; stop via `/drivestop`.

### Offline checks

Inside the container after `./scripts/build_workspace.bash`:

- `colcon test --packages-select kanga_core_controller` (kinematics gtests)

### Bench (with drive)

1. Launch wheels + controller
2. `set_closed_loop true`
3. Publish `/cmd_vel`; confirm joint commands and ×50 motor `control_message` while CLOSED_LOOP
4. Stop publishing `/cmd_vel` → zeros still stream; leave CLOSED_LOOP → stream stops

---

## Shared drivetrain profile

`kanga_core_description/config/drivetrains/drivetrain_2025.yaml` is the single
source for measured wheel geometry, outside wheel-envelope dimensions, grouser
angle, motor-to-wheel reduction, and motor TPS limit. The loader derives
wheel-centre geometry, effective radius, and joint speed capability.

`kanga_core_bringup` passes the selected `drivetrain_profile` to controller and
drive. `commission_wheels` consumes it as well, so saved ODrive limits and
runtime limits share the same value. Physical values no longer belong in
`controller.yaml`, `drive.yaml`, or C++ defaults.

---

## Offline checks — drive (no rover)

- `./scripts/build_workspace.bash` inside the container (pulls in vendor ODrive)
- Config-merge unit test: `colcon test --packages-select kanga_core_drive`
- Launch may fail at runtime without `can_core` — expected until hardware

## Bench checklist — drive (when rover available)

1. Vendor import (once) + `./scripts/build_workspace.bash`
2. `drive.launch.py` — four namespaces idle
3. `set_closed_loop true` → `velocity_ramp_test` on one wheel
4. `commission_wheels --wheels fl --calibrate` (wheel off ground) or `calibrate_fl` Trigger
5. `commission_wheels --wheels all --save`
6. JointState echoes estimates
