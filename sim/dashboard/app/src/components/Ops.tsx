/* Live-ops building blocks shared by several views: the commander strip, people, swarm and the event feed. */
import { useState } from 'react';
import { Copy, Check, Triangle, Radio, Battery } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { E, COND_C, COND_L, ROLE_C, DRONES, PHASES, role, short, clockStr, type Person } from '../lib/engine';
import { activity, fmtLL, verifies } from '../lib/geo';
import { useEngine, useUI } from '../lib/store';
import { Bar, Chip, Dot, Empty, Stat, Tip, cn } from './ui';

export function useMission() {
  useEngine('story', 'fleet', 'plan', 'persons', 'traffic', 'mode', 'seek');
  const S = E.S, st = S.story || {};
  const fleet = Object.entries(S.fleet);
  const lost = fleet.filter(([n, s]) => E.isLost(n, s)).map(([n]) => n);
  const airborne = fleet.filter(([n, s]) => !E.isLost(n, s) && s.state !== 'STAGING' && s.agl > 2).length;
  const alive = S.persons.filter(p => p.condition === 'ALIVE').length, dead = S.persons.filter(p => p.condition === 'DECEASED_SUSPECTED').length;
  const cand = S.persons.filter(p => p.condition === 'UNKNOWN' && !p.rechecked).length;
  const hopsArr = fleet.filter(([n, s]) => !E.isLost(n, s)).map(([, s]) => s.hops).filter(h => h > 0);
  return {
    phase: (st.phase as string) || (E.live.ok || E.replay ? 'STANDBY' : null), t: E.mt(), target: st.target as number | undefined,
    found: alive + dead, alive, dead, cand, coverage: st.coverage ?? S.plan?.coverage ?? null, pos: st.pos ?? S.plan?.pos ?? null,
    airborne, lost, reserves: (st.reserves_at_camp || []) as string[], brain: st.brain_host as string | undefined,
    pdr: E.pdrNow().pdr, hops: hopsArr.length ? hopsArr.reduce((a, b) => a + b, 0) / hopsArr.length : null, mapCov: st.map_coverage || {}
  };
}

export function CommanderStrip() {
  const m = useMission();
  const pct = (v: number | null) => (v == null ? '—' : Math.round(v * 100) + '%');
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" id="ops-kpis"
      data-explain="Every number here reached the camp over the drone mesh: people located and their condition, debris swept, the swarm's health and how well the mesh is delivering.">
      <div className="glass px-4 py-3.5"><Stat label="People located" value={m.found}
        sub={<><span style={{ color: COND_C.ALIVE }}>{m.alive} alive</span> · {m.dead} likely deceased{m.cand ? ` · ${m.cand} to verify` : ''}</>} /></div>
      <div className="glass px-4 py-3.5"><Stat label="Debris swept" value={pct(m.coverage)} sub={m.pos != null ? `probability of success ${(m.pos as number).toFixed(2)}` : 'search map not started'} /></div>
      <div className="glass px-4 py-3.5"><Stat label="Swarm" value={<>{m.airborne}<span className="text-faint text-xl"> airborne</span></>}
        sub={m.lost.length ? <span style={{ color: 'var(--danger)' }}>{m.lost.map(short).join(', ')} lost · {m.reserves.length} reserve{m.reserves.length === 1 ? '' : 's'} at camp</span> : `${m.reserves.length} reserve${m.reserves.length === 1 ? '' : 's'} at camp`} /></div>
      <div className="glass px-4 py-3.5"><Stat label="Mesh delivery" value={m.pdr == null ? '—' : (m.pdr * 100).toFixed(1) + '%'} sub={m.hops != null ? `ETX routing · ${m.hops.toFixed(1)} hops to camp on average` : 'waiting for traffic'} /></div>
    </div>
  );
}

export function PhaseRail() {
  const m = useMission(); const i = m.phase ? PHASES.indexOf(m.phase) : -1;
  return (
    <div className="flex items-center gap-1.5" aria-label="Mission phase">
      {PHASES.map((p, k) => (
        <div key={p} className="flex items-center gap-1.5">
          <span className={cn('num text-[10.5px] tracking-wider', k === i ? 'text-accent' : k < i ? 'text-muted' : 'text-faint/60')}>{p}</span>
          {k < PHASES.length - 1 && <span className={cn('h-px w-4', k < i ? 'bg-white/30' : 'bg-white/10')} />}
        </div>
      ))}
    </div>
  );
}

