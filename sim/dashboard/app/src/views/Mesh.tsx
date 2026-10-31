import { useMemo, useState } from 'react';
import { E, KIND_C, ROLE_C, role, short, clockStr } from '../lib/engine';
import { useEngine } from '../lib/store';
import { nodePos } from '../lib/geo';
import { Panel, Segmented, Empty, Chip, Stat, cn } from '../components/ui';
import { TimeArea } from '../components/charts';

const GUIDE: [string, string][] = [
  ['No tower, no internet', 'Every drone carries a mesh radio and passes messages for the others. The camp tower is just one more node.'],
  ['Each drone picks the path', 'Drones beacon every second. Each link gets a score, ETX: how many tries a message needs to get through. Lower is better.'],
  ['Best path, not shortest', 'A clean two-hop path beats a weak direct link. Click any node to see its own routing table.'],
  ['Nothing is lost', 'With no route, a message waits on the drone and flies with it until a link appears. The tracer replays real messages hop by hop.']
];

export default function Mesh() {
  const [node, setNode] = useState<string>('tower');
  return (
    <div className="flex flex-col gap-3">
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {GUIDE.map(([h, p], i) => (
        <div key={h} className="glass px-4 py-3.5">
          <div className="flex items-center gap-2"><span className="num text-[11px] text-accent">0{i + 1}</span><span className="text-[13.5px] font-medium text-hi">{h}</span></div>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{p}</p>
        </div>
      ))}
    </div>
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-3">
        <Panel id="mesh-topo" title="Topology" sub="rows = radio hops to the camp · link width = delivery ratio · labels = ETX"
          explain="The mesh laid out by how many radio hops each node is from the camp. Each link's width is its measured hello delivery ratio; the label is its ETX (expected transmissions, 1/r²). Routes follow the lowest total ETX, as in Babel, not the fewest hops. Click a node for its routing table.">
          <Topology sel={node} onSel={setNode} />
        </Panel>
        <Panel title="Delivery over the mission" sub="frames delivered ÷ (delivered + lost), per traffic report">
          <PdrChart />
        </Panel>
      </div>
      <div className="flex flex-col gap-3">
        <Panel title={'Routing table · ' + (node === 'tower' ? 'camp tower' : short(node))} sub="destination → next hop, total cost (ETX)">
          <Routes node={node} />
        </Panel>
        <Panel id="mesh-trace" title="Packet tracer" sub="real frames, hop by hop, as the radio medium logged them" className="min-h-[420px]" bodyClass="overflow-hidden flex flex-col"
          explain="Every frame the radio medium carried is traced: who sent it, every hop, losses and retries, and how long it took to reach its destination. Pick a sighting to follow a person's coordinates home.">
          <Tracer />
        </Panel>
      </div>
    </div>
    </div>
  );
}

