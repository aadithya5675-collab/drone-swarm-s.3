std_msgs/Header header
string[] node_a
string[] node_b
float32[] quality             # 0..1, 0 = no link
float32[] distance_m
string[] reachable_base       # nodes that currently have a route to the rescue base
uint32 pins_buffered          # pins held by store-and-forward, waiting for a route
