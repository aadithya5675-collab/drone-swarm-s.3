#!/usr/bin/env bash
# Hit a flying drone (a random Scout unless named). usage: damage.sh [scout_1|mapper_1|relay_1|...]
source "$(dirname "$0")/story_env.sh"
ros2 run resqmesh_mission damage_scout --ros-args -p fleet:=$CFG/fleet_story.yaml -p scout:=${1:-any}
