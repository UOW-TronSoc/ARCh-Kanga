#!/usr/bin/env bash
#
# Host-side CAN interface setup for the Kanga rover.
#
# The HOST is responsible for creating and stably naming CAN interfaces.
# Docker later talks to these interfaces via host networking + SocketCAN.
#
# Usage:
#   ./scripts/setup_can.bash [interface] [bitrate]
#   ./scripts/setup_can.bash can_core 500000
#
set -euo pipefail

INTERFACE="${1:-can_core}"
BITRATE="${2:-500000}"

echo "Setting up CAN interface '${INTERFACE}' at bitrate ${BITRATE}..."

# 1. Bring the interface down if it exists (ignore error if already down/absent).
if ip link show "${INTERFACE}" >/dev/null 2>&1; then
    echo "Bringing ${INTERFACE} down..."
    sudo ip link set "${INTERFACE}" down || true
else
    echo "Interface ${INTERFACE} not currently present; attempting configuration anyway."
fi

# 2. Set the CAN bitrate.
echo "Setting ${INTERFACE} bitrate to ${BITRATE}..."
sudo ip link set "${INTERFACE}" type can bitrate "${BITRATE}"

# 3. Bring the interface up.
echo "Bringing ${INTERFACE} up..."
sudo ip link set "${INTERFACE}" up

# 4. Print interface details.
echo "Current state of ${INTERFACE}:"
ip -details link show "${INTERFACE}"
