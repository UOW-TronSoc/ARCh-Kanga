#!/usr/bin/env bash
# Start the persistent onboard ROS launch agent without starting rover systems.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f install/setup.bash ]]; then
    echo "ERROR: install/setup.bash missing; build the ROS workspace first." >&2
    exit 1
fi

export KANGA_UID="${KANGA_UID:-$(id -u)}"
export KANGA_GID="${KANGA_GID:-$(id -g)}"

# shellcheck source=kanga_host_network.bash
source "${ROOT_DIR}/scripts/kanga_host_network.bash"

COMPOSE_FILES=(-f docker/compose.onboard.yaml)
if kanga_use_compose_host_network; then
    COMPOSE_FILES+=(-f docker/compose.onboard.host.yaml)
fi

if [[ "${SKIP_ONBOARD_BUILD:-0}" != "1" ]]; then
    docker compose "${COMPOSE_FILES[@]}" build
fi
docker compose "${COMPOSE_FILES[@]}" up -d --no-build

echo "Onboard launch agent is up; no rover subsystem has been started."
