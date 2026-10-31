import { useEffect, useState } from 'react';
import * as D from '@radix-ui/react-dialog';
import { X, Loader2, MonitorCheck, MonitorX, Play, Zap, Square, Terminal } from 'lucide-react';
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

export function LivePanel() {
  const open = useUI(s => s.live), setOpen = useUI(s => s.setLive);
  const [st, setSt] = useState<'scan' | 'found' | 'none' | 'starting'>('scan');
  const [status, setStatus] = useState<Status | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const say = (s: string) => setLog(l => [...l.slice(-6), s]);

  const scan = async () => {
    setSt('scan'); setLog([]);
    const s = await call('/status', 'GET', undefined, 30000);
    setStatus(s); setSt(s?.ok ? 'found' : 'none');
  };
  useEffect(() => { if (open) scan(); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const enter = () => { E.startLive(); setOpen(false); useUI.getState().go('twin'); };
  const start = async () => {
    setSt('starting');
    if (!status?.swarm_ready) {
      if (!status?.running) { say('Starting Gazebo, PX4 and the swarm…'); await call('/start', 'POST', {}, 8000); }
      else say('Gazebo is up. Waiting for the swarm to join the mesh…');
      // the camp takes a few minutes on a laptop: Gazebo, then each drone's PX4 and agent, then the mesh
      const t0 = performance.now();
      let ready = false;
      while (performance.now() - t0 < 15 * 60e3) {
        await sleep(4000);
        const s = await call('/status', 'GET', undefined, 30000); if (s) setStatus(s);
        if (s?.swarm_ready) { ready = true; break; }
        const secs = Math.round((performance.now() - t0) / 1000);
        if (secs % 20 < 4) say((s?.running ? 'Swarm powering up on the pads… ' : 'Opening the valley in Gazebo… ') + secs + ' s');
      }
      if (!ready) { say('The swarm did not report in. Check the Gazebo window, then press the button again.'); setSt('found'); return; }
    }
    say('Swarm on the pads. Triggering the landslide…');
    const r = await call('/trigger', 'POST', { seed: 19 }, 15000);
    if (!r?.ok) { say('The agent did not accept the trigger. Is live_agent.py still running?'); setSt('found'); return; }
    enter();
  };

  return (
    <D.Root open={open} onOpenChange={setOpen}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <D.Content className="glass fixed top-1/2 left-1/2 z-50 w-[min(620px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 bg-[#0a0d13]/92 p-6 outline-none">
          <D.Title className="text-base font-medium text-hi">Run it live</D.Title>
          <D.Description className="mt-1 text-[13px] text-muted">The website drives the simulation on this machine through a small local agent.</D.Description>
          <div className="mt-5">
            {st === 'scan' && <div className="flex items-center gap-3 py-6 text-sm text-muted"><Loader2 size={16} className="animate-spin text-accent" />Scanning this device for the ResQMesh simulation…</div>}
            {(st === 'found' || st === 'starting') && (
              <div className="space-y-4">
                <div className="flex items-start gap-3 rounded-xl border border-alive/25 bg-alive/[.06] p-4">
                  <MonitorCheck size={18} className="mt-0.5 shrink-0 text-alive" />
                  <div className="text-[13px]">
                    <div className="font-medium text-hi">Simulation found on this device</div>
                    <div className="num mt-1 text-[11.5px] text-muted">WSL {status?.wsl ? 'ok' : '—'} · build {status?.sim_ready ? 'ready' : 'not built'} · {status?.running ? 'running' + (status.phase ? ' · ' + status.phase : '') : 'stopped'}</div>
                  </div>
                </div>
                {log.length > 0 && <div className="num space-y-1 rounded-lg bg-black/40 p-3 text-[11.5px] text-muted">{log.map((l, i) => <div key={i}>{l}</div>)}</div>}
                <div className="flex flex-wrap gap-2">
                  {status?.running && status.phase && status.phase !== 'STANDBY'
                    ? <Button variant="accent" className="h-10 px-4 text-sm" onClick={enter}>Watch the running mission</Button>
                    : <Button variant="accent" className="h-10 px-4 text-sm" disabled={st === 'starting' || !status?.sim_ready} onClick={start}>
                        {st === 'starting' ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}{status?.swarm_ready ? 'Trigger the landslide' : status?.running ? 'Wait for the swarm, then trigger' : 'Start the mission'}
                      </Button>}
                </div>
                <p className="text-xs text-faint">Gazebo opens on this machine. The mission takes about ten minutes from the alert to everyone back at the camp.</p>
              </div>
            )}
            {st === 'none' && <SetupGuide onRetry={scan} />}
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
    ['Start the local agent', 'python sim/tools/live_agent.py']
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
