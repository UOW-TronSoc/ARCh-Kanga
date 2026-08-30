#!/usr/bin/env bash
# Shared by docker_shell.bash and basestation_{up,down}.bash.
#
# Host networking is only useful on a real Linux host (rover Orin, native
# Ubuntu) where "host" is the machine. Docker Desktop — including the Ubuntu
# WSL2 distro it integrates with — implements host networking inside a VM, and
# Compose then discards published ports such as 8000:8000.
#
# Override: KANGA_HOST_NETWORK=1 force on, KANGA_HOST_NETWORK=0 force off.

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
