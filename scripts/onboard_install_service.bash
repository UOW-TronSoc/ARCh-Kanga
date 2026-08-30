#!/usr/bin/env bash
# Install the persistent onboard launch-agent systemd unit (run with sudo).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="${ROOT_DIR}/src/kanga_util/kanga_launch_agent/deploy/kanga-onboard.service"
UNIT_DST="/etc/systemd/system/kanga-onboard.service"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi
if [[ ! -f "${ROOT_DIR}/install/setup.bash" ]]; then
    echo "ERROR: ${ROOT_DIR}/install/setup.bash missing; build first." >&2
    exit 1
fi

sed "s|/home/kanga/kanga_wip|${ROOT_DIR}|g" "${UNIT_SRC}" > "${UNIT_DST}"
systemctl daemon-reload

echo "Installed ${UNIT_DST}"
echo "Build the image once with: ${ROOT_DIR}/scripts/onboard_up.bash"
echo "Then enable on boot: systemctl enable --now kanga-onboard"
