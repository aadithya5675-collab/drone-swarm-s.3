// Every recording is fetched once, right after the page loads, and kept in memory as a blob URL, so the step insets
// and the report's recordings play instantly instead of buffering. Files that are missing or not real videos are
// remembered as missing so nothing shows a broken player.
import { useSyncExternalStore } from 'react';
import { VIDEOS } from '../config';

type State = { src: string; ready: boolean; missing: boolean };
const state = new Map<string, State>();
const subs = new Set<() => void>();
const emit = () => subs.forEach(f => f());
let started = false;

async function load(file: string) {
  try {
    const r = await fetch('videos/' + file, { cache: 'force-cache' });
    const type = r.headers.get('content-type') || '';
    if (!r.ok || type.includes('text/html')) throw new Error('missing');
    const blob = await r.blob();
    if (blob.size < 10_000) throw new Error('placeholder');
    state.set(file, { src: URL.createObjectURL(blob), ready: true, missing: false });
  } catch {
    state.set(file, { src: 'videos/' + file, ready: false, missing: true });
  }
  emit();
}

export function preloadVideos() {
  if (started) return;
  started = true;
  const queue = VIDEOS.map(v => v.file);
  const worker = async () => { for (let f = queue.shift(); f; f = queue.shift()) await load(f); };
  const go = () => { for (let k = 0; k < 3; k++) worker(); };
  // after the first paint, so the page itself loads first
  if (document.readyState === 'complete') setTimeout(go, 800);
  else addEventListener('load', () => setTimeout(go, 800), { once: true });
}

const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };

/** The best source for a recording: its in-memory copy once loaded, the network file until then. */
export function useVideo(file: string): State {
  const name = file.endsWith('.mp4') ? file : file + '.mp4';
  return useSyncExternalStore(subscribe, () => state.get(name) ?? PENDING(name));
}

const pending = new Map<string, State>();
function PENDING(name: string) {
  let s = pending.get(name);
  if (!s) { s = { src: 'videos/' + name, ready: false, missing: false }; pending.set(name, s); }
  return s;
}
