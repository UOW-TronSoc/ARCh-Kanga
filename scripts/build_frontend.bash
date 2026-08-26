#!/usr/bin/env bash
# Build the React operator UI into basestation/server/static/ (vite outDir).
#
# Default: Node 20 via Docker (same toolchain for every machine). Host npm is
# opt-in for UI iteration only — set USE_HOST_NPM=1 when you have Node 18+.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/basestation/frontend"

host_node_major() {
  node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0
}

build_with_npm() {
  local major
  major="$(host_node_major)"
  if (( major < 18 )); then
    echo "ERROR: host Node is v$(node -v 2>/dev/null || echo '?') (need 18+ for Vite 6)." >&2
    echo "Unset USE_HOST_NPM to build with Docker, or upgrade Node." >&2
    exit 1
  fi
  cd "${FRONTEND_DIR}"
  if [[ ! -d node_modules ]]; then
    npm ci
  fi
  npm run build
}

build_with_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker not found (needed to build the basestation UI)." >&2
    exit 1
  fi
  echo "Building frontend via Docker (node:20-bookworm-slim)…"
  docker run --rm \
    -v "${ROOT_DIR}/basestation:/src/basestation" \
    -w /src/basestation/frontend \
    node:20-bookworm-slim \
    bash -c "npm ci && npm run build"
}

if [[ "${USE_HOST_NPM:-0}" == "1" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: USE_HOST_NPM=1 but npm is not on PATH." >&2
    exit 1
  fi
  build_with_npm
else
  build_with_docker
fi

echo "Frontend built → basestation/server/static/"

cat > "${ROOT_DIR}/basestation/server/static/.gitignore" <<'EOF'
# Vite build output — run ./scripts/build_frontend.bash
*
!.gitignore
EOF
