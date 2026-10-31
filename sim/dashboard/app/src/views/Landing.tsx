import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence, useInView, useScroll, useTransform } from 'motion/react';
import { Radio, Film, ChevronDown, Github } from 'lucide-react';
import { E } from '../lib/engine';
import { useEngine, useUI, reducedMotion } from '../lib/store';
import { corridorEdges } from '../lib/geo';
import { cn } from '../components/ui';
import { openBestReplay } from '../components/Replay';
import { REPO_URL } from '../config';
import type { RoleName } from '../three/parts';

const SwarmStage = lazy(() => import('../three/SwarmStage'));
const CampStage = lazy(() => import('../three/CampStage'));
const Explode = lazy(() => import('../three/Explode'));

const SURVIVAL = [{ d: 'Day 1', v: 88 }, { d: 'Day 2', v: 35 }, { d: 'Day 3', v: 9 }];

const ROLES: { id: RoleName; name: string; n: string; color: string; job: string }[] = [
  { id: 'scout', name: 'Scout', n: '2 flying + 2 reserves', color: 'var(--scout)', job: 'Flies low over the debris. Its thermal and colour cameras find people, tell the living from the likely deceased by body heat, and send their location to the camp.' },
  { id: 'mapper', name: 'Mapper', n: '2 flying', color: 'var(--mapper)', job: 'Scans the new ground with a 3D lidar so the Scouts know where it is safe to fly, and runs the swarm’s planner. If one is lost, the other takes over.' },
  { id: 'relay', name: 'Relay-Anchor', n: '1 flying', color: 'var(--relay)', job: 'Holds high over the swarm and carries every message back to the camp tower, across a valley with no phone network.' }
];

const COMPARE: [string, string, string][] = [
  ['Who searches', 'Teams on foot in deep mud', 'A swarm that flies itself'],
  ['Finding people', 'Calling out, sniffer dogs, by hand', 'Thermal + colour cameras, on board'],
  ['Alive or not', 'Only when someone reaches them', 'Body heat read from the air'],
  ['Map of the ground', 'Pre-disaster maps, now wrong', 'Live 3D lidar map of the debris'],
  ['Communication', 'Towers down, radios patchy', 'Its own mesh back to the camp'],
  ['When a drone is lost', 'Mission stops', 'Swarm re-plans, a reserve takes off']
];

const STEPS = [
  { k: 'ALERT', h: 'The alert reaches the swarm', p: 'The camp tower floods the landslide alert over the mesh. The swarm takes off by itself — no pilot, no phone network.' },
  { k: 'MAP', h: 'Mappers scan the debris', p: 'Mappers fly lidar passes over the corridor. A sector opens to the Scouts only after it has been mapped.' },
  { k: 'SEARCH', h: 'Scouts sweep low', p: 'Scouts sweep each mapped sector 18 m above the measured ground, each on its own altitude layer so they never meet.' },
  { k: 'DETECT', h: 'People are found on board', p: 'Image processing on each Scout finds bodies in the thermal camera and hi-vis clothing in the colour camera. Body heat decides alive or likely deceased.' },
  { k: 'LOCATE', h: 'Views meet at the person', p: 'Every detection is a camera ray. The camp intersects rays from different viewpoints, so the person is placed where the views meet — accurate even over unmapped debris.' },
  { k: 'RESCUE', h: 'Route the rescuers, fly home', p: 'The camp turns pins into a walking route for the ground team, living people first. Corridor searched, every drone flies back to the camp.' }
];

export default function Landing() {
  const scroller = useRef<HTMLDivElement>(null);
  const [explode, setExplode] = useState<RoleName | null>(null);
  useEffect(() => { const t = setTimeout(() => { import('../three/SwarmStage'); import('../three/CampStage'); import('../three/Explode'); }, 600); return () => clearTimeout(t); }, []);
  return (
    <div ref={scroller} className="relative h-full overflow-y-auto overflow-x-hidden">
      <div className="atmo" />
      <Hero />
      <SwarmScroll scroller={scroller} onExplode={setExplode} />
      <Roles />
      <Camp />
      <Workflow />
      <SeeItRun />
      <footer className="relative z-10 mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-6 pb-10 text-xs text-faint lg:px-10">
        <span>ResQMesh · Team Apex · Hack-Orbital 2026 · PS S.3</span>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-fg"><Github size={13} />source code</a>
      </footer>
      {explode && <Suspense fallback={null}><Explode key={explode} role={explode} onClose={() => setExplode(null)} /></Suspense>}
    </div>
  );
}

