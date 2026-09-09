#!/usr/bin/env bash
# Stop and remove the persistent kanga-dev container.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

docker compose -f docker/compose.dev.yaml stop kanga-dev
docker compose -f docker/compose.dev.yaml rm -f kanga-dev

echo "Kanga development container stopped."
