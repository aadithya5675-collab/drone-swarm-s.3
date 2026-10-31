/* ResQMesh data engine: one mutable mission state fed by two transports that deliver exactly what rosbridge
   delivers — live (rosbridge websocket :9090, the same topics the camp publishes) and replay (recorded
   dashboard/replays/*.jsonl). React reads it through version counters (see store.ts); canvases read it per frame. */

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Cond = 'ALIVE' | 'DECEASED_SUSPECTED' | 'UNKNOWN';
export interface Drone {
  drone: string; role: string; state: string; x: number; y: number; z: number; agl: number; battery: number;
  sector_id: string; waypoint_index: number; n_waypoints: number; why: string; speed: number; tilt: number; hops: number; age: number;
}
export interface Person {
  id: string; x: number; y: number; z?: number; n: number; condition: Cond; max_temp_k: number; sensors: string[];
  found_by: string; via_hops: number; lat: number; lon: number; t_since_alert?: number; rechecked?: boolean;
  fix?: 'triangulated' | 'ground'; fix_rays?: number; fix_rms_m?: number; fix_spread_deg?: number;
}
export interface Ev { t: number | null; level: string; source: string; text: string }
export interface Cloud { n: number; xs: Float32Array; ys: Float32Array; zs: Float32Array; zmin: number; zmax: number; ver: number }

export const DRONES = ['scout_1', 'scout_2', 'scout_3', 'scout_4', 'mapper_1', 'mapper_2', 'relay_1'];
export const SCOUTS = ['scout_1', 'scout_2', 'scout_3', 'scout_4'];
export const PHASES = ['STANDBY', 'DEPLOY', 'SEARCH', 'RTB', 'COMPLETE'];
export const ROLE_C: Record<string, string> = { scout: '#f5b544', mapper: '#7dd3fc', relay: '#c4b5fd', tower: '#fb7185' };
export const COND_C: Record<string, string> = { ALIVE: '#4ade80', DECEASED_SUSPECTED: '#a1a1aa', UNKNOWN: '#fbbf24' };
export const COND_L: Record<string, string> = { ALIVE: 'Alive', DECEASED_SUSPECTED: 'Likely deceased', UNKNOWN: 'Candidate' };
export const KIND_C: Record<string, string> = { status: '#7dd3fc', sighting: '#fde047', alert: '#fb7185', plan: '#c4b5fd', waypoints: '#c4b5fd', event: '#f5b544', reserve_request: '#f87171', ack: '#64748b', hello: '#334155', verify: '#f0abfc' };
export const role = (n: string) => (n === 'tower' ? 'tower' : String(n).split('_')[0]);
export const short = (n: string) => String(n).replace('scout_', 'S').replace('mapper_', 'M').replace('relay_', 'R').replace('tower', 'Camp');
export const clockStr = (t: number | null | undefined) => {
  if (t == null || isNaN(t)) return '--:--';
  const s = Math.max(0, Math.floor(t));
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
};

function fresh() {
  return {
    fleet: {} as Record<string, Drone>, persons: [] as Person[], plan: null as any, story: null as any, map: null as any,
    mapImg: null as HTMLImageElement | null, trails: {} as Record<string, number[][]>, traffic: null as any, mesh: {} as Record<string, any>,
    vision: {} as Record<string, any>, vf: {} as Record<string, { s: any; t: number }>, cloud: null as Cloud | null,
    frames: {} as Record<string, { src: string; t: number }>, packets: [] as any[], pdr: [] as number[][], lastTot: null as any,
    traces: [] as any[], history: [] as any[], events: [] as Ev[], taskObs: {} as Record<string, any>, traf: [] as number[][],
    posSeries: [] as number[][], search: null as any, rescue: null as any, searchImg: null as HTMLCanvasElement | null, searchVer: 0,
    pings: [] as any[], seen: new Set<string>(), confirmedAt: {} as Record<string, number>, lossT: [] as { d: string; t: number }[],
    _cloudRaw: null as any, _searchRaw: null as any, _mapPending: null as any
  };
}
export type State = ReturnType<typeof fresh>;

type Listener = (keys: Set<string>) => void;
class Engine {
  S: State = fresh();
  V: any = null;          // valley.json: bounds, corridor, sectors, tower, pads, river, origin
  T: any = null;          // terrain.json: height grid (m, relative to camp)
  ver: Record<string, number> = {};
  dirty = new Set<string>();
  seeking = false;
  replay: null | { name: string; recs: any[]; i: number; t: number; dur: number; speed: number; playing: boolean; tAlert: number | null } = null;
  live = { ws: null as WebSocket | null, ok: false, everOk: false, tries: 0, stopped: false };
  private listeners = new Set<Listener>();
  onToast: ((text: string, ok: boolean) => void) | null = null;

