"""Thin a recorded mission (tools/record_dashboard.py output) so the dashboard loads it fast."""
import json
import os
import sys

PERIOD = {'/base/mapimg': 40.0, '/base/cloud': 40.0, '/base/history': 10.0, '/base/eventlog': 15.0}
src, name, title, note = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ''
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(here, 'replays', name + '.jsonl')
lines = []
for ln in open(src, encoding='utf-8'):
    try:
        lines.append((json.loads(ln)['topic'], json.loads(ln)['t'], ln if ln.endswith('\n') else ln + '\n'))
    except ValueError:
        pass                                     # a line cut off by the recorder stopping
last_idx = {}
for i, (tp, _, _) in enumerate(lines):
    last_idx[tp] = i
kept, last_t = [], {}
for i, (tp, t, ln) in enumerate(lines):
    p = 3.0 if tp.endswith('/vision/annotated') else PERIOD.get(tp, 0.0)
    if p and i != last_idx[tp] and t - last_t.get(tp, -1e9) < p:
        continue
    last_t[tp] = t
    kept.append(ln)
open(out, 'w', encoding='utf-8', newline='\n').writelines(kept)
dur = lines[-1][1] if lines else 0
idx_path = os.path.join(here, 'replays', 'index.json')
idx = json.load(open(idx_path)) if os.path.exists(idx_path) else []
idx = [r for r in idx if r['file'] != name + '.jsonl']
idx.insert(0, {'file': name + '.jsonl', 'title': title, 'note': note, 'minutes': round(dur / 60, 1), 'mb': round(os.path.getsize(out) / 1e6, 1)})
json.dump(idx, open(idx_path, 'w'), indent=1)
print('%s: %d of %d messages, %.1f MB, %.1f min' % (out, len(kept), len(lines), os.path.getsize(out) / 1e6, dur / 60))
