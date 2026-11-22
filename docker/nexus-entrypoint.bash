#!/usr/bin/env bash
# Source the ARCh workspace overlay when it has been built, then start NEXUS.
# A missing overlay still leaves the web server up; /health reports ROS apart
# from that.
set -euo pipefail

set +u
source /opt/ros/humble/setup.bash
if [[ -f /workspace/install/setup.bash ]]; then
  source /workspace/install/setup.bash
fi
set -u

cat >/etc/profile.d/nexus-ros.sh <<'EOF'
set +u
source /opt/ros/humble/setup.bash
if [[ -f /workspace/install/setup.bash ]]; then
  source /workspace/install/setup.bash
fi
set -u
EOF
if ! grep -q '/etc/profile.d/nexus-ros.sh' /etc/bash.bashrc 2>/dev/null; then
  printf '\n%s\n' 'source /etc/profile.d/nexus-ros.sh' >> /etc/bash.bashrc
fi

exec "$@"