  subscribe(f: Listener) { this.listeners.add(f); return () => { this.listeners.delete(f); }; }
  bump(k: string) { this.ver[k] = (this.ver[k] || 0) + 1; this.dirty.add(k); }
  flush() { if (!this.dirty.size) return; const d = this.dirty; this.dirty = new Set(); this.listeners.forEach(f => f(d)); }

  clock() { return this.replay ? this.replay.t : performance.now() / 1000; }
  speed() { return this.replay ? (this.replay.playing ? this.replay.speed : 1) : 1; }
  mt(): number | null { const s = this.S.story; return s && s.t_since_alert != null ? s.t_since_alert : null; }
  /** mission time (T+) at which the camp first fused a sighting of this person: first_seen is the camp's clock,
      and the camp's clock at the alert is recovered from any fleet entry (t + age = camp now) minus T+ now */
  foundAt(p: Person): number | null {
    const st = this.S.story, f = Object.values(this.S.fleet)[0] as any;
    if ((p as any).first_seen != null && st && st.t_since_alert != null && f && f.t != null) return (p as any).first_seen - (f.t + f.age - st.t_since_alert);
    return this.S.confirmedAt[p.id] ?? null;
  }
  isLost(n: string, s: Drone) { const p = this.S.plan; return (p && (p.lost || []).includes(n)) || s.state === 'CRASHED' || s.state === 'LOST' || s.age > 12; }
  ground(x: number, y: number) {
    const T = this.T; if (!T) return 0;
    const fx = (x - T.x0) / T.res, fy = (y - T.y0) / T.res, i = Math.floor(fy), j = Math.floor(fx);
    if (i < 0 || j < 0 || i >= T.h - 1 || j >= T.w - 1) return 0;
    const a = fx - j, b = fy - i, z = T.z, w = T.w;
    return z[i * w + j] * (1 - a) * (1 - b) + z[i * w + j + 1] * a * (1 - b) + z[(i + 1) * w + j] * (1 - a) * b + z[(i + 1) * w + j + 1] * a * b;
  }

  async loadStatic() {
    const [v, t] = await Promise.all([fetch('valley.json').then(r => r.json()), fetch('terrain.json').then(r => r.json())]);
    this.V = v; this.T = t; this.bump('static');
  }

