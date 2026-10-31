import { lazy, Suspense, useEffect, useRef } from 'react';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import { ArrowLeft, CircleCheck, TriangleAlert } from 'lucide-react';
import { E, clockStr } from './lib/engine';
import { useEngine, useUI, VIEWS } from './lib/store';
import { Tip, cn } from './components/ui';
import { ReplayBar, LoadingVeil } from './components/Replay';
import { LivePanel, LiveControls } from './components/Live';
import ErrorBoundary from './components/ErrorBoundary';
import Landing from './views/Landing';

const Twin = lazy(() => import('./views/Twin'));
const Mesh = lazy(() => import('./views/Mesh'));
const Report = lazy(() => import('./views/Report'));
const RUN_VIEWS = { twin: Twin, mesh: Mesh, report: Report };

function ModeChip() {
  useEngine('mode', 'story', 'clock');
  const t = E.mt(), phase = E.S.story?.phase;
  const mode = E.replay ? 'recorded' : E.live.ok ? 'live' : 'connecting';
  return (
    <div className="flex items-center gap-3">
      <Tip content={mode === 'live' ? 'Connected to the simulation through rosbridge (ws://localhost:9090)' : mode === 'recorded' ? 'Playing a recorded mission' : 'Waiting for the simulation on this machine'}>
        <span className={cn('flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium tracking-wide uppercase',
          mode === 'live' ? 'bg-alive/10 text-alive' : mode === 'recorded' ? 'bg-accent/10 text-accent' : 'bg-white/5 text-faint')}>
          <span className={cn('h-1.5 w-1.5 rounded-full', mode === 'live' ? 'bg-alive' : mode === 'recorded' ? 'bg-accent' : 'bg-faint')} />{mode}
        </span>
      </Tip>
      {phase && <span className="num hidden text-[11px] tracking-wider text-accent sm:inline">{phase}</span>}
      <span className="num text-[13px] text-hi">T+ {clockStr(t)}</span>
    </div>
  );
}

function Toasts() {
  const toasts = useUI(s => s.toasts);
  return (
    <div className="pointer-events-none fixed right-4 bottom-20 z-50 flex w-[380px] max-w-[calc(100vw-32px)] flex-col gap-2">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div key={t.id} initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 20 }}
            className="glass flex items-start gap-2.5 bg-[#0b0e14]/80 px-3.5 py-3 text-[13px]">
            {t.ok ? <CircleCheck size={16} className="mt-px shrink-0 text-alive" /> : <TriangleAlert size={16} className="mt-px shrink-0 text-danger" />}
            <span>{t.text}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function RunShell() {
  const { view, go } = useUI();
  useEngine('mode');
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => { mainRef.current?.scrollTo(0, 0); }, [view]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null; if (el && typeof el.closest === 'function' && el.closest('input,textarea,select,[contenteditable]')) return;
      const v = VIEWS.find(x => x.key === e.key); if (v) return go(v.id);
      if (e.key === ' ' && E.replay) { e.preventDefault(); E.replay.playing = !E.replay.playing; E.bump('mode'); }
    };
    addEventListener('keydown', key); return () => removeEventListener('keydown', key);
  }, [go]);
  const V = RUN_VIEWS[view as keyof typeof RUN_VIEWS] || Twin;
  const leave = () => { E.exit(); useUI.getState().setLive(false); go('home'); };
  return (
    <div className={cn('relative flex h-full flex-col', E.replay && 'pb-14')}>
      <div className="atmo" />
      <header className="relative z-20 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-b border-white/[.06] bg-[#06080c]/60 px-4 py-2 backdrop-blur-xl md:h-14 md:flex-nowrap md:py-0 lg:px-6">
        <button onClick={leave} className="flex items-center gap-2.5 text-muted hover:text-hi" aria-label="Back to the story">
          <ArrowLeft size={15} />
          <span className="text-[15px] font-semibold tracking-tight text-hi">ResQMesh</span>
        </button>
        <nav className="order-last -mx-1 flex w-full min-w-0 items-center gap-0.5 overflow-x-auto md:order-none md:mx-0 md:w-auto md:flex-1" aria-label="Run views">
          {VIEWS.map(v => (
            <button key={v.id} onClick={() => go(v.id)} aria-current={view === v.id}
              className={cn('relative h-8 shrink-0 rounded-lg px-3 text-[13px] transition-colors', view === v.id ? 'text-hi' : 'text-muted hover:text-fg')}>
              {view === v.id && <motion.span layoutId="navpill" className="absolute inset-0 rounded-lg bg-white/[.08]" transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }} />}
              <span className="relative">{v.label}</span>
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 md:ml-0"><div className="hidden lg:block"><LiveControls /></div><ModeChip /></div>
      </header>
      <main ref={mainRef} className="relative z-10 min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto h-full max-w-[1720px] p-3 lg:p-4">
          <ErrorBoundary resetKey={view}>
            <Suspense fallback={<div className="flex h-64 items-center justify-center text-sm text-faint">Loading…</div>}>
              <AnimatePresence mode="wait">
                <motion.div key={view} className="h-full" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                  <V />
                </motion.div>
              </AnimatePresence>
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
      {E.replay && <ReplayBar />}
    </div>
  );
}

export default function App() {
  const view = useUI(s => s.view);
  return (
    <MotionConfig reducedMotion="user">
      {view === 'home' ? <Landing /> : <RunShell />}
      <LivePanel />
      <LoadingVeil />
      <Toasts />
    </MotionConfig>
  );
}
