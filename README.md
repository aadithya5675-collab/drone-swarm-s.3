# ResQMesh

**Team Apex · Hack-Orbital 2026 · Problem statement S.3**

ResQMesh is a self-organising drone swarm for landslide search and rescue. Scouts find people in the debris with
thermal and RGB cameras, Mappers build a live 3D lidar map of ground no map has seen, and a Relay-Anchor keeps the
swarm connected to the rescue camp, all over a decentralised mesh that keeps working when drones are lost.

This repository is the Phase 2 build: a full simulation of the 30 July 2024 Mundakkai–Chooralmala landslide on the
real terrain of the Wayanad valley, with the drone designs, the swarm software and the camp's mission-control website.

| Folder | Contents |
|---|---|
| [`sim/`](sim/README.md) | Gazebo world, PX4 drones, ROS 2 swarm software, CAD pipeline, mission-control website |
| [`pitch/`](pitch/) | Phase 1 deck (PDF, PPTX) and speaker script |

Start with [`sim/README.md`](sim/README.md) for how it works, how to install it and how to run the mission.

The website also runs without the simulator: serve `sim/dashboard/` (for example `python -m http.server 8080` in that
folder) and open `http://localhost:8080/story.html` to watch a recorded mission.
