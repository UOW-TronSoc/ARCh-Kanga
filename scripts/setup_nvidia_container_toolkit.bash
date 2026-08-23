#!/usr/bin/env bash
#
# Install and register NVIDIA Container Toolkit on an Ubuntu / Debian host.
# The Docker restart is deliberately opt-in because it interrupts containers.
#
set -euo pipefail

RESTART_DOCKER=false
case "${1:-}" in
    "")
        ;;
    --restart)
        RESTART_DOCKER=true
        ;;
    -h|--help)
        cat <<'EOF'
Usage: ./scripts/setup_nvidia_container_toolkit.bash [--restart]

Installs NVIDIA Container Toolkit and registers its Docker runtime. By default,
the script does not restart Docker because doing so interrupts every running
container. Pass --restart only after stopping work that must remain running.
EOF
        exit 0
        ;;
    *)
        echo "ERROR: unknown argument: ${1}" >&2
        exit 2
        ;;
esac

if [ "${EUID}" -eq 0 ]; then
    echo "ERROR: Run this script as your ordinary user; it invokes sudo itself." >&2
    exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1 \
    || ! nvidia-smi -L >/dev/null 2>&1
then
    echo "ERROR: The host NVIDIA driver is not working; fix that before container setup." >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not installed." >&2
    exit 1
fi

echo "Installing NVIDIA Container Toolkit from NVIDIA's stable apt repository..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor --yes \
        -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker

if [ "${RESTART_DOCKER}" = true ]; then
    if [ -n "$(docker ps -q 2>/dev/null)" ]; then
        echo "WARNING: Restarting Docker will interrupt these containers:" >&2
        docker ps --format '  {{.Names}} ({{.Status}})' >&2
    fi
    sudo systemctl restart docker
    echo "Docker restarted; NVIDIA Container Toolkit is active."
else
    cat <<'EOF'

Toolkit installed and Docker configured, but the daemon has not been restarted.
After closing active containers, apply the runtime with:

  sudo systemctl restart docker

Then reopen the Kanga shell. NVIDIA passthrough will be selected automatically.
EOF
fi
