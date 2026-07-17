#!/usr/bin/env bash
#
# Host-side CAN check for the Kanga rover.
#
# This MUST pass natively on the host before testing CAN inside Docker.
# If CAN does not work here, Docker is not the problem.
#
# Usage:
#   ./scripts/check_can.bash [interface]
#   ./scripts/check_can.bash can_core
#
set -euo pipefail

INTERFACE="${1:-can_core}"

# 1. Print all CAN interfaces.
echo "=== All CAN interfaces ==="
ip -details link show type can || true
echo

# 2. Print details of the selected interface.
echo "=== Details for ${INTERFACE} ==="
ip -details link show "${INTERFACE}"
echo

# 3. Dump up to 10 frames from the interface.
echo "=== candump ${INTERFACE} -n 10 ==="
echo "(Listening for 10 CAN frames; press Ctrl-C to stop early)"
candump "${INTERFACE}" -n 10

# 4. Explain likely causes if candump hangs.
cat <<'EOF'

If candump appears to hang with no frames, likely causes are:
  - wrong bitrate (host configured differently to the device)
  - wiring problem (CAN-H/CAN-L swapped or disconnected)
  - missing/incorrect bus termination (need ~120 ohm at both ends)
  - ODrive (or other CAN node) not powered
  - wrong interface name (e.g. device is can1, not can0)
EOF
