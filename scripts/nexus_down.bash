#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"

COMPOSE_FILES=(-f docker/compose.nexus.yaml)
if kanga_use_compose_host_network; then
  COMPOSE_FILES+=(-f docker/compose.nexus.host.yaml)
fi

docker compose "${COMPOSE_FILES[@]}" stop nexus
docker compose "${COMPOSE_FILES[@]}" rm -f nexus
echo "NEXUS container stopped."
