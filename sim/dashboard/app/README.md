# ResQMesh Mission Control

Vite + React + TypeScript. The build goes into `sim/dashboard/` (`story.html`, `index.html`, `assets/`, `models/`), next to
the data it reads (`replays/`, `terrain.json`, `valley.json`), and the simulation serves it at
`http://localhost:8080/story.html`.

Live data comes from rosbridge (`ws://<host>:9090`): the camp's `/base/*`, `/mesh/*`, `/brain/searchmap`, `/swarm/events`
and the Scouts' `/vision/annotated`. Replays are `replays/*.jsonl`, listed in `replays/index.json`.
Deep link: `story.html?replay=mission_seed19.jsonl&t=600&speed=4&paused=1`.

## Build
    npm install
    npm run build

## Drone models
After a CAD or `gen_models.py` change:

    python ../../tools/export_web_models.py
    npm run build

Stack: React 18, Tailwind 4, Radix, Motion, React Three Fiber + drei, Recharts, Zustand, Lucide, Geist and JetBrains Mono
(bundled, works offline).
