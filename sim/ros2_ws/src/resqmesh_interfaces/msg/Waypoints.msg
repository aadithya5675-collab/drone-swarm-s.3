# Path for one drone, world ENU metres. The flight agent flies them in order.
std_msgs/Header header
string drone
string sector_id
uint32 plan_version
float64[] x
float64[] y
float64[] z
uint32 start_index            # resume point when a path is handed over mid-way
bool land_at_end              # return-and-land path: land at the last waypoint
string altitude_mode          # "AGL": z is height above the mapped surface (terrain following), "ABS": world z