function Topology({ sel, onSel }: { sel: string; onSel: (n: string) => void }) {
  useEngine('traffic', 'mesh', 'fleet', 'seek');
  const S = E.S, tr = S.traffic;
  const nodes = tr ? Object.keys(tr.nodes) : [];
  if (!nodes.length) return <Empty>Waiting for mesh traffic reports…</Empty>;
  // layered by hops to the camp (top), ordered within a layer by where the drone is along the valley
  const W = 720, H = 420, hopsOf = (n: string) => n === 'tower' ? 0 : (S.fleet[n] && E.isLost(n, S.fleet[n])) ? 9 : (S.mesh[n]?.routes?.tower?.[0] ?? S.fleet[n]?.hops ?? 3);
  const layers: Record<number, string[]> = {};
  for (const n of nodes) (layers[hopsOf(n)] = layers[hopsOf(n)] || []).push(n);
  const keys = Object.keys(layers).map(Number).sort((a, b) => a - b), pos: Record<string, number[]> = {};
  keys.forEach((k, li) => {
    const row = layers[k].sort((a, b) => (nodePos(a)?.[0] ?? 0) - (nodePos(b)?.[0] ?? 0));
    row.forEach((n, i) => { pos[n] = [W / 2 + (i - (row.length - 1) / 2) * Math.min(150, (W - 120) / Math.max(1, row.length - 1 || 1)), 48 + li * ((H - 96) / Math.max(1, keys.length - 1))]; });
  });
  const P = (n: string) => pos[n];
  const etx = (a: string, b: string) => S.mesh[a]?.etx?.[b] ?? S.mesh[b]?.etx?.[a];
  const route = S.mesh[sel]?.routes || {};
  const onPath = new Set<string>(); // links on sel's routes
  for (const [, v] of Object.entries<[number, string]>(route)) onPath.add([sel, v[1]].sort().join('|'));
  const flows = (tr.flows as [string, string, string, number][]).filter(f => f[2] !== 'hello' && f[2] !== 'ack').slice(0, 40);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[420px] w-full" role="img" aria-label="Mesh topology">
      {(tr.links as [string, string, number, number, boolean][]).map(([a, b, q, d, up], k) => {
        if (!up || q <= 0) return null; const A = P(a), B = P(b), hot = onPath.has([a, b].sort().join('|')), e = etx(a, b);
        return <g key={k}>
          <line x1={A[0]} y1={A[1]} x2={B[0]} y2={B[1]} stroke={hot ? '#5eead4' : '#e7eaf0'} strokeOpacity={hot ? 0.8 : 0.12 + 0.35 * q} strokeWidth={0.6 + 3 * q} />
          {e != null && <text x={(A[0] + B[0]) / 2 + 4} y={(A[1] + B[1]) / 2 - 4} fontSize="10" fill={hot ? '#5eead4' : 'rgba(231,234,240,.45)'} fontFamily="JetBrains Mono Variable">{e.toFixed(2)}</text>}
          <title>{`${short(a)} ↔ ${short(b)} · ${Math.round(d)} m · delivery ${(q * 100).toFixed(0)}%`}</title>
        </g>;
      })}
      {flows.map(([a, b, k], i) => {
        if (!tr.nodes[a] || !tr.nodes[b]) return null; const A = P(a), B = P(b);
        return <circle key={i + a + b + k} r="2.6" fill={KIND_C[k] || '#fff'}><animateMotion dur={`${1 + (i % 5) * 0.25}s`} repeatCount="indefinite" path={`M${A[0]},${A[1]} L${B[0]},${B[1]}`} /></circle>;
      })}
      {nodes.map(n => {
        const p = P(n), c = n === 'tower' ? '#fb7185' : ROLE_C[role(n)], s = S.fleet[n], lost = s && E.isLost(n, s);
        return <g key={n} onClick={() => onSel(n)} className="cursor-pointer">
          {n === sel && <circle cx={p[0]} cy={p[1]} r="17" fill="none" stroke="#5eead4" strokeOpacity=".7" />}
          <circle cx={p[0]} cy={p[1]} r="11" fill="#06080c" stroke={lost ? '#71717a' : c} strokeWidth="2" strokeDasharray={lost ? '3 3' : undefined} />
          <text x={p[0]} y={p[1] + 3.5} textAnchor="middle" fontSize="10" fontWeight="600" fill={lost ? '#71717a' : '#f4f6fa'} fontFamily="JetBrains Mono Variable">{short(n).replace('Camp', 'C')}</text>
          {(S.mesh[n]?.services || []).length > 0 && <text x={p[0]} y={p[1] + 26} textAnchor="middle" fontSize="9.5" fill="#5eead4" fontFamily="Geist Variable">{S.mesh[n].services.join(', ')}</text>}
        </g>;
      })}
    </svg>
  );
}

