# Rover session checklist — `feat/core-controller`

Work through top to bottom. Stop and fix before continuing if a step fails.

**Branch:** `feat/core-controller` (includes `kanga_core_drive` + `kanga_core_controller` + `kanga_core_bringup`)

**CAN policy:** bus and all wheel ODrive S1s run at **250000** bit/s (BMS requirement).

**Interface naming:** code defaults to `can_core`. If the host shows `can0` or
`can1`, either rename the interface (Phase 1), pass the name to every `--can`
flag, or launch with `can_interface:=can0`.

---

## Session log

| Phase | Step | Pass? | Notes |
|-------|------|-------|-------|
| 0 | Repo + vendor + build | | |
| 1 | CAN host up | | |
| 2 | Confirm all wheels at 250k | | |
| 3 | Commission + calibrate | | |
| 4 | Drive stack (idle) | | |
| 5 | CLOSED_LOOP + single wheel | | |
| 6 | Full stack + `/cmd_vel` | | |
| 7 | Stale cmd + idle | | |
| 8 | Battery (optional) | | |

---

## Phase 0 — Software (CAN can stay down)

### 0.1 Confirm branch and vendor

```bash
cd ~/kanga_wip   # or wherever the repo lives on the rover
git branch --show-current    # expect: feat/core-controller
git status

# Vendor (skip if src/vendor/custom_ros_odrive already exists)
vcs import src/vendor < src/vendor/kanga_vendor.repos
```

**Pass:** `src/vendor/custom_ros_odrive/custom_odrive` exists.

### 0.2 Host environment

```bash
./scripts/check_devices.bash
docker --version
docker compose version
```

**Pass:** USB-CAN adapter visible; Docker works.

### 0.3 Build in container

```bash
./scripts/docker_shell.bash
# inside container:
./scripts/build_workspace.bash
source install/setup.bash
```

**Pass:** build finishes with no errors.

### 0.4 Offline unit tests (no CAN)

```bash
colcon test --packages-select kanga_core_controller kanga_core_drive \
  --event-handlers console_direct+
colcon test-result --verbose
```

**Pass:** all tests green.

---

## Phase 1 — CAN host (power drives + BMS if on same bus)

### 1.1 Discover interface name

```bash
# on host (outside container)
ip -details link show type can
```

Note the name (e.g. `can0`, `can1`). Below we use **`CAN_IF`** — substitute your name.

### 1.2 Optional: rename to `can_core` (avoids editing launch files)

```bash
sudo ip link set can0 down
sudo ip link set can0 name can_core
export CAN_IF=can_core
```

If you skip rename, set `export CAN_IF=can0` and pass
`can_interface:=${CAN_IF}` when launching the drive stack.

### 1.3 Bring up the 250k bus

Power the wheel ODrives.

```bash
./scripts/setup_can.bash ${CAN_IF:-can_core} 250000
./scripts/check_can.bash ${CAN_IF:-can_core}
```

**Pass:** `candump` shows ODrive heartbeat traffic (IDs 0x21, 0x22, 0x23, 0x24 for node_ids 1–4).

If there are no frames, check termination, CAN-H/L, ODrive power, bitrate,
and the interface name.

### 1.4 Container sees CAN

```bash
./scripts/docker_shell.bash
ip -details link show type can
candump ${CAN_IF:-can_core} -n 5
```

**Pass:** same traffic visible inside container.

---

## Phase 2 — Confirm all wheels at 250k

The shared motor config and host setup helper both default to 250000 bit/s.

### 2.1 Confirm commissioning at 250k

Confirm the host interface is running at 250k before commissioning.

Inside `docker_shell` (odrivetool cache is bind-mounted from the host):

```bash
ros2 run kanga_core_drive commission_wheels -- \
  --wheels fl --can ${CAN_IF:-can0} --save
ros2 run kanga_core_drive commission_wheels -- \
  --wheels bl --can ${CAN_IF:-can0} --save
ros2 run kanga_core_drive commission_wheels -- \
  --wheels br --can ${CAN_IF:-can0} --save
ros2 run kanga_core_drive commission_wheels -- \
  --wheels fr --can ${CAN_IF:-can0} --save
```

With `drive.launch` running, omit `--bench` (default — parks each wheel via ROS).
With drive stopped, add `--bench` and confirm at the prompt.

Each wheel reboots after save. Do one at a time if the bus gets noisy.

**Pass:** all four exit 0; no Fibre errors.

### 2.2 Switch host to 250k

```bash
# host
./scripts/setup_can.bash ${CAN_IF:-can_core} 250000
candump ${CAN_IF:-can_core}   # all four ODrives still visible
```

