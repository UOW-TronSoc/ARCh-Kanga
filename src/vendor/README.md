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

The reusable ODrive ROS integration lives in its own repository and is imported
here once that repository and its stable interface exist. It must remain
independent of Kanga-specific packages so other club projects can reuse it.

That repository owns its direct SocketCAN path and any epoll / socket helpers
internally. It must not depend on `kanga_canbus` or other Kanga packages. Its
public API should stay generic. Document upstream origin (expanded from
[odriverobotics/ros_odrive](https://github.com/odriverobotics/ros_odrive)),
local modifications, hardware compatibility, and release process.
