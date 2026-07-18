#!/usr/bin/env bash
#
# Build and start basestation scaffold services (ports 3000/8000/8001/8080).
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

docker compose -f docker/compose.basestation.yaml build
docker compose -f docker/compose.basestation.yaml up -d

cat <<'EOF'

Basestation scaffold is up (host networking):

  Frontend:  http://localhost:3000/
  Django:    http://localhost:8000/health
  Arm API:   http://localhost:8001/health
  FastAPI:   http://localhost:8080/health

Stop with: ./scripts/basestation_down.bash
EOF
