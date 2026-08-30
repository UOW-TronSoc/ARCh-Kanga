#!/usr/bin/env bash
#
# Stop the basestation server started by basestation_up.bash.
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILES=(-f docker/compose.basestation.yaml)
if [[ "$(uname -s)" == "Linux" ]]; then
  COMPOSE_FILES+=(-f docker/compose.basestation.host.yaml)
fi

docker compose "${COMPOSE_FILES[@]}" down

echo "Basestation server stopped."