function Hero() {
  return (
    <section className="relative z-10 mx-auto grid min-h-screen max-w-[1400px] items-center gap-10 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:px-10">
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }}>
        <div className="num text-[13px] tracking-[0.2em] text-camp">AT 2:17 AM · JULY 30, 2024</div>
        <h1 className="mt-5 text-[clamp(36px,5vw,68px)] leading-[1.03] font-semibold tracking-[-0.035em] text-hi">
          A hillside above Mundakkai collapsed in the dark.
        </h1>
        <p className="mt-6 max-w-xl text-[16px] leading-relaxed text-muted">
          The debris flow buried <span className="text-fg">Mundakkai</span> and <span className="text-fg">Chooralmala</span> in Wayanad, Kerala,
          and washed away the only bridge. Rescuers searched by hand, in deep mud, with no phone network and no map of the new ground.
        </p>
        <div className="mt-8 rounded-2xl border border-camp/25 bg-camp/[.06] p-5">
          <div className="text-[12px] font-medium tracking-wide text-camp uppercase">The problem</div>
          <p className="mt-2 text-[19px] leading-snug font-medium text-hi">
            Survivors buried in a disaster zone have hours, not days — and today nobody can find them fast enough, or tell the camp where they are.
          </p>
        </div>
        <div className="mt-8">
          <div className="text-[12px] text-muted">Chance a trapped person is still alive</div>
          <div className="mt-3 grid max-w-xl grid-cols-3 gap-3">
            {SURVIVAL.map((s, i) => (
              <div key={s.d} className="glass px-4 py-3">
                <div className="num text-[34px] leading-none font-semibold" style={{ color: i === 0 ? 'var(--alive)' : i === 1 ? 'var(--cand)' : 'var(--danger)' }}>{s.v}%</div>
                <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10"><motion.div className="h-full rounded-full" style={{ background: i === 0 ? 'var(--alive)' : i === 1 ? 'var(--cand)' : 'var(--danger)' }}
                  initial={{ width: 0 }} animate={{ width: s.v + '%' }} transition={{ delay: 0.6 + i * 0.2, duration: 1 }} /></div>
                <div className="mt-2 text-xs text-muted">{s.d}</div>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-faint">Reported survival of trapped victims, 1990 Philippines earthquake — from our Phase 1 research.</div>
        </div>
      </motion.div>
      <HeroValley />
      <div className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-1 text-xs text-faint lg:flex"><span>our answer</span><ChevronDown size={14} className="animate-bounce" /></div>
    </section>
  );
}

function HeroValley() {
  useEngine('static');
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c || !E.T) return;
    const g = c.getContext('2d')!, T = E.T, still = reducedMotion();
    let raf = 0;
    const pts: number[][] = [];
    for (let i = 0; i < T.h; i += 1) for (let j = 0; j < T.w; j += 1) pts.push([T.x0 + j * T.res, T.y0 + i * T.res, T.z[i * T.w + j]]);
    let zmin = 1e9, zmax = -1e9; for (const p of pts) { zmin = Math.min(zmin, p[2]); zmax = Math.max(zmax, p[2]); }
    const edges = corridorEdges();
    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      const k = devicePixelRatio || 1, r = c.getBoundingClientRect(), w = Math.round(r.width * k), h = Math.round(r.height * k);
      if (c.width !== w) { c.width = w; c.height = h; }
      g.clearRect(0, 0, w, h);
      const a = still ? 0.6 : 0.6 + Math.sin(now / 9000) * 0.25, ca = Math.cos(a), sa = Math.sin(a), cx = -150, cy = -620;
      const s = Math.min(w, h) / 1150, tilt = 0.52;
      const P = (x: number, y: number, z: number) => { const dx = x - cx, dy = y - cy, rx = dx * ca - dy * sa, ry = dx * sa + dy * ca; return [w / 2 + rx * s, h * 0.56 - ry * s * tilt - (z - zmin) * s * 1.6]; };
      const scan = still ? 1e9 : ((now / 5200) % 1.4) * (zmax - zmin + 400) - 200;
      for (const p of pts) {
        const q = P(p[0], p[1], p[2]), u = (p[2] - zmin) / (zmax - zmin);
        const near = Math.abs((p[1] + 1450) * 0.6 - scan) < 26 ? 0.5 : 0;
        g.fillStyle = `rgba(${210 + 40 * near},${225 + 30 * near},235,${0.1 + 0.42 * u + near})`;
        g.fillRect(q[0], q[1], 1.3 * k, 1.3 * k);
      }
      g.strokeStyle = 'rgba(94,234,212,.75)'; g.lineWidth = 1.2 * k;
      for (const e of edges) { g.beginPath(); e.forEach((p, i) => { const q = P(p[0], p[1], E.ground(p[0], p[1]) + 4); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.stroke(); }
      const t = P(E.V.tower.x, E.V.tower.y, E.ground(E.V.tower.x, E.V.tower.y));
      g.fillStyle = '#fb7185'; g.beginPath(); g.arc(t[0], t[1], 3.5 * k, 0, 7); g.fill();
      g.font = `500 ${11 * k}px "Geist Variable"`; g.fillStyle = 'rgba(244,246,250,.7)'; g.fillText('Chooralmala camp', t[0] + 8 * k, t[1] + 4 * k);
      const m = P(E.V.mundakkai[0], E.V.mundakkai[1], E.ground(E.V.mundakkai[0], E.V.mundakkai[1]) + 20);
      g.fillText('Mundakkai', m[0] + 8 * k, m[1]);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [E.T]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2, delay: 0.2 }} className="relative aspect-[4/3.4] w-full">
      <canvas ref={ref} className="absolute inset-0 h-full w-full" aria-label="The Mundakkai valley as a lidar point field, with the debris corridor outlined" />
      <div className="absolute right-2 bottom-2 text-right text-[11px] leading-snug text-faint">real SRTM elevation, 10 m grid<br /><span className="text-accent/80">— debris corridor</span></div>
    </motion.div>
  );
}

