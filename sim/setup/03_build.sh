#!/usr/bin/env bash
# Copies the project into ~/resqmesh, installs models and airframes into PX4, builds PX4 SITL and the ROS 2
# workspace. Run as your normal WSL user:  wsl -d Ubuntu-24.04 -- bash setup/03_build.sh
set -eo pipefail
WIN=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[ -d "$WIN/ros2_ws/src/resqmesh_mission" ] || { echo "not a ResQMesh checkout: $WIN" >&2; exit 1; }
SIM=$HOME/resqmesh/sim
PX4=$HOME/PX4-Autopilot
source /opt/ros/jazzy/setup.bash

mkdir -p "$SIM"
rsync -a --delete --exclude dashboard/app/node_modules --exclude cad_export/bodies --exclude 'cad_export/*.step' --exclude 'cad_export/roles/*.step' \
      --exclude ros2_ws/build --exclude ros2_ws/install --exclude ros2_ws/log --exclude terrain/tiles "$WIN/" "$SIM/"
find "$SIM" -name '*.sh' -exec sed -i 's/\r$//' {} +


GZ=$PX4/Tools/simulation/gz
for m in resqmesh_quad resqmesh_scout resqmesh_mapper resqmesh_relay resqmesh_scout_parked resqmesh_mapper_parked resqmesh_relay_parked; do
  rm -rf "$GZ/models/$m" && cp -r "$SIM/models/$m" "$GZ/models/$m"
done
cp "$SIM/worlds/"*.sdf "$GZ/worlds/"
AF=$PX4/ROMFS/px4fmu_common/init.d-posix/airframes
for f in "$SIM"/px4/airframes/*; do
  cp "$f" "$AF/"; chmod +x "$AF/$(basename "$f")"
  grep -q "$(basename "$f")" "$AF/CMakeLists.txt" || sed -i "/^px4_add_romfs_files(/a\\	$(basename "$f")" "$AF/CMakeLists.txt"
done
make -C "$PX4" px4_sitl_default


WS=$SIM/ros2_ws
[ -d "$HOME/px4_msgs" ] || git clone --depth 1 https://github.com/PX4/px4_msgs.git "$HOME/px4_msgs"
# px4_msgs must match the firmware exactly: replace its definitions with the ones in this PX4 tree
rm -f "$HOME/px4_msgs/msg/"*.msg "$HOME/px4_msgs/srv/"*.srv
cp "$PX4/msg/"*.msg "$HOME/px4_msgs/msg/"
[ -d "$PX4/msg/versioned" ] && cp "$PX4/msg/versioned/"*.msg "$HOME/px4_msgs/msg/"
[ -d "$PX4/srv" ] && cp "$PX4/srv/"*.srv "$HOME/px4_msgs/srv/"
ln -sfn "$HOME/px4_msgs" "$WS/src/px4_msgs"
cd "$WS"
colcon build --symlink-install --packages-up-to resqmesh_mission --event-handlers console_cohesion+ \
  --cmake-args -DCMAKE_BUILD_TYPE=Release
echo "BUILD DONE"
