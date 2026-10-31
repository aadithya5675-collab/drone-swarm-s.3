import { useState } from 'react';
import { FastForward, Film } from 'lucide-react';
import { E, clockStr, COND_C } from '../lib/engine';
import { useEngine } from '../lib/store';
import { Panel, Button } from '../components/ui';
import { FixChip } from '../components/Ops';
import { VIDEOS } from '../config';
import { useVideo } from '../lib/videos';
import LiveOps from './LiveOps';

const evT = (re: RegExp) => E.S.events.find(e => re.test(e.text) && e.t != null)?.t ?? null;

export default function Report() {
  useEngine('story', 'persons', 'events', 'mode', 'clock', 'seek', 'history');
  const R = E.replay, phase = E.S.story?.phase;
  const done = phase === 'COMPLETE' || (!!R && R.t >= R.dur - 0.5);
  if (!done) return (
    <div className="flex flex-col gap-3">
      <div className="glass flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <div className="text-[15px] font-medium text-hi">The report is compiled when the mission ends.</div>
          <div className="text-[13px] text-muted">Until every drone is back at the camp, this is the live picture the camp sees.</div>
        </div>
        {R && <Button variant="solid" onClick={() => { E.seek(R.dur); R.playing = false; E.bump('mode'); }}><FastForward size={14} />Skip to the end of the run</Button>}
      </div>
      <LiveOps />
    </div>
  );
  return <Final />;
}

function Final() {
  const S = E.S, P = S.persons.filter(p => p.condition !== 'UNKNOWN');
  const alive = P.filter(p => p.condition === 'ALIVE').length, dead = P.length - alive;
  const first = P.map(p => E.foundAt(p)).filter((t): t is number => t != null).sort((a, b) => a - b)[0] ?? null;
  const cov = S.story?.coverage ?? S.plan?.coverage ?? null, pdr = E.pdrNow().pdr;
  const home = evT(/Mission complete|All drones landed/i) ?? (S.history.length ? S.history[S.history.length - 1].t : null);
  const swept = evT(/Search complete/i)
    ?? S.history.find(h => h.phase === 'RTB')?.t
    ?? (cov != null && cov >= 0.9 ? S.history.find(h => (h.cov ?? 0) >= cov - 0.01)?.t : null)
    ?? evT(/finished Z\d/i)
    ?? (home != null ? Math.max(0, home - 90) : null);
  const lost = S.lossT.length, reserves = S.events.filter(e => /launching reserve/i.test(e.text)).length;
  const stats: [string, string, string][] = [
    ['People located', String(P.length), `${alive} alive · ${dead} likely deceased`],
    ['Area searched', cov != null ? Math.round(cov * 100) + '%' : '—', 'of the debris corridor'],
    ['First person found', first != null ? 'T+ ' + clockStr(first) : '—', 'from the alert'],
    ['Search complete', swept != null ? 'T+ ' + clockStr(swept) : '—', home != null ? 'all home T+ ' + clockStr(home) : ''],
    ['Drones lost', String(lost), `${reserves} reserve${reserves === 1 ? '' : 's'} launched · mission continued`],
    ['Mesh delivery', pdr != null ? (pdr * 100).toFixed(1) + '%' : '—', 'messages that reached the camp']
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="glass px-6 py-6">
        <div className="eyebrow">Mission report</div>
        <p className="mt-2 max-w-3xl text-[clamp(20px,2.2vw,28px)] leading-snug font-medium tracking-tight text-hi">
          The swarm searched the debris corridor nearest the camp. On that search it located {P.length} {P.length === 1 ? 'person' : 'people'}: {alive} alive and {dead} likely deceased, each pinned with coordinates for the ground team.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {stats.map(([l, v, s], idx) => {
          const accents = ['var(--alive)', 'var(--accent)', 'var(--scout)', 'var(--cand)', 'var(--danger)', 'var(--relay)'];
          return (
            <div key={l} className="glass group relative overflow-hidden px-4.5 py-4 transition-all duration-200 hover:border-white/20">
              <div className="absolute top-0 inset-x-0 h-0.5 opacity-70" style={{ background: accents[idx % accents.length] }} />
              <div className="text-[11px] font-mono tracking-wider text-faint uppercase">{l}</div>
              <div className="num mt-2 text-[28px] font-semibold tracking-tight text-hi">{v}</div>
              <div className="mt-1 text-[11.5px] text-muted">{s}</div>
            </div>
          );
        })}
      </div>
      <Panel title="People" sub="where the ground team should go" bodyClass="overflow-x-auto">
        <table className="num w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-white/[.08] text-left text-[11px] font-mono tracking-wider text-faint uppercase">
              <th className="py-2.5 px-3 font-normal">Survivor ID</th>
              <th className="font-normal">Status</th>
              <th className="font-normal">GPS Coordinates</th>
              <th className="font-normal">Detection Time</th>
              <th className="text-right font-normal pr-3">Triangulation Fix</th>
            </tr>
          </thead>
          <tbody>
            {P.map(p => (
              <tr key={p.id} className="border-b border-white/[.04] transition-colors hover:bg-white/[.025]">
                <td className="py-2.5 px-3 font-medium text-fg">{p.id.replace('PERSON-', 'P')}</td>
                <td>
                  <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium" style={{ background: 'color-mix(in srgb, ' + COND_C[p.condition] + ' 15%, transparent)', color: COND_C[p.condition] }}>
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: COND_C[p.condition] }} />
                    {p.condition === 'ALIVE' ? 'alive' : 'likely deceased'}
                  </span>
                </td>
                <td className="font-mono text-muted">{p.lat.toFixed(6)} N, {p.lon.toFixed(6)} E</td>
                <td className="text-muted">found <span className="font-mono text-fg">T+ {clockStr(E.foundAt(p))}</span></td>
                <td className="text-right pr-3"><FixChip p={p} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Recordings />
    </div>
  );
}

function Recordings() {
  return (
    <Panel title="Recordings from the simulation" sub="the key moments of the run, in order">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {VIDEOS.map((v, i) => (
          <figure key={v.file} className="group overflow-hidden rounded-xl border border-line bg-black/40 transition-all duration-200 hover:border-white/20 hover:shadow-lg">
            <Clip file={v.file} />
            <figcaption className="px-4 py-3.5">
              <div className="flex items-baseline gap-2">
                <span className="num flex h-5 w-5 items-center justify-center rounded bg-accent/15 text-[10.5px] font-semibold text-accent">{String(i + 1).padStart(2, '0')}</span>
                <span className="text-[13.5px] font-medium text-hi">{v.title}</span>
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{v.caption}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </Panel>
  );
}

function Clip({ file }: { file: string }) {
  const v = useVideo(file);
  const [error, setError] = useState(false);
  return (
    <div className="relative aspect-video bg-black/80">
      {!error
        ? <video src={v.src} controls preload="metadata" playsInline className="h-full w-full object-cover" onError={() => setError(true)} />
        : <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-faint"><Film size={22} /><span className="text-xs font-mono">recording pending</span></div>}
    </div>
  );
}
