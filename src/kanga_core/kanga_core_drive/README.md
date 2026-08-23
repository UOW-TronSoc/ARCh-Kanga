# kanga_core_drive

ODrive-facing drive package for the Kanga rover base: launch motor nodes,
Fibre commissioning (apply / calibrate / save), closed-loop trigger, and wheel
`JointState` from ODrive estimates.

Twist→wheel mapping lives in **`kanga_core_controller`**. Do not put chassis
kinematics here.

## Owns

- Multi-motor `custom_odrive` launch (`can_core`, wheel namespaces) — same
  explicit Node-per-wheel style as `custom_odrive` `example_multi_launch.py`
- `wheel_actuator` — wheel-joint rad/s → selected reduction, final independent
  motor safety clamp, CLOSED_LOOP-gated motor-shaft `ControlMessage`
- Shared + per-wheel Fibre motor configs (merged at commission time)
- `commission_wheels` CLI (Python) wrapping `custom_odrive commission`
- `drive_manager` (C++) — drive state, all-wheel error clearing, and per-wheel
  calibration services
- `wheel_joint_state_publisher` (C++) — `/wheel_*/controller_status` → `wheel_joint_states`

## Does not own

- Chassis-to-wheel kinematics or `/cmd_vel` (`kanga_core_controller`)
- ODrive protocol / SocketCAN internals (vendor `custom_odrive`)
- Differential-bar JointState, WHS, error UX, whole-rover bringup

## Functional status

As of 2026-08-05, the current v1 drive-package scope is functionally complete
and bench-validated on the rover. Commissioning, calibration, four-wheel state
management, the 50:1 actuator conversion, joint feedback, direction handling,
22 TPS limiting, uniform desaturation, command timeouts, `/drivestop`, and
recovery after a stop have all been exercised with the physical ODrives.

Uniform desaturation has since moved to `kanga_core_controller`, where that
control decision belongs. Drive retains a per-motor hard safety clamp.

This status means the drive actuator boundary is ready for controller work; it
does not mean the complete rover is field-qualified. Loaded/on-ground driving,
long-duration thermal/current testing, power-cycle or CAN-loss recovery, and
integrated WHS behaviour on the physical rover remain whole-system validation.
Physical Twist calibration and effective wheel radius belong to
`kanga_core_controller`, not this package.

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

The optional `drivetrain_profile` argument defaults to `drivetrain_2025`.

## Services (`drive_manager`)

```bash
# Enter / leave CLOSED_LOOP on all wheels
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: false}"

# Clear sticky errors on every wheel without changing axis state
ros2 service call /drive_manager/clear_errors std_srvs/srv/Trigger "{}"

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

Both launch and commissioning load the same selected profile, so the runtime
reduction/limit and the saved ODrive velocity limit cannot silently diverge.

## Runtime notes

- `config/drive.yaml` contains runtime behaviour only (publish rate and command
  timeout). Physical reduction and motor TPS/TPS-per-second limits come from
  the selected `kanga_core_description` drivetrain profile.
- `wheel_actuator` accepts one atomic `/wheel_joint_velocity_command` containing
  all four wheel-joint velocities, applies the selected reduction,
  independently clamps only as a final actuator safety guard, and sends
  motor-shaft rad/s to generic
  `custom_odrive` nodes. Motion-preserving uniform scaling belongs upstream.
- `wheel_joint_state_publisher` divides motor position/velocity feedback by the
  selected reduction
  so `wheel_joint_states` is expressed at the wheel joint.
- Launch leaves `start_enabled` at the package default (do not override). Use
  `/drivestop` for global stop. Closed-loop only via `set_closed_loop`.
- Invert via launch `invert_direction` (left wheels only — do not also invert
  in the controller).
- Motor setpoint streaming is `wheel_actuator` (CLOSED_LOOP only). A stale
  joint-command vector stops transmission; the firmware watchdog
  must be enabled in the shared Fibre config for this to disarm a moving axis.
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