**Pass:** heartbeat traffic from all node IDs at 250k.

---

## Phase 3 — Calibrate (wheel off ground)

**Safety:** FULL_CALIBRATION moves the motor. One wheel at a time.

```bash
ros2 run kanga_core_drive commission_wheels -- \
  --wheels fl --can ${CAN_IF:-can0} --calibrate
# repeat: bl, br, fr
```

**Pass:** each wheel completes without fault.

---

## Phase 4 — Drive stack idle

### 4.1 Launch drive only

```bash
ros2 launch kanga_core_drive drive.launch.py can_interface:=${CAN_IF:-can_core}
```

Second shell (`docker_shell` + `source install/setup.bash`):

```bash
ros2 node list
ros2 topic echo /wheel_fl/controller_status --once
```

**Pass:** `drive_manager`, `wheel_actuator`, `wheel_{fl,bl,br,fr}/can_node`,
`wheel_joint_state_publisher`; `axis_state: 1` (IDLE).

### 4.2 Clear drivestop if needed

If nodes ignore commands until `/drivestop` is received:

```bash
ros2 topic pub /drivestop std_msgs/msg/Bool "{data: false}" --once
```

---

## Phase 5 — CLOSED_LOOP (no `/cmd_vel` yet)

### 5.1 Enter CLOSED_LOOP on all wheels

```bash
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
```

Check each wheel:

```bash
ros2 topic echo /wheel_fl/controller_status --once   # axis_state == 8
```

**Pass:** all four `axis_state == 8`, `success: true`.

### 5.2 Single-wheel velocity test (optional isolate)

```bash
ros2 run custom_odrive velocity_ramp_test -- --ns /wheel_fl --target-vel 3.14
```

`custom_odrive` works in motor-shaft units, so this requests `3.14` motor rad/s
(`0.5` motor turns/s). The generic test intentionally does not apply Kanga's
gearbox reduction.

**Pass:** wheel spins correct direction; `wheel_joint_states` updates.

---

## Phase 6 — Full stack + motion

### 6.1 Launch drive + controller

Stop previous launch (Ctrl-C), then:

```bash
ros2 launch kanga_core_bringup core_drive.launch.py can_interface:=${CAN_IF:-can_core}
```

```bash
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
```

### 6.2 Confirm mapper stream (zero cmd)

```bash
ros2 topic echo /wheel_joint_velocity_command
ros2 topic echo /wheel_fl/control_message
```

**Pass:** both ~10 Hz and near zero; motor `input_vel` is the joint command ×50.

### 6.3 Motion smoke test

Clear space / prefer wheels elevated first.

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" \
  --rate 10
```

Watch:

```bash
ros2 topic echo /wheel_joint_velocity_command
ros2 topic echo /wheel_fl/control_message
ros2 topic echo /wheel_joint_states
```

**Pass:** both velocities leave zero and motor `input_vel ≈ joint × 50`;
robot/wheels move forward; left wheels not fighting right.

---

## Phase 7 — Stop behaviour

### 7.1 Stale `/cmd_vel`

Stop the `topic pub` (Ctrl-C). Within ~0.5 s:

```bash
ros2 topic echo /wheel_fl/control_message
```

**Pass:** `input_vel → 0`, still CLOSED_LOOP.

### 7.2 Leave CLOSED_LOOP

```bash
ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: false}"
```

**Pass:** `axis_state → 1`; `control_message` stream stops.

---

## Phase 8 — Battery (optional, separate branch)

`feat/core-controller` only has a battery package stub. Merge first:

```bash
git fetch origin
git merge origin/feat/battery-feedback
# rebuild in container
```

CAN must be at **250000**. With drive stack **idle** (not CLOSED_LOOP):

```bash
ros2 launch kanga_core_battery bms_launch.py \
  launch_socketcan:=true interface:=${CAN_IF:-can_core}

ros2 topic echo /battery/battery_info
```

Then repeat with `core_drive.launch.py` running to confirm shared-bus stability.

**Pass:** battery topics update; drive still enters CLOSED_LOOP and accepts `/cmd_vel`.

---

## Quick troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `candump` silent | Wrong bitrate, interface down, no termination, ODrives off |
| Only some wheels on bus | Check power, node IDs, wiring, and that every S1 is saved at 250k |
| `set_closed_loop` fails | CAN down, fault latched — `clear_errors` via service or power cycle |
| No `wheel_joint_velocity_command` | Controller not running |
| No `control_message` | Stale joint command, not in CLOSED_LOOP, or `/drivestop` true |
| Motion backwards / fighting | Check `invert_direction` on FL/BL in `drive.launch.py` only |
