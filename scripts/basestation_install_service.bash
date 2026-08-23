#!/usr/bin/env bash
# Install the basestation systemd unit on the rover (run with sudo).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="${ROOT_DIR}/basestation/deploy/kanga-basestation.service"
UNIT_DST="/etc/systemd/system/kanga-basestation.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/install/setup.bash" ]]; then
  echo "ERROR: ${ROOT_DIR}/install/setup.bash missing — build the workspace first." >&2
  exit 1
fi

sed "s|/home/kanga/kanga_wip|${ROOT_DIR}|g" "${UNIT_SRC}" > "${UNIT_DST}"
systemctl daemon-reload
echo "Installed ${UNIT_DST}"
echo ""
echo "  Enable on boot:  systemctl enable kanga-basestation"
echo "  Start now:       systemctl start kanga-basestation"
echo "  Status:          systemctl status kanga-basestation"
echo ""
echo "If robot bringup has its own unit, add After=/Wants= in:"
echo "  systemctl edit kanga-basestation"
