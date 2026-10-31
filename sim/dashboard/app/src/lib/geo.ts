/* Shared mission geometry and derived facts (no drawing). */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { E, type Drone } from './engine';

export const corridorEdges = () => {
  const V = E.V, out: number[][][] = [[], []];
  if (!V) return out;
  V.corridor.forEach((p: number[], i: number) => {
    const q = V.corridor[Math.min(i + 1, V.corridor.length - 1)], r = V.corridor[Math.max(i - 1, 0)];
    const tx = q[0] - r[0], ty = q[1] - r[1], n = Math.hypot(tx, ty) || 1;
    out[0].push([p[0] - ty / n * V.half_width, p[1] + tx / n * V.half_width]);
    out[1].push([p[0] + ty / n * V.half_width, p[1] - tx / n * V.half_width]);
  });
  return out;
};

export const isVerify = (t: any) => /^VERIFY/.test(t.id || t.root || '');

export interface SectorRoot { id: string; t: any; status: Set<string>; owners: Set<string>; prog: number; released: boolean; done: boolean }
export const sectorRoots = (): SectorRoot[] => {
  const p = E.S.plan, roots: Record<string, SectorRoot> = {};
  if (!p || !p.tasks) return [];
  for (const t of p.tasks) {
    if (isVerify(t)) continue;
    const r = (roots[t.root] = roots[t.root] || { id: t.root, t, status: new Set(), owners: new Set(), prog: t.root_progress ?? 0, released: false, done: false });
    r.status.add(t.status); if (t.owner && t.status === 'ASSIGNED') r.owners.add(t.owner); if (t.id === t.root) r.t = t;
    if (t.root_progress != null) r.prog = Math.max(r.prog, t.root_progress);
    if (t.released) r.released = true;
  }
  for (const r of Object.values(roots)) r.done = [...r.status].every(s => s === 'DONE' || s === 'ABANDONED') && r.prog >= 0.999;
  return Object.values(roots);
};

export interface Verify { drone: string; person: import('./engine').Person | undefined; id: string; task: any }
export const verifies = (): Verify[] => {
  const S = E.S; if (!S.plan || !S.plan.tasks) return [];
  return S.plan.tasks.filter((t: any) => isVerify(t) && t.status === 'ASSIGNED' && t.owner).map((t: any) => {
    const pid = t.id.replace(/^VERIFY-/, '').replace(/\.\d+$/, '');
    return { drone: t.owner as string, person: S.persons.find(p => p.id === pid), id: pid as string, task: t };
  }).filter((v: any) => v.person && S.fleet[v.drone]);
};

export const nodePos = (n: string): number[] | null => {
  const S = E.S, tr = S.traffic && S.traffic.nodes && S.traffic.nodes[n];
  if (tr) return tr;
  if (n === 'tower' && E.V) return [E.V.tower.x, E.V.tower.y, E.V.tower.z];
  const s = S.fleet[n]; return s ? [s.x, s.y, s.z] : null;
};

/** what the drone is doing, in words a commander reads */
export const activity = (n: string, s: Drone) => {
  if (E.isLost(n, s)) return s.state === 'CRASHED' ? 'lost · ' + (s.why || 'crashed') : 'no contact';
  const st = s.state;
  if (st === 'LANDED' || st === 'IDLE' || st === 'STAGING') return 'on the pad';
  if (st === 'TAKEOFF') return 'taking off';
  if (st === 'RETURNING' || s.sector_id === 'RTB') return 'returning to camp';
  if (/^HOLD-/.test(s.sector_id)) return 'waiting for lidar · ' + s.sector_id.slice(5);
  if (/^MR/.test(s.sector_id)) return 'lidar edge pass ' + s.sector_id;
  if (s.sector_id === 'OVERWATCH') return 'overwatch · ' + Math.round(s.agl) + ' m';
  if (s.sector_id === 'RELAY') return 'mesh anchor · ' + Math.round(s.agl) + ' m';
  if (st === 'HOLDING') return 'holding' + (s.sector_id ? ' · ' + s.sector_id : '');
  if (/^VERIFY/.test(s.sector_id)) return 'thermal re-check';
  if (/^M/.test(s.sector_id)) return 'lidar pass ' + s.sector_id;
  return (st === 'SEARCHING' ? 'sweeping ' : st.toLowerCase() + ' ') + (s.sector_id || '') + ' · ' + Math.round(s.agl) + ' m AGL';
};

export const fmtLL = (lat: number, lon: number) => lat.toFixed(6) + ' N, ' + lon.toFixed(6) + ' E';
