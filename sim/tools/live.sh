#!/usr/bin/env bash
# Live mission from a terminal: copies this checkout into WSL, opens the camp (Gazebo + swarm + base + rosbridge on :9090)
# and keeps the session open. The website's Live panel connects by itself. Ctrl+C stops everything.
# usage (PowerShell, in the repo folder):  wsl -d Ubuntu-24.04 -- bash sim/tools/live.sh
cd "$(dirname "$0")/.." || exit 1
bash tools/sync.sh
bash ~/resqmesh/sim/tools/run_story.sh
trap 'bash ~/resqmesh/sim/tools/kill_all.sh >/dev/null 2>&1; exit 0' INT TERM
echo
echo "Camp is up. The website connects on its own. Trigger the landslide from a second terminal:"
echo "  wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/trigger.sh 19"
echo "Keep this window open; Ctrl+C stops the simulation."
# WSL ends this session's background processes when the window closes, so stay here while Gazebo runs
while pgrep -f "gz sim -" >/dev/null; do sleep 5; done
