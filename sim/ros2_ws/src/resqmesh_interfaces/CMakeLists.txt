cmake_minimum_required(VERSION 3.8)
project(resqmesh_interfaces)
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/DroneState.msg"
  "msg/Waypoints.msg" "msg/LinkState.msg" "msg/MissionEvent.msg"
  "msg/HeightMap.msg" "msg/MeshFrame.msg"
  DEPENDENCIES std_msgs)
ament_export_dependencies(rosidl_default_runtime)
ament_package()
