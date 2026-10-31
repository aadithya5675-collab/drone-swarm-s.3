import { Pause, Play } from 'lucide-react';
import { BEST_REPLAY, FALLBACK_REPLAY } from '../config';
import { E, clockStr } from '../lib/engine';
import { useEngine, useUI } from '../lib/store';
import { Button, Segmented } from './ui';

export async function openReplay(file: string, title = file) {
  const ui = useUI.getState();
  ui.setLoading(0);
  try {
    const recs = await E.loadReplay('replays/' + file, f => ui.setLoading(f));
    E.startReplay(title, recs);
    ui.setLive(false);
    if (ui.view === 'home') ui.go('twin');
  } catch (err) { ui.toast('Could not load ' + file + ': ' + (err as Error).message, false); ui.setLoading(null); return false; }
  ui.setLoading(null);
  return true;
}

export async function openBestReplay() {
  const ok = await fetch('replays/' + BEST_REPLAY, { method: 'HEAD' }).then(r => r.ok && !(r.headers.get('content-type') || '').includes('text/html')).catch(() => false);
  return openReplay(ok ? BEST_REPLAY : FALLBACK_REPLAY, 'Recorded mission');
}

export function LoadingVeil() {
  const f = useUI(s => s.loading);
  if (f == null) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass w-80 bg-[#0a0d13]/90 p-5">
        <div className="text-[13px] text-hi">Loading the mission record…</div>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-accent transition-[width]" style={{ width: f * 100 + '%' }} /></div>
        <div className="num mt-2 text-[11px] text-faint">{Math.round(f * 100)}%</div>
      </div>
    </div>
  );
}

export function ReplayBar() {
  useEngine('clock', 'mode', 'seek');
  const R = E.replay; if (!R) return null;
  const tA = R.tAlert ?? 0, mt = R.t - tA;
  const marks = E.S.lossT.map(l => ({ x: (l.t + tA) / R.dur, l: l.d }));
  const toggle = () => { R.playing = !R.playing; if (R.playing && R.t >= R.dur) E.seek(0); E.bump('mode'); };
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 flex h-14 items-center gap-3 border-t border-white/[.06] bg-[#06080c]/75 px-4 backdrop-blur-xl">
      <Button variant="solid" className="w-9 justify-center px-0" onClick={toggle} aria-label={R.playing ? 'Pause' : 'Play'}>{R.playing ? <Pause size={15} /> : <Play size={15} />}</Button>
      <span className="num w-20 text-[13px] text-hi">{mt < 0 ? '−' + clockStr(-mt) : 'T+ ' + clockStr(mt)}</span>
      <div className="relative flex-1">
        <input type="range" min={0} max={R.dur} step={0.5} value={R.t} aria-label="Mission time"
          onChange={e => { const p = R.playing; E.seek(+e.target.value); R.playing = p; }}
          className="w-full accent-[var(--accent)]" />
        {marks.map(m => <span key={m.l} title={m.l + ' lost'} className="pointer-events-none absolute top-[3px] h-2.5 w-[2px] rounded bg-danger" style={{ left: `calc(${m.x * 100}% )` }} />)}
      </div>
      <span className="num hidden w-16 text-[11px] text-faint sm:inline">{clockStr(R.dur - tA)}</span>
      <Segmented value={String(R.speed)} onChange={v => { R.speed = +v; E.bump('mode'); }} options={[1, 4, 16, 64].map(s => ({ v: String(s), l: s + '×' }))} />
      <span className="hidden max-w-64 truncate text-xs text-muted xl:inline">{R.name}</span>
    </div>
  );
}
