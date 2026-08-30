#!/usr/bin/env bash
# Container entry point for the persistent onboard launch agent.
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"

# ROS setup scripts reference variables that may not exist yet.
set +u
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [[ ! -f /workspace/install/setup.bash ]]; then
    echo "ERROR: /workspace/install/setup.bash is missing." >&2
    exit 1
fi
# shellcheck disable=SC1091
source /workspace/install/setup.bash
set -u

exec ros2 launch kanga_launch_agent launch_agent.launch.py
