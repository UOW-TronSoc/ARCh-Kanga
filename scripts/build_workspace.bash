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
    # 2. Resolve dependencies for packages under src/.
    echo "Resolving dependencies with rosdep..."
    rosdep install --from-paths src --ignore-src --rosdistro humble -r -y

    # 3. Build the workspace.
    echo "Building workspace with colcon..."
    colcon build --symlink-install

    echo
    echo "Build complete. Source the overlay with:"
    echo "  source install/setup.bash"
else
    echo "No 'src/' directory found in $(pwd)."
    echo "There are no Kanga ROS 2 packages to build yet."
    echo "Create packages under 'src/' (e.g. src/<package_name>) and re-run this script."
fi