function SwarmScroll({ scroller, onExplode }: { scroller: React.RefObject<HTMLDivElement>; onExplode: (r: RoleName) => void }) {
  const target = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ container: scroller, target, offset: ['start start', 'end end'], layoutEffect: false });
  const near = useInView(target, { root: scroller, margin: '1200px', once: true });
  const title = useTransform(scrollYProgress, [0, 0.08, 0.3, 0.42], [0, 1, 1, 0]);
  const hint = useTransform(scrollYProgress, [0.55, 0.7], [0, 1]);
  return (
    <section ref={target} className="relative z-10 h-[320vh]">
      <div className="sticky top-0 h-screen overflow-hidden">
        <div className="absolute inset-0">{near && <Suspense fallback={null}><SwarmStage progress={scrollYProgress} onExplode={onExplode} /></Suspense>}</div>
        <motion.div style={{ opacity: title }} className="pointer-events-none absolute top-10 left-1/2 w-full max-w-3xl -translate-x-1/2 px-6 text-center">
          <div className="eyebrow">Our answer</div>
          <h2 className="mt-3 text-[clamp(30px,4vw,54px)] font-semibold tracking-tight text-hi">ResQMesh: a swarm that searches by itself.</h2>
          <p className="mx-auto mt-3 max-w-xl text-[15px] text-muted">Seven drones, three jobs, one mesh. When the towers fall, the sky becomes the network.</p>
        </motion.div>
        <motion.div style={{ opacity: hint }} className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-black/40 px-4 py-2 text-xs text-muted backdrop-blur-md">
          drag to turn the swarm 360° · double-click a drone to see how it is built
        </motion.div>
      </div>
    </section>
  );
}

