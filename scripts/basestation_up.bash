#!/usr/bin/env bash
#
# Build and start the basestation server (operator UI + API on port 8000).
# Requires a prior workspace build so install/setup.bash exists (Path A).
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f install/setup.bash ]]; then
  cat >&2 <<'EOF'
ERROR: install/setup.bash not found.

Build the ROS workspace first (Path A), then retry:

  docker compose -f docker/compose.dev.yaml build
  ./scripts/docker_shell.bash
  # inside the container:
  ./scripts/build_workspace.bash

EOF
  exit 1
fi

# Match docker_shell.bash identity exports for consistency on this machine.
export KANGA_UID="${KANGA_UID:-$(id -u)}"
export KANGA_GID="${KANGA_GID:-$(id -g)}"

if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  ./scripts/build_frontend.bash
fi

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"

# Default compose publishes 8000:8000 (required on Docker Desktop / WSL).
# Native Linux can opt into host networking to share the ROS graph.
COMPOSE_FILES=(-f docker/compose.basestation.yaml)
if kanga_use_compose_host_network; then
  COMPOSE_FILES+=(-f docker/compose.basestation.host.yaml)
fi

docker compose "${COMPOSE_FILES[@]}" build
docker compose "${COMPOSE_FILES[@]}" up -d

cat <<'EOF'

Basestation server is up:

  Operator UI:  http://localhost:8000/
  Health:       http://localhost:8000/health

Stop with: ./scripts/basestation_down.bash
EOF
