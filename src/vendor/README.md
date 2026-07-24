# Vendor repositories

External ROS repositories used by Kanga are imported beneath this structure
folder and remain independently maintained. This folder is not a ROS package.

Use the version-controlled `kanga_vendor.repos` manifest in this directory and
`vcs import` so each dependency is pinned to an intentional revision. Do not
manually copy third-party source trees into this repository.

```bash
# From the kanga_wip repository root (host or container):
vcs import src/vendor < src/vendor/kanga_vendor.repos
```

Imported trees under `src/vendor/` are gitignored. Only this README and
`kanga_vendor.repos` are tracked.

## ros2_socketcan

Upstream: [autowarefoundation/ros2_socketcan](https://github.com/autowarefoundation/ros2_socketcan)

Pinned in `kanga_vendor.repos` to tag `1.3.0`. Provides:

- `ros2_socketcan` — SocketCAN ↔ ROS bridge nodes
- `ros2_socketcan_msgs` — package-local messages

Use this for club-owned CAN devices (BMS, microcontrollers, science). Do not
use it to command ODrive axes; ODrive nodes open SocketCAN directly.

Humble binary packages also exist (`ros-humble-ros2-socketcan` and
`ros-humble-ros2-socketcan-msgs`). Prefer the vendor pin so the workspace
builds the same revision on every machine.

## ODrive

Upstream lineage: [odriverobotics/ros_odrive](https://github.com/odriverobotics/ros_odrive)

Club fork: [`UOW-TronSoc/custom-ros-odrive`](https://github.com/UOW-TronSoc/custom-ros-odrive)
— reusable per-motor ROS 2 integration with internal SocketCAN/epoll helpers.
Independent of Kanga packages.

Not yet pinned in `kanga_vendor.repos`. Add an entry and run `vcs import` as
part of the `feat/vendor-odrive-pin` slice (see
[core drive next steps](../../docs/migration/core_drive.md)).
