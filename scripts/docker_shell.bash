#!/usr/bin/env bash
#
# Convenience script to open an interactive shell in the Kanga dev container.
#
# Builds (if needed) and runs the kanga-dev service, removing the container on exit.
# Set KANGA_SIM=none to skip Gazebo Fortress and ros_gz (needed on Apple Silicon).
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
# Let the non-root container user open the host's direct-rendering nodes.
export KANGA_RENDER_GID="${KANGA_RENDER_GID:-$(stat -c '%g' /dev/dri/renderD128 2>/dev/null || echo 109)}"

# docker compose run --rm gives the development user a fresh home directory on
# every invocation. Persist odrivetool's device descriptor cache from the host;
# otherwise the first Fibre-over-CAN connection must download ~50 KiB of JSON
# over the live CAN bus again. The matched UID/GID keeps the bind mount writable.
KANGA_CACHE_BASE="${XDG_CACHE_HOME:-${HOME}/.cache}"
export KANGA_ODRIVE_CACHE="${KANGA_ODRIVE_CACHE:-${KANGA_CACHE_BASE}/odrivetool}"
mkdir -p "${KANGA_ODRIVE_CACHE}"

# shellcheck source=kanga_host_network.bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kanga_host_network.bash"

COMPOSE_ARGUMENTS=(-f docker/compose.dev.yaml)

# Native Linux (rover Orin, etc.): real host networking for SocketCAN and the
# ROS graph. Docker Desktop — macOS, Windows, and WSL2 — stays on the default
# bridge in compose.dev.yaml so published ports still work.
if kanga_use_compose_host_network; then
    COMPOSE_ARGUMENTS+=(-f docker/compose.dev.host.yaml)
fi

# KANGA_SIM=full (default) installs Gazebo Fortress and ros_gz. KANGA_SIM=none
# skips those packages so the image builds on hosts without Humble sim binaries,
# such as Apple Silicon.
KANGA_SIM_MODE="${KANGA_SIM:-full}"
case "${KANGA_SIM_MODE}" in
    full)
        ;;
    none)
        COMPOSE_ARGUMENTS+=(-f docker/compose.nosim.yaml)
        echo "Gazebo / ros_gz packages omitted from the image."
        ;;
    *)
        echo "ERROR: KANGA_SIM must be one of: full, none." >&2
        exit 1
        ;;
esac

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

        # KANGA_GPU=auto (default) uses NVIDIA when both the host driver and
        # Docker runtime are ready. KANGA_GPU=nvidia makes a missing runtime a
        # hard error; KANGA_GPU=none leaves GPU selection to Mesa / the host.
        KANGA_GPU_MODE="${KANGA_GPU:-auto}"
        case "${KANGA_GPU_MODE}" in
            auto|nvidia|none)
                ;;
            *)
                echo "ERROR: KANGA_GPU must be one of: auto, nvidia, none." >&2
                exit 1
                ;;
        esac

        HOST_HAS_NVIDIA=false
        if command -v nvidia-smi >/dev/null 2>&1 \
            && nvidia-smi -L >/dev/null 2>&1
        then
            HOST_HAS_NVIDIA=true
        fi

        DOCKER_HAS_NVIDIA=false
        if docker info --format '{{json .Runtimes}}' 2>/dev/null \
            | grep -q '"nvidia"'
        then
            DOCKER_HAS_NVIDIA=true
        fi

        if [ "${KANGA_GPU_MODE}" != "none" ] \
            && [ "${HOST_HAS_NVIDIA}" = true ] \
            && [ "${DOCKER_HAS_NVIDIA}" = true ]
        then
            COMPOSE_ARGUMENTS+=(-f docker/compose.nvidia.yaml)
            echo "NVIDIA GPU passthrough enabled."
        elif [ "${KANGA_GPU_MODE}" = "nvidia" ]; then
            cat >&2 <<'EOF'
ERROR: NVIDIA GPU passthrough was requested but is not ready.

The host must have a working NVIDIA driver and Docker must register the NVIDIA
runtime. Run ./scripts/setup_nvidia_container_toolkit.bash, then restart Docker
after closing active containers.
EOF
            exit 1
        elif [ "${KANGA_GPU_MODE}" = "auto" ] \
            && [ "${HOST_HAS_NVIDIA}" = true ] \
            && [ "${DOCKER_HAS_NVIDIA}" = false ]
        then
            cat >&2 <<'EOF'
WARNING: The host NVIDIA GPU is working, but Docker's NVIDIA runtime is absent.
The GUI will use an available Mesa renderer. To enable the NVIDIA GPU, run:
  ./scripts/setup_nvidia_container_toolkit.bash
EOF
        fi
    else
        echo "WARNING: DISPLAY is set but no Xauthority file was found; starting headless." >&2
    fi
fi

docker compose "${COMPOSE_ARGUMENTS[@]}" run --rm --build kanga-dev
