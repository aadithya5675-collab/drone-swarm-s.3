#!/usr/bin/env bash
# Download the Gazebo Fuel models the world uses, so the sim runs offline.
source /opt/ros/jazzy/setup.bash
for m in "Ambulance" "Fire truck" "Pickup" "ground_station" "Jersey Barrier" "Standing person" "Rescue Randy"; do
  u="https://fuel.gazebosim.org/1.0/OpenRobotics/models/${m// /%20}"
  gz fuel download -u "$u" -v 1 && echo "ok  $m" || echo "FAIL $m"
done
