import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence, useInView, useScroll, useTransform } from 'motion/react';
import { Radio, Film, ChevronDown, Github, BellRing, ScanLine, Radar, Thermometer, Crosshair, Route } from 'lucide-react';
import { E } from '../lib/engine';
import { useEngine, useUI, reducedMotion } from '../lib/store';
import { corridorEdges } from '../lib/geo';
import { cn } from '../components/ui';
import { openBestReplay } from '../components/Replay';
import { REPO_URL } from '../config';
import { useVideo } from '../lib/videos';
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
      <Hero scroller={scroller} />
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

function Hero({ scroller }: { scroller: React.RefObject<HTMLDivElement> }) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ container: scroller, target: ref, offset: ['start start', 'end start'], layoutEffect: false });
  const fade = useTransform(scrollYProgress, [0, 0.75], [1, 0]);
  const lift = useTransform(scrollYProgress, [0, 1], [0, -90]);
  const shrink = useTransform(scrollYProgress, [0, 1], [1, 0.96]);
  return (
    <motion.section ref={ref} style={{ opacity: fade, y: lift, scale: shrink }} className="relative z-10 mx-auto grid min-h-screen max-w-[1400px] items-center gap-10 px-6 py-16 will-change-transform lg:grid-cols-[1.05fr_1fr] lg:px-10">
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }}>
        <div className="inline-flex items-center gap-2 rounded-full border border-camp/35 bg-camp/10 px-3 py-1 font-mono text-[11.5px] tracking-[0.2em] text-camp uppercase shadow-[0_0_15px_rgba(251,113,133,0.18)] backdrop-blur-md">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-camp opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-camp" />
          </span>
          AT 2:17 AM · JULY 30, 2024
        </div>
        <h1 className="mt-5 text-[clamp(36px,5vw,68px)] leading-[1.03] font-semibold tracking-[-0.035em] text-hi">
          A hillside above Mundakkai collapsed in the dark.
        </h1>
        <p className="mt-6 max-w-xl text-[16px] leading-relaxed text-muted">
          The debris flow buried <span className="text-fg font-medium">Mundakkai</span> and <span className="text-fg font-medium">Chooralmala</span> in Wayanad, Kerala,
          and washed away the only bridge. Rescuers searched by hand, in deep mud, with no phone network and no map of the new ground.
        </p>
        <div className="relative mt-8 overflow-hidden rounded-2xl border border-camp/30 bg-gradient-to-r from-camp/[.12] via-camp/[.04] to-transparent p-5 backdrop-blur-md shadow-[0_8px_30px_rgba(0,0,0,0.3)] before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-camp">
          <div className="text-[11.5px] font-semibold tracking-widest text-camp uppercase">The problem</div>
          <p className="mt-2 text-[19px] leading-snug font-medium text-hi">
            Survivors buried in a disaster zone have hours, not days — and today nobody can find them fast enough, or tell the camp where they are.
          </p>
        </div>
        <div className="mt-8">
          <div className="text-[12px] font-medium tracking-wide text-muted uppercase">Chance a trapped person is still alive</div>
          <div className="mt-3 grid max-w-xl grid-cols-3 gap-3">
            {SURVIVAL.map((s, i) => (
              <div key={s.d} className="glass group relative overflow-hidden px-4 py-3.5 transition-all duration-200 hover:border-white/20">
                <div className="num text-[34px] leading-none font-semibold tracking-tight" style={{ color: i === 0 ? 'var(--alive)' : i === 1 ? 'var(--cand)' : 'var(--danger)' }}>{s.v}%</div>
                <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/10">
                  <motion.div className="h-full rounded-full" style={{ background: i === 0 ? 'var(--alive)' : i === 1 ? 'var(--cand)' : 'var(--danger)' }}
                    initial={{ width: 0 }} animate={{ width: s.v + '%' }} transition={{ delay: 0.6 + i * 0.2, duration: 1 }} />
                </div>
                <div className="mt-2 text-xs font-medium text-muted">{s.d}</div>
              </div>
            ))}
          </div>
          <div className="mt-2.5 text-[11px] text-faint">Reported survival of trapped victims, 1990 Philippines earthquake — from our Phase 1 research.</div>
        </div>
      </motion.div>
      <HeroValley />
      <button onClick={() => scroller.current?.scrollBy({ top: window.innerHeight * 0.9, behavior: 'smooth' })} className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-1 text-xs text-faint transition-colors hover:text-fg lg:flex"><span>our answer</span><ChevronDown size={14} className="animate-bounce" /></button>
    </motion.section>
  );
}

