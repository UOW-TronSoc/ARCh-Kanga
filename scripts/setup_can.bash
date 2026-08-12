#!/usr/bin/env bash
#
# Host-side CAN interface setup for the Kanga rover.
#
# The HOST is responsible for creating and stably naming CAN interfaces.
# Docker later talks to these interfaces via host networking + SocketCAN.
#
# Usage:
#   ./scripts/setup_can.bash [interface] [bitrate] [tx_queue_len]
#   ./scripts/setup_can.bash can_core 250000 256
#
set -euo pipefail

INTERFACE="${1:-can_core}"
BITRATE="${2:-250000}"
TX_QUEUE_LEN="${3:-256}"

if ! [[ "${TX_QUEUE_LEN}" =~ ^[1-9][0-9]*$ ]]; then
    echo "tx_queue_len must be a positive integer (got '${TX_QUEUE_LEN}')." >&2
    exit 2
fi

echo "Setting up CAN interface '${INTERFACE}' at bitrate ${BITRATE}, txqueuelen ${TX_QUEUE_LEN}..."

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

# 3. Give Fibre/configuration transfers enough SocketCAN TX queue headroom.
# The kernel/default value of 10 is too small for bursty multi-frame transfers.
echo "Setting ${INTERFACE} TX queue length to ${TX_QUEUE_LEN}..."
sudo ip link set dev "${INTERFACE}" txqueuelen "${TX_QUEUE_LEN}"

# 4. Bring the interface up.
echo "Bringing ${INTERFACE} up..."
sudo ip link set "${INTERFACE}" up

# 5. Print interface details and accumulated error counters.
echo "Current state of ${INTERFACE}:"
ip -details -statistics link show "${INTERFACE}"
