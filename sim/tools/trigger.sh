#!/usr/bin/env bash
# Trigger the landslide (6 people in the search area, 2 of them deceased). usage: trigger.sh [seed]
source "$(dirname "$0")/story_env.sh"
ros2 run resqmesh_mission trigger_landslide --ros-args -p sim_dir:=$SIM -p seed:=${1:--1}
