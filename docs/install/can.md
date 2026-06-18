# CAN Setup & Debugging (Initial)

This documents the current CAN approach for the Kanga rover during early lab
testing.

## Responsibility split

- The **USB-CAN adapter is handled by the host**, not Docker.
- The **host creates `can0` / `can1`** (and sets the bitrate).
- **Docker uses host networking** (`network_mode: host`) to access SocketCAN.
- A **native CAN test on the host must pass before the Docker CAN test.**

Docker is not responsible for creating the CAN interfaces yet. If the host can't
see CAN traffic, the container won't either.

## Host setup

Use the helper script:

```bash
./scripts/setup_can.bash can0 500000
./scripts/check_can.bash can0
```

## Basic debugging commands

```bash
ip -details link show type can
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
candump can0
```

## Likely issues

- wrong bitrate
- adapter not detected
- interface name is `can1` not `can0`
- termination missing (need ~120 ohm at both ends of the bus)
- CAN-H / CAN-L swapped
- ODrive not powered
- container missing host networking
- container not privileged

## Test order

1. Confirm the adapter is detected on the host (`./scripts/check_devices.bash`).
2. Bring up the interface on the host (`./scripts/setup_can.bash`).
3. Confirm native `candump` works (`./scripts/check_can.bash`).
4. Only then test inside the container:

```bash
docker compose -f docker/compose.can-test.yaml run --rm can-test
# inside container:
ip -details link show type can
candump can0 -n 10
```
