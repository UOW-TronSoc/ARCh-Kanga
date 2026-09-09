#!/usr/bin/env bash
#
# Build the Kanga colcon workspace.
#
# Intended to be run INSIDE the dev container (where ROS 2 Humble is installed),
# from the workspace root (/workspace).
#
set -eo pipefail

# 1. Source the ROS 2 environment.
source /opt/ros/humble/setup.bash
set -u

if [ -d "src" ]; then
    # 2. Populate any source dependencies pinned in the vendor manifest.
    # Existing checkouts are left alone so routine builds work offline and do
    # not overwrite local vendor work.
    VENDOR_MANIFEST="src/vendor/kanga_vendor.repos"
    if [ -f "${VENDOR_MANIFEST}" ]; then
        mapfile -t VENDOR_REPOSITORIES < <(
            python3 - "${VENDOR_MANIFEST}" <<'PY'
import sys

import yaml


with open(sys.argv[1], encoding="utf-8") as manifest_file:
    manifest = yaml.safe_load(manifest_file)

for repository in manifest.get("repositories", {}):
    print(repository)
PY
        )

        MISSING_VENDOR_REPOSITORIES=()
        for repository in "${VENDOR_REPOSITORIES[@]}"; do
            if [ ! -d "src/vendor/${repository}" ]; then
                MISSING_VENDOR_REPOSITORIES+=("${repository}")
            fi
        done

        if [ "${#MISSING_VENDOR_REPOSITORIES[@]}" -gt 0 ]; then
            echo "Importing missing pinned vendor repositories: ${MISSING_VENDOR_REPOSITORIES[*]}"
            vcs import src/vendor \
                --input "${VENDOR_MANIFEST}" \
                --skip-existing
        fi
    fi

    # 3. Resolve dependencies for packages under src/.
    echo "Resolving dependencies with rosdep..."
    ROSDEP_ARGUMENTS=(install --from-paths src --ignore-src --rosdistro humble -r -y)
    COLCON_ARGUMENTS=(build --symlink-install)
    if [ "${KANGA_ENABLE_SIM:-1}" = "0" ]; then
        echo "Skipping Gazebo simulation packages (KANGA_ENABLE_SIM=0)."
        ROSDEP_ARGUMENTS+=(
            --skip-keys
            "ignition-gazebo6 ignition-plugin ros_gz_bridge ros_gz_sim"
        )
        COLCON_ARGUMENTS+=(--packages-skip kanga_core_simulation kanga_sim)
    fi
    rosdep "${ROSDEP_ARGUMENTS[@]}"

    # 4. Build the workspace.
    echo "Building workspace with colcon..."
    colcon "${COLCON_ARGUMENTS[@]}"

    echo
    echo "Build complete. Source the overlay with:"
    echo "  source install/setup.bash"
else
    echo "No 'src/' directory found in $(pwd)."
    echo "There are no Kanga ROS 2 packages to build yet."
    echo "Create packages under 'src/' (e.g. src/<package_name>) and re-run this script."
fi
