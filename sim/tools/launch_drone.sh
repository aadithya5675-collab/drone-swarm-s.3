#!/usr/bin/env bash
# Start one drone on its pad: PX4 SITL, mesh agent, companion agent and its detector or lidar mapper.
# usage: launch_drone.sh <name>
source "$(dirname "$0")/story_env.sh"
N=$1; ROLE=$(fleet_get $N role); INST=$(fleet_get $N px4_instance); MODEL=$(fleet_get $N model); read PX PY <<< "$(fleet_get $N pad)"
AF=$(python3 -c "print({'scout':4560,'mapper':4561,'relay':4562}['$ROLE'])")
gz service -s /world/$WORLD/remove --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 3000 \
  --req "name: \"parked_$N\" type: MODEL" >/dev/null 2>&1
( cd "$PX4" && PX4_GZ_STANDALONE=1 PX4_GZ_WORLD=$WORLD PX4_SYS_AUTOSTART=$AF PX4_SIM_MODEL=gz_$MODEL \
  PX4_GZ_MODEL_POSE="$PX,$PY,0.15,0,0,1.5708" PX4_UXRCE_DDS_NS=$N exec ./build/px4_sitl_default/bin/px4 -i $INST -d ) > "$LOG/px4_$N.log" 2>&1 &
COMMON="-p fleet:=$CFG/fleet_story.yaml -p layout:=$CFG/wayanad.json -p prior:=$CFG/dem_prior.npz"
ros2 run resqmesh_mission mesh_agent --ros-args -r __node:=mesh_$N -p node:=$N > "$LOG/mesh_$N.log" 2>&1 &
ros2 run resqmesh_mission drone_agent --ros-args -r __node:=agent_$N -p drone:=$N -p role:=$ROLE -p px4_ns:=$N \
  -p px4_instance:=$INST -p spawn_x:=$PX -p spawn_y:=$PY -p cruise_speed:=$(python3 -c "import yaml; print(float(yaml.safe_load(open('$CFG/fleet_story.yaml'))['mission']['cruise_speed_mps']))") -p prior:=$CFG/dem_prior.npz > "$LOG/agent_$N.log" 2>&1 &
G=/world/$WORLD/model/${MODEL}_$INST/link/base_link/sensor
if [ "$ROLE" = scout ]; then
  ros2 run resqmesh_mission story_detector --ros-args -r __node:=detector_$N -p drone:=$N -p role:=$ROLE -p seed:=$INST     -p fleet:=$CFG/fleet_story.yaml -p layout:=$CFG/wayanad.json -p params:=$CFG/vehicle_params.yaml -p prior:=$CFG/dem_prior.npz     -p gz_prefix:=$G > "$LOG/detector_$N.log" 2>&1 &
elif [ "$ROLE" = mapper ]; then
  ros2 run resqmesh_mission lidar_mapper --ros-args -r __node:=lidar_mapper_$N -p drone:=$N -p layout:=$CFG/wayanad.json     -p prior:=$CFG/dem_prior.npz -p gz_prefix:=$G > "$LOG/lidar_$N.log" 2>&1 &
fi
echo "$N ($ROLE) launching on pad ($PX, $PY), PX4 instance $INST"
