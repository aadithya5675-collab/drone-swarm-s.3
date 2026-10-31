#!/usr/bin/env bash
# PX4 SITL build dependencies and the uXRCE-DDS agent. Run as root after cloning PX4-Autopilot into ~/PX4-Autopilot:
#   wsl -d Ubuntu-24.04 -u root -- bash setup/02_px4_deps.sh [wsl_user]
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
PX4=/home/${1:-$(ls /home | head -1)}/PX4-Autopilot

[ -f /root/.px4_apt_done ] || { bash "$PX4/Tools/setup/ubuntu.sh" --no-nuttx --no-sim-tools || true; touch /root/.px4_apt_done; }
# keep Ubuntu's numpy: ROS 2 is built against it
echo "numpy==$(python3 -c 'import numpy; print(numpy.__version__)')" > /tmp/pin.txt
python3 -m pip install --break-system-packages -c /tmp/pin.txt -r "$PX4/Tools/setup/requirements.txt"
python3 -m pip install --break-system-packages "empy==3.3.4"            # ROS 2 rosidl and PX4 both want empy 3

if ! command -v MicroXRCEAgent >/dev/null; then
  rm -rf /tmp/xrce && git clone --depth 1 -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /tmp/xrce
  cmake -S /tmp/xrce -B /tmp/xrce/build -DCMAKE_BUILD_TYPE=Release
  cmake --build /tmp/xrce/build -j"$(nproc)"
  cmake --install /tmp/xrce/build
  ldconfig /usr/local/lib/
fi
echo "PX4 DEPS DONE"
