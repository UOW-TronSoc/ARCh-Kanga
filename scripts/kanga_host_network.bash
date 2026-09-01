#!/usr/bin/env bash
# Shared by docker_shell.bash and basestation_{up,down}.bash.
#
# Host networking is only useful on a real Linux host (rover Orin, native
# Ubuntu) where "host" is the machine. Docker Desktop — including the Ubuntu
# WSL2 distro it integrates with — implements host networking inside a VM, and
# Compose then discards published ports such as 8000:8000.
#
# Override: KANGA_HOST_NETWORK=1 force on, KANGA_HOST_NETWORK=0 force off.

kanga_require_docker() {
    local docker_output=""
    local docker_status=0

    if ! command -v docker >/dev/null 2>&1; then
        cat >&2 <<'EOF'
ERROR: docker is not on PATH.

Install Docker Engine, or on Windows/WSL2 start Docker Desktop and enable
this distro under Settings → Resources → WSL integration.
EOF
        exit 1
    fi

    docker_output="$(docker info 2>&1)" || docker_status=$?
    if [[ "${docker_status}" -eq 0 ]]; then
        return 0
    fi

    cat >&2 <<'EOF'
ERROR: Docker is not available.

This is not a second kanga-dev container. The docker CLI cannot talk to an
engine, so later scripts must not treat its error text as container names.

On WSL2 this usually means Docker Desktop is stopped, or Ubuntu is not enabled
under Settings → Resources → WSL integration. Start Docker Desktop, wait until
it is running, then open a new terminal.
EOF
    if [[ -n "${docker_output}" ]]; then
        printf '\n%s\n' "${docker_output}" >&2
    fi
    exit 1
}

kanga_use_compose_host_network() {
    case "${KANGA_HOST_NETWORK:-auto}" in
        1|true|yes)
            return 0
            ;;
        0|false|no)
            return 1
            ;;
        auto)
            ;;
        *)
            echo "ERROR: KANGA_HOST_NETWORK must be one of: auto, 1, 0." >&2
            return 1
            ;;
    esac

    [[ "$(uname -s)" == "Linux" ]] || return 1

    # WSL2: uname is Linux, but Docker Desktop's engine is still a VM.
    if [[ -n "${WSL_DISTRO_NAME:-}${WSL_INTEROP:-}" ]]; then
        return 1
    fi
    if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
        return 1
    fi
    if [[ -r /proc/version ]] && grep -qi microsoft /proc/version; then
        return 1
    fi
    return 0
}
