import { useEffect, useRef } from 'react';
import { E } from './engine';

/** A DPR-correct canvas redrawn every animation frame while visible. draw(g, w, h, k, now) in device pixels. */
export function useCanvas(draw: (g: CanvasRenderingContext2D, w: number, h: number, k: number, now: number) => void, fps = 60) {
  const ref = useRef<HTMLCanvasElement>(null);
  const fn = useRef(draw); fn.current = draw;
  useEffect(() => {
    const c = ref.current!; const g = c.getContext('2d')!;
    let raf = 0, last = 0, vis = true;
    const io = new IntersectionObserver(e => { vis = e[0].isIntersecting; });
    io.observe(c);
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (!vis || now - last < 1000 / fps - 2) return;
      last = now;
      const k = devicePixelRatio || 1, r = c.getBoundingClientRect();
      const w = Math.max(1, Math.round(r.width * k)), h = Math.max(1, Math.round(r.height * k));
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
      try { fn.current(g, w, h, k, now); } catch (err) { console.error(err); }
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); io.disconnect(); };
  }, [fps]);
  return ref;
}

/** Pan/zoom view over the valley's ENU metres (x east, y north). */
export class MapView {
  v: { x: number; y: number; z: number };
  home: { x: number; y: number; z: number };
  w = 1; h = 1;
  private drag: number[] | null = null;
  constructor(home = { x: -200, y: -760, z: 1.9 }) { this.home = { ...home }; this.v = { ...home }; }
  scale() { const V = E.V; return V ? Math.min(this.w / (V.x1 - V.x0), this.h / (V.y1 - V.y0)) * this.v.z : 1; }
  P(x: number, y: number): [number, number] { const s = this.scale(); return [this.w / 2 + (x - this.v.x) * s, this.h / 2 - (y - this.v.y) * s]; }
  inv(px: number, py: number): [number, number] { const s = this.scale(); return [this.v.x + (px - this.w / 2) / s, this.v.y - (py - this.h / 2) / s]; }
  reset() { this.v = { ...this.home }; }
  attach(c: HTMLCanvasElement) {
    const k = () => devicePixelRatio || 1;
    const down = (e: PointerEvent) => { this.drag = [e.clientX, e.clientY, this.v.x, this.v.y]; c.setPointerCapture(e.pointerId); };
    const move = (e: PointerEvent) => {
      if (!this.drag) return; const s = this.scale() / k();
      this.v.x = this.drag[2] - (e.clientX - this.drag[0]) / s; this.v.y = this.drag[3] + (e.clientY - this.drag[1]) / s;
    };
    const up = () => { this.drag = null; };
    const wheel = (e: WheelEvent) => {
      e.preventDefault(); const r = c.getBoundingClientRect(), mx = (e.clientX - r.left) * k(), my = (e.clientY - r.top) * k();
      const [wx, wy] = this.inv(mx, my);
      this.v.z = Math.min(20, Math.max(0.6, this.v.z * Math.exp(-e.deltaY * 0.0015)));
      const s1 = this.scale(); this.v.x = wx - (mx - this.w / 2) / s1; this.v.y = wy + (my - this.h / 2) / s1;
    };
    const dbl = () => this.reset();
    c.addEventListener('pointerdown', down); c.addEventListener('pointermove', move); c.addEventListener('pointerup', up);
    c.addEventListener('wheel', wheel, { passive: false }); c.addEventListener('dblclick', dbl);
    return () => { c.removeEventListener('pointerdown', down); c.removeEventListener('pointermove', move); c.removeEventListener('pointerup', up); c.removeEventListener('wheel', wheel); c.removeEventListener('dblclick', dbl); };
  }
}

/** Monochrome hillshade of the pre-disaster terrain grid (terrain.json), built once: the lidar-relief base layer. */
let relief: HTMLCanvasElement | null = null;
export function terrainRelief() {
  if (relief || !E.T) return relief;
  const T = E.T, up = 4, W = T.w * up, H = T.h * up;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d')!, im = g.createImageData(W, H);
  let zmin = 1e9, zmax = -1e9; for (const z of T.z) { if (z < zmin) zmin = z; if (z > zmax) zmax = z; }
  const at = (x: number, y: number) => E.ground(T.x0 + x * T.res / up, T.y0 + y * T.res / up);
  for (let i = 0; i < H; i++) for (let j = 0; j < W; j++) {
    const y = H - 1 - i, z = at(j, y), dzx = at(j + 1, y) - at(j - 1, y), dzy = at(j, y + 1) - at(j, y - 1);
    const shade = Math.max(0, Math.min(1, 0.55 + (-dzx * 0.6 + dzy * 0.6) / (2 * T.res / up) * 0.35));
    const hgt = (z - zmin) / (zmax - zmin);
    const contour = Math.abs(((z / 20) % 1 + 1) % 1 - 0.5) > 0.47 ? 0.16 : 0;    // 20 m contours
    const v = Math.round(255 * Math.min(1, 0.05 + 0.16 * shade + 0.07 * hgt + contour));
    const o = (i * W + j) * 4; im.data[o] = v; im.data[o + 1] = v + 2; im.data[o + 2] = v + 5; im.data[o + 3] = 255;
  }
  g.putImageData(im, 0, 0); relief = c; return c;
}
