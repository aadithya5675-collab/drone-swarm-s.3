import { useEffect, useMemo, useState } from 'react';
import { Crosshair, Layers } from 'lucide-react';
import { E, COND_C, ROLE_C, KIND_C, role, short } from '../lib/engine';
import { MapView, terrainRelief, useCanvas } from '../lib/canvas';
import { corridorEdges, sectorRoots, verifies, nodePos } from '../lib/geo';
import { useUI } from '../lib/store';
import { Button, Tip, cn } from './ui';

type Layer = 'lidar' | 'search' | 'mesh' | 'trails';

export default function TacticalMap({ className, compact }: { className?: string; compact?: boolean }) {
  const mv = useMemo(() => new MapView({ x: -245, y: -860, z: compact ? 2.6 : 3.1 }), [compact]);
  const [layers, setLayers] = useState<Record<Layer, boolean>>({ lidar: true, search: !compact, mesh: true, trails: true });
  const [hover, setHover] = useState<string | null>(null);
  const L = layers;

  const ref = useCanvas((g, w, h, k, now) => {
    mv.w = w; mv.h = h;
    g.fillStyle = '#0a0c10'; g.fillRect(0, 0, w, h);
    const V = E.V, T = E.T, S = E.S; if (!V || !T) return;
    const font = (px: number, wgt = 500) => `${wgt} ${px * k}px "Geist Variable", system-ui`;
    const mono = (px: number) => `500 ${px * k}px "JetBrains Mono Variable", monospace`;
    // relief (pre-disaster DEM, monochrome)
    const rel = terrainRelief();
    if (rel) { const a = mv.P(T.x0, T.y0 + T.h * T.res), b = mv.P(T.x0 + T.w * T.res, T.y0); g.globalAlpha = 0.95; g.drawImage(rel, a[0], a[1], b[0] - a[0], b[1] - a[1]); g.globalAlpha = 1; }
    // measured lidar surface (live): brighter, still monochrome
    if (L.lidar && S.mapImg && S.map) {
      const d = S.map, a = mv.P(d.x0, d.y0 + d.h * d.res), b = mv.P(d.x0 + d.w * d.res, d.y0);
      g.save(); g.filter = 'grayscale(1) brightness(1.55) contrast(1.15)'; g.globalAlpha = 0.85; g.drawImage(S.mapImg, a[0], a[1], b[0] - a[0], b[1] - a[1]); g.restore();
    }
    if (L.search && S.searchImg && S.search) {
      const d = S.search, a = mv.P(d.x0, d.y0 + d.h * d.res), b = mv.P(d.x0 + d.w * d.res, d.y0);
      g.save(); g.globalCompositeOperation = 'screen'; g.globalAlpha = 0.32; g.imageSmoothingEnabled = true; g.drawImage(S.searchImg, a[0], a[1], b[0] - a[0], b[1] - a[1]); g.restore();
    }
    // river + corridor
    g.strokeStyle = 'rgba(125,211,252,.22)'; g.lineWidth = 1.5 * k; g.beginPath();
    V.river.forEach((p: number[], i: number) => { const q = mv.P(p[0], p[1]); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.stroke();
    g.setLineDash([4 * k, 5 * k]); g.strokeStyle = 'rgba(255,255,255,.22)'; g.lineWidth = 1 * k;
    for (const edge of corridorEdges()) { g.beginPath(); edge.forEach((p, i) => { const q = mv.P(p[0], p[1]); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.stroke(); }
    g.setLineDash([]);
    // sectors
    const mass = (S.plan && S.plan.sector_mass) || {};
    for (const r of sectorRoots()) {
      const t = r.t; if (!t.geom || t.role !== 'scout') continue;
      const [A, B, hw] = t.geom, dx = B[0] - A[0], dy = B[1] - A[1], Ln = Math.hypot(dx, dy) || 1, nx = -dy / Ln * hw, ny = dx / Ln * hw;
      const poly = [mv.P(A[0] + nx, A[1] + ny), mv.P(B[0] + nx, B[1] + ny), mv.P(B[0] - nx, B[1] - ny), mv.P(A[0] - nx, A[1] - ny)];
      const col = r.done ? '74,222,128' : r.released ? '94,234,212' : '231,234,240';
      g.fillStyle = `rgba(${col},${r.done ? 0.06 : r.released ? 0.05 : 0.02})`; g.strokeStyle = `rgba(${col},${r.released || r.done ? 0.7 : 0.3})`;
      g.lineWidth = 1.2 * k; g.setLineDash(r.released || r.done ? [] : [3 * k, 4 * k]);
      g.beginPath(); poly.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.fill(); g.stroke(); g.setLineDash([]);
      if (!compact || mv.v.z > 1.5) {
        const c = mv.P(A[0] + dx * 0.5 + nx * 1.04, A[1] + dy * 0.5 + ny * 1.04);
        const lbl = r.id + '  ' + (r.done ? 'swept' : r.released ? Math.round(100 * r.prog) + '%' : 'awaiting lidar') + (mass[r.id] != null ? '  p ' + Math.round(100 * mass[r.id]) + '%' : '');
        g.font = mono(10.5); g.fillStyle = `rgba(${col},.9)`; g.fillText(lbl, c[0] + 4 * k, c[1]);
      }
    }
    // trails
    if (L.trails) for (const [n, tr] of Object.entries(S.trails)) {
      if (tr.length < 2) continue; g.strokeStyle = ROLE_C[role(n)] + '40'; g.lineWidth = 1 * k; g.beginPath();
      tr.forEach((p, i) => { const q = mv.P(p[0], p[1]); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.stroke();
    }
    // mesh links + frames in flight
    if (L.mesh && S.traffic) {
      for (const [a, b, q, , up] of S.traffic.links) {
        if (!up) continue; const A = nodePos(a), B = nodePos(b); if (!A || !B) continue;
        const pa = mv.P(A[0], A[1]), pb = mv.P(B[0], B[1]);
        g.strokeStyle = `rgba(94,234,212,${0.08 + 0.4 * q})`; g.lineWidth = (0.6 + 1.2 * q) * k; g.beginPath(); g.moveTo(pa[0], pa[1]); g.lineTo(pb[0], pb[1]); g.stroke();
      }
      for (const p of S.packets) {
        const u = (now - p.t0) / p.dur; if (u < 0 || u > 1) continue; const A = nodePos(p.a), B = nodePos(p.b); if (!A || !B) continue;
        const q = mv.P(A[0] + (B[0] - A[0]) * u, A[1] + (B[1] - A[1]) * u);
        g.fillStyle = KIND_C[p.k] || '#fff'; g.beginPath(); g.arc(q[0], q[1], 1.8 * k, 0, 7); g.fill();
      }
      if (S.packets.length > 600) S.packets = S.packets.filter(p => now - p.t0 < p.dur);
    }
    // re-checks in flight
    for (const v of verifies()) {
      const s = S.fleet[v.drone], A = mv.P(s.x, s.y), B = mv.P(v.person!.x, v.person!.y);
      g.strokeStyle = '#f0abfc'; g.lineWidth = 1.6 * k; g.setLineDash([5 * k, 4 * k]); g.lineDashOffset = -(now / 40) * k;
      g.beginPath(); g.moveTo(A[0], A[1]); g.lineTo(B[0], B[1]); g.stroke(); g.setLineDash([]); g.lineDashOffset = 0;
    }
    // camp
    const tw = mv.P(V.tower.x, V.tower.y);
    g.fillStyle = '#fb7185'; g.beginPath(); g.moveTo(tw[0], tw[1] - 8 * k); g.lineTo(tw[0] - 6 * k, tw[1] + 5 * k); g.lineTo(tw[0] + 6 * k, tw[1] + 5 * k); g.fill();
    g.font = font(11, 600); g.fillStyle = 'rgba(244,246,250,.85)'; g.fillText('Camp', tw[0] + 9 * k, tw[1] + 4 * k);
    for (const [nm, xy] of [['Mundakkai', V.mundakkai], ['Chooralmala', V.chooralmala]] as [string, number[]][]) {
      const q = mv.P(xy[0], xy[1]); g.font = font(12, 400); g.fillStyle = 'rgba(244,246,250,.5)'; g.fillText(nm, q[0], q[1]);
    }
    // people
    const sel = useUI.getState().person;
    for (const p of S.persons) {
      const q = mv.P(p.x, p.y), c = p.rechecked && p.condition === 'UNKNOWN' ? '#52525b' : COND_C[p.condition];
      if (p.id === sel || p.id === hover) { g.strokeStyle = c; g.lineWidth = 1.5 * k; g.beginPath(); g.arc(q[0], q[1], 13 * k, 0, 7); g.stroke(); }
      g.fillStyle = c + '30'; g.beginPath(); g.arc(q[0], q[1], 8 * k, 0, 7); g.fill();
      g.fillStyle = c; g.strokeStyle = '#04060a'; g.lineWidth = 2 * k; g.beginPath(); g.arc(q[0], q[1], 4.2 * k, 0, 7); g.fill(); g.stroke();
      if (!compact || mv.v.z > 2.4) { g.font = mono(10); g.fillStyle = c; g.fillText(p.id.replace('PERSON-', 'P'), q[0] + 8 * k, q[1] - 6 * k); }
    }
    for (let i = S.pings.length - 1; i >= 0; i--) {
      const p = S.pings[i], u = (now - p.t) / 2200; if (u > 3) { S.pings.splice(i, 1); continue; }
      const q = mv.P(p.x, p.y), f = u % 1; g.strokeStyle = p.c; g.globalAlpha = 1 - f; g.lineWidth = 1.5 * k;
      g.beginPath(); g.arc(q[0], q[1], (6 + 34 * f) * k, 0, 7); g.stroke(); g.globalAlpha = 1;
    }
    // drones
    const selD = useUI.getState().sel;
    for (const [n, s] of Object.entries(S.fleet)) {
      const q = mv.P(s.x, s.y), lost = E.isLost(n, s), c = lost ? '#71717a' : ROLE_C[role(n)];
      if (n === selD || n === hover) { g.strokeStyle = c; g.lineWidth = 1.2 * k; g.beginPath(); g.arc(q[0], q[1], 12 * k, 0, 7); g.stroke(); }
      if (lost) { g.strokeStyle = c; g.lineWidth = 2 * k; const r = 4.5 * k; g.beginPath(); g.moveTo(q[0] - r, q[1] - r); g.lineTo(q[0] + r, q[1] + r); g.moveTo(q[0] + r, q[1] - r); g.lineTo(q[0] - r, q[1] + r); g.stroke(); }
      else { g.fillStyle = c; g.beginPath(); g.moveTo(q[0], q[1] - 6 * k); g.lineTo(q[0] + 5 * k, q[1] + 4 * k); g.lineTo(q[0], q[1] + 2 * k); g.lineTo(q[0] - 5 * k, q[1] + 4 * k); g.closePath(); g.fill(); }
      g.font = mono(10.5); g.fillStyle = lost ? '#71717a' : 'rgba(244,246,250,.92)'; g.fillText(short(n), q[0] + 8 * k, q[1] + 4 * k);
    }
    // scale bar
    const s = mv.scale(), m = [50, 100, 200, 500, 1000].find(x => x * s > 70 * k) || 1000, x0 = 14 * k, y0 = h - 14 * k;
    g.strokeStyle = 'rgba(244,246,250,.6)'; g.lineWidth = 1 * k; g.beginPath(); g.moveTo(x0, y0 - 4 * k); g.lineTo(x0, y0); g.lineTo(x0 + m * s, y0); g.lineTo(x0 + m * s, y0 - 4 * k); g.stroke();
    g.font = mono(10); g.fillStyle = 'rgba(244,246,250,.6)'; g.fillText(m + ' m', x0 + m * s + 6 * k, y0);
  });

  useEffect(() => {
    const c = ref.current!; const off = mv.attach(c);
    const hit = (e: MouseEvent) => {
      const r = c.getBoundingClientRect(), k = devicePixelRatio || 1, px = (e.clientX - r.left) * k, py = (e.clientY - r.top) * k;
      let best: [string, number] | null = null;
      for (const p of E.S.persons) { const q = mv.P(p.x, p.y), d = Math.hypot(q[0] - px, q[1] - py); if (d < 14 * k && (!best || d < best[1])) best = [p.id, d]; }
      for (const [n, s] of Object.entries(E.S.fleet)) { const q = mv.P(s.x, s.y), d = Math.hypot(q[0] - px, q[1] - py); if (d < 12 * k && (!best || d < best[1])) best = [n, d]; }
      return best ? best[0] : null;
    };
    const mm = (e: MouseEvent) => { const h = hit(e); setHover(h); c.style.cursor = h ? 'pointer' : 'grab'; };
    const click = (e: MouseEvent) => { const h = hit(e); if (!h) return; if (h.startsWith('PERSON')) useUI.getState().pickPerson(h); else useUI.getState().select(h); };
    c.addEventListener('mousemove', mm); c.addEventListener('click', click);
    return () => { off(); c.removeEventListener('mousemove', mm); c.removeEventListener('click', click); };
  }, [mv, ref]);

  // fly to a picked person
  const person = useUI(s => s.person);
  useEffect(() => { const p = E.S.persons.find(q => q.id === person); if (p) { mv.v.x = p.x; mv.v.y = p.y; mv.v.z = Math.max(mv.v.z, 4); } }, [person, mv]);

  const toggle = (l: Layer) => setLayers(s => ({ ...s, [l]: !s[l] }));
  return (
    <div className={cn('relative h-full min-h-64 overflow-hidden rounded-xl border border-line bg-black', className)}>
      <canvas ref={ref} className="absolute inset-0 h-full w-full touch-none" aria-label="Tactical map of the Mundakkai debris corridor" />
      <div className="absolute top-2.5 right-2.5 flex items-center gap-1 rounded-lg border border-line bg-black/50 p-0.5 backdrop-blur-md">
        <Layers size={13} className="mx-1.5 text-faint" />
        {(['lidar', 'search', 'mesh', 'trails'] as Layer[]).map(l => (
          <button key={l} onClick={() => toggle(l)} className={cn('h-6 rounded-md px-2 text-[11px] font-medium capitalize', L[l] ? 'bg-white/10 text-fg' : 'text-faint hover:text-fg')}>{l === 'search' ? 'probability' : l}</button>
        ))}
        <Tip content="Reset view (or double-click the map)"><Button className="h-6 px-1.5" onClick={() => mv.reset()} aria-label="Reset view"><Crosshair size={13} /></Button></Tip>
      </div>
      <div className="pointer-events-none absolute bottom-2.5 right-3 flex gap-3 text-[11px] text-muted">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: COND_C.ALIVE }} />alive</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: COND_C.DECEASED_SUSPECTED }} />likely deceased</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: COND_C.UNKNOWN }} />candidate</span>
      </div>
    </div>
  );
}
