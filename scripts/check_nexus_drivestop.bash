#!/usr/bin/env bash
# Late subscriber inside the NEXUS container. Gazebo must already be running.
# QoS matches WHS: reliable, transient-local, keep-last one.
set -euo pipefail

if ! docker ps --format '{{.Names}}' | grep -qx 'nexus'; then
  echo "error: the nexus container is not running. Start it with ./scripts/nexus_up.bash" >&2
  exit 1
fi

docker exec nexus bash -lc \
  'ros2 topic echo --once /drivestop --qos-reliability reliable --qos-durability transient_local --qos-history keep_last --qos-depth 1'
