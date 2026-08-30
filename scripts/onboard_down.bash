#!/usr/bin/env bash
# Stop the onboard agent and any launch processes that it owns.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck source=kanga_host_network.bash
source "${ROOT_DIR}/scripts/kanga_host_network.bash"

COMPOSE_FILES=(-f docker/compose.onboard.yaml)
if kanga_use_compose_host_network; then
    COMPOSE_FILES+=(-f docker/compose.onboard.host.yaml)
fi

# Basestation, onboard, and local simulation deliberately share the Compose
# project network on Docker Desktop. Remove only this service, not that network.
docker compose "${COMPOSE_FILES[@]}" stop
docker compose "${COMPOSE_FILES[@]}" rm -f
echo "Onboard launch agent stopped."