function Routes({ node }: { node: string }) {
  useEngine('mesh', 'seek');
  const M = E.S.mesh[node];
  if (!M) return <Empty>No report from this node yet.</Empty>;
  const rows = Object.entries<[number, string]>(M.routes || {}).sort((a, b) => (M.cost?.[a[0]] ?? 99) - (M.cost?.[b[0]] ?? 99));
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1.5 text-[11px]">
        <Chip>neighbours {M.neighbours?.map(short).join(', ') || 'none'}</Chip>
        <Chip color={M.queued ? '#fbbf24' : undefined}>{M.queued} queued (store-carry-forward)</Chip>
        {M.age > 5 && <Chip color="#f87171">silent {Math.round(M.age)} s</Chip>}
      </div>
      <table className="num w-full text-[12px]">
        <thead><tr className="text-left text-[10.5px] text-faint"><th className="py-1 font-normal">destination</th><th className="font-normal">next hop</th><th className="font-normal">hops</th><th className="text-right font-normal">cost</th></tr></thead>
        <tbody>
          {rows.map(([d, [h, nh]]) => (
            <tr key={d} className="border-t border-white/[.05]">
              <td className="py-1.5 text-fg">{d === 'base' || d === 'brain' ? <span className="text-accent">{d}</span> : short(d)}</td>
              <td className="text-muted">{short(nh)}</td><td className="text-muted">{h}</td>
              <td className="text-right text-fg">{M.cost?.[d] != null ? M.cost[d].toFixed(2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-faint">base and brain are service addresses (anycast): the route follows whichever node hosts them.</p>
    </div>
  );
}

function Tracer() {
  useEngine('trace', 'seek');
  const [kind, setKind] = useState<'sighting' | 'status' | 'plan' | 'all'>('sighting');
  const [pick, setPick] = useState<number | null>(null);
  const list = E.S.traces.filter(t => kind === 'all' || t.k === kind).slice(0, 60);
  const t = list.find(x => x.id === pick) || list[0];
  return (
    <>
      <Segmented value={kind} onChange={v => { setKind(v); setPick(null); }} options={[{ v: 'sighting', l: 'Sightings' }, { v: 'status', l: 'Status' }, { v: 'plan', l: 'Plans' }, { v: 'all', l: 'All' }]} />
      {!t ? <Empty>No {kind === 'all' ? '' : kind + ' '}frames traced yet.</Empty> : (
        <div className="mt-3 grid min-h-0 flex-1 gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
          <ul className="max-h-[300px] overflow-y-auto pr-1">
            {list.map(x => (
              <li key={x.id}><button onClick={() => setPick(x.id)} className={cn('num flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11.5px]', x === t ? 'bg-white/[.08] text-fg' : 'text-muted hover:bg-white/[.04]')}>
                <i className="h-1.5 w-1.5 rounded-full" style={{ background: KIND_C[x.k] || '#fff' }} />
                <span className="w-10 text-faint">{clockStr(x.mt)}</span><span>{short(x.o)}</span><span className="ml-auto">{x.h.length}h</span>
              </button></li>
            ))}
          </ul>
          <TraceDetail t={t} />
        </div>
      )}
    </>
  );
}

function TraceDetail({ t }: { t: { k: string; o: string; final: string; at: string; dt: number; h: [number, string, string, string][]; p: Record<string, unknown> } }) {
  const ok = t.at === t.final || (t.final === 'base' && t.at === 'tower');
  const steps = useMemo(() => t.h, [t]);
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <Chip color={KIND_C[t.k]}>{t.k}</Chip>
        <span className="text-[13px] text-fg">{short(t.o)} → {t.final}</span>
        <span className={cn('num ml-auto text-[13px]', ok ? 'text-alive' : 'text-cand')}>{t.dt < 1 ? Math.round(t.dt * 1000) + ' ms' : t.dt.toFixed(2) + ' s'}</span>
      </div>
      <ol className="mt-3 space-y-0">
        {steps.map(([dt, a, b, r], i) => (
          <li key={i} className="relative flex gap-3 pb-3 pl-5">
            <span className="absolute top-1.5 left-0 h-2 w-2 rounded-full" style={{ background: r === 'ok' ? '#5eead4' : '#f87171' }} />
            {i < steps.length - 1 && <span className="absolute top-4 left-[3.5px] h-full w-px bg-white/10" />}
            <span className="num w-14 text-[11px] text-faint">+{dt < 1 ? Math.round(dt * 1000) + 'ms' : dt.toFixed(2) + 's'}</span>
            <span className="num text-[12px] text-fg">{short(a)} → {short(b)}</span>
            <span className={cn('text-[11px]', r === 'ok' ? 'text-muted' : 'text-danger')}>{r === 'ok' ? 'delivered' : r}</span>
          </li>
        ))}
      </ol>
      {t.k === 'sighting' && t.p && Object.keys(t.p).length > 0 && (
        <pre className="num mt-1 max-h-28 overflow-auto rounded-lg bg-black/30 p-2 text-[10.5px] leading-snug text-muted">{JSON.stringify(t.p, null, 0).slice(0, 600)}</pre>
      )}
    </div>
  );
}

function PdrChart() {
  useEngine('traffic', 'history', 'seek');
  const S = E.S, last = S.traffic?.totals;
  const data = S.history.filter(h => h.pdr != null).map(h => ({ t: h.t, pdr: h.pdr }));
  return (
    <div>
      <div className="mb-3 grid grid-cols-3 gap-4">
        <Stat label="Delivered" value={last ? last.delivered.toLocaleString() : '—'} />
        <Stat label="Lost on air" value={last ? last.lost.toLocaleString() : '—'} />
        <Stat label="Blocked" value={last ? last.blocked.toLocaleString() : '—'} sub="terrain shadow" />
      </div>
      {data.length > 1 ? <TimeArea data={data} k="pdr" fmt={v => (v * 100).toFixed(0) + '%'} domain={[0.5, 1]} /> : <Empty>The delivery history builds up during the mission.</Empty>}
    </div>
  );
}
