#!/usr/bin/env bash
pkill -f 'ros2 launch resqmesh_mission' ; pkill -f 'lib/resqmesh_mission/' ; pkill -f rosbridge_websocket
pkill -f 'http.server 8080' ; pkill -9 -f 'bin/px4 -i'
pkill -f 'MicroXRCEAgent udp4' ; pkill -f 'gz sim -'
sleep 2; pkill -9 -f 'gz sim -' ; echo stopped
