#!/usr/bin/env bash
# Source ROS 2 and the workspace install overlay, then exec the service command.
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"

# ROS setup scripts reference unset variables (e.g. AMENT_TRACE_SETUP_FILES),
# so nounset must be relaxed while sourcing them.
set +u

if [[ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
else
  echo "ERROR: /opt/ros/${ROS_DISTRO}/setup.bash not found" >&2
  exit 1
fi

if [[ -f /workspace/install/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /workspace/install/setup.bash
else
  echo "WARN: /workspace/install/setup.bash missing; workspace msgs unavailable" >&2
fi

set -u

exec "$@"
