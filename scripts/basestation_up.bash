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

  ./scripts/docker_shell.bash
  # inside the container:
  ./scripts/build_workspace.bash

EOF
  exit 1
fi

# Host workspace path for the Terminal page (starting cwd of the host PTY).
export KANGA_HOST_WORKSPACE="${KANGA_HOST_WORKSPACE:-${ROOT_DIR}}"

# Prefer the workspace directory owner so systemd (User=root) does not spawn
# a root host shell. Fall back to the invoking uid/gid.
if [[ -z "${KANGA_UID:-}" || -z "${KANGA_GID:-}" ]]; then
  if [[ -d "${KANGA_HOST_WORKSPACE}" ]]; then
    export KANGA_UID="${KANGA_UID:-$(stat -c '%u' "${KANGA_HOST_WORKSPACE}")}"
    export KANGA_GID="${KANGA_GID:-$(stat -c '%g' "${KANGA_HOST_WORKSPACE}")}"
  else
    export KANGA_UID="${KANGA_UID:-$(id -u)}"
    export KANGA_GID="${KANGA_GID:-$(id -g)}"
  fi
fi

# Real home dir for ~/.bashrc (aliases, ls colors). Container passwd may differ.
if [[ -z "${KANGA_USER_HOME:-}" ]]; then
  KANGA_USER_HOME="$(getent passwd "${KANGA_UID}" 2>/dev/null | cut -d: -f6 || true)"
  if [[ -n "${KANGA_USER_HOME}" ]]; then
    export KANGA_USER_HOME
  fi
fi

if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  ./scripts/build_frontend.bash
fi

# Boot-time starts skip image rebuilds (network metadata fetch can hang).
# Default SKIP_BASESTATION_BUILD to SKIP_FRONTEND_BUILD so existing systemd
# units that only set the latter still skip compose build. Override with
# SKIP_BASESTATION_BUILD=0 to rebuild the image without rebuilding the UI.
SKIP_BASESTATION_BUILD="${SKIP_BASESTATION_BUILD:-${SKIP_FRONTEND_BUILD:-0}}"

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"

# Default compose publishes 8000:8000 (required on Docker Desktop / WSL).
# Native Linux can opt into host networking to share the ROS graph.
COMPOSE_FILES=(-f docker/compose.basestation.yaml)
if kanga_use_compose_host_network; then
  COMPOSE_FILES+=(-f docker/compose.basestation.host.yaml)
fi

if [[ "${SKIP_BASESTATION_BUILD}" != "1" ]]; then
  docker compose "${COMPOSE_FILES[@]}" build
fi
docker compose "${COMPOSE_FILES[@]}" up -d --no-build

cat <<'EOF'

Basestation server is up:

  Operator UI:  http://localhost:8000/
  Health:       http://localhost:8000/health

Stop with: ./scripts/basestation_down.bash
EOF
