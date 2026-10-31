/* The simulated drones as three.js models: GLBs exported from the exact Gazebo model.sdf files
   (sim/tools/export_web_models.py), so what the judges turn around here is what flies in the simulation. */
import { useMemo, useRef, useEffect } from 'react';
import { useFrame, type ThreeEvent } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

import type { RoleName } from './parts';
export type { RoleName } from './parts';
export const MODEL_URL: Record<RoleName, string> = { scout: 'models/scout.glb', mapper: 'models/mapper.glb', relay: 'models/relay.glb' };

export function DroneModel({ role, spin = true, hover, onHover, scale = 1, ghost, ...rest }: {
  role: RoleName; spin?: boolean; hover?: string | null; onHover?: (name: string | null) => void; scale?: number; ghost?: boolean
} & JSX.IntrinsicElements['group']) {
  const { scene } = useGLTF(MODEL_URL[role]);
  const root = useMemo(() => {
    const s = scene.clone(true);
    s.traverse(o => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.material = (m.material as THREE.MeshStandardMaterial).clone();
        const mat = m.material as THREE.MeshStandardMaterial;
        mat.envMapIntensity = 1.1;
        if (ghost) { mat.transparent = true; mat.opacity = 0.9; }
        m.castShadow = true;
        m.userData.base = mat.emissive.clone(); m.userData.baseI = mat.emissiveIntensity;
      }
    });
    return s;
  }, [scene, ghost]);
  // centre on the airframe, 1 unit ~ 0.25 m
  const offset = useMemo(() => { const b = new THREE.Box3().setFromObject(root), c = b.getCenter(new THREE.Vector3()); return [-c.x, -c.y, -c.z] as [number, number, number]; }, [root]);
  const rotors = useMemo(() => { const r: THREE.Object3D[] = []; root.traverse(o => { if (/^rotor_\d_visual/.test(o.name)) r.push(o); }); return r; }, [root]);
  const g = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (spin && g.current) g.current.rotation.y += dt * 0.25;
    for (const r of rotors) r.rotateZ(dt * 40);          // node frames keep the SDF's Z-up axes
  });
  useEffect(() => {
    root.traverse(o => {
      const m = o as THREE.Mesh; if (!m.isMesh) return;
      const mat = m.material as THREE.MeshStandardMaterial;
      if (hover && m.name === hover) { mat.emissive.set('#5eead4'); mat.emissiveIntensity = 0.6; }
      else { mat.emissive.copy(m.userData.base); mat.emissiveIntensity = m.userData.baseI; }
    });
  }, [hover, root]);
  const over = (e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover?.(e.object.name); };
  return (
    <group ref={g} {...rest} scale={4 * scale}>
      <primitive object={root} position={offset} onPointerOver={onHover ? over : undefined} onPointerOut={onHover ? () => onHover(null) : undefined} />
    </group>
  );
}

Object.values(MODEL_URL).forEach(u => useGLTF.preload(u));
