#!/usr/bin/env bash
# Opens the Wayanad valley and the rescue camp, puts the swarm on its pads and starts the base and dashboard.
# Then: tools/trigger.sh (the landslide), tools/damage.sh <drone>, tools/stop_story.sh
source "$(dirname "$0")/story_env.sh"
bash "$SIM/tools/stop_story.sh" >/dev/null 2>&1
rm -f "$LOG"/*.log "$RUN"/truth.json "$RUN"/landslide.flag
cp "$SIM"/px4/airframes/456* "$PX4/build/px4_sitl_default/etc/init.d-posix/airframes/"
# PX4 spawns drones from its own model folder
for m in resqmesh_scout resqmesh_mapper resqmesh_relay resqmesh_scout_parked resqmesh_mapper_parked resqmesh_relay_parked resqmesh_quad; do
  rsync -a --delete "$SIM/models/$m/" "$PX4/Tools/simulation/gz/models/$m/"
done
echo "[1/5] Gazebo: Mundakkai - Chooralmala valley"
gz sim --verbose=1 -r -s "$SIM/worlds/$WORLD.sdf" > "$LOG/gz_server.log" 2>&1 &
for i in $(seq 240); do gz service -l 2>/dev/null | grep -q "/world/$WORLD/create" && break; sleep 1; done
python3 "$SIM/tools/make_gui_config.py" "$SIM/config/gui_story.config" >/dev/null
gz sim -g --gui-config "$SIM/config/gui_story.config" > "$LOG/gz_gui.log" 2>&1 &
echo "[2/5] reserve Scouts parked on their pads"
for N in $(python3 -c "import yaml; print(' '.join(d['name'] for d in yaml.safe_load(open('$CFG/fleet_story.yaml'))['drones'] if d.get('reserve')))"); do
  read PX PY <<< "$(fleet_get $N pad)"; M=$(fleet_get $N model)
  gz service -s /world/$WORLD/create --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean --timeout 5000 \
    --req "sdf: '<sdf version=\"1.9\"><include><name>parked_$N</name><uri>model://${M}_parked</uri><pose>$PX $PY 0 0 0 1.5708</pose></include></sdf>'" >/dev/null
done
echo "[3/5] uXRCE-DDS agent, radio medium, tower, base, Brain"
MicroXRCEAgent udp4 -p 8888 > "$LOG/xrce.log" 2>&1 &
ros2 launch resqmesh_mission story.launch.py sim_dir:=$SIM > "$LOG/stack.log" 2>&1 &
echo "[4/5] powering the active swarm"
for N in $(python3 -c "import yaml; print(' '.join(d['name'] for d in yaml.safe_load(open('$CFG/fleet_story.yaml'))['drones'] if not d.get('reserve')))"); do
  bash "$SIM/tools/launch_drone.sh" $N; sleep 4
done
echo "[5/5] waiting for the swarm to report in over the mesh"
for i in $(seq 30); do
  n=$(timeout 12 ros2 topic echo --once /base/fleet std_msgs/msg/String 2>/dev/null | grep -o 'state' | wc -l)
  [ "${n:-0}" -ge 5 ] && break; sleep 2
done
echo
echo "READY. Swarm on the pads at the Chooralmala camp ($n drones reporting through the tower)."
echo "  dashboard:            http://localhost:8080/story.html"
echo "  trigger the landslide: wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/trigger.sh"
echo "  damage a drone:        wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/damage.sh [scout_1|mapper_1|relay_1]"
