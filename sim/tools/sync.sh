#!/usr/bin/env bash
# Copy this checkout into WSL (~/resqmesh/sim), where the story scripts run. usage: wsl -- bash tools/sync.sh
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[ -d "$SRC/ros2_ws/src/resqmesh_mission" ] || { echo "not a ResQMesh checkout: $SRC" >&2; exit 1; }
rsync -a --exclude dashboard/app/node_modules --exclude ros2_ws/build --exclude ros2_ws/install --exclude ros2_ws/log \
  --exclude cad_export/bodies --exclude terrain/tiles "$SRC/" "$HOME/resqmesh/sim/"
sed -i 's/\r$//' "$HOME"/resqmesh/sim/tools/*.sh
echo "synced $SRC -> $HOME/resqmesh/sim"