  // ------------------------------------------------------------- message handling
  handle(topic: string, msg: any, cache?: any) {
    const S = this.S;
    if (topic === '/swarm/events') return this.addEvent(msg.level, msg.source, msg.text);
    if (topic.endsWith('/vision/annotated')) {
      S.frames[topic.split('/')[1]] = { src: 'data:image/jpeg;base64,' + msg.data, t: cache && cache.t != null ? cache.t : this.clock() };
      this.bump('frame'); return;
    }
    let d = cache && cache._d;
    if (d === undefined) { try { d = JSON.parse(msg.data); } catch { d = null; } if (cache) cache._d = d; }
    if (d == null) return;
    switch (topic) {
      case '/base/fleet': S.fleet = d; this.trails(); this.bump('fleet'); break;
      case '/base/persons': this.onPersons(d); break;
      case '/base/plan': this.onPlan(d); break;
      case '/base/story': S.story = d; this.bump('story'); break;
      case '/base/mapimg': S.map = d; if (!this.seeking) this.loadMapImg(d); else S._mapPending = d; this.bump('mapimg'); break;
      case '/base/mesh': S.mesh = d; this.bump('mesh'); break;
      case '/base/vision': this.visionStats(d); break;
      case '/base/cloud': S._cloudRaw = d; if (!this.seeking) S.cloud = this.decodeCloud(d); this.bump('cloud'); break;
      case '/mesh/traffic': this.onTraffic(d); break;
      case '/mesh/trace': this.onTrace(d); break;
      case '/base/history': S.history = d; this.bump('history'); break;
      case '/base/eventlog': this.onEventLog(d); break;
      case '/brain/searchmap': S._searchRaw = d; if (!this.seeking) this.onSearch(d); this.bump('search'); break;
      case '/base/rescue': S.rescue = d; this.bump('rescue'); break;
    }
  }
  private afterSeek() {
    const S = this.S;
    if (S._cloudRaw) S.cloud = this.decodeCloud(S._cloudRaw);
    if (S._searchRaw) this.onSearch(S._searchRaw);
    if (S._mapPending) this.loadMapImg(S._mapPending);
  }
  private trails() {
    const S = this.S;
    for (const [n, s] of Object.entries(S.fleet)) {
      const tr = (S.trails[n] = S.trails[n] || []), l = tr[tr.length - 1];
      if (!l || Math.hypot(l[0] - s.x, l[1] - s.y) > 2.5 || Math.abs(l[2] - s.z) > 2) { tr.push([s.x, s.y, s.z]); if (tr.length > 1600) tr.shift(); }
    }
  }
  private onPersons(d: Person[]) {
    const S = this.S; S.persons = d;
    const t = this.mt();      // when the camp first held a thermal verdict for this person (mission time)
    for (const p of d) if (p.condition !== 'UNKNOWN' && S.confirmedAt[p.id] == null && t != null) S.confirmedAt[p.id] = t;
    for (const p of d) if (!S.seen.has(p.id)) {
      S.seen.add(p.id);
      if (!this.seeking) S.pings.push({ x: p.x, y: p.y, t: performance.now(), c: COND_C[p.condition] });
    }
    this.bump('persons');
  }
  private onPlan(d: any) {
    const S = this.S, t = this.mt(); S.plan = d;
    if (t != null) {
      for (const k of d.tasks || []) {
        const o = (S.taskObs[k.id] = S.taskObs[k.id] || { id: k.id, root: k.root, role: k.role });
        o.owner = k.owner || o.owner; o.status = k.status; o.start = k.start; o.end = k.end; o.done = k.done;
        if (k.status === 'ASSIGNED' && o.tA == null) o.tA = t;
        if (k.released && o.tR == null) o.tR = t;
        if ((k.status === 'DONE' || k.status === 'ABANDONED') && o.tE == null) o.tE = t;
      }
      for (const n of d.lost || []) if (!S.lossT.find(l => l.d === n)) S.lossT.push({ d: n, t });
      if (d.pos != null) { const l = S.posSeries[S.posSeries.length - 1]; if (!l || t - l[0] >= 2) S.posSeries.push([t, d.pos]); }
    }
    this.bump('plan');
  }
  private loadMapImg(d: any) {
    const im = new Image(); im.onload = () => { this.S.mapImg = im; this.bump('mapimgready'); }; im.src = 'data:image/png;base64,' + d.png;
  }
  private visionStats(d: any) {
    const S = this.S, now = this.clock();
    for (const [n, s] of Object.entries<any>(d)) {
      const o = S.vf[n];
      if (o) {
        const dt = now - o.t;
        if (dt > 0.4) { s.tfps = (s.thermal_frames - o.s.thermal_frames) / dt; s.rfps = (s.rgb_frames - o.s.rgb_frames) / dt; }
        else { s.tfps = o.s.tfps; s.rfps = o.s.rfps; }
        if (dt <= 0.4) continue;
      }
      S.vf[n] = { s, t: now };
    }
    S.vision = d; this.bump('vision');
  }
  private decodeCloud(d: any): Cloud {
    const n = d.n, r = d.res, p = d.p, xs = new Float32Array(n), ys = new Float32Array(n), zs = new Float32Array(n);
    let zmin = 1e9, zmax = -1e9;
    for (let i = 0; i < n; i++) {
      xs[i] = p[3 * i] * r; ys[i] = p[3 * i + 1] * r; zs[i] = p[3 * i + 2] * r;
      if (zs[i] < zmin) zmin = zs[i]; if (zs[i] > zmax) zmax = zs[i];
    }
    return { n, xs, ys, zs, zmin, zmax, ver: (this.S.cloud ? this.S.cloud.ver : 0) + 1 };
  }
  private onTraffic(d: any) {
    const S = this.S, now = performance.now(), sp = this.speed();
    S.traffic = d;
    if (!this.seeking && sp <= 32) {
      const budget = sp > 4 ? 0.35 : 1;
      for (const [s, t, k, n] of d.flows) {
        if (k === 'hello' || (k === 'ack' && Math.random() > 0.3)) continue;
        const m = Math.min(n, k === 'ack' ? 1 : 3);
        for (let i = 0; i < m; i++) if (Math.random() < budget)
          S.packets.push({ a: s, b: t, k, t0: now + Math.random() * 900 / Math.min(sp, 4), dur: (650 + Math.random() * 250) / Math.min(sp, 4) });
      }
      if (S.packets.length > 1400) S.packets.splice(0, S.packets.length - 1400);
    }
    const T = d.totals;
    if (S.lastTot) {
      const dd = T.delivered - S.lastTot.delivered, dl = (T.lost - S.lastTot.lost) + (T.blocked - S.lastTot.blocked);
      if (dd >= 0 && dl >= 0) {
        S.pdr.push([dd, dl]); if (S.pdr.length > 30) S.pdr.shift();
        const t = this.mt(); if (t != null) { S.traf.push([t, dd, dl]); if (S.traf.length > 2000) S.traf.shift(); }
      }
    }
    S.lastTot = T;
    this.bump('traffic');
  }
  pdrNow() {
    const P = this.S.pdr, a = P.reduce((x, y) => x + y[0], 0), b = P.reduce((x, y) => x + y[1], 0);
    return { pdr: a + b ? a / (a + b) : null, fps: a / Math.max(1, P.length) };
  }
  private onTrace(d: any) {
    d.mt = this.mt(); this.S.traces.unshift(d);
    if (this.S.traces.length > 500) this.S.traces.length = 500;
    this.bump('trace');
  }
  private onSearch(d: any) {
    const S = this.S; S.search = d;
    const c = document.createElement('canvas'); c.width = d.w; c.height = d.h;
    const g = c.getContext('2d')!, im = g.createImageData(d.w, d.h);
    for (let i = 0; i < d.h; i++) for (let j = 0; j < d.w; j++) {
      const q = d.q[i * d.w + j], o = ((d.h - 1 - i) * d.w + j) * 4;   // canvas row 0 = north
      if (!q) { im.data[o + 3] = 0; continue; }
      const u = q / 255;                                                 // probability mass: teal, brighter = likelier
      im.data[o] = 40 + 60 * u; im.data[o + 1] = 160 + 80 * u; im.data[o + 2] = 150 + 70 * u; im.data[o + 3] = 40 + 170 * u;
    }
    g.putImageData(im, 0, 0);
    S.searchImg = c; S.searchVer++;
  }

