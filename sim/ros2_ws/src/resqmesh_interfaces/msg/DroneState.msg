std_msgs/Header header
string drone                  # scout_1, scout_2, mapper_1, mapper_2, relay_1
string role                   # scout | mapper | relay
string state                  # STAGING TAKEOFF SEARCHING HOLDING RETURNING LANDED LOST
float64 x                     # world ENU, metres
float64 y
float64 z
float32 battery               # 0..1 (simulated)
string sector_id              # current assignment, "" if none
float32 sector_progress       # 0..1 of the current sector's path flown
uint32 waypoint_index         # waypoints of the current path flown so far
uint32 plan_version           # version of the path being flown
