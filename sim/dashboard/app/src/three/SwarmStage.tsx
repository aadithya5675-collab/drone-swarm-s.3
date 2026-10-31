import { useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Environment, Lightformer, PresentationControls, Html } from '@react-three/drei';
import type { MotionValue } from 'motion/react';
import * as THREE from 'three';
import { E } from '../lib/engine';
import { DroneModel } from './DroneModel';
import type { RoleName } from './parts';

const FORMATION: { role: RoleName; label: string; p: [number, number, number] }[] = [
  { role: 'relay', label: 'Relay-Anchor', p: [0, 2.3, -2.3] },
  { role: 'mapper', label: 'Mapper 1', p: [-1.1, 1.9, -0.7] },
  { role: 'mapper', label: 'Mapper 2', p: [1.1, 1.9, -0.7] },
  { role: 'scout', label: 'Scout 1', p: [-0.85, 1.5, 0.9] },
  { role: 'scout', label: 'Scout 2', p: [0.85, 1.5, 0.9] },
  { role: 'scout', label: 'Reserve Scout', p: [-2.55, 1.5, 0.9] },
  { role: 'scout', label: 'Reserve Scout', p: [2.55, 1.5, 0.9] }
];
const appearAt = (k: number) => 0.16 + k * 0.065;
const ease = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x));

function TerrainPoints() {
  const geo = useMemo(() => {
    const T = E.T, pos: number[] = [], col: number[] = [];
    if (!T) return new THREE.BufferGeometry();
    let zmin = 1e9, zmax = -1e9;
    for (const z of T.z) { zmin = Math.min(zmin, z); zmax = Math.max(zmax, z); }
    const cx = -165, cy = -720, s = 1 / 85;
    for (let i = 0; i < T.h; i++) for (let j = 0; j < T.w; j++) {
      const x = T.x0 + j * T.res, y = T.y0 + i * T.res, z = T.z[i * T.w + j];
      pos.push((x - cx) * s, (z - zmin) * s * 1.3 - 2.4, -(y - cy) * s);
      const u = 0.18 + 0.6 * (z - zmin) / (zmax - zmin);
      col.push(u * 0.86, u * 0.93, u);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    return g;
  }, []);
  return <points geometry={geo}><pointsMaterial size={0.035} vertexColors transparent opacity={0.85} sizeAttenuation /></points>;
}

function Rig({ progress }: { progress: MotionValue<number> }) {
  const { camera, size } = useThree();
  const from = useMemo(() => ({ p: new THREE.Vector3(0, 11, 17), t: new THREE.Vector3(0, -0.5, -1) }), []);
  const to = useMemo(() => ({ p: new THREE.Vector3(0, 3.6, 7.6), t: new THREE.Vector3(0, 1.3, -0.3) }), []);
  const tgt = useRef(new THREE.Vector3());
  useFrame(() => {
    const k = ease(progress.get() / 0.65);
    tgt.current.lerpVectors(from.t, to.t, k);
    camera.position.lerpVectors(from.p, to.p, k).sub(tgt.current).multiplyScalar(Math.max(1, 1.75 / (size.width / size.height))).add(tgt.current);
    camera.lookAt(tgt.current);
  });
  return null;
}

function Member({ m, k, progress, onExplode, hovered }: { m: (typeof FORMATION)[number]; k: number; progress: MotionValue<number>; onExplode: (r: RoleName) => void; hovered: React.MutableRefObject<RoleName | null> }) {
  const g = useRef<THREE.Group>(null);
  const [shown, setShown] = useState(false);
  const [hot, setHot] = useState(false);
  const lastDown = useRef(0);
  const down = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    const now = performance.now();
    if (now - lastDown.current < 380) { lastDown.current = 0; onExplode(m.role); } else lastDown.current = now;
  };
  useFrame((_, dt) => {
    if (!g.current) return;
    const want = progress.get() > appearAt(k) ? 1 : 0, s = g.current.scale.x;
    const n = s + (want - s) * Math.min(1, dt * 6);
    g.current.scale.setScalar(Math.max(0.0001, n));
    g.current.position.y = m.p[1] + Math.sin(performance.now() / 900 + k) * 0.04;
    if ((n > 0.6) !== shown) setShown(n > 0.6);
  });
  return (
    <group ref={g} position={m.p} scale={0.0001}
      onPointerDown={down}
      onPointerOver={e => { e.stopPropagation(); setHot(true); hovered.current = m.role; document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { setHot(false); if (hovered.current === m.role) hovered.current = null; document.body.style.cursor = ''; }}>
      <DroneModel role={m.role} spin={false} scale={0.85} />
      {shown && <Html position={[0, -0.55, 0]} center distanceFactor={9}>
        <button onDoubleClick={e => { e.stopPropagation(); onExplode(m.role); }} onMouseEnter={() => setHot(true)} onMouseLeave={() => setHot(false)} title="double-click to see how it is built"
          className={'rounded-md px-2 py-0.5 text-[12px] whitespace-nowrap backdrop-blur-sm transition-colors ' + (hot ? 'bg-accent/25 text-hi' : 'bg-black/45 text-white/80')}>{m.label}</button>
      </Html>}
    </group>
  );
}

export default function SwarmStage({ progress, onExplode }: { progress: MotionValue<number>; onExplode: (r: RoleName) => void }) {
  const hovered = useRef<RoleName | null>(null);
  return (
    <div className="h-full w-full" onDoubleClick={() => { if (hovered.current) onExplode(hovered.current); }}>
    <Canvas dpr={[1, 2]} camera={{ position: [0, 11, 17], fov: 38, near: 0.05, far: 200 }} gl={{ antialias: true, alpha: true }}
      raycaster={{ params: { Points: { threshold: 0.02 }, Line: { threshold: 0.02 } } as never }}>
      <fog attach="fog" args={['#06080c', 14, 34]} />
      <Environment resolution={256}>
        <Lightformer intensity={2.2} position={[0, 4, 3]} scale={[8, 1.5, 1]} />
        <Lightformer intensity={0.8} color="#5eead4" position={[-4, 1, -1]} scale={[1, 5, 1]} />
        <Lightformer intensity={0.6} color="#f5b544" position={[4, 0.5, -2]} scale={[1, 4, 1]} />
      </Environment>
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 6, 4]} intensity={1.3} />
      <Rig progress={progress} />
      <PresentationControls polar={[-0.25, 0.35]} azimuth={[-Infinity, Infinity]} speed={1.4}>
        <group>
          <TerrainPoints />
          {FORMATION.map((m, k) => <Member key={k} m={m} k={k} progress={progress} onExplode={onExplode} hovered={hovered} />)}
        </group>
      </PresentationControls>
    </Canvas>
    </div>
  );
}