function Roles() {
  return (
    <section className="relative z-10 mx-auto max-w-[1400px] px-6 py-20 lg:px-10">
      <div className="grid gap-3 md:grid-cols-3">
        {ROLES.map((r, i) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-80px' }} transition={{ delay: i * 0.08 }} className="glass p-6">
            <div className="flex items-center justify-between">
              <span className="text-lg font-semibold text-hi">{r.name}</span>
              <span className="num rounded-md px-2 py-1 text-[11px]" style={{ background: 'color-mix(in srgb, ' + r.color + ' 14%, transparent)', color: r.color }}>{r.n}</span>
            </div>
            <p className="mt-3 text-[14px] leading-relaxed text-muted">{r.job}</p>
          </motion.div>
        ))}
      </div>
      <div className="mt-14">
        <div className="eyebrow">Why it is different</div>
        <h3 className="mt-3 text-[clamp(24px,2.8vw,36px)] font-semibold tracking-tight text-hi">Conventional search vs ResQMesh</h3>
        <div className="glass mt-6 overflow-hidden">
          <div className="grid grid-cols-[1fr_1.2fr_1.2fr] border-b border-white/[.07] px-5 py-3 text-[11px] tracking-wide text-faint uppercase">
            <span /><span>Conventional</span><span className="text-accent">ResQMesh</span>
          </div>
          {COMPARE.map(([a, b, c]) => (
            <div key={a} className="grid grid-cols-[1fr_1.2fr_1.2fr] gap-3 border-b border-white/[.04] px-5 py-3 text-[13.5px] last:border-0">
              <span className="text-muted">{a}</span><span className="text-faint">{b}</span><span className="text-hi">{c}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Camp() {
  const ref = useRef<HTMLDivElement>(null), seen = useInView(ref, { once: true, margin: '300px' });
  return (
    <section ref={ref} className="relative z-10 mx-auto max-w-[1400px] px-6 py-16 lg:px-10">
      <div className="grid items-center gap-8 lg:grid-cols-[380px_minmax(0,1fr)]">
        <div>
          <div className="eyebrow">The rescue camp</div>
          <h3 className="mt-3 text-[clamp(24px,2.8vw,36px)] font-semibold tracking-tight text-hi">Every sighting finds its way home.</h3>
          <p className="mt-4 text-[14px] leading-relaxed text-muted">A Scout sees a person deep in the corridor. The message hops drone to drone — Scout, Relay-Anchor, camp tower — along the path most likely to deliver, chosen by each drone on its own.</p>
          <ul className="mt-5 space-y-2.5 text-[13.5px] text-fg">
            {['No tower, no internet: the drones are the network', 'Each link is scored by how many tries it takes to get a message through', 'No route? The message waits on the drone and flies with it', 'The camp fuses every report into one pin per person'].map(t =>
              <li key={t} className="flex gap-2.5"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />{t}</li>)}
          </ul>
        </div>
        <div className="glass relative aspect-[16/10] overflow-hidden">
          {seen && <Suspense fallback={null}><CampStage /></Suspense>}
          <div className="pointer-events-none absolute bottom-3 left-4 flex flex-wrap gap-3 text-[11px] text-muted">
            <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-scout" />Scout</span>
            <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-mapper" />Mapper</span>
            <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-relay" />Relay-Anchor</span>
            <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-camp" />camp tower</span>
            <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-[#fde047]" />message</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function Workflow() {
  useEngine('static');
  const [i, setI] = useState(0), [auto, setAuto] = useState(true);
  const ref = useRef<HTMLDivElement>(null), inView = useInView(ref, { amount: 0.4 });
  useEffect(() => { if (!auto || !inView || reducedMotion()) return; const t = setTimeout(() => setI(x => (x + 1) % STEPS.length), 6500); return () => clearTimeout(t); }, [i, auto, inView]);
  return (
    <section ref={ref} className="relative z-10 mx-auto max-w-[1400px] px-6 py-16 lg:px-10">
      <div className="eyebrow">How a mission unfolds</div>
      <h3 className="mt-3 text-[clamp(24px,2.8vw,36px)] font-semibold tracking-tight text-hi">Six steps, all on their own.</h3>
      <div className="mt-8 grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
        <ol className="space-y-1.5">
          {STEPS.map((s, k) => (
            <li key={s.k}>
              <button onClick={() => { setI(k); setAuto(false); }} className={cn('w-full rounded-xl border px-4 py-3 text-left transition-colors', k === i ? 'border-white/20 bg-white/[.07]' : 'border-transparent hover:bg-white/[.04]')}>
                <div className="flex items-baseline gap-3">
                  <span className={cn('num text-[11px]', k === i ? 'text-accent' : 'text-faint')}>0{k + 1}</span>
                  <span className={cn('text-sm font-medium', k === i ? 'text-hi' : 'text-muted')}>{s.h}</span>
                </div>
                <AnimatePresence initial={false}>
                  {k === i && <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden pt-2 pl-[30px] text-[13px] leading-relaxed text-muted">{s.p}</motion.p>}
                </AnimatePresence>
                {k === i && auto && inView && <motion.div key={'b' + i} className="mt-3 ml-[30px] h-px bg-accent/60" initial={{ width: 0 }} animate={{ width: 'calc(100% - 30px)' }} transition={{ duration: 6.5, ease: 'linear' }} />}
              </button>
            </li>
          ))}
        </ol>
        <div className="glass relative min-h-[420px] overflow-hidden">
          {E.V && <FlowArt step={i} />}
          <div className="absolute bottom-3 left-4 text-[11px] text-faint">schematic · real corridor geometry</div>
        </div>
      </div>
    </section>
  );
}

function FlowArt({ step }: { step: number }) {
  const V = E.V;
  const B = { x0: -560, x1: 120, y0: -1060, y1: 80 };
  const W = 680, H = 520, sc = Math.min(W / (B.x1 - B.x0), H / (B.y1 - B.y0));
  const P = (x: number, y: number): [number, number] => [(x - B.x0) * sc + (W - (B.x1 - B.x0) * sc) / 2, H - (y - B.y0) * sc - 10];
  const path = (pts: number[][]) => pts.map((p, k) => (k ? 'L' : 'M') + P(p[0], p[1]).map(v => v.toFixed(1)).join(',')).join(' ');
  const edges = useMemo(() => corridorEdges(), []);
  type Sec = { id: string; start: number[]; end: number[]; half_width: number };
  const sectors = V.sectors as Sec[], sec = (k: number) => sectors[k % sectors.length];
  const poly = (s: Sec) => {
    const [A, Bp] = [s.start, s.end], dx = Bp[0] - A[0], dy = Bp[1] - A[1], L = Math.hypot(dx, dy), nx = -dy / L * s.half_width, ny = dx / L * s.half_width;
    return path([[A[0] + nx, A[1] + ny], [Bp[0] + nx, Bp[1] + ny], [Bp[0] - nx, Bp[1] - ny], [A[0] - nx, A[1] - ny], [A[0] + nx, A[1] + ny]]);
  };
  const lawn = (s: Sec, n = 5) => {
    const [A, Bp] = [s.start, s.end], dx = Bp[0] - A[0], dy = Bp[1] - A[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L, pts: number[][] = [];
    for (let k = 0; k < n; k++) { const o = -s.half_width * 0.8 + (1.6 * s.half_width * k) / (n - 1), a = [A[0] + nx * o, A[1] + ny * o], b = [Bp[0] + nx * o, Bp[1] + ny * o]; if (k % 2) pts.push(b, a); else pts.push(a, b); }
    return path(pts);
  };
  const mid = (s: Sec, f: number, o = 0) => { const dx = s.end[0] - s.start[0], dy = s.end[1] - s.start[1], L = Math.hypot(dx, dy); return [s.start[0] + dx * f - dy / L * o, s.start[1] + dy * f + dx / L * o]; };
  const T = P(V.tower.x, V.tower.y), camp = [V.tower.x, V.tower.y];
  const pins = [mid(sec(1), 0.4, 30), mid(sec(1), 0.75, -40), mid(sec(0), 0.3, 20), mid(sec(0), 0.7, -30)];
  const dead = 3;
  const relay = mid(sec(1), 0.9, 0);
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.5 } };
  const pin = (p: number[], k: number, delay = 0) => <motion.circle key={k} cx={P(p[0], p[1])[0]} cy={P(p[0], p[1])[1]} r="5.5" fill={k === dead ? '#a1a1aa' : '#4ade80'} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay, type: 'spring' }} />;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label={'Mission step ' + STEPS[step].k}>
      <path d={path(V.river)} fill="none" stroke="#7dd3fc" strokeOpacity=".18" strokeWidth="1.5" />
      {edges.map((e, k) => <path key={k} d={path(e)} fill="none" stroke="#f4f6fa" strokeOpacity=".22" strokeDasharray="3 4" />)}
      {sectors.map((s, k) => <g key={s.id}>
        <path d={poly(s)} fill="none" stroke="#f4f6fa" strokeOpacity=".12" />
        {step >= 1 && <motion.path d={poly(s)} fill="#5eead4" initial={{ fillOpacity: 0 }} animate={{ fillOpacity: step === 1 ? [0, 0.1] : 0.06 }} transition={{ delay: step === 1 ? k * 1.4 : 0, duration: 0.8 }} />}
      </g>)}
      <AnimatePresence>
        {step === 0 && <motion.g key="alert" {...fade}>
          {[0, 1, 2].map(k => <circle key={k} cx={T[0]} cy={T[1]} r="10" fill="none" stroke="#fb7185" strokeOpacity=".8">
            <animate attributeName="r" from="8" to="300" dur="2.4s" begin={`${k * 0.8}s`} repeatCount="indefinite" />
            <animate attributeName="stroke-opacity" from=".8" to="0" dur="2.4s" begin={`${k * 0.8}s`} repeatCount="indefinite" /></circle>)}
        </motion.g>}
        {step === 1 && <motion.g key="map" {...fade}>
          {[0, 1].map(m => { const line = V.corridor.slice().reverse().map((p: number[]) => [p[0] + (m ? 35 : -35), p[1]]); return <g key={m}>
            <motion.path d={path(line)} fill="none" stroke="#7dd3fc" strokeOpacity=".6" strokeWidth="1.2" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 5, ease: 'linear' }} />
            <circle r="4" fill="#7dd3fc"><animateMotion dur="5s" fill="freeze" path={path([camp, ...line])} /></circle>
          </g>; })}
        </motion.g>}
        {step === 2 && <motion.g key="search" {...fade}>
          {sectors.map((s) => <g key={s.id}>
            <motion.path d={lawn(s)} fill="none" stroke="#f5b544" strokeOpacity=".55" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 5.5, ease: 'linear' }} />
            <circle r="4" fill="#f5b544"><animateMotion dur="5.5s" fill="freeze" path={lawn(s)} /></circle>
          </g>)}
        </motion.g>}
        {step === 3 && <motion.g key="detect" {...fade}>
          {sectors.map(s => <path key={s.id} d={lawn(s)} fill="none" stroke="#f5b544" strokeOpacity=".2" />)}
          {pins.map((p, k) => <g key={k}>{pin(p, k, 0.4 + k * 0.7)}
            <motion.text x={P(p[0], p[1])[0] + 10} y={P(p[0], p[1])[1] + 4} fill={k === dead ? '#a1a1aa' : '#4ade80'} fontSize="11" fontFamily="JetBrains Mono Variable" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 + k * 0.7 }}>
              {k === dead ? '25.0 °C · likely deceased' : (34 + k * 0.4).toFixed(1) + ' °C · alive'}</motion.text></g>)}
        </motion.g>}
        {step === 4 && <motion.g key="locate" {...fade}>
          {pins.map((p, k) => k === 0 ? null : <circle key={k} cx={P(p[0], p[1])[0]} cy={P(p[0], p[1])[1]} r="4" fill={k === dead ? '#a1a1aa' : '#4ade80'} fillOpacity=".5" />)}
          {[[-90, -60], [70, -80], [0, 90]].map(([dx, dy], k) => { const o = [pins[0][0] + dx, pins[0][1] + dy]; return <g key={k}>
            <motion.path d={path([o, pins[0]])} stroke="#fde047" strokeOpacity=".7" strokeDasharray="4 3" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: k * 0.5, duration: 0.8 }} />
            <circle cx={P(o[0], o[1])[0]} cy={P(o[0], o[1])[1]} r="4" fill="#f5b544" /></g>; })}
          {pin(pins[0], 0, 1.6)}
          <path d={path([pins[0], relay, camp])} fill="none" stroke="#5eead4" strokeOpacity=".4" strokeDasharray="4 4" />
          <circle cx={P(relay[0], relay[1])[0]} cy={P(relay[0], relay[1])[1]} r="5" fill="#c4b5fd" />
          <circle r="3.5" fill="#fde047"><animateMotion dur="2.6s" begin="2s" repeatCount="indefinite" path={path([pins[0], relay, camp])} /></circle>
          <text x={P(pins[0][0], pins[0][1])[0] + 12} y={P(pins[0][0], pins[0][1])[1] - 10} fill="#fde047" fontSize="11" fontFamily="Geist Variable">three views meet here</text>
        </motion.g>}
        {step === 5 && <motion.g key="home" {...fade}>
          {pins.map((p, k) => pin(p, k))}
          <motion.path d={path([camp, pins[2], pins[0], pins[1], pins[3]])} fill="none" stroke="#4ade80" strokeOpacity=".6" strokeDasharray="5 4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.5, duration: 3 }} />
          {[mid(sec(1), 0.8, 0), mid(sec(0), 0.5, 0), relay, mid(sec(0), 0.2, 40)].map((p, k) => (
            <circle key={k} r="4" fill={['#f5b544', '#7dd3fc', '#c4b5fd', '#f5b544'][k]}><animateMotion dur={`${3 + k * 0.5}s`} fill="freeze" path={path([p, camp])} /></circle>
          ))}
          <text x={T[0] + 14} y={T[1] + 4} fill="#4ade80" fontSize="11" fontFamily="Geist Variable">ground-team route: living first</text>
        </motion.g>}
      </AnimatePresence>
      <path d={`M${T[0]},${T[1] - 9} L${T[0] - 7},${T[1] + 5} L${T[0] + 7},${T[1] + 5} Z`} fill="#fb7185" />
      <text x={T[0] + 12} y={T[1] - 6} fill="#f4f6fa" fillOpacity=".8" fontSize="12" fontFamily="Geist Variable">Camp</text>
    </svg>
  );
}