function HeroValley() {
  useEngine('static');
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c || !E.T) return;
    const g = c.getContext('2d')!, T = E.T, still = reducedMotion();
    let raf = 0, last = 0, visible = true;
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible && !raf) raf = requestAnimationFrame(draw); });
    io.observe(c);
    const pts: number[][] = [];
    for (let i = 0; i < T.h; i += 1) for (let j = 0; j < T.w; j += 1) pts.push([T.x0 + j * T.res, T.y0 + i * T.res, T.z[i * T.w + j]]);
    let zmin = 1e9, zmax = -1e9; for (const p of pts) { zmin = Math.min(zmin, p[2]); zmax = Math.max(zmax, p[2]); }
    const edges = corridorEdges();
    const draw = (now: number) => {
      if (!visible) { raf = 0; return; }
      raf = requestAnimationFrame(draw);
      if (now - last < 33 && !still) return;
      last = now;
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
    return () => { cancelAnimationFrame(raf); io.disconnect(); };
  }, [E.T]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2, delay: 0.2 }} className="relative aspect-[4/3.4] w-full rounded-2xl border border-white/10 bg-black/40 p-2 shadow-2xl backdrop-blur-sm">
      <div className="absolute top-2.5 left-3.5 z-10 flex items-center gap-2 text-[10.5px] font-mono tracking-wider text-muted/70 uppercase">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
        Corridor Lidar Topology · 11°33'N 76°08'E
      </div>
      <canvas ref={ref} className="h-full w-full" aria-label="The Mundakkai valley as a lidar point field, with the debris corridor outlined" />
      <div className="absolute right-3.5 bottom-2.5 z-10 text-right font-mono text-[11px] leading-snug text-faint">real SRTM elevation · 10 m grid<br /><span className="text-accent/90">— debris corridor</span></div>
      <div className="pointer-events-none absolute top-1.5 left-1.5 h-3 w-3 border-t-2 border-l-2 border-accent/40" />
      <div className="pointer-events-none absolute top-1.5 right-1.5 h-3 w-3 border-t-2 border-r-2 border-accent/40" />
      <div className="pointer-events-none absolute bottom-1.5 left-1.5 h-3 w-3 border-b-2 border-l-2 border-accent/40" />
      <div className="pointer-events-none absolute bottom-1.5 right-1.5 h-3 w-3 border-b-2 border-r-2 border-accent/40" />
    </motion.div>
  );
}

function SwarmScroll({ scroller, onExplode }: { scroller: React.RefObject<HTMLDivElement>; onExplode: (r: RoleName) => void }) {
  const target = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ container: scroller, target, offset: ['start start', 'end end'], layoutEffect: false });
  const near = useInView(target, { root: scroller, margin: '1600px', once: true });
  const onScreen = useInView(target, { root: scroller, margin: '300px' });
  const { scrollYProgress: enter } = useScroll({ container: scroller, target, offset: ['start end', 'start start'], layoutEffect: false });
  const stage = useTransform(enter, [0.15, 0.85], [0, 1]);
  const rise = useTransform(enter, [0.3, 1], [40, 0]);
  const title = useTransform([enter, scrollYProgress] as never, ([a, b]: number[]) => Math.min(Math.max(0, (a - 0.45) / 0.4), b < 0.3 ? 1 : Math.max(0, 1 - (b - 0.3) / 0.12)));
  const hint = useTransform(scrollYProgress, [0.55, 0.7], [0, 1]);
  return (
    <section ref={target} className="relative z-10 h-[320vh]">
      <div className="sticky top-0 h-screen overflow-hidden">
        <motion.div style={{ opacity: stage }} className="absolute inset-0">{near && <Suspense fallback={null}><SwarmStage progress={scrollYProgress} onExplode={onExplode} active={onScreen} /></Suspense>}</motion.div>
        <motion.div style={{ opacity: title, y: rise }} className="pointer-events-none absolute top-10 left-1/2 w-full max-w-3xl -translate-x-1/2 px-6 text-center">
          <div className="rounded-3xl bg-black/60 px-6 py-4 backdrop-blur-md border border-white/[0.08] shadow-2xl">
            <div className="eyebrow">Our answer</div>
            <h2 className="mt-3 text-[clamp(30px,4vw,54px)] font-semibold tracking-tight text-hi drop-shadow-md">ResQMesh: a swarm that searches by itself.</h2>
            <p className="mx-auto mt-3 max-w-xl text-[15px] text-muted drop-shadow">Seven drones, three jobs, one mesh. When the towers fall, the sky becomes the network.</p>
          </div>
        </motion.div>
        <motion.div style={{ opacity: hint }} className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border border-white/15 bg-black/70 px-5 py-2.5 text-xs text-muted backdrop-blur-md shadow-xl">
          drag to turn the swarm 360° · double-click a drone to see how it is built
        </motion.div>
      </div>
    </section>
  );
}

