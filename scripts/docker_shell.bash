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
# Let ROS joy read the host's /dev/input/event* devices from inside Docker.
export KANGA_INPUT_GID="${KANGA_INPUT_GID:-$(stat -c '%g' /dev/input/event0 2>/dev/null || echo 107)}"

# docker compose run --rm gives the development user a fresh home directory on
# every invocation. Persist odrivetool's device descriptor cache from the host;
# otherwise the first Fibre-over-CAN connection must download ~50 KiB of JSON
# over the live CAN bus again. The matched UID/GID keeps the bind mount writable.
KANGA_CACHE_BASE="${XDG_CACHE_HOME:-${HOME}/.cache}"
export KANGA_ODRIVE_CACHE="${KANGA_ODRIVE_CACHE:-${KANGA_CACHE_BASE}/odrivetool}"
mkdir -p "${KANGA_ODRIVE_CACHE}"

docker compose -f docker/compose.dev.yaml run --rm --build kanga-dev
