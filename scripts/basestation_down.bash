#!/usr/bin/env bash
#
# Stop the basestation server started by basestation_up.bash.
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"

COMPOSE_FILES=(-f docker/compose.basestation.yaml)
if kanga_use_compose_host_network; then
  COMPOSE_FILES+=(-f docker/compose.basestation.host.yaml)
fi

# The local onboard agent and simulation may still use the shared ROS network.
# Remove only the web service and leave that network intact.
docker compose "${COMPOSE_FILES[@]}" stop
docker compose "${COMPOSE_FILES[@]}" rm -f

echo "Basestation server stopped."
