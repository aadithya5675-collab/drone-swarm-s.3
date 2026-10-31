import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import TacticalMap from '../components/TacticalMap';
import { CommanderStrip, EventFeed, PeopleList, RescueRoute, SwarmStrip, useMission } from '../components/Ops';
import { Button, Panel, Segmented } from '../components/ui';
import { useUI } from '../lib/store';

export default function LiveOps() {
  const go = useUI(s => s.go);
  const [tab, setTab] = useState<'people' | 'route'>('people');
  const m = useMission();
  return (
    <div className="flex min-h-full flex-col gap-3">
      <CommanderStrip />
      <div className="grid gap-3 lg:h-[clamp(440px,calc(100vh_-_222px),980px)] lg:grid-cols-[minmax(0,1fr)_400px]">
        <Panel id="ops-map" title="Tactical picture" sub="Lidar relief of the valley · sectors open to Scouts once mapped · live radio links"
          explain="The real valley in monochrome lidar relief. A sector opens to Scouts only once the Mappers have scanned it. The teal haze is where survivors are most likely; it fades as Scouts search. Click a person or a drone."
          actions={<Button onClick={() => go('twin')}>3D twin <ArrowUpRight size={13} /></Button>} className="min-h-[440px]" bodyClass="pb-3">
          <TacticalMap />
        </Panel>
        <Panel id="ops-people" title={tab === 'people' ? 'People located' : 'Ground-team route'}
          sub={tab === 'people' ? `${m.found} confirmed by thermal${m.cand ? ` · ${m.cand} colour-only to verify` : ''}` : 'what the camp sends the rescuers'}
          explain="Each person arrives with GPS coordinates and a thermal verdict: alive, or likely deceased — verify. △ marks a fix triangulated from several camera viewpoints. The route tab is the plan for the ground team: every survivor first."
          actions={<Segmented value={tab} onChange={setTab} options={[{ v: 'people', l: 'People' }, { v: 'route', l: 'Route' }]} />}
          className="min-h-[440px]" bodyClass="overflow-y-auto">
          {tab === 'people' ? <PeopleList /> : <RescueRoute />}
        </Panel>
      </div>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Panel title="Swarm" sub={m.brain ? `planner (Brain) running on ${m.brain.replace('_', ' ')}` : 'nobody flies these by hand'}
          explain="Every drone, what it is doing right now, its battery and how many radio hops it is from the camp. A lost drone turns grey; the swarm re-plans its unflown work and the camp launches a reserve.">
          <SwarmStrip />
        </Panel>
        <Panel title="Mission log" sub="as received at the camp" className="max-h-64" bodyClass="overflow-y-auto">
          <EventFeed max={40} />
        </Panel>
      </div>
    </div>
  );
}
