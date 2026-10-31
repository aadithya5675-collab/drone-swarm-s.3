#!/usr/bin/env bash
# Stop the story and everything it started.
for pat in "tools/run_story.sh" "record_dashboard.py"; do
  for p in $(pgrep -f "$pat"); do [ "$p" != "$$" ] && [ "$p" != "$PPID" ] && kill $p 2>/dev/null; done
done
bash "$(dirname "$0")/stop_story.sh" >/dev/null 2>&1
pkill -9 -f "gz sim -" ; pkill -9 -f "lib/resqmesh_mission/" ; pkill -9 -f "bin/px4 -i"
sleep 2; free -m | awk '/Mem:/{print "avail_mb=" $7}'
