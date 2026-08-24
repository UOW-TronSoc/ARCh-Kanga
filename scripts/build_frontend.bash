#!/usr/bin/env bash
# Build the React operator UI into basestation/server/static/ (vite outDir).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/basestation/frontend"

build_with_npm() {
  cd "${FRONTEND_DIR}"
  if [[ ! -d node_modules ]]; then
    npm ci
  fi
  npm run build
}

build_with_docker() {
  docker run --rm \
    -v "${ROOT_DIR}/basestation:/src/basestation" \
    -w /src/basestation/frontend \
    node:20-bookworm-slim \
    bash -c "npm ci && npm run build"
}

if command -v npm >/dev/null 2>&1; then
  build_with_npm
elif command -v docker >/dev/null 2>&1; then
  echo "Building frontend via Docker (npm not on PATH)…"
  build_with_docker
else
  echo "ERROR: need npm or docker to build the basestation UI." >&2
  exit 1
fi

echo "Frontend built → basestation/server/static/"

cat > "${ROOT_DIR}/basestation/server/static/.gitignore" <<'EOF'
# Vite build output — run ./scripts/build_frontend.bash
*
!.gitignore
EOF
