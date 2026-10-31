/* The digital twin as a 3D lidar sees it: the valley's real elevation as a monochrome point cloud, the Mappers'
   measured debris surface in bright points, and the swarm, radio links and people as minimal overlays. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Html, Line } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OC } from 'three-stdlib';
import { E, COND_C, ROLE_C, role, short, clockStr } from '../lib/engine';
import { useEngine, useUI, reducedMotion } from '../lib/store';
import { corridorEdges, nodePos, activity } from '../lib/geo';
import { Panel, Segmented, Chip } from '../components/ui';
import { FixChip } from '../components/Ops';

const toV = (x: number, y: number, z: number) => new THREE.Vector3(x, z, -y);   // ENU -> three (Y up)
const CENTER = { x: -200, y: -780 };

const vert = /* glsl */ `
  attribute float aI; uniform float uT; uniform float uSize; uniform float zMin; uniform float zMax; uniform float uLive;
  varying float vB;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    float h = clamp((position.y - zMin) / (zMax - zMin), 0.0, 1.0);
    float band = uLive > 0.5 ? 0.0 : smoothstep(18.0, 0.0, abs(mod(-position.z * 0.55 - uT * 120.0, 900.0) - 450.0));
    vB = uLive > 0.5 ? 0.75 + 0.25 * aI : (0.16 + 0.62 * h) * (0.72 + 0.28 * aI) + 0.55 * band;
    gl_PointSize = clamp(uSize * (uLive > 0.5 ? 1.5 : 1.0) * (650.0 / -mv.z), 1.0, 6.0);
    gl_Position = projectionMatrix * mv;
  }`;
const frag = /* glsl */ `
  uniform float uLive; varying float vB;
  void main() {
    vec2 c = gl_PointCoord - 0.5; if (dot(c, c) > 0.25) discard;
    vec3 col = uLive > 0.5 ? mix(vec3(0.75, 1.0, 0.95), vec3(1.0), 0.4) : vec3(0.86, 0.9, 0.95);
    gl_FragColor = vec4(col * vB, uLive > 0.5 ? 0.95 : 0.85);
  }`;

function makeMat(live: boolean, zMin: number, zMax: number) {
  return new THREE.ShaderMaterial({
    vertexShader: vert, fragmentShader: frag, transparent: true, depthWrite: false,
    uniforms: { uT: { value: 0 }, uSize: { value: live ? 1.1 : 1.4 }, zMin: { value: zMin }, zMax: { value: zMax }, uLive: { value: live ? 1 : 0 } }
  });
}

