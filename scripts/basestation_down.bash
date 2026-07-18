#!/usr/bin/env bash
#
# Stop basestation scaffold services started by basestation_up.bash.
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

docker compose -f docker/compose.basestation.yaml down

echo "Basestation scaffold stopped."
