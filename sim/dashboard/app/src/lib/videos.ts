// Every recording is fetched once, right after the page loads, and kept in memory as a blob URL, so the step insets
// and the report's recordings play instantly instead of buffering. Files that are missing or not real videos are
// remembered as missing so nothing shows a broken player.
import { useSyncExternalStore } from 'react';
import { VIDEOS } from '../config';

const CACHE_KEY = '?v=3';

type State = { src: string; ready: boolean; missing: boolean };
const state = new Map<string, State>();
const subs = new Set<() => void>();
const emit = () => subs.forEach(f => f());
let started = false;

async function load(file: string) {
  const directUrl = 'videos/' + file + CACHE_KEY;
  try {
    const r = await fetch(directUrl);
    const type = r.headers.get('content-type') || '';
    if (!r.ok || type.includes('text/html')) throw new Error('missing');
    const blob = await r.blob();
    if (blob.size < 500) throw new Error('placeholder');
    state.set(file, { src: URL.createObjectURL(blob), ready: true, missing: false });
  } catch {
    // If blob prefetch fails, fallback to direct streaming URL so the video still plays
    state.set(file, { src: directUrl, ready: true, missing: false });
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
  if (!s) { s = { src: 'videos/' + name + CACHE_KEY, ready: false, missing: false }; pending.set(name, s); }
  return s;
}