function SeeItRun() {
  const setLive = useUI(s => s.setLive);
  const [busy, setBusy] = useState(false);
  return (
    <section className="relative z-10 mx-auto max-w-[1400px] px-6 pt-10 pb-20 lg:px-10">
      <div className="eyebrow">See it run</div>
      <h3 className="mt-3 text-[clamp(28px,3.4vw,44px)] font-semibold tracking-tight text-hi">Watch the swarm work.</h3>
      <div className="mt-8 grid gap-3 md:grid-cols-2">
        <button onClick={() => setLive(true)} className="glass group flex flex-col items-start gap-4 p-7 text-left transition-colors hover:bg-white/[.07]">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-alive/10 text-alive"><Radio size={20} /></span>
          <span><span className="block text-xl font-semibold text-hi">Live</span>
            <span className="mt-1 block text-[14px] text-muted">Starts the full Gazebo simulation on this machine and streams the swarm’s readings here as they happen.</span></span>
          <span className="text-xs text-accent group-hover:underline">scan this device →</span>
        </button>
        <button onClick={async () => { setBusy(true); await openBestReplay(); setBusy(false); }} className="glass group flex flex-col items-start gap-4 p-7 text-left transition-colors hover:bg-white/[.07]">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 text-accent"><Film size={20} /></span>
          <span><span className="block text-xl font-semibold text-hi">Pre-recorded</span>
            <span className="mt-1 block text-[14px] text-muted">A recorded run of the mission: landslide, search, a Scout and a Mapper lost and recovered from, replayed exactly as the camp saw it.</span></span>
          <span className="text-xs text-accent group-hover:underline">{busy ? 'loading…' : 'play the mission →'}</span>
        </button>
      </div>
    </section>
  );
}
