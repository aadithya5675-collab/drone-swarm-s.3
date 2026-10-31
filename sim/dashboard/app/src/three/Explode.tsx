import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer, OrbitControls, Html, useGLTF } from '@react-three/drei';
import { motion } from 'motion/react';
import { X } from 'lucide-react';
import * as THREE from 'three';
import { MODEL_URL } from './DroneModel';
import type { RoleName } from './parts';

const GROUPS = [
  { key: 'frame', title: 'Airframe & propulsion', color: '#f4f6fa', re: /airframe|rotor|led_motor|Landing_gear|battery_under|adapter_plate|role_beacon/ },
  { key: 'brain', title: 'Flight, power & compute', color: '#5eead4', re: /SpeedyBee|Jetson|Raspberry|GNSS|LiPo/ },
  { key: 'payload', title: 'Mission payload', color: '#f5b544', re: /Sensor_head|Livox|RFD900|Wi_Fi_LoRa/ }
];
const NAMES: Record<RoleName, string> = { scout: 'Scout', mapper: 'Mapper', relay: 'Relay-Anchor' };

const label = (n: string) => {
  const b = n.replace(/_\d+$/, '').replace(/_visual$/, '');
  const M: [RegExp, string][] = [
    [/airframe/, 'Carbon frame + motors'], [/rotor/, 'Propeller'], [/Landing_gear/, 'Landing gear'], [/adapter_plate/, 'Adapter plate'], [/battery_under/, '4S LiPo battery'],
    [/SpeedyBee/, 'SpeedyBee F405 · PX4 flight controller'], [/Jetson/, 'NVIDIA Jetson Nano · on-board AI'], [/Raspberry/, 'Raspberry Pi Zero 2 W · mesh router'],
    [/GNSS/, 'M10 GNSS + compass'], [/LiPo/, '4S 1550 mAh LiPo'], [/Sensor_head/, 'IMX219 RGB + Lepton 3.5 thermal'], [/Livox/, 'Livox Mid-360 3D lidar'],
    [/RFD900/, 'RFD900x long-range radio'], [/Wi_Fi_LoRa/, 'Wi-Fi / LoRa mesh node']
  ];
  return (M.find(([re]) => re.test(b)) || [null, null])[1];
};

function Exploded({ role }: { role: RoleName }) {
  const { scene } = useGLTF(MODEL_URL[role]);
  const { root, items, labels } = useMemo(() => {
    const src = scene.clone(true); src.updateMatrixWorld(true);
    const root = new THREE.Group(), meshes: THREE.Mesh[] = [];
    src.traverse(o => { if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh); });
    const named = (m: THREE.Mesh) => { let o: THREE.Object3D | null = m; while (o && !GROUPS.some(g => g.re.test(o!.name))) o = o.parent; return o ? o.name : m.name; };
    for (const m of meshes) { m.userData.part = named(m); m.material = (m.material as THREE.Material).clone(); root.attach(m); }
    const box = new THREE.Box3().setFromObject(root), c = box.getCenter(new THREE.Vector3());
    root.children.forEach(o => o.position.sub(c));
    const items = root.children.map(o => {
      const m = o as THREE.Mesh, gi = Math.max(0, GROUPS.findIndex(g => g.re.test(m.userData.part)));
      const ctr = new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3());
      return { m, gi, base: m.position.clone(), ctr, off: new THREE.Vector3() };
    });
    const gc = GROUPS.map((_, gi) => { const s = items.filter(i => i.gi === gi); const v = new THREE.Vector3(); s.forEach(i => v.add(i.ctr)); return s.length ? v.divideScalar(s.length) : v; });
    for (const it of items) {
      const slot = new THREE.Vector3((it.gi - 1) * 0.42, 0, 0);
      const spread = it.ctr.clone().sub(gc[it.gi]).multiplyScalar(0.55);
      it.off = slot.sub(gc[it.gi]).add(spread);
    }
    const seen = new Set<string>(), labels: { text: string; it: (typeof items)[number] }[] = [];
    for (const it of items) { const t = label(it.m.userData.part); if (t && !seen.has(t)) { seen.add(t); labels.push({ text: t, it }); } }
    return { root, items, labels };
  }, [scene]);
  const t = useRef(0), lab = useRef<(THREE.Group | null)[]>([]);
  useFrame((_, dt) => {
    t.current = Math.min(1, t.current + dt * 0.9);
    const k = 1 - Math.pow(1 - t.current, 3);
    for (const it of items) it.m.position.copy(it.base).addScaledVector(it.off, k);
    labels.forEach((l, i) => { const g = lab.current[i]; if (g) g.position.copy(l.it.ctr).addScaledVector(l.it.off, k); });
  });
  return (
    <group scale={4}>
      <primitive object={root} />
      {labels.map((l, i) => (
        <group key={l.text} ref={el => (lab.current[i] = el)}>
          <Html center distanceFactor={3} style={{ pointerEvents: 'none' }}>
            <div className="rounded border px-1.5 py-0.5 text-[10px] whitespace-nowrap backdrop-blur-sm" style={{ borderColor: GROUPS[l.it.gi].color + '55', background: '#000a', color: GROUPS[l.it.gi].color }}>{l.text}</div>
          </Html>
        </group>
      ))}
    </group>
  );
}

export default function Explode({ role, onClose }: { role: RoleName; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    addEventListener('keydown', k); return () => removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="fixed inset-0 z-50 bg-[#05070b]/92 backdrop-blur-md">
      <div className="absolute top-0 inset-x-0 z-10 flex items-center justify-between px-6 py-5">
        <div>
          <div className="eyebrow">How it is built</div>
          <div className="mt-1 text-2xl font-semibold tracking-tight text-hi">{NAMES[role]}</div>
        </div>
        <button onClick={onClose} className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-muted hover:text-hi"><X size={14} />Esc</button>
      </div>
      <div className="absolute inset-x-0 bottom-6 z-10 flex justify-center gap-3 px-6">
        {GROUPS.map(g => <span key={g.key} className="flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-fg"><i className="h-2 w-2 rounded-full" style={{ background: g.color }} />{g.title}</span>)}
      </div>
      <Canvas dpr={[1, 2]} camera={{ position: [0, 1.2, 4.6], fov: 34 }} gl={{ antialias: true, alpha: true, powerPreference: 'default' }}
        onCreated={({ gl }) => {
          gl.domElement.addEventListener('webglcontextlost', e => e.preventDefault(), false);
        }}>
        <Environment resolution={256}>
          <Lightformer intensity={2.2} position={[0, 3, 2]} scale={[6, 1.2, 1]} />
          <Lightformer intensity={0.8} color="#5eead4" position={[-3, 1, -1]} scale={[1, 4, 1]} />
        </Environment>
        <ambientLight intensity={0.3} /><directionalLight position={[2, 4, 3]} intensity={1.3} />
        <Suspense fallback={<Html center><span className="text-xs text-faint">loading…</span></Html>}><Exploded role={role} /></Suspense>
        <OrbitControls enablePan={false} minDistance={2} maxDistance={8} enableDamping />
      </Canvas>
    </motion.div>
  );
}
