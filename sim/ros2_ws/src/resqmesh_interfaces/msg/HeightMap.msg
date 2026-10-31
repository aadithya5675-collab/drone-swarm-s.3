# 2.5D surface map built by a Mapper from its 3D lidar: highest return per cell (ground, debris, trees, roofs).
# World ENU metres. Cell (i, j) covers x = origin_x + j*resolution, y = origin_y + i*resolution. NaN = not seen yet.
std_msgs/Header header
string source                 # mapper that built it
float32 origin_x
float32 origin_y
float32 resolution
uint32 width                  # cells along x
uint32 height                 # cells along y
float32[] z                   # row-major, height*width
float32 coverage              # fraction of the search corridor's cells already seen
uint64 points_total           # lidar returns integrated so far