  // ------------------------------------------------------------- events
  addEvent(level: string, source: string, text: string, t?: number) {
    const S = this.S, e: Ev = { t: t !== undefined ? t : this.mt(), level, source: source || 'swarm', text };
    const last = S.events[S.events.length - 1];
    if (last && last.text === e.text && last.level === e.level) return;
    S.events.push(e); if (S.events.length > 600) S.events.shift();
    this.bump('events');
    if (!this.seeking) this.maybeToast(e);
  }
  private onEventLog(list: Ev[]) {
    const S = this.S, texts = new Set(list.map(e => e.text));
    const tail = S.events.filter(e => !texts.has(e.text) && (e.t == null || !list.length || e.t >= (list[list.length - 1].t || 0)));
    S.events = list.map(e => ({ t: e.t, level: e.level, source: e.source, text: e.text })).concat(tail);
    this.bump('events');
  }
  private maybeToast(e: Ev) {
    const tx = e.text, f = this.onToast; if (!f) return;
    if (/LOST|is down|CRASHED|DAMAGE/i.test(tx) && e.level !== 'INFO') f(tx, false);
    else if (/launching reserve|joins the search|rejoins|now hosts|Search complete|Mission complete/i.test(tx)) f(tx, true);
    else if (/ALIVE/.test(tx) && /found by/i.test(tx)) f(tx, true);
  }

  // ------------------------------------------------------------- live transport (rosbridge)
  static TOPICS: [string, number][] = [['/base/fleet', 300], ['/base/persons', 0], ['/base/plan', 800], ['/base/story', 400], ['/base/mapimg', 2500],
    ['/base/mesh', 900], ['/base/vision', 900], ['/base/cloud', 3500], ['/base/history', 4000], ['/base/eventlog', 2900], ['/mesh/traffic', 0],
    ['/mesh/trace', 0], ['/brain/searchmap', 3500], ['/base/rescue', 0]];
  connectLive = () => {
    const L = this.live;
    if (this.replay || L.stopped) return;
    let ws: WebSocket;
    const host = location.protocol === 'https:' || !location.hostname ? 'localhost' : location.hostname;
    try { ws = new WebSocket('ws://' + host + ':9090'); } catch { setTimeout(this.connectLive, 2000); return; }
    L.ws = ws;
    ws.onopen = () => {
      L.ok = L.everOk = true; L.tries = 0; this.bump('mode');
      const sub = (topic: string, type: string, rate = 0) => ws.send(JSON.stringify({ op: 'subscribe', topic, type, throttle_rate: rate, queue_length: 1 }));
      for (const [t, r] of Engine.TOPICS) sub(t, 'std_msgs/msg/String', r);
      sub('/swarm/events', 'resqmesh_interfaces/msg/MissionEvent');
      for (const d of SCOUTS) sub('/' + d + '/vision/annotated', 'sensor_msgs/msg/CompressedImage', 900);
    };
    ws.onclose = () => {
      const was = L.ok; L.ok = false; L.tries++; this.bump('mode');
      // back off while the simulator is down (1.5 s, 3 s, 6 s ... 15 s)
      if (!this.replay && !L.stopped) setTimeout(this.connectLive, was ? 1500 : Math.min(15000, 1500 * 2 ** Math.min(L.tries, 4)));
    };
    ws.onerror = () => { try { ws.close(); } catch { /* closed */ } };
    ws.onmessage = e => { const m = JSON.parse(e.data); if (m.op === 'publish') this.handle(m.topic, m.msg); };
  };
  stopLive() { this.live.stopped = true; if (this.live.ws) try { this.live.ws.close(); } catch { /* closed */ } this.live.ok = false; }

