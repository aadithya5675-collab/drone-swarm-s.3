import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer, OrbitControls, Html, Line } from '@react-three/drei';
import * as THREE from 'three';
import { DroneModel } from './DroneModel';
import type { RoleName } from './parts';
import { reducedMotion } from '../lib/store';

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const NODES: Record<string, { p: THREE.Vector3; role?: RoleName; label: string }> = {
  s1: { p: V(-6.2, 1.4, 1.2), role: 'scout', label: 'Scout · person found' },
  s2: { p: V(-5.2, 1.6, -1.8), role: 'scout', label: 'Scout' },
  m1: { p: V(-3.4, 2.6, 0.4), role: 'mapper', label: 'Mapper' },
  r1: { p: V(-0.6, 4.2, -0.4), role: 'relay', label: 'Relay-Anchor' },
  tw: { p: V(3.6, 3.3, 0), label: 'Camp tower' },
  base: { p: V(5.4, 0.6, 1.4), label: 'Rescue base' }
};
const ROUTES: string[][] = [['s1', 'r1', 'tw', 'base'], ['s2', 'm1', 'r1', 'tw', 'base'], ['m1', 'r1', 'tw', 'base']];

function Packet({ route, delay, color }: { route: string[]; delay: number; color: string }) {
  const m = useRef<THREE.Mesh>(null);
  const pts = route.map(n => NODES[n].p);
  const lens = pts.slice(1).map((p, i) => p.distanceTo(pts[i])), total = lens.reduce((a, b) => a + b, 0);
  useFrame(({ clock }) => {
    if (!m.current) return;
    let d = ((clock.elapsedTime * 2.4 + delay) % (total + 3));
    if (d > total) { m.current.visible = false; return; }
    m.current.visible = true;
    for (let i = 0; i < lens.length; i++) { if (d <= lens[i]) { m.current.position.lerpVectors(pts[i], pts[i + 1], d / lens[i]); return; } d -= lens[i]; }
  });
  return <mesh ref={m}><sphereGeometry args={[0.09, 12, 12]} /><meshBasicMaterial color={color} /></mesh>;
}

function Ground() {
  const geo = useMemo(() => {
    const pos: number[] = [];
    for (let x = -9; x <= 8; x += 0.25) for (let z = -5; z <= 5; z += 0.25) {
      const h = x < 1 ? 0.35 * Math.sin(x * 0.7) * Math.cos(z * 0.9) + 0.25 * Math.sin(z * 1.7 + x) : 0;
      pos.push(x + (Math.random() - 0.5) * 0.1, h, z + (Math.random() - 0.5) * 0.1);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); return g;
  }, []);
  return <points geometry={geo}><pointsMaterial size={0.035} color="#9aa4b2" transparent opacity={0.55} /></points>;
}

function CampProps() {
  return (
    <group>
      {[[4.6, 1.8], [6.2, 0.2], [5.0, -1.4], [6.6, -2.2]].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.35, z]} rotation={[0, i * 0.6, 0]}><coneGeometry args={[0.55, 0.7, 4]} /><meshStandardMaterial color="#cbd5e1" roughness={0.8} /></mesh>
      ))}
      <mesh position={[3.6, 1.6, 0]}><cylinderGeometry args={[0.05, 0.12, 3.2, 8]} /><meshStandardMaterial color="#e2e8f0" metalness={0.5} roughness={0.4} /></mesh>
      <mesh position={[3.6, 3.3, 0]}><sphereGeometry args={[0.16, 16, 16]} /><meshBasicMaterial color="#fb7185" /></mesh>
      <mesh position={[5.4, 0.3, 1.4]}><boxGeometry args={[0.9, 0.6, 0.6]} /><meshStandardMaterial color="#475569" /></mesh>
    </group>
  );
}

export default function CampStage() {
  const still = reducedMotion();
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [-0.2, 5.2, 12.5], fov: 40 }} gl={{ antialias: true, alpha: true }}>
      <Environment resolution={128}><Lightformer intensity={2} position={[0, 5, 3]} scale={[8, 2, 1]} /></Environment>
      <ambientLight intensity={0.4} /><directionalLight position={[3, 6, 3]} intensity={1.2} />
      <Ground /><CampProps />
      {Object.entries(NODES).map(([k, n]) => (
        <group key={k} position={n.p}>
          {n.role && <DroneModel role={n.role} spin={false} scale={0.8} />}
          <Html position={[0, n.role ? 0.5 : 0.35, 0]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
            <div className="rounded bg-black/50 px-1.5 py-0.5 text-[11px] whitespace-nowrap text-white/85">{n.label}</div>
          </Html>
        </group>
      ))}
      {ROUTES.map((r, i) => <Line key={i} points={r.map(n => NODES[n].p)} color="#5eead4" lineWidth={1} transparent opacity={0.35} dashed dashSize={0.25} gapSize={0.18} />)}
      {ROUTES.map((r, i) => [0, 4.5].map(d => <Packet key={i + '-' + d} route={r} delay={d + i * 1.7} color="#fde047" />))}
      <OrbitControls enablePan={false} enableZoom={false} autoRotate={!still} autoRotateSpeed={0.35} maxPolarAngle={Math.PI * 0.45} minPolarAngle={Math.PI * 0.2} target={[-0.3, 1.8, 0]} />
    </Canvas>
  );
}
