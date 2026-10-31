# ResQMesh simulation

A swarm of seven drones searches the debris of the 30 July 2024 Mundakkai–Chooralmala landslide (Wayanad, Kerala)
on the real terrain of the valley. Gazebo Harmonic simulates the world, PX4 SITL flies every drone, ROS 2 Jazzy runs
the swarm software, and a React website is the rescue camp's mission control.

| Role | Count | Hardware (Fusion designs from `tools/fusion_build_roles.py`) | Job |
|---|---|---|---|
| Scout | 2 + 2 reserve | Jetson Nano, Arducam IMX219 RGB + FLIR Lepton 3.5 thermal on a head tilted 34° down | the only drones that find people; geolocate them |
| Mapper | 2 | Livox Mid-360 under the frame (spin axis forward), Jetson Nano, LiPo on top, tall legs | 3D lidar map of the new ground; hosts the planner |
| Relay-Anchor | 1 | RFD900x long-range modem, Wi-Fi/LoRa mesh node, Raspberry Pi Zero 2 W | 4 km backhaul from the swarm to the camp tower |

All three are built on the team's frame (`assembly final`) with a SpeedyBee F405 Mini stack, an M10 GNSS mast and
carbon landing legs. Component shapes are datasheet-sized envelopes, not vendor CAD.

## Layout
```
cad_export/   Fusion exports: frame bodies, role parts, geometry.json
config/       fleet, mission and vehicle parameters, terrain priors, Gazebo server config
dashboard/    mission-control website (built) and its source in dashboard/app
docs/         screenshots
models/       Gazebo models: the three drones, terrain, villages, forest, camp, debris
px4/          PX4 airframes 4560-4562
ros2_ws/      resqmesh_interfaces (messages) and resqmesh_mission (all swarm nodes)
setup/        WSL install and build scripts
terrain/      DEM and layout the world is generated from
tools/        run scripts, generators, Fusion scripts
worlds/       resqmesh_wayanad.sdf
```

## Install (Windows 11, WSL Ubuntu 24.04)
From this folder in PowerShell (PX4 is pinned to the `main` commit it was built and tested with):
```
wsl -d Ubuntu-24.04 -u root -- bash setup/01_ros_gazebo.sh
wsl -d Ubuntu-24.04 -- bash -lc "git clone --recursive https://github.com/PX4/PX4-Autopilot.git ~/PX4-Autopilot && cd ~/PX4-Autopilot && git checkout f94f879 && git submodule update --init --recursive"
wsl -d Ubuntu-24.04 -u root -- bash setup/02_px4_deps.sh
wsl -d Ubuntu-24.04 -- bash setup/03_build.sh
wsl -d Ubuntu-24.04 -- bash setup/04_fetch_models.sh
```

## Run
```
wsl -d Ubuntu-24.04 -- bash tools/sync.sh                          # after any change on the Windows side
wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/run_story.sh      # Gazebo opens on the camp; website on :8080
wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/trigger.sh 19     # the landslide (seed = where people land)
wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/damage.sh scout_1 # or mapper_1
wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/kill_all.sh       # stop everything
```
Website: http://localhost:8080/story.html. For the website's LIVE button, run `python tools/live_agent.py` on Windows:
it serves the site at http://127.0.0.1:8765 and starts, triggers and stops the simulation in WSL. To record a mission
for replay, run
`python3 tools/record_dashboard.py dashboard/replays/<name>.jsonl <minutes>` in WSL during the run, then add it to the
site with `dashboard/tools/compact_replay.py`.

## What the swarm does
1. **Alert.** The camp's tower floods the landslide alert over the mesh. The Relay-Anchor climbs 95 m and parks over
   the middle of the swarm, pulled back toward the tower only as far as the terrain needs for line of sight.
2. **Mapping.** Mappers fly offset passes along the debris corridor 45 m up. The Mid-360 hangs with its spin axis
   forward, so every revolution slices the ground across the track; points go into a 0.5 m voxel map and a 2 m surface
   grid. Returns from other drones are dropped, so a Scout below is never mapped as terrain.
3. **Search.** A Scout sector is released once the map covers 45 % of it. Scouts sweep 18 m above the mapped surface
   at 12 m/s, each in its own 3 m altitude layer, with pass spacing from the thermal camera's oblique footprint.
4. **Detection (Scouts only, on board).**
   - Thermal: pixels above body temperature, connected components, a range-aware size gate (0.2–2.6 m), peak
     temperature ≥ 30 °C = alive, person-sized but cooler = likely deceased (verify on the ground).
   - RGB: HSV segmentation of hi-vis clothing with size, aspect and context filters; confirmed over 3 frames.
   - RGB-only candidates trigger sensor-cued re-tasking: the nearest Scout breaks off and checks with thermal.
