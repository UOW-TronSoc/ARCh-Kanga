# Vendor repositories

External ROS repositories used by Kanga are imported beneath this structure
folder and remain independently maintained. This folder is not a ROS package.

Use a version-controlled `.repos` manifest and `vcs import` so each dependency
is pinned to an intentional revision. Do not manually copy third-party source
trees into this repository.

## ODrive

The reusable ODrive ROS integration lives in its own repository and is imported
here once that repository and its stable interface exist. It must remain
independent of Kanga-specific packages so other club projects can reuse it.

That repository owns its direct SocketCAN path and any epoll / socket helpers
internally. It must not depend on `kanga_canbus` or other Kanga packages. Its
public API should stay generic. Document upstream origin (expanded from
[odriverobotics/ros_odrive](https://github.com/odriverobotics/ros_odrive)),
local modifications, hardware compatibility, and release process.
