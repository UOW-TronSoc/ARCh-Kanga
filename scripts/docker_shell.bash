#!/usr/bin/env bash
#
# Convenience script to open an interactive shell in the Kanga dev container.
#
# Builds (if needed) and runs the kanga-dev service, removing the container on exit.
#
set -euo pipefail

docker compose -f docker/compose.dev.yaml run --rm kanga-dev
