import { useEffect, useState } from 'react';
import * as D from '@radix-ui/react-dialog';
import { X, Loader2, MonitorCheck, MonitorX, Zap, Square, Terminal } from 'lucide-react';
import { AGENT_URL, REPO_URL, LOCAL_SITE } from '../config';
import { E } from '../lib/engine';
import { useEngine, useUI } from '../lib/store';
import { Button, cn } from './ui';

interface Status { ok: boolean; wsl?: boolean; sim_ready?: boolean; running?: boolean; swarm_ready?: boolean; phase?: string | null }

async function call(path: string, method = 'GET', body?: unknown, ms = 2500): Promise<Status | null> {
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(AGENT_URL + path, { method, signal: ctl.signal, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
    return r.ok ? await r.json() : null;
  } catch { return null; } finally { clearTimeout(t); }
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

const RUN_CMDS: [string, string][] = [
  ['Open the camp (PowerShell, in the repo folder). Keep this window open.', 'wsl -d Ubuntu-24.04 -- bash sim/tools/live.sh'],
  ['When it prints "Camp is up", trigger the landslide from a second window', 'wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/trigger.sh 19'],
  ['Optional: hit a drone mid-mission', 'wsl -d Ubuntu-24.04 -- bash ~/resqmesh/sim/tools/damage.sh scout_1']
];

/** True once the simulation's rosbridge answers on this machine. */
function probe(ms = 1500): Promise<boolean> {
  return new Promise(res => {
    let ws: WebSocket;
    try { ws = new WebSocket('ws://localhost:9090'); } catch { res(false); return; }
    const t = setTimeout(() => { ws.close(); res(false); }, ms);
    ws.onopen = () => { clearTimeout(t); ws.close(); res(true); };
    ws.onerror = () => { clearTimeout(t); res(false); };
  });
}

function Cmd({ c }: { c: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="group relative">
      <pre className="num overflow-x-auto rounded-lg border border-white/10 bg-black/50 px-3 py-2.5 pr-16 text-[12px] text-fg">{c}</pre>
      <button onClick={() => { navigator.clipboard?.writeText(c); setDone(true); setTimeout(() => setDone(false), 1200); }}
        className="absolute top-1.5 right-1.5 rounded-md border border-white/10 bg-white/[.06] px-2 py-1 text-[11px] text-muted hover:text-fg">{done ? 'copied' : 'copy'}</button>
    </div>
  );
}

export function LivePanel() {
  const open = useUI(s => s.live), setOpen = useUI(s => s.setLive);
  const [st, setSt] = useState<'scan' | 'wait' | 'linked'>('scan');
  const [secs, setSecs] = useState(0);
  const [setup, setSetup] = useState(false);
  const enter = () => { E.startLive(); setOpen(false); useUI.getState().go('twin'); };

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setSt('scan'); setSecs(0);
    (async () => {
      for (let i = 0; alive; i++) {
        if (await probe()) { if (!alive) return; setSt('linked'); setTimeout(() => alive && enter(), 900); return; }
        if (!alive) return;
        setSt('wait'); setSecs(2 * i);
        await sleep(2000);
      }
    })();
    return () => { alive = false; };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <D.Root open={open} onOpenChange={setOpen}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <D.Content className="glass fixed top-1/2 left-1/2 z-50 max-h-[90vh] w-[min(660px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto bg-[#0a0d13]/92 p-6 outline-none">
          <D.Title className="text-base font-medium text-hi">Run it live</D.Title>
          <D.Description className="mt-1 text-[13px] text-muted">Start the simulation from a terminal on this machine. This page links to it by itself and shows the live mission.</D.Description>
          <div className="mt-5 space-y-4">
            <div className={cn('flex items-center gap-3 rounded-xl border p-4 text-[13px]', st === 'linked' ? 'border-alive/30 bg-alive/[.07]' : 'border-white/10 bg-white/[.03]')}>
              {st === 'linked' ? <MonitorCheck size={18} className="shrink-0 text-alive" /> : <Loader2 size={17} className="shrink-0 animate-spin text-accent" />}
              <div>
                <div className="font-medium text-hi">{st === 'linked' ? 'Simulation linked: opening the live mission' : st === 'scan' ? 'Scanning this device for the simulation…' : 'Waiting for the simulation on this device'}</div>
                {st === 'wait' && <div className="num mt-0.5 text-[11.5px] text-muted">listening on localhost:9090 · {secs} s · run the commands below</div>}
              </div>
            </div>
            {st !== 'linked' && <>
              <ol className="space-y-3">
                {RUN_CMDS.map(([h, c], i) => (
                  <li key={c} className="flex gap-3">
                    <span className="num mt-0.5 text-[11px] text-accent">0{i + 1}</span>
                    <div className="min-w-0 flex-1"><div className="mb-1.5 text-[13px] text-fg">{h}</div><Cmd c={c} /></div>
                  </li>
                ))}
              </ol>
              <p className="text-xs text-faint">The camp takes 3 to 5 minutes to come up. The mission runs about 14 minutes from the alert to every drone back on its pad.
                {location.protocol === 'https:' && <> If this page never links, open <a className="text-accent underline" href={LOCAL_SITE}>{LOCAL_SITE}</a> instead.</>}</p>
              <button onClick={() => setSetup(v => !v)} className="text-xs text-muted underline hover:text-fg">{setup ? 'hide' : 'first time on this machine? install steps'}</button>
              {setup && <SetupGuide onRetry={() => setSetup(false)} />}
            </>}
          </div>
          <D.Close asChild><Button className="absolute top-3 right-3 px-2" aria-label="Close"><X size={15} /></Button></D.Close>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

function SetupGuide({ onRetry }: { onRetry: () => void }) {
  const https = location.protocol === 'https:';
  const steps: [string, string][] = [
    ['Get the code', `git clone ${REPO_URL}`],
    ['Install ROS 2, Gazebo and PX4 (WSL Ubuntu 24.04)', 'wsl -d Ubuntu-24.04 -u root -- bash sim/setup/01_ros_gazebo.sh\nwsl -d Ubuntu-24.04 -u root -- bash sim/setup/02_px4_deps.sh'],
    ['Build and fetch models', 'wsl -d Ubuntu-24.04 -- bash sim/setup/03_build.sh\nwsl -d Ubuntu-24.04 -- bash sim/setup/04_fetch_models.sh'],
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/[.03] p-4">
        <MonitorX size={18} className="mt-0.5 shrink-0 text-cand" />
        <div className="text-[13px] text-muted">
          <div className="font-medium text-hi">No simulation on this device</div>
          The live mission needs the simulation installed locally. It takes four steps; full details are in the repository README.
          {https && <> Browsers can block a secure page from talking to a local agent: once it is running, open <a className="text-accent underline" href={LOCAL_SITE}>{LOCAL_SITE}</a>.</>}
        </div>
      </div>
      <ol className="space-y-3">
        {steps.map(([h, c], i) => (
          <li key={h} className="flex gap-3">
            <span className="num mt-0.5 text-[11px] text-accent">0{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] text-hi">{h}</div>
              <pre className="num mt-1.5 overflow-x-auto rounded-lg bg-black/45 px-3 py-2 text-[11.5px] leading-relaxed text-fg">{c}</pre>
            </div>
          </li>
        ))}
      </ol>
      <div className="flex gap-2">
        <Button variant="solid" onClick={onRetry}>Scan again</Button>
        <a href={REPO_URL} target="_blank" rel="noreferrer"><Button>Open the repository</Button></a>
      </div>
    </div>
  );
}

export function LiveControls() {
  useEngine('mode', 'story');
  const [busy, setBusy] = useState<string | null>(null);
  if (E.replay) return null;
  const act = async (k: string, path: string, body?: unknown) => { setBusy(k); await call(path, 'POST', body, 8000); setBusy(null); };
  const phase = E.S.story?.phase;
  return (
    <div className="flex items-center gap-1">
      {(!phase || phase === 'STANDBY') && <Button onClick={() => act('t', '/trigger')} className={cn(busy === 't' && 'opacity-60')}><Zap size={14} />Landslide</Button>}
      <Button onClick={() => act('s', '/damage', { drone: 'scout_1' })} className={cn(busy === 's' && 'opacity-60')}><Terminal size={14} />Hit a Scout</Button>
      <Button onClick={() => act('m', '/damage', { drone: 'mapper_1' })} className={cn(busy === 'm' && 'opacity-60')}><Terminal size={14} />Hit a Mapper</Button>
      <Button onClick={() => act('x', '/stop')} aria-label="Stop the simulation"><Square size={13} /></Button>
    </div>
  );
}