function Roles() {
  return (
    <section className="relative z-10 mx-auto max-w-[1400px] px-6 py-20 lg:px-10">
      <div className="grid gap-4 md:grid-cols-3">
        {ROLES.map((r, i) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-80px' }} transition={{ delay: i * 0.08 }} className="glass group relative overflow-hidden p-6 transition-all duration-200 hover:border-white/20">
            <div className="absolute top-0 inset-x-0 h-1 opacity-80" style={{ background: r.color }} />
            <div className="flex items-center justify-between">
              <span className="text-lg font-semibold text-hi flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />
                {r.name}
              </span>
              <span className="num rounded-md px-2.5 py-1 text-[11px] font-medium border border-white/5" style={{ background: 'color-mix(in srgb, ' + r.color + ' 16%, transparent)', color: r.color }}>{r.n}</span>
            </div>
            <p className="mt-3.5 text-[14px] leading-relaxed text-muted">{r.job}</p>
          </motion.div>
        ))}
      </div>
      <div className="mt-14">
        <div className="eyebrow">Why it is different</div>
        <h3 className="mt-3 text-[clamp(24px,2.8vw,36px)] font-semibold tracking-tight text-hi">Conventional search vs ResQMesh</h3>
        <div className="glass mt-6 overflow-hidden rounded-2xl border border-white/10 shadow-xl">
          <div className="grid grid-cols-[1fr_1.2fr_1.2fr] border-b border-white/[.08] bg-white/[.02] px-6 py-3.5 text-[11px] font-mono tracking-wider text-faint uppercase">
            <span /><span>Conventional</span><span className="text-accent flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-accent" />ResQMesh</span>
          </div>
          {COMPARE.map(([a, b, c], idx) => (
            <div key={a} className={cn("grid grid-cols-[1fr_1.2fr_1.2fr] items-center gap-4 border-b border-white/[.04] px-6 py-3.5 text-[13.5px] transition-colors hover:bg-white/[.02] last:border-0", idx % 2 === 1 && "bg-white/[0.01]")}>
              <span className="font-medium text-muted">{a}</span>
              <span className="text-faint">{b}</span>
              <span className="font-medium text-hi flex items-center gap-2"><span className="text-accent/80 text-xs">✓</span>{c}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Camp() {
  const ref = useRef<HTMLDivElement>(null), seen = useInView(ref, { once: true, margin: '600px' }), onScreen = useInView(ref, { margin: '100px' });
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
        <div className="glass relative aspect-[16/10] overflow-hidden rounded-2xl border border-white/10 shadow-2xl">
          {seen && <Suspense fallback={null}><CampStage active={onScreen} /></Suspense>}
          <div className="pointer-events-none absolute bottom-3.5 left-4 flex flex-wrap gap-2 text-[11px] text-muted">
            <span className="flex items-center gap-1.5 rounded-md bg-black/70 px-2.5 py-1 backdrop-blur-md border border-white/10"><i className="h-2 w-2 rounded-full bg-scout" />Scout</span>
            <span className="flex items-center gap-1.5 rounded-md bg-black/70 px-2.5 py-1 backdrop-blur-md border border-white/10"><i className="h-2 w-2 rounded-full bg-mapper" />Mapper</span>
            <span className="flex items-center gap-1.5 rounded-md bg-black/70 px-2.5 py-1 backdrop-blur-md border border-white/10"><i className="h-2 w-2 rounded-full bg-relay" />Relay-Anchor</span>
            <span className="flex items-center gap-1.5 rounded-md bg-black/70 px-2.5 py-1 backdrop-blur-md border border-white/10"><i className="h-2 w-2 rounded-full bg-camp" />Camp tower</span>
            <span className="flex items-center gap-1.5 rounded-md bg-black/70 px-2.5 py-1 backdrop-blur-md border border-white/10"><i className="h-2 w-2 rounded-full bg-[#fde047]" />Message</span>
          </div>
        </div>
      </div>
    </section>
  );
}

const STEP_ICON = [BellRing, ScanLine, Radar, Thermometer, Crosshair, Route];
const STEP_CLIP = ['03_takeoff', '07_mapper_mapping', '04_swarm', '05_scout_detection', '06_alive_vs_deceased', '13_return_to_camp'];
const STEP_DUR = 6500;

function Workflow() {
  useEngine('static');
  const [i, setI] = useState(0), [auto, setAuto] = useState(true);
  const ref = useRef<HTMLDivElement>(null), inView = useInView(ref, { amount: 0.4 });
  useEffect(() => { if (!auto || !inView || reducedMotion()) return; const t = setTimeout(() => setI(x => (x + 1) % STEPS.length), STEP_DUR); return () => clearTimeout(t); }, [i, auto, inView]);
  const pick = (k: number) => { setI(k); setAuto(false); };
  return (
    <section ref={ref} className="relative z-10 mx-auto max-w-[1400px] px-6 py-16 lg:px-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">How a mission unfolds</div>
          <h3 className="mt-3 text-[clamp(24px,2.8vw,36px)] font-semibold tracking-tight text-hi">Six steps, all on their own.</h3>
          <p className="mt-2 max-w-xl text-[14px] text-muted">From the alert to every drone back on its pad, no pilot touches the controls. Pick a step, or let it play.</p>
        </div>
        <button onClick={() => setAuto(a => !a)} className="rounded-full border border-white/10 bg-white/[.04] px-3.5 py-1.5 text-xs text-muted transition-colors hover:text-fg">{auto ? 'pause' : 'play'} the sequence</button>
      </div>
      <div className="mt-8 grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
        <ol className="relative space-y-1.5">
          <span className="pointer-events-none absolute top-6 bottom-6 left-[27px] w-px bg-gradient-to-b from-accent/40 via-white/10 to-transparent" />
          {STEPS.map((s, k) => {
            const Icon = STEP_ICON[k], on = k === i, done = k < i;
            return (
              <li key={s.k} className="relative">
                <button onClick={() => pick(k)} className={cn('group w-full rounded-xl border px-3 py-3 text-left transition-all duration-300', on ? 'border-accent/40 bg-white/[.07] shadow-[0_8px_30px_rgba(0,0,0,0.35)]' : 'border-transparent hover:bg-white/[.04]')}>
                  <div className="flex items-center gap-3">
                    <span className={cn('relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-all duration-300',
                      on ? 'border-accent/50 bg-accent/15 text-accent shadow-[0_0_14px_rgba(94,234,212,0.35)]' : done ? 'border-accent/25 bg-[#0b0f14] text-accent/70' : 'border-white/10 bg-[#0b0f14] text-faint group-hover:text-muted')}>
                      <Icon size={15} />
                    </span>
                    <span className="min-w-0">
                      <span className={cn('num block text-[10.5px] font-semibold tracking-wider', on ? 'text-accent' : 'text-faint')}>STEP 0{k + 1} · {s.k}</span>
                      <span className={cn('block text-[14px] font-medium transition-colors', on ? 'text-hi' : 'text-muted group-hover:text-fg')}>{s.h}</span>
                    </span>
                  </div>
                  <AnimatePresence initial={false}>
                    {on && <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden pt-2 pl-11 text-[13px] leading-relaxed text-muted">{s.p}</motion.p>}
                  </AnimatePresence>
                  {on && auto && inView && <motion.div key={'b' + i} className="mt-3 ml-11 h-0.5 rounded-full bg-accent/70 shadow-[0_0_8px_rgba(94,234,212,0.5)]" initial={{ width: 0 }} animate={{ width: 'calc(100% - 44px)' }} transition={{ duration: STEP_DUR / 1000, ease: 'linear' }} />}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="glass relative overflow-hidden rounded-2xl border border-white/10 shadow-xl">
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-4 bg-gradient-to-b from-[#06080c]/90 to-transparent px-5 pt-4 pb-10">
            <AnimatePresence mode="wait">
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.3 }}>
                <div className="num text-[11px] font-semibold tracking-[0.2em] text-accent">0{i + 1} / 06 · {STEPS[i].k}</div>
                <div className="mt-1 text-[17px] font-semibold text-hi">{STEPS[i].h}</div>
              </motion.div>
            </AnimatePresence>
            <div className="hidden flex-wrap justify-end gap-x-3 gap-y-1 text-[11px] text-muted sm:flex">
              {[['#f5b544', 'Scout'], ['#7dd3fc', 'Mapper'], ['#c4b5fd', 'Relay-Anchor'], ['#4ade80', 'alive'], ['#a1a1aa', 'likely deceased']].map(([c, l]) =>
                <span key={l} className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full" style={{ background: c }} />{l}</span>)}
            </div>
          </div>
          <div className="aspect-[900/470] min-h-[340px] w-full">{E.V && <FlowArt step={i} />}</div>
          <StepClip step={i} />
          <div className="absolute inset-x-0 bottom-0 z-10 flex items-center gap-1.5 px-5 pb-3.5">
            {STEPS.map((s, k) => (
              <button key={s.k} onClick={() => pick(k)} aria-label={'step ' + (k + 1)} className="group flex-1 py-1.5">
                <span className={cn('block h-1 rounded-full transition-all duration-300', k < i ? 'bg-accent/60' : k === i ? 'bg-accent shadow-[0_0_8px_rgba(94,234,212,0.6)]' : 'bg-white/10 group-hover:bg-white/25')} />
              </button>
            ))}
            <span className="ml-3 hidden font-mono text-[10.5px] text-faint md:block">schematic · real corridor geometry · N →</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function StepClip({ step }: { step: number }) {
  const v = useVideo(STEP_CLIP[step]);
  const [bad, setBad] = useState<Record<number, boolean>>({});
  if (bad[step] || v.missing) return null;
  return (
    <AnimatePresence mode="wait">
      <motion.div key={step} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }}
        className="absolute left-4 bottom-12 z-10 hidden w-[28%] max-w-[250px] overflow-hidden rounded-xl border border-white/15 bg-black shadow-2xl md:block">
        <video src={v.src} autoPlay muted loop playsInline preload="auto" className="block aspect-video w-full object-cover"
          onError={() => setBad(b => ({ ...b, [step]: true }))} />
        <div className="absolute top-1.5 left-2 flex items-center gap-1.5 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[9.5px] tracking-wider text-white/80 uppercase">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-camp" />simulation
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function FlowArt({ step }: { step: number }) {
  const V = E.V;
  type Sec = { id: string; start: number[]; end: number[]; half_width: number };
  const sectors = V.sectors as Sec[], sec = (k: number) => sectors[k % sectors.length];
  const mid = (s: Sec, f: number, o = 0) => { const dx = s.end[0] - s.start[0], dy = s.end[1] - s.start[1], L = Math.hypot(dx, dy); return [s.start[0] + dx * f - dy / L * o, s.start[1] + dy * f + dx / L * o]; };
  const camp = [V.tower.x, V.tower.y];
  const pins = [mid(sec(0), 0.35, 30), mid(sec(0), 0.7, -40), mid(sec(0), 0.2, -25), mid(sec(0), 0.85, 35)];
  const dead = 3;
  const relay = mid(sec(0), 1.6, 0);
  // north runs left to right so the corridor and the camp fill the wide panel
  const W = 900, H = 470;
  const view = useMemo(() => {
    const pts: number[][] = [camp, relay, ...(V.corridor as number[][]), ...sectors.flatMap(s => [s.start, s.end])];
    const ys = pts.map(p => p[1]), xs = pts.map(p => p[0]);
    const pad = 110, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad, x0 = Math.min(...xs) - pad * 1.4, x1 = Math.max(...xs) + pad * 1.4;
    const sc = Math.min((W - 60) / (y1 - y0), (H - 110) / (x1 - x0));
    return { y0, x0, sc, ox: (W - (y1 - y0) * sc) / 2, oy: 62 + (H - 110 - (x1 - x0) * sc) / 2, x1, y1 };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const P = (x: number, y: number): [number, number] => [view.ox + (y - view.y0) * view.sc, view.oy + (x - view.x0) * view.sc];
  const path = (pts: number[][]) => pts.map((p, k) => (k ? 'L' : 'M') + P(p[0], p[1]).map(v => v.toFixed(1)).join(',')).join(' ');
  const poly = (s: Sec) => {
    const [A, Bp] = [s.start, s.end], dx = Bp[0] - A[0], dy = Bp[1] - A[1], L = Math.hypot(dx, dy), nx = -dy / L * s.half_width, ny = dx / L * s.half_width;
    return path([[A[0] + nx, A[1] + ny], [Bp[0] + nx, Bp[1] + ny], [Bp[0] - nx, Bp[1] - ny], [A[0] - nx, A[1] - ny], [A[0] + nx, A[1] + ny]]);
  };
  const lawn = (s: Sec, n = 7, f0 = 0, f1 = 1) => {
    const A = mid(s, f0), Bp = mid(s, f1), dx = Bp[0] - A[0], dy = Bp[1] - A[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L, pts: number[][] = [];
    for (let k = 0; k < n; k++) { const o = -s.half_width * 0.82 + (1.64 * s.half_width * k) / (n - 1), a = [A[0] + nx * o, A[1] + ny * o], b = [Bp[0] + nx * o, Bp[1] + ny * o]; if (k % 2) pts.push(b, a); else pts.push(a, b); }
    return path(pts);
  };
  const terrain = useMemo(() => {
    const T = E.T; if (!T) return [] as { x: number; y: number; u: number }[];
    const out: { x: number; y: number; u: number }[] = [], stride = Math.max(1, Math.round(22 / T.res));
    let zmin = 1e9, zmax = -1e9;
    for (let i = 0; i < T.h; i += stride) for (let j = 0; j < T.w; j += stride) {
      const x = T.x0 + j * T.res, y = T.y0 + i * T.res;
      if (x < view.x0 || x > view.x1 || y < view.y0 || y > view.y1) continue;
      const z = T.z[i * T.w + j]; zmin = Math.min(zmin, z); zmax = Math.max(zmax, z); out.push({ x, y, u: z });
    }
    return out.map(p => ({ ...p, u: (p.u - zmin) / Math.max(1, zmax - zmin) }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const T = P(camp[0], camp[1]);
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.5 } };
  const drone = (c: string, dur: string, d: string, extra: Record<string, string> = {}) => (
    <g><circle r="9" fill={c} fillOpacity=".18" /><circle r="4.2" fill={c} stroke="#06080c" strokeWidth="1.2" />
      <animateMotion dur={dur} fill="freeze" path={d} {...extra} /></g>);
  const pin = (p: number[], k: number, delay = 0) => { const q = P(p[0], p[1]); return (
    <motion.g key={k} initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay, type: 'spring', stiffness: 260, damping: 16 }} style={{ transformOrigin: `${q[0]}px ${q[1]}px` }}>
      <circle cx={q[0]} cy={q[1]} r="11" fill={k === dead ? '#a1a1aa' : '#4ade80'} fillOpacity=".15" />
      <circle cx={q[0]} cy={q[1]} r="5.5" fill={k === dead ? '#a1a1aa' : '#4ade80'} stroke="#06080c" strokeWidth="1.2" />
    </motion.g>); };
  const s0 = sec(0), labelAt = P(mid(s0, 0.5, s0.half_width + 22)[0], mid(s0, 0.5, s0.half_width + 22)[1]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label={'Mission step ' + STEPS[step].k}>
      <defs>
        <radialGradient id="campglow"><stop offset="0" stopColor="#fb7185" stopOpacity=".35" /><stop offset="1" stopColor="#fb7185" stopOpacity="0" /></radialGradient>
      </defs>
      {terrain.map((p, k) => { const q = P(p.x, p.y); return <rect key={k} x={q[0]} y={q[1]} width="1.6" height="1.6" fill="#cbd5e1" fillOpacity={0.05 + 0.22 * p.u} />; })}
      <path d={path(V.river)} fill="none" stroke="#7dd3fc" strokeOpacity=".28" strokeWidth="2" />
      <path d={path(V.corridor)} fill="none" stroke="#a16207" strokeOpacity=".35" strokeWidth={Math.max(6, 2 * V.half_width * view.sc * 0.8)} strokeLinecap="round" strokeLinejoin="round" />
      {sectors.map((s, k) => <g key={s.id}>
        <path d={poly(s)} fill="#f4f6fa" fillOpacity=".02" stroke="#f4f6fa" strokeOpacity=".22" strokeDasharray="4 4" />
        {step >= 1 && <motion.path d={poly(s)} fill="#5eead4" initial={{ fillOpacity: 0 }} animate={{ fillOpacity: step === 1 ? [0, 0.12] : 0.07 }} transition={{ delay: step === 1 ? 2.5 + k : 0, duration: 1.2 }} />}
      </g>)}
      <text x={labelAt[0]} y={labelAt[1]} textAnchor="middle" fill="#f4f6fa" fillOpacity=".55" fontSize="11" fontFamily="JetBrains Mono Variable">sector {s0.id} · debris corridor</text>
      <circle cx={T[0]} cy={T[1]} r="60" fill="url(#campglow)" />
      <AnimatePresence>
        {step === 0 && <motion.g key="alert" {...fade}>
          {[0, 1, 2].map(k => <circle key={k} cx={T[0]} cy={T[1]} r="10" fill="none" stroke="#fb7185" strokeOpacity=".8" strokeWidth="1.5">
            <animate attributeName="r" from="8" to="420" dur="2.6s" begin={`${k * 0.85}s`} repeatCount="indefinite" />
            <animate attributeName="stroke-opacity" from=".8" to="0" dur="2.6s" begin={`${k * 0.85}s`} repeatCount="indefinite" /></circle>)}
          {([['#f5b544', -26], ['#f5b544', -14], ['#7dd3fc', -2], ['#7dd3fc', 10], ['#c4b5fd', 22]] as [string, number][]).map(([c, o], k) => {
            const a = [camp[0] + o, camp[1] - 14], b = k === 4 ? relay : mid(s0, 1.05, o * 2);
            return <g key={k}>{drone(c, `${2.4 + k * 0.25}s`, path([a, b]), { begin: `${0.4 + k * 0.2}s` })}</g>;
          })}
          <text x={T[0] - 8} y={T[1] + 34} textAnchor="end" fill="#fb7185" fontSize="12" fontFamily="Geist Variable">alert floods the mesh · swarm launches</text>
        </motion.g>}
        {step === 1 && <motion.g key="map" {...fade}>
          {[-1, 1].map(m => { const off = m * s0.half_width * 0.45, a = mid(s0, 1.05, off), b = mid(s0, -0.05, off); return <g key={m}>
            <motion.path d={path([a, b])} fill="none" stroke="#7dd3fc" strokeWidth={s0.half_width * view.sc * 0.9} strokeLinecap="round" initial={{ pathLength: 0, opacity: 0.1 }} animate={{ pathLength: 1, opacity: 0.16 }} transition={{ duration: 4.5, ease: 'linear' }} />
            {drone('#7dd3fc', '4.5s', path([camp, a, b]))}
          </g>; })}
          <text x={P(relay[0], relay[1])[0]} y={P(relay[0], relay[1])[1] + 30} textAnchor="middle" fill="#7dd3fc" fontSize="12" fontFamily="Geist Variable">lidar swath builds the 3D map</text>
        </motion.g>}
        {step === 2 && <motion.g key="search" {...fade}>
          {[[0, 0.5], [0.5, 1]].map(([f0, f1], k) => <g key={k}>
            <motion.path d={lawn(s0, 7, f0, f1)} fill="none" stroke="#f5b544" strokeOpacity=".6" strokeWidth="1.3" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 5.5, ease: 'linear' }} />
            {drone('#f5b544', '5.5s', lawn(s0, 7, f0, f1))}
          </g>)}
          <text x={P(relay[0], relay[1])[0]} y={P(relay[0], relay[1])[1] + 30} textAnchor="middle" fill="#f5b544" fontSize="12" fontFamily="Geist Variable">two Scouts, two altitude layers, no overlap</text>
        </motion.g>}
        {step === 3 && <motion.g key="detect" {...fade}>
          {[[0, 0.5], [0.5, 1]].map(([f0, f1], k) => <path key={k} d={lawn(s0, 7, f0, f1)} fill="none" stroke="#f5b544" strokeOpacity=".18" />)}
          {pins.map((p, k) => {
            const pt = P(p[0], p[1]), lx = Math.max(...pins.map(q => P(q[0], q[1])[0])) + 70, ly = P(s0.start[0], s0.start[1])[1] - 46 + k * 26;
            const label = k === dead ? '25.0 °C · likely deceased' : (33.4 + k * 0.7).toFixed(1) + ' °C · alive', c = k === dead ? '#a1a1aa' : '#4ade80';
            return (
              <g key={k}>
                {pin(p, k, 0.4 + k * 0.7)}
                <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 + k * 0.7 }}>
                  <path d={`M${pt[0]},${pt[1]} L${lx - 14},${ly} L${lx},${ly}`} fill="none" stroke={c} strokeOpacity=".4" />
                  <rect x={lx} y={ly - 10} width={label.length * 6.6 + 12} height="19" rx="4" fill="#06080c" fillOpacity=".92" stroke={c} strokeOpacity=".45" />
                  <text x={lx + 6} y={ly + 3.5} fill={c} fontSize="10.5" fontFamily="JetBrains Mono Variable" fontWeight="500">{label}</text>
                </motion.g>
              </g>
            );
          })}
        </motion.g>}
        {step === 4 && <motion.g key="locate" {...fade}>
          {pins.map((p, k) => k === 0 ? null : <circle key={k} cx={P(p[0], p[1])[0]} cy={P(p[0], p[1])[1]} r="4" fill={k === dead ? '#a1a1aa' : '#4ade80'} fillOpacity=".4" />)}
          {[[-120, -50], [-30, 110], [110, -40]].map(([dx, dy], k) => { const o = [pins[0][0] + dx, pins[0][1] + dy], q = P(o[0], o[1]); return <g key={k}>
            <motion.path d={path([o, pins[0]])} stroke="#fde047" strokeOpacity=".75" strokeWidth="1.3" strokeDasharray="5 3" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: k * 0.5, duration: 0.8 }} />
            <circle cx={q[0]} cy={q[1]} r="9" fill="#f5b544" fillOpacity=".18" />
            <circle cx={q[0]} cy={q[1]} r="4" fill="#f5b544" /></g>; })}
          {pin(pins[0], 0, 1.6)}
          <path d={path([pins[0], relay, camp])} fill="none" stroke="#5eead4" strokeOpacity=".45" strokeDasharray="4 4" />
          <circle cx={P(relay[0], relay[1])[0]} cy={P(relay[0], relay[1])[1]} r="10" fill="#c4b5fd" fillOpacity=".18" />
          <circle cx={P(relay[0], relay[1])[0]} cy={P(relay[0], relay[1])[1]} r="5" fill="#c4b5fd" />
          <circle r="3.5" fill="#fde047"><animateMotion dur="2.6s" begin="2s" repeatCount="indefinite" path={path([pins[0], relay, camp])} /></circle>
          <text x={P(pins[0][0], pins[0][1])[0] + 14} y={P(pins[0][0], pins[0][1])[1] - 14} fill="#fde047" fontSize="12" fontFamily="Geist Variable">three views meet at the person</text>
          <text x={P(relay[0], relay[1])[0]} y={P(relay[0], relay[1])[1] + 26} textAnchor="middle" fill="#c4b5fd" fontSize="11" fontFamily="Geist Variable">pin hops to the camp over the mesh</text>
        </motion.g>}
        {step === 5 && <motion.g key="home" {...fade}>
          {pins.map((p, k) => pin(p, k))}
          <motion.path d={path([camp, pins[0], pins[1], pins[2], pins[3]])} fill="none" stroke="#4ade80" strokeOpacity=".7" strokeWidth="1.6" strokeDasharray="6 4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.5, duration: 3 }} />
          {[mid(s0, 0.8, 30), mid(s0, 0.4, -30), relay, mid(s0, 0.2, 40)].map((p, k) => (
            <g key={k}>{drone(['#f5b544', '#7dd3fc', '#c4b5fd', '#f5b544'][k], `${3 + k * 0.5}s`, path([p, [camp[0] + 34, camp[1] - 30 + k * 16]]))}</g>
          ))}
          <text x={T[0] - 8} y={T[1] + 34} textAnchor="end" fill="#4ade80" fontSize="12" fontFamily="Geist Variable">ground-team route: living first · drones home</text>
        </motion.g>}
      </AnimatePresence>
      <path d={`M${T[0]},${T[1] - 10} L${T[0] - 8},${T[1] + 6} L${T[0] + 8},${T[1] + 6} Z`} fill="#fb7185" />
      <text x={T[0]} y={T[1] - 16} textAnchor="middle" fill="#f4f6fa" fillOpacity=".85" fontSize="12.5" fontWeight="600" fontFamily="Geist Variable">Chooralmala camp</text>
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
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <button onClick={() => setLive(true)} className="glass group relative overflow-hidden flex flex-col items-start gap-4 p-7 text-left transition-all duration-300 hover:border-alive/30 hover:bg-white/[.06] hover:shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-alive/60 via-alive/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-alive/10 text-alive border border-alive/20 shadow-[0_0_15px_rgba(74,222,128,0.15)]"><Radio size={22} /></span>
          <span>
            <span className="block text-xl font-semibold text-hi">Live</span>
            <span className="mt-1.5 block text-[14px] leading-relaxed text-muted">Starts the full Gazebo simulation on this machine and streams the swarm’s readings here as they happen.</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-alive group-hover:underline">
            scan this device <span className="transition-transform duration-200 group-hover:translate-x-1">→</span>
          </span>
        </button>
        <button onClick={async () => { setBusy(true); await openBestReplay(); setBusy(false); }} className="glass group relative overflow-hidden flex flex-col items-start gap-4 p-7 text-left transition-all duration-300 hover:border-accent/30 hover:bg-white/[.06] hover:shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
          <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-accent/60 via-accent/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent border border-accent/20 shadow-[0_0_15px_rgba(94,234,212,0.15)]"><Film size={22} /></span>
          <span>
            <span className="block text-xl font-semibold text-hi">Pre-recorded</span>
            <span className="mt-1.5 block text-[14px] leading-relaxed text-muted">A recorded run of the mission: landslide, search, a Scout and a Mapper lost and recovered from, replayed exactly as the camp saw it.</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-accent group-hover:underline">
            {busy ? 'loading…' : 'play the mission'} <span className="transition-transform duration-200 group-hover:translate-x-1">→</span>
          </span>
        </button>
      </div>
    </section>
  );
}