function Terrain() {
  const T = E.T;
  const { geo, mat } = useMemo(() => {
    const step = 4, pos: number[] = [], I: number[] = [];
    let zmin = 1e9, zmax = -1e9;
    for (let y = T.y0; y < T.y0 + (T.h - 1) * T.res; y += step) for (let x = T.x0; x < T.x0 + (T.w - 1) * T.res; x += step) {
      const jx = x + (Math.random() - 0.5) * step * 0.6, jy = y + (Math.random() - 0.5) * step * 0.6, z = E.ground(jx, jy);
      pos.push(jx, z, -jy); I.push(Math.random()); zmin = Math.min(zmin, z); zmax = Math.max(zmax, z);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('aI', new THREE.Float32BufferAttribute(I, 1));
    return { geo: g, mat: makeMat(false, zmin, zmax) };
  }, [T]);
  const still = reducedMotion();
  useFrame(({ clock }) => { mat.uniforms.uT.value = still ? 0 : clock.elapsedTime; });
  return <points geometry={geo} material={mat} />;
}

function LidarCloud() {
  useEngine('cloud', 'seek');
  const c = E.S.cloud;
  const { geo, mat } = useMemo(() => {
    const g = new THREE.BufferGeometry(); if (!c) return { geo: g, mat: makeMat(true, 0, 1) };
    const pos = new Float32Array(c.n * 3), I = new Float32Array(c.n);
    for (let i = 0; i < c.n; i++) { pos[3 * i] = c.xs[i]; pos[3 * i + 1] = c.zs[i]; pos[3 * i + 2] = -c.ys[i]; I[i] = Math.random(); }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aI', new THREE.BufferAttribute(I, 1));
    return { geo: g, mat: makeMat(true, c.zmin, c.zmax) };
  }, [c?.ver]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!c) return null;
  return <points geometry={geo} material={mat} />;
}

function Corridor() {
  const lines = useMemo(() => corridorEdges().map(e => e.map(p => toV(p[0], p[1], E.ground(p[0], p[1]) + 2))), []);
  return <>{lines.map((l, k) => <Line key={k} points={l} color="#5eead4" lineWidth={1} transparent opacity={0.45} dashed dashSize={8} gapSize={8} />)}</>;
}

function Swarm({ labels }: { labels: boolean }) {
  useEngine('fleet', 'persons', 'traffic', 'seek', 'plan');
  const sel = useUI(s => s.sel), select = useUI(s => s.select), pick = useUI(s => s.pickPerson);
  const S = E.S;
  return (
    <group>
      {Object.entries(S.fleet).map(([n, s]) => {
        const lost = E.isLost(n, s), c = lost ? '#71717a' : ROLE_C[role(n)], g = s.z - s.agl, p = toV(s.x, s.y, s.z);
        return (
          <group key={n}>
            <Line points={[p, toV(s.x, s.y, g)]} color={c} lineWidth={1} transparent opacity={0.45} />
            <mesh position={p} onClick={e => { e.stopPropagation(); select(n); }}>
              <octahedronGeometry args={[n === sel ? 5 : 3.4]} />
              <meshBasicMaterial color={c} wireframe={lost} />
            </mesh>
            <mesh position={toV(s.x, s.y, g + 0.6)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[3, 3.8, 24]} /><meshBasicMaterial color={c} transparent opacity={0.5} side={THREE.DoubleSide} /></mesh>
            {labels && <Html position={p} distanceFactor={600} zIndexRange={[10, 0]} style={{ pointerEvents: 'none' }}>
              <div className="num -translate-y-6 translate-x-2 rounded bg-black/55 px-1.5 py-0.5 text-[11px] whitespace-nowrap text-white/90">{short(n)} <span className="text-white/45">{Math.round(s.agl)} m</span></div>
            </Html>}
          </group>
        );
      })}
      {S.persons.map(q => {
        const c = q.rechecked && q.condition === 'UNKNOWN' ? '#52525b' : COND_C[q.condition], g = E.ground(q.x, q.y);
        return (
          <group key={q.id} onClick={e => { e.stopPropagation(); pick(q.id); }}>
            <Line points={[toV(q.x, q.y, g), toV(q.x, q.y, g + 26)]} color={c} lineWidth={2} />
            <mesh position={toV(q.x, q.y, g + 26)}><sphereGeometry args={[2.4, 12, 12]} /><meshBasicMaterial color={c} /></mesh>
            <mesh position={toV(q.x, q.y, g + 0.8)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[4, 5.2, 32]} /><meshBasicMaterial color={c} transparent opacity={0.8} side={THREE.DoubleSide} /></mesh>
            {labels && <Html position={toV(q.x, q.y, g + 26)} distanceFactor={600} style={{ pointerEvents: 'none' }}>
              <div className="num -translate-y-5 translate-x-2 text-[11px] font-medium whitespace-nowrap" style={{ color: c }}>{q.id.replace('PERSON-', 'P')}</div>
            </Html>}
          </group>
        );
      })}
      {S.traffic?.links.filter((l: unknown[]) => l[4]).map((l: [string, string, number], k: number) => {
        const a = nodePos(l[0]), b = nodePos(l[1]); if (!a || !b) return null;
        return <Line key={k} points={[toV(a[0], a[1], a[2]), toV(b[0], b[1], b[2])]} color="#5eead4" lineWidth={1} transparent opacity={0.12 + 0.45 * l[2]} />;
      })}
      {E.V && <group>
        <Line points={[toV(E.V.tower.x, E.V.tower.y, E.ground(E.V.tower.x, E.V.tower.y)), toV(E.V.tower.x, E.V.tower.y, E.V.tower.z)]} color="#fb7185" lineWidth={2} />
        <mesh position={toV(E.V.tower.x, E.V.tower.y, E.V.tower.z)}><sphereGeometry args={[3, 12, 12]} /><meshBasicMaterial color="#fb7185" /></mesh>
        {labels && <Html position={toV(E.V.tower.x, E.V.tower.y, E.V.tower.z)} distanceFactor={600} style={{ pointerEvents: 'none' }}><div className="-translate-y-6 translate-x-2 text-[11px] whitespace-nowrap text-[#fb7185]">Camp tower</div></Html>}
      </group>}
    </group>
  );
}

function Routes() {
  useEngine('rescue', 'persons', 'seek', 'static');
  const passes = useMemo(() => {
    if (!E.V) return [];
    return (E.V.sectors as { start: number[]; end: number[]; half_width: number }[]).map(s => {
      const dx = s.end[0] - s.start[0], dy = s.end[1] - s.start[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L, pts: THREE.Vector3[] = [];
      const n = Math.max(2, Math.round((2 * s.half_width) / 30) + 1);
      for (let k = 0; k < n; k++) {
        const o = -s.half_width + (2 * s.half_width * k) / (n - 1), a = [s.start[0] + nx * o, s.start[1] + ny * o], b = [s.end[0] + nx * o, s.end[1] + ny * o];
        for (const q of k % 2 ? [b, a] : [a, b]) pts.push(toV(q[0], q[1], E.ground(q[0], q[1]) + 18));
      }
      return pts;
    });
  }, [E.V]); // eslint-disable-line react-hooks/exhaustive-deps
  const R = E.S.rescue, byId = Object.fromEntries(E.S.persons.map(p => [p.id, p]));
  const route = R?.route?.length ? [[0, 0], ...R.route.map((r: { id: string; x?: number; y?: number }) => r.x != null ? [r.x, r.y] : byId[r.id] ? [byId[r.id].x, byId[r.id].y] : null).filter(Boolean)] as number[][] : null;
  return (
    <group>
      {passes.map((p, k) => <Line key={k} points={p} color="#f5b544" lineWidth={1} transparent opacity={0.28} />)}
      {route && route.length > 1 && <Line points={route.map(q => toV(q[0], q[1], E.ground(q[0], q[1]) + 3))} color="#4ade80" lineWidth={2} dashed dashSize={10} gapSize={6} />}
    </group>
  );
}

const MARKS: [string, RegExp][] = [
  ['Take-off', /Deploying the swarm|alert received/i], ['First person found', /Found by/i], ['Scout lost', /scout_\d LOST/i],
  ['Reserve on station', /joins the search/i], ['Mapper lost', /mapper_\d LOST/i], ['Brain moved', /Planner moved/i],
  ['Search complete', /Search complete/i], ['All home', /Mission complete|All drones landed/i]
];

function Timeline() {
  useEngine('events', 'clock', 'seek', 'story');
  const R = E.replay, now = E.mt() ?? 0;
  const all = useMemo(() => {
    if (!R) return null;
    for (let i = R.recs.length - 1; i >= 0; i--) if (R.recs[i].topic === '/base/eventlog') { try { return JSON.parse(R.recs[i].msg.data) as { t: number | null; text: string }[]; } catch { return null; } }
    return null;
  }, [R?.name, R?.recs.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const evs = all || E.S.events;
  const marks = [{ l: 'Alert', t: 0 }, ...MARKS.map(([l, re]) => ({ l, t: evs.find(e => e.t != null && re.test(e.text))?.t ?? null })).filter(m => m.t != null)] as { l: string; t: number }[];
  const end = Math.max(R ? R.dur - (R.tAlert ?? 0) : 0, now, ...marks.map(m => m.t), 60);
  const go = (t: number) => { if (!R) return; const p = R.playing; E.seek((R.tAlert ?? 0) + t); R.playing = p; };
  return (
    <div className="glass px-5 pt-3 pb-4">
      <div className="flex items-center justify-between"><span className="text-[13px] font-medium text-hi">Mission timeline</span><span className="text-[11px] text-faint">{R ? 'click a moment to jump to it' : 'key moments as they happen'}</span></div>
      <div className="relative mt-7 h-8">
        <div className="absolute inset-x-0 top-3 h-px bg-white/15" />
        <div className="absolute top-3 left-0 h-px bg-accent" style={{ width: Math.min(100, (now / end) * 100) + '%' }} />
        {marks.map((m, i) => (
          <button key={m.l} onClick={() => go(m.t)} className="group absolute -translate-x-1/2" style={{ left: (m.t / end) * 100 + '%' }} title={m.l + ' · T+ ' + clockStr(m.t)}>
            <span className={'block h-2.5 w-2.5 translate-y-[7px] rounded-full border ' + (m.t <= now ? 'border-accent bg-accent' : 'border-white/40 bg-bg')} />
            <span className={'absolute left-1/2 -translate-x-1/2 text-[10.5px] whitespace-nowrap ' + (i % 2 ? 'top-5' : '-top-6') + (m.t <= now ? ' text-fg' : ' text-faint') + ' group-hover:text-hi'}>{m.l} <span className="num text-faint">{clockStr(m.t)}</span></span>
          </button>
        ))}
      </div>
    </div>
  );
}

type Mode = 'overview' | 'follow' | 'top';
function Rig({ mode, follow }: { mode: Mode; follow: string | null }) {
  const { camera } = useThree(), controls = useThree(s => s.controls) as unknown as OC | null;
  const goal = useRef<{ pos: THREE.Vector3; tgt: THREE.Vector3 } | null>(null);
  useEffect(() => {
    const g0 = E.ground(CENTER.x, CENTER.y);
    if (mode === 'overview') goal.current = { pos: toV(CENTER.x + 430, CENTER.y - 600, g0 + 400), tgt: toV(CENTER.x, CENTER.y, g0) };
    if (mode === 'top') goal.current = { pos: toV(CENTER.x, CENTER.y - 1, g0 + 1500), tgt: toV(CENTER.x, CENTER.y, g0) };
    if (mode === 'follow') goal.current = null;
  }, [mode]);
  useFrame((_, dt) => {
    if (!controls) return;
    const k = 1 - Math.exp(-dt * 3);
    if (mode === 'follow' && follow && E.S.fleet[follow]) {
      const s = E.S.fleet[follow], t = toV(s.x, s.y, s.z);
      const off = camera.position.clone().sub(controls.target);
      if (off.length() > 260) off.setLength(160);
      controls.target.lerp(t, k); camera.position.copy(controls.target).add(off);
    } else if (goal.current) {
      camera.position.lerp(goal.current.pos, k); controls.target.lerp(goal.current.tgt, k);
      if (camera.position.distanceTo(goal.current.pos) < 2 && controls.target.distanceTo(goal.current.tgt) < 2) goal.current = null;
    }
    controls.update();
  });
  return null;
}

export default function Twin() {
  useEngine('static', 'fleet', 'persons');
  const sel = useUI(s => s.sel), select = useUI(s => s.select), person = useUI(s => s.person);
  const [mode, setMode] = useState<Mode>('overview');
  const [labels, setLabels] = useState(true);
  const [routes, setRoutes] = useState(true);
  const follow = sel && E.S.fleet[sel] ? sel : Object.keys(E.S.fleet).find(n => n.startsWith('scout') && !E.isLost(n, E.S.fleet[n]) && E.S.fleet[n].agl > 3) || null;
  const s = sel ? E.S.fleet[sel] : null, p = person ? E.S.persons.find(q => q.id === person) : null;
  return (
    <div className="flex h-full flex-col gap-3">
    <Timeline />
    <div className="grid min-h-[600px] flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Panel id="twin-stage" title="Digital twin" sub="as the lidar sees it · real SRTM elevation · bright points: the Mappers' measured debris surface"
        explain="The valley's real elevation rendered as a point cloud, the way a 3D lidar returns it. The brighter points are the post-landslide surface the Mappers actually measured. Drones show their height above the ground; lines between them are live radio links."
        actions={<>
          <Segmented value={mode} onChange={setMode} options={[{ v: 'overview', l: 'Overview' }, { v: 'follow', l: 'Follow' }, { v: 'top', l: 'Top' }]} />
          <Segmented value={labels ? 'on' : 'off'} onChange={v => setLabels(v === 'on')} options={[{ v: 'on', l: 'Labels' }, { v: 'off', l: 'Off' }]} />
          <Segmented value={routes ? 'on' : 'off'} onChange={v => setRoutes(v === 'on')} options={[{ v: 'on', l: 'Routes' }, { v: 'off', l: 'Off' }]} />
        </>} bodyClass="pb-3">
        <div className="relative h-full min-h-[520px] overflow-hidden rounded-xl border border-line bg-[#020305]">
          {E.T && (
            <Canvas
              camera={{ fov: 42, near: 1, far: 9000, position: toV(CENTER.x + 650, CENTER.y - 900, 700).toArray() }}
              dpr={[1, 2]}
              gl={{ antialias: true, alpha: true, powerPreference: 'default' }}
              onCreated={({ gl }) => {
                gl.domElement.addEventListener('webglcontextlost', e => e.preventDefault(), false);
              }}
              onPointerMissed={() => select(null)}>
              <color attach="background" args={['#020305']} />
              <fog attach="fog" args={['#020305', 1400, 3200]} />
              <Terrain /><LidarCloud /><Corridor />{routes && <Routes />}<Swarm labels={labels} />
              <OrbitControls makeDefault enableDamping maxPolarAngle={Math.PI * 0.49} minDistance={20} maxDistance={3200} />
              <Rig mode={mode} follow={follow} />
            </Canvas>
          )}
          <div className="pointer-events-none absolute top-3 left-3 flex flex-col gap-1 text-[11px] text-muted">
            <span className="flex items-center gap-2"><i className="h-1.5 w-1.5 rounded-full bg-white/40" />terrain returns (pre-disaster DEM)</span>
            <span className="flex items-center gap-2"><i className="h-1.5 w-1.5 rounded-full bg-[#c8fff2]" />measured debris surface ({E.S.cloud ? E.S.cloud.n.toLocaleString() : 0} pts)</span>
            {routes && <span className="flex items-center gap-2"><i className="h-px w-3 bg-scout" />planned Scout passes</span>}
            {routes && <span className="flex items-center gap-2"><i className="h-px w-3 bg-alive" />ground-team route, living first</span>}
          </div>
          {mode === 'follow' && follow && <div className="num pointer-events-none absolute bottom-3 left-3 rounded-md bg-black/60 px-2 py-1 text-[11px] text-fg">following {short(follow)}</div>}
        </div>
      </Panel>
      <div className="flex flex-col gap-3">
        <Panel title={s ? short(sel!) + ' · ' + role(sel!) : p ? p.id : 'Selection'} sub={s ? activity(sel!, s) : p ? 'person' : 'click a drone or a pin'}>
          {s ? (
            <dl className="num grid grid-cols-2 gap-y-2 text-[12px]">
              <dt className="text-muted">height AGL</dt><dd className="text-right text-fg">{s.agl.toFixed(1)} m</dd>
              <dt className="text-muted">altitude</dt><dd className="text-right text-fg">{s.z.toFixed(1)} m</dd>
              <dt className="text-muted">speed</dt><dd className="text-right text-fg">{s.speed.toFixed(1)} m/s</dd>
              <dt className="text-muted">tilt</dt><dd className="text-right text-fg">{s.tilt.toFixed(1)}°</dd>
              <dt className="text-muted">battery</dt><dd className="text-right text-fg">{Math.round(s.battery * 100)}%</dd>
              <dt className="text-muted">hops to camp</dt><dd className="text-right text-fg">{s.hops}</dd>
              <dt className="text-muted">task</dt><dd className="text-right text-fg">{s.sector_id || '—'} {s.n_waypoints ? `${s.waypoint_index}/${s.n_waypoints}` : ''}</dd>
            </dl>
          ) : p ? (
            <div className="space-y-2 text-[12px]">
              <Chip color={COND_C[p.condition]}>{p.condition.replace('_', ' ').toLowerCase()}</Chip> <FixChip p={p} />
              <div className="num text-muted">{p.lat.toFixed(6)} N, {p.lon.toFixed(6)} E</div>
              {p.max_temp_k > 0 && <div className="num text-muted">peak {(p.max_temp_k - 273.15).toFixed(1)} °C · {p.n} sightings</div>}
            </div>
          ) : <p className="text-[13px] text-faint">Drag to orbit, scroll to zoom, right-drag to pan. Follow rides with the selected drone.</p>}
        </Panel>
        <Panel title="Altitude layers" sub="Scouts never share a height" className="flex-1">
          <AglBars />
        </Panel>
      </div>
    </div>
    </div>
  );
}

function AglBars() {
  useEngine('fleet');
  const F = Object.entries(E.S.fleet).filter(([n, s]) => !E.isLost(n, s));
  const max = Math.max(100, ...F.map(([, s]) => s.agl));
  return (
    <div className="flex h-full min-h-40 items-end gap-2">
      {F.map(([n, s]) => (
        <div key={n} className="flex flex-1 flex-col items-center gap-1">
          <span className="num text-[10px] text-muted">{Math.round(s.agl)}</span>
          <div className="w-full rounded-t" style={{ height: Math.max(2, (s.agl / max) * 150), background: ROLE_C[role(n)], opacity: 0.75 }} />
          <span className="num text-[10px] text-faint">{short(n)}</span>
        </div>
      ))}
    </div>
  );
}
