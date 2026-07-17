#!/usr/bin/env bash
#
# Convenience script to open an interactive shell in the Kanga dev container.
#
# Builds (if needed) and runs the kanga-dev service, removing the container on exit.
#
set -euo pipefail

# Pass the host identity into image builds so bind-mounted workspace artifacts
# remain editable by the host user. Defaults in Compose still cover UID/GID 1000.
export KANGA_UID="${KANGA_UID:-$(id -u)}"
export KANGA_GID="${KANGA_GID:-$(id -g)}"

docker compose -f docker/compose.dev.yaml run --rm --build kanga-dev
