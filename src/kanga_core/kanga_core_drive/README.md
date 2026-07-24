# kanga_core_drive

ODrive-facing drive package for the Kanga rover base: launch motor nodes,
Fibre commissioning (apply / calibrate / save), closed-loop trigger, and wheel
`JointState` from ODrive estimates.

Twist→wheel mapping lives in **`kanga_core_controller`**. Do not put chassis
kinematics here.

## Owns

- Multi-motor `custom_odrive` launch (`can_core`, wheel namespaces) — same
  explicit Node-per-wheel style as `custom_odrive` `example_multi_launch.py`
- Shared + per-wheel Fibre motor configs (merged at commission time)
- `commission_wheels` CLI (Python) wrapping `custom_odrive commission`
- `drive_manager` (C++) — `set_closed_loop` + per-wheel `calibrate_<id>` services
- `wheel_joint_state_publisher` (C++) — `/wheel_*/controller_status` → `wheel_joint_states`

## Does not own

- Chassis-to-wheel kinematics or `/cmd_vel` (`kanga_core_controller`)
- ODrive protocol / SocketCAN internals (vendor `custom_odrive`)
- Differential-bar JointState, WHS, error UX, whole-rover bringup

## Build (dev container)

Build and run this package **inside the Docker workspace**, not with ad-hoc
`colcon` on the host:

```bash
# Host: enter the container
./scripts/docker_shell.bash

# Inside the container (workspace root = /workspace)
./scripts/build_workspace.bash
source install/setup.bash
```

`custom_odrive` comes from the vendor pin under `src/vendor/` (see
[`src/vendor/README.md`](../../../src/vendor/README.md)). Import that once when
setting up a machine / after changing `kanga_vendor.repos` — not before every
build.

## Launch

Host must bring up `can_core` first. Then, inside the container (after build +
`source install/setup.bash`):

```bash
ros2 launch kanga_core_drive drive.launch.py
```

## Services (`drive_manager`)

```bash
# Enter / leave CLOSED_LOOP on all wheels
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: false}"

# Calibrate one wheel (basestation motor-status button target)
ros2 service call /drive_manager/calibrate_fl std_srvs/srv/Trigger "{}"
# also: calibrate_bl, calibrate_br, calibrate_fr
```

## Commission CLI

```bash
# Apply + save all (sequential)
ros2 run kanga_core_drive commission_wheels -- --wheels all --can can_core --save

# Calibrate one
ros2 run kanga_core_drive commission_wheels -- --wheels fl --can can_core --calibrate
```

## Runtime notes

- Launch leaves `start_enabled` at the package default (do not override). Use
  `/drivestop` for global stop. Closed-loop only via `set_closed_loop`.
- Invert via launch `invert_direction` (left wheels only — do not also invert
  in the controller).
- Shared Fibre `watchdog_timeout = 1` s. Setpoint streaming is
  `kanga_core_controller` (CLOSED_LOOP only).
- Calibrate: one wheel per request. Save: sequential apply+save in one CLI.

## Provenance

- Vendor: [`custom-ros-odrive`](https://github.com/UOW-TronSoc/custom-ros-odrive)
  (pinned in `src/vendor/kanga_vendor.repos`)
- Prior patterns: `ARCH2026-Kanga` `kanga_drive`
- Motor serials moved from `custom_odrive/config/wheel_*` into `config/motors/`

See [`docs/migration/core_drive.md`](../../../docs/migration/core_drive.md).

**Rover checklist:** step-by-step bench procedure lives in
[`kanga_core_bringup/README.md`](../kanga_core_bringup/README.md) (section
“Rover test procedure”).