const condRank: Record<string, number> = { ALIVE: 0, DECEASED_SUSPECTED: 1, UNKNOWN: 2 };
export function PeopleList({ dense }: { dense?: boolean }) {
  useEngine('persons', 'plan', 'seek');
  const sel = useUI(s => s.person), pick = useUI(s => s.pickPerson);
  const P = [...E.S.persons].sort((a, b) => condRank[a.condition] - condRank[b.condition] || (a.rechecked ? 1 : 0) - (b.rechecked ? 1 : 0) || a.id.localeCompare(b.id));
  if (!P.length) return <Empty>No one located yet. The swarm launches itself when the landslide alert reaches the camp.</Empty>;
  return (
    <ul className="divide-y divide-white/[.05]">
      <AnimatePresence initial={false}>
        {P.map(p => <motion.li key={p.id} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
          <PersonRow p={p} open={sel === p.id} dense={dense} onClick={() => pick(sel === p.id ? null : p.id)} />
        </motion.li>)}
      </AnimatePresence>
    </ul>
  );
}

function PersonRow({ p, open, onClick, dense }: { p: Person; open: boolean; onClick: () => void; dense?: boolean }) {
  const [copied, setCopied] = useState(false);
  const ver = verifies().find(v => v.id === p.id);
  const dim = p.condition === 'UNKNOWN' && p.rechecked;
  const c = dim ? '#52525b' : COND_C[p.condition];
  const label = p.condition === 'UNKNOWN' ? (p.rechecked ? 'No heat on re-check' : ver ? `Re-check · ${short(ver.drone)} in flight` : 'Colour-only candidate') : COND_L[p.condition];
  const ll = fmtLL(p.lat, p.lon);
  const copy = (e: React.MouseEvent) => { e.stopPropagation(); navigator.clipboard?.writeText(p.lat.toFixed(6) + ', ' + p.lon.toFixed(6)); setCopied(true); setTimeout(() => setCopied(false), 1200); };
  return (
    <div role="button" tabIndex={0} onClick={onClick} onKeyDown={e => e.key === 'Enter' && onClick()}
      className={cn('group cursor-pointer px-1 py-2.5 outline-none focus-visible:bg-white/[.04]', dim && 'opacity-50', open && 'bg-white/[.03]')}>
      <div className="flex items-center gap-3">
        <Dot color={c} pulse={p.condition === 'ALIVE' && !dense} />
        <span className="num w-8 text-[13px] text-hi">{p.id.replace('PERSON-', 'P')}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="truncate text-[13px] font-medium" style={{ color: c }}>{label}</span>
            {p.max_temp_k > 0 && <span className="num text-xs text-muted">{(p.max_temp_k - 273.15).toFixed(1)} °C</span>}
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <button onClick={copy} className="num flex items-center gap-1 truncate text-[11px] text-muted hover:text-fg" title="Copy coordinates">
              {ll} {copied ? <Check size={11} className="text-accent" /> : <Copy size={11} className="opacity-0 group-hover:opacity-100" />}
            </button>
          </div>
        </div>
        <FixChip p={p} />
      </div>
      {open && (
        <div className="num mt-2 ml-[52px] grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted">
          <span>found by <b className="font-medium text-fg">{short(p.found_by)}</b> · {p.via_hops} hop{p.via_hops > 1 ? 's' : ''} to camp</span>
          <span>found T+ {clockStr(E.foundAt(p))} · {p.n} sighting{p.n === 1 ? '' : 's'}</span>
          <span>sensors {(p.sensors || []).join(' + ') || '—'}</span>
          <span>{p.fix === 'triangulated' ? `${p.fix_rays} rays · spread ${p.fix_spread_deg}° · rms ${p.fix_rms_m} m` : 'ray-cast onto the lidar ground'}</span>
        </div>
      )}
    </div>
  );
}

export function FixChip({ p }: { p: Person }) {
  if (p.fix === 'triangulated') return (
    <Tip content={`Position = least-squares intersection of ${p.fix_rays} camera bearing rays from different viewpoints, spanning ${p.fix_spread_deg}°, residual ${p.fix_rms_m} m. Independent of the ground model.`}>
      <span><Chip color="#5eead4"><Triangle size={9} strokeWidth={2.5} /><span className="num">{p.fix_rays} · ±{p.fix_rms_m} m</span></Chip></span>
    </Tip>
  );
  return <Tip content="Single-view fix: one bearing ray dropped onto the lidar-measured ground. Becomes a triangulated fix once rays from other viewpoints arrive."><span><Chip>ground fix</Chip></span></Tip>;
}

