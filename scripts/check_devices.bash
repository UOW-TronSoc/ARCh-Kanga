#!/usr/bin/env bash
#
# Host-side device/environment check for the Kanga rover.
#
# Prints a quick overview of the host so we can confirm hardware, CAN, and Docker
# are visible BEFORE entering the container.
#
set -euo pipefail

echo "==================== System info ===================="
lsb_release -a || true
uname -a || true

echo
echo "==================== Jetson / NVIDIA info ===================="
cat /etc/nv_tegra_release || true

echo
echo "==================== USB devices ===================="
lsusb || true

echo
echo "==================== Network interfaces ===================="
ip link show || true

echo
echo "==================== CAN interfaces ===================="
ip -details link show type can || true

echo
echo "==================== Video devices ===================="
ls -l /dev/video* 2>/dev/null || echo "No /dev/video devices found"

echo
echo "==================== Serial devices ===================="
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No USB serial devices found"

echo
echo "==================== Docker ===================="
docker --version || true
docker compose version || true
