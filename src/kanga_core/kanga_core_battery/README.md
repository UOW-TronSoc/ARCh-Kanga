# kanga_core_battery

Talks to the rover **BMS** and publishes voltage, current, SOC, temps, cells, and faults.

This package does **not** open SocketCAN. A `ros2_socketcan` bridge turns the wire into
ROS Frame topics; this node only speaks ROS.

Hardware protocol PDF: `docs/reference/Daly-CAN-Communications-Protocol-V1.0.pdf`

## Data flow

```text
  BMS  <--CAN @ 250 kbit/s-->  SocketCAN (can1 / can_core)
                                    |
                             ros2_socketcan bridge
                                    |
                    /<interface>/from_can_bus
                    /<interface>/to_can_bus
                                    |
                             bms_can_node
                                    |
                    /battery/battery_info
                    /battery/bms_status
```

## Launch vs ROS parameters

**Launch arguments** — only for the launch file itself:

| Arg | Default | Meaning |
|-----|---------|---------|
| `launch_socketcan` | `false` | Also start ros2_socketcan (testing only) |
| `interface` | `can1` | Which bus; forwarded to the node as a ROS param |

**ROS parameters** — normal node params (`declare_parameter` / `get_parameter`):

| Param | Default | Meaning |
|-------|---------|---------|
| `interface` | `can1` | Frame topic prefix (`/can1/...`) |
| `req_period` | `1` | Seconds between poll cycles |
| `local_node_id` | `320` | Our TX address (fixed; override only if needed) |
| `bms_node_id` | `16385` | BMS RX filter (fixed; do not change) |

Launch only sets `interface` and `req_period`. Node IDs use the defaults in code.

## Run

CAN must be up at **250000**.

```bash
ros2 launch kanga_core_battery bms_launch.py
ros2 launch kanga_core_battery bms_launch.py launch_socketcan:=true
ros2 launch kanga_core_battery bms_launch.py launch_socketcan:=true interface:=can_core
```

```bash
ros2 topic echo /battery/battery_info
ros2 topic echo /can1/from_can_bus
```

## Provenance

- Source: `ARCH2026-Kanga` / `kanga_hardware/kanga_battery`
- Ref: `feat/arm-simulation` @ `8b0c0537823fac7aaac26c1bea8bd4f3763bdc06`