export function RescueRoute() {
  useEngine('rescue', 'seek');
  const R = E.S.rescue;
  if (!R || !R.route?.length) return <Empty>The ground-team route appears once people are located.</Empty>;
  let cum = 0;
  return (
    <div>
      <p className="mb-2 text-xs text-muted">Living first, then the deceased to verify. Nearest-neighbour + 2-opt over the debris at {R.speed_mps} m/s walking pace.</p>
      <ol className="space-y-0.5">
        {R.route.map((r: { id: string; condition: string; leg_m: number; eta_s: number }, i: number) => { cum += r.leg_m; return (
          <li key={r.id} className="flex items-center gap-3 py-1.5">
            <span className="num w-5 text-right text-[11px] text-faint">{i + 1}</span>
            <Dot color={COND_C[r.condition]} />
            <span className="num w-8 text-[13px] text-hi">{r.id.replace('PERSON-', 'P')}</span>
            <span className="flex-1 text-xs text-muted">{COND_L[r.condition]}</span>
            <span className="num text-[11px] text-muted">+{Math.round(r.leg_m)} m</span>
            <span className="num w-14 text-right text-[12px] text-fg">{clockStr(r.eta_s)}</span>
          </li>); })}
      </ol>
      <p className="num mt-2 text-[11px] text-faint">total {(cum / 1000).toFixed(2)} km</p>
    </div>
  );
}

export function SwarmStrip({ vertical }: { vertical?: boolean }) {
  useEngine('fleet', 'plan', 'seek');
  const sel = useUI(s => s.sel), select = useUI(s => s.select);
  const S = E.S, names = DRONES.filter(n => S.fleet[n]);
  if (!names.length) return <Empty>Waiting for the swarm to report in over the mesh…</Empty>;
  return (
    <div className={cn('grid gap-2', vertical ? 'grid-cols-1' : 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-7')}>
      {names.map(n => {
        const s = S.fleet[n], lost = E.isLost(n, s), c = lost ? '#71717a' : ROLE_C[role(n)];
        return (
          <button key={n} onClick={() => select(sel === n ? null : n)}
            className={cn('rounded-xl border px-3 py-2.5 text-left transition-colors', sel === n ? 'border-white/25 bg-white/[.07]' : 'border-line bg-white/[.025] hover:bg-white/[.05]')}>
            <div className="flex items-center gap-2">
              <span className="h-3.5 w-[3px] rounded-full" style={{ background: c }} />
              <span className="num text-[13px] font-medium text-hi">{short(n)}</span>
              <span className="text-[11px] capitalize text-faint">{role(n)}</span>
              <span className="ml-auto flex items-center gap-1 text-[11px] text-muted"><Radio size={11} />{lost ? '—' : s.hops}</span>
            </div>
            <div className={cn('mt-1.5 truncate text-[11.5px]', lost ? 'text-danger' : 'text-muted')}>{activity(n, s)}</div>
            <div className="mt-2 flex items-center gap-2">
              <Battery size={12} className="text-faint" />
              <Bar v={s.battery} color={s.battery < 0.25 ? 'var(--danger)' : 'rgba(231,234,240,.55)'} />
              <span className="num text-[10.5px] text-muted">{Math.round(s.battery * 100)}%</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

const LV: Record<string, string> = { ALERT: '#fb7185', WARN: '#fbbf24', INFO: 'rgba(231,234,240,.4)' };
export function EventFeed({ max = 60, filter }: { max?: number; filter?: (t: string) => boolean }) {
  useEngine('events', 'seek');
  const ev = E.S.events.filter(e => !filter || filter(e.text)).slice(-max).reverse();
  if (!ev.length) return <Empty>Mission log is empty.</Empty>;
  return (
    <ul className="space-y-0.5">
      {ev.map((e, i) => (
        <li key={i + e.text} className="flex gap-3 py-1 text-[12.5px] leading-snug">
          <span className="num w-11 shrink-0 pt-px text-[11px] text-faint">{e.t == null ? '—' : clockStr(e.t)}</span>
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: LV[e.level] || LV.INFO }} />
          <span className={cn(e.level === 'INFO' ? 'text-muted' : 'text-fg')}>{e.text}</span>
        </li>
      ))}
    </ul>
  );
}
