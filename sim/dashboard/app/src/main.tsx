import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import * as RT from '@radix-ui/react-tooltip';
import './index.css';
import App from './App';
import { E } from './lib/engine';

E.loadStatic().catch(err => console.error('static data', err));
const q = new URLSearchParams(location.search);
if (q.get('replay')) {
  const file = q.get('replay')!.replace(/[^\w.-]/g, '');
  import('./components/Replay').then(m => m.openReplay(file)).then(() => {
    const R = E.replay; if (!R) return;
    if (q.get('t')) E.seek((R.tAlert ?? 0) + +q.get('t')!);
    if (q.get('speed')) R.speed = +q.get('speed')!;
    if (q.get('paused')) R.playing = false;
  });
} else if (location.hash && location.hash !== '#home') {
  import('./lib/store').then(m => m.useUI.getState().go('home'));
}

// one clock for the whole app: replay advances every frame, React hears about changes ~8x/s
let last = performance.now();
const loop = (now: number) => {
  requestAnimationFrame(loop);
  E.replayTick(Math.min(0.25, (now - last) / 1000)); last = now;
};
requestAnimationFrame(loop);
setInterval(() => E.flush(), 120);

createRoot(document.getElementById('root')!).render(
  <StrictMode><RT.Provider><App /></RT.Provider></StrictMode>
);
