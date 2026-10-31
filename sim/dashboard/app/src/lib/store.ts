import { useSyncExternalStore } from 'react';
import { create } from 'zustand';
import { E } from './engine';

const subs = new Map<string, (cb: () => void) => () => void>();
export function useEngine(...keys: string[]) {
  const id = keys.join('|');
  let sub = subs.get(id);
  if (!sub) {
    sub = cb => E.subscribe(d => { for (const k of keys) if (d.has(k)) { cb(); return; } });
    subs.set(id, sub);
  }
  return useSyncExternalStore(sub, () => keys.map(k => E.ver[k] || 0).join('.'));
}

export type View = 'home' | 'twin' | 'mesh' | 'report';
export const VIEWS: { id: Exclude<View, 'home'>; label: string; key: string }[] = [
  { id: 'twin', label: 'Digital twin', key: '1' }, { id: 'mesh', label: 'Mesh', key: '2' }, { id: 'report', label: 'Report', key: '3' }
];
const ALL: View[] = ['home', 'twin', 'mesh', 'report'];
const fromHash = (): View => { const v = location.hash.slice(1) as View; return ALL.includes(v) ? v : 'home'; };

interface Toast { id: number; text: string; ok: boolean }
interface UI {
  view: View; go: (v: View) => void;
  sel: string | null; select: (d: string | null) => void;
  person: string | null; pickPerson: (p: string | null) => void;
  toasts: Toast[]; toast: (text: string, ok: boolean) => void;
  live: boolean; setLive: (b: boolean) => void;
  loading: number | null; setLoading: (f: number | null) => void;
}
let tid = 0;
export const useUI = create<UI>(set => ({
  view: fromHash(),
  go: v => { set({ view: v }); history.replaceState(null, '', v === 'home' ? location.pathname + location.search : '#' + v); },
  sel: null, select: d => set({ sel: d }),
  person: null, pickPerson: p => set({ person: p }),
  toasts: [], toast: (text, ok) => {
    const id = ++tid;
    set(s => ({ toasts: [...s.toasts.slice(-2), { id, text: text.length > 140 ? text.slice(0, 137) + '…' : text, ok }] }));
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), 5200);
  },
  live: false, setLive: b => set({ live: b }),
  loading: null, setLoading: f => set({ loading: f })
}));
E.onToast = (t, ok) => useUI.getState().toast(t, ok);

export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
addEventListener('hashchange', () => { const v = fromHash(); if (useUI.getState().view !== v) useUI.setState({ view: v }); });
