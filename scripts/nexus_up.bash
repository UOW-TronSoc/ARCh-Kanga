#!/usr/bin/env bash
# Build and start NEXUS on port 8001. Does not start or modify the ARCh
# basestation. Reuses the workspace DDS profile and host-network selection.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"
kanga_require_docker

MODEL="${ROOT_DIR}/nexus/frontend/public/assets/models/kanga-assembly.glb"
if [[ ! -f "${MODEL}" ]] || head -c 200 "${MODEL}" | grep -q "git-lfs.github.com/spec"; then
  echo "error: the rover model is a Git LFS pointer. Install Git LFS, then run: git lfs pull" >&2
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

COMPOSE_FILES=(-f docker/compose.nexus.yaml)
if kanga_use_compose_host_network; then
  COMPOSE_FILES+=(-f docker/compose.nexus.host.yaml)
  echo "Using host networking so NEXUS joins the ROS graph on this machine."
fi

docker compose "${COMPOSE_FILES[@]}" up -d --build nexus

cat <<'EOF'

NEXUS is up:

  Rover:   http://localhost:8001/rover
  Health:  http://localhost:8001/health

Health answers while the web server is up. ros.initialized is separate.
Launch Gazebo from the ROS dev container, then confirm the latched stop with:

  ./scripts/check_nexus_drivestop.bash

Stop with: ./scripts/nexus_down.bash
EOF