5. **Geolocation.** Every detection is a bearing ray from the camera at the frame's time. The camp triangulates all
   rays of a person (least squares, Huber-reweighted, weak pull to the lidar ground), so views from different
   passes meet at the person instead of leaving two pins over unmapped debris. Coordinates are WGS84.
6. **Planning.** The Brain runs on Mapper 1 with Mapper 2 as hot standby (anycast address `brain`). Idle drones get
   tasks by exact optimal assignment (bitmask DP) of travel against the unsearched probability of each sector; a
   finished drone steals the far half of a teammate's remaining passes. A lost drone's remainder is re-planned from
   its last waypoint; a crashed Scout is replaced by a reserve from the camp; a drone below 25 % battery hands its
   work back and flies home. If the Relay-Anchor is lost, reserves and finished Mappers form a chain of mesh relays
   back to the tower.
7. **Search map.** An 8 m Bayesian probability-of-containment grid (uniform, flow axis, houses), updated by every
   sweep with POD 0.8. POS = 1 − remaining mass tells the camp how complete the search is.
8. **Rescue route.** The camp plans the ground teams' route: living people first, then the deceased, nearest
   neighbour + 2-opt, with walking times over debris.

## The mesh
- `radio_medium` is the channel: a frame reaches a neighbour only within range (450 m drone–drone, 650 m relay–drone,
  4 km relay–tower) and with terrain line of sight on the DEM (blocked links fall back to weak, lossy LoRa).
- `mesh_agent` runs on every drone and on the tower: distance-vector routing on an ETX metric (as in Babel), hop-by-hop
  ACK and retry, store-carry-forward for up to 180 s when there is no route, flooding for alerts, and anycast service
  names (`brain`, `base`).
- Every hop of every message is traced, and the website can replay any sighting's path to the camp.

## Physics and sensor models
| | Model |
|---|---|
| Wind | SW monsoon, 3.2 m/s from WSW, gusting ±30 % with turbulence (`config/gz_server.config`) |
| Body drag | Gazebo WindEffects on every airframe, ~1.3 N at 12 m/s |
| GNSS | u-blox M10 class: per-receiver offset (0.7 m horizontal, 1.2 m vertical) plus centimetre jitter, 10 Hz |
| PX4 frame | PX4 projects GPS on a 6371 km sphere; `flight_agent` converts to true WGS84 metres (0.52 % north here) |
| Thermal | Lepton 3.5: 50 mK NETD, column fixed-pattern noise, per-unit radiometric offset (1 K), 0.01 K steps |
| RGB | IMX219 640×480 with pixel noise |
| Lidar | Mid-360 geometry, 2 cm range noise |
| IMU, baro, mag | PX4 SITL noise levels |
| Failures | motor failure with impact on any drone, silent drones, battery drain |

Sensor rendering runs on the NVIDIA GPU through WSL's D3D12 driver (`tools/story_env.sh`).

## Drone CAD checks
`tools/fusion_build_roles.py` rebuilds the three designs and runs Fusion's exact interference analysis and a contact
check (minimum distance < 20 µm) over every visible solid, fasteners included. Every part of all three drones is one
connected structure; the only overlaps are threads engaging nuts and standoffs.

## Regenerate
```
python -I tools/cad_to_meshes.py       # after a new Fusion export
python -I tools/gen_models.py          # after editing config/vehicle_params.yaml
python -I tools/gen_airframes.py
python tools/export_web_models.py      # drone models for the website, then npm run build in dashboard/app
python -I tools/gen_wayanad.py --seed 7
```

## Tests
```
cd ros2_ws/src/resqmesh_mission
python test/test_story_plan.py && python test/test_triangulate.py && python test/test_search_map.py
python test/test_rescue_route.py && python test/test_geo.py
```

## Limitations
- Masses and thrust constants are class-typical values until the parts are weighed and a thrust stand is run.
- The mesh is a link model (range, line of sight, loss), not RF propagation; the lidar map itself travels on the
  ROS 2 network, not over the emulated radios.
- Mapping uses the GNSS/INS pose; a lidar-SLAM front end is future work.
- The RGB detector finds hi-vis clothing, not a learned person model. Thermal reads surface temperature: "no live heat"
  means "check first", never a medical verdict.
- Sensor rates are below the real parts (thermal 4 Hz, RGB 2 Hz, lidar 12 k points/s) because Gazebo leaks memory per
  rendered frame on WSL.
- The demo searches the 166 m of the debris corridor nearest the camp (sector Z4) with six people in it, so a whole
  mission, from alert to every drone back on its pad, takes about 14 minutes.
