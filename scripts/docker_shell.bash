#!/usr/bin/env bash
#
# Convenience script to open an interactive shell in the Kanga dev container.
#
# Builds (if needed) and runs the kanga-dev service, removing the container on exit.
#
set -euo pipefail

if [ "${EUID}" -eq 0 ]; then
    cat >&2 <<'EOF'
ERROR: Do not run docker_shell.bash with sudo.

The script passes your host UID/GID into the development image and expects
your user account to have access to the Docker socket.
EOF
    exit 1
fi

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

COMPOSE_ARGUMENTS=(-f docker/compose.dev.yaml)

# Forward an available desktop X11 session so RViz and other Qt tools work in
# the ordinary development shell. Headless/SSH sessions continue without the
# GUI override.
if [ -n "${DISPLAY:-}" ]; then
    GUI_XAUTHORITY="${KANGA_XAUTHORITY:-${XAUTHORITY:-}}"

    if [ -z "${GUI_XAUTHORITY}" ] || [ ! -f "${GUI_XAUTHORITY}" ]; then
        for candidate in \
            "${HOME}/.Xauthority" \
            "${XDG_RUNTIME_DIR:-}/gdm/Xauthority"
        do
            if [ -f "${candidate}" ]; then
                GUI_XAUTHORITY="${candidate}"
                break
            fi
        done
    fi

    if [ -n "${GUI_XAUTHORITY}" ] && [ -f "${GUI_XAUTHORITY}" ]; then
        export KANGA_XAUTHORITY="${GUI_XAUTHORITY}"
        COMPOSE_ARGUMENTS+=(-f docker/compose.gui.yaml)
        echo "Docker GUI forwarding enabled for DISPLAY=${DISPLAY}."
    else
        echo "WARNING: DISPLAY is set but no Xauthority file was found; starting headless." >&2
    fi
fi

docker compose "${COMPOSE_ARGUMENTS[@]}" run --rm --build kanga-dev
