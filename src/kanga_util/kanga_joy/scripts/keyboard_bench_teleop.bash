#!/usr/bin/env bash
# Run the existing bench safety node beside the interactive keyboard adapter.
set -euo pipefail

PACKAGE_PREFIX="$(ros2 pkg prefix kanga_joy)"
BENCH_CONFIG="${PACKAGE_PREFIX}/share/kanga_joy/config/bench_teleop.yaml"
BENCH_EXECUTABLE="${PACKAGE_PREFIX}/lib/kanga_joy/bench_teleop"
KEYBOARD_EXECUTABLE="${PACKAGE_PREFIX}/lib/kanga_joy/keyboard_joy"
BENCH_PID=""

cleanup() {
    if [ -n "${BENCH_PID}" ]; then
        # SIGINT follows the node's normal shutdown path, which publishes one
        # final zero Twist before destroying its ROS context.
        kill -INT "${BENCH_PID}" 2>/dev/null || true
        wait "${BENCH_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

"${BENCH_EXECUTABLE}" \
    --ros-args --params-file "${BENCH_CONFIG}" &
BENCH_PID="$!"

# Keep this process in the foreground so it owns the interactive terminal.
"${KEYBOARD_EXECUTABLE}" "$@"