  // ------------------------------------------------------------- replay transport
  async loadReplay(file: string, onProgress?: (f: number) => void) {
    const res = await fetch(file);
    if (!res.ok || !res.body) throw new Error('cannot load ' + file);
    const total = +(res.headers.get('content-length') || 0), recs: any[] = [];
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = '', got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      got += value.length; buf += dec.decode(value, { stream: true });
      let k;
      while ((k = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, k); buf = buf.slice(k + 1); if (line) try { recs.push(JSON.parse(line)); } catch { /* partial */ } }
      if (onProgress && total) onProgress(got / total);
    }
    if (buf.trim()) try { recs.push(JSON.parse(buf)); } catch { /* partial */ }
    recs.sort((a, b) => a.t - b.t);
    return recs;
  }
  startReplay(name: string, recs: any[]) {
    this.stopLive();
    let tAlert: number | null = null;
    for (const r of recs) if (r.topic === '/base/story') {
      try { const d = JSON.parse(r.msg.data); if (d.t_since_alert != null) { tAlert = r.t - d.t_since_alert; break; } } catch { /* skip */ }
    }
    this.replay = { name, recs, i: 0, t: 0, dur: recs.length ? recs[recs.length - 1].t : 0, speed: 16, playing: true, tAlert };
    this.seek(tAlert != null ? Math.max(0, tAlert - 6) : 0);
    this.bump('mode');
  }
  startLive() { this.replay = null; this.S = fresh(); this.bumpAll(); this.live.stopped = false; this.live.everOk = false; this.live.tries = 0; this.connectLive(); this.bump('mode'); }
  exit() { this.stopLive(); this.replay = null; this.S = fresh(); this.bumpAll(); this.bump('mode'); }
  stopReplay() {
    this.replay = null; this.S = fresh(); this.bumpAll();
    this.live.stopped = false; this.live.everOk = false; this.live.tries = 0; this.connectLive(); this.bump('mode');
  }
  private bumpAll() { for (const k of ['fleet', 'persons', 'plan', 'story', 'mapimg', 'mesh', 'vision', 'cloud', 'traffic', 'trace', 'history', 'events', 'search', 'rescue', 'frame', 'reset']) this.bump(k); }
  seek(t: number) {
    const R = this.replay; if (!R) return;
    this.S = fresh();
    this.seeking = true;
    R.t = t;                                                  // handlers stamp frames with the replay clock
    const recs = R.recs; let n = 0;
    while (n < recs.length && recs[n].t <= t) n++;
    const lastImg: Record<string, number> = {};               // only the latest image per camera matters
    for (let i = 0; i < n; i++) if (recs[i].topic.endsWith('/annotated')) lastImg[recs[i].topic] = i;
    for (let i = 0; i < n; i++) {
      const r = recs[i];
      if (r.topic.endsWith('/annotated') && lastImg[r.topic] !== i) continue;
      this.handle(r.topic, r.msg, r);
    }
    this.seeking = false;
    R.i = n; R.t = t;
    this.afterSeek();
    this.bumpAll(); this.bump('seek');
  }
  replayTick(dt: number) {
    const R = this.replay; if (!R || !R.playing) return;
    R.t = Math.min(R.dur, R.t + dt * R.speed);
    const recs = R.recs;
    while (R.i < recs.length && recs[R.i].t <= R.t) { const r = recs[R.i++]; this.handle(r.topic, r.msg, r); }
    if (R.t >= R.dur) R.playing = false;
    this.bump('clock');
  }
}

export const E = new Engine();
(window as any).RQE = E;   // for debugging from the console
