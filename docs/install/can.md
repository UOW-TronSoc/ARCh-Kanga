# CAN Setup & Debugging (Initial)

This documents the current CAN approach for the Kanga rover during early lab
testing.

## Responsibility split

- The **USB-CAN adapter is handled by the host**, not Docker.
- The **host creates and stably names `can_core` / `can_payload`** (and sets the bitrate).
- **Docker uses host networking** (`network_mode: host`) to access SocketCAN.
- A **native CAN test on the host must pass before the Docker CAN test.**

Docker is not responsible for creating the CAN interfaces yet. If the host can't
see CAN traffic, the container won't either.

## Host setup

Use the helper script:

```bash
./scripts/setup_can.bash can_core 500000
./scripts/setup_can.bash can_payload 500000
./scripts/check_can.bash can_core
./scripts/check_can.bash can_payload
```

## Basic debugging commands

```bash
ip -details link show type can
sudo ip link set can_core down
sudo ip link set can_core type can bitrate 500000
sudo ip link set can_core up
candump can_core
```

## Likely issues

- wrong bitrate
- adapter not detected
- stable interface naming has not been configured on the host
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
candump can_core -n 10
candump can_payload -n 10
```

## Stable adapter naming

> **TODO (Orin setup):** Add persistent host udev/systemd `.link` rules that
> assign the two USB-CAN adapters to `can_core` and `can_payload`. Match by each
> adapter's unique `ID_SERIAL_SHORT` where available; if the serials are absent
> or identical, match by `ID_PATH` for the chosen Orin USB ports. Confirm the
> names survive an adapter reconnect and an Orin reboot.

Use `./scripts/check_devices.bash` to inspect `ID_SERIAL_SHORT` and `ID_PATH` for
each detected `can*` interface. Prefer a unique adapter serial in the host udev
rules. If the adapters have no unique serials, match their physical USB paths.
Physically label both adapters in either case.

The logical mapping is:

- `can_core`: core rover systems and standard drive ODrives
- `can_payload`: arm, science, and other payload systems

## Laptop Docker proof-of-concept

The initial single-bus test was completed using a USB-CAN adapter and an ESP32
at 500000 bit/s:

- [x] Host detected and configured the SocketCAN interface
- [x] ESP32-to-host traffic confirmed
- [x] Host-to-ESP32 traffic confirmed
- [x] CAN interface visible inside the development container
- [x] ESP32-to-container traffic confirmed
- [x] Container-to-ESP32 traffic confirmed
- [ ] Second adapter and CAN network tested
- [ ] Persistent `can_core` and `can_payload` naming configured on the Orin
