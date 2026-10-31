"""The swarm's planner ("Brain")."""
import json
import math

import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from std_msgs.msg import String

from resqmesh_interfaces.msg import HeightMap, MeshFrame

from .coverage import oriented_lawnmower, sector_cells
from .search_map import SearchMap
from .story_plan import Task, TaskPlan
from .terrain import Terrain

SCOUT_CAM_PITCH, THERMAL_HFOV = 0.5934, 0.994   # rad, as in config/vehicle_params.yaml
RESERVE_GRACE_S = 20.0
LOW_BATTERY = 0.25
POD = 0.8
VALUE_M = 800.0
VERIFY_MAX_M = 150.0
RELAY_HOP_M = 420.0


class Brain(Node):
    def __init__(self):
        super().__init__('brain')
        for k, v in (('fleet', ''), ('layout', ''), ('prior', ''), ('host', 'mapper_1'), ('standby', 'mapper_2')):
            self.declare_parameter(k, v)
        fleet = yaml.safe_load(open(self.get_parameter('fleet').value))
        self.lay = json.load(open(self.get_parameter('layout').value))
        self.cfg = fleet['mission']
        self.roles = {d['name']: d['role'] for d in fleet['drones']}
        self.reserves = [d['name'] for d in fleet['drones'] if d.get('reserve')]
        self.pads = {d['name']: d['pad'] for d in fleet['drones']}
        self.relays = [d for d in self.roles if self.roles[d] == 'relay']
        self.plan = TaskPlan()
        slant = self.cfg['scout_agl_m'] / math.sin(SCOUT_CAM_PITCH)
        spacing = 2.0 * slant * math.tan(THERMAL_HFOV / 2.0) * 0.85
        for s in self.lay['sectors']:
            self.plan.add_task(s['id'], 'scout', oriented_lawnmower(s['start'], s['end'], s['half_width'], spacing, self.cfg['scout_agl_m']),
                               needs_map=True, geom=(s['start'], s['end'], s['half_width']))
        line = np.array(self.lay['corridor']['line'], float)
        mid = len(line) // 2
        for k, part in enumerate((line[:mid + 1], line[mid:])):
            path = self.offset_passes(part, 40.0, self.cfg['mapper_agl_m'])
            self.plan.add_task('M%d' % (k + 1), 'mapper', path, geom=(path[0][:2], path[len(path) // 2 - 1][:2], 60.0))
        for d, r in self.roles.items():
            if d not in self.reserves and r in ('scout', 'mapper'):
                self.plan.add_drone(d, r)
        self.host, self.standby = self.get_parameter('host').value, self.get_parameter('standby').value
        self.state, self.seen, self.lost, self.requested = {}, {}, set(), {}
        self.crashed, self.reserve_due = set(), {}
        self.retired, self.overwatching = set(), set()
        self.chain, self.relay_down = {}, None
        self.refine_added = False
        self.verify_q, self.verified = [], set()
        c = self.lay['corridor']
        self.smap = SearchMap(c['line'], c['half_width'], [(h['x'], h['y']) for h in self.lay['landslide']['houses']])
        self.footprint = spacing / 0.85
        self.last_xy = {}
        self.map_pub = self.create_publisher(String, '/brain/searchmap', 2)
        self.create_timer(4.0, lambda: self.map_pub.publish(String(data=json.dumps(self.smap.to_msg()))))
        self.terrain = Terrain(self.get_parameter('prior').value) if self.get_parameter('prior').value else None
        self.phase, self.t_alert, self.launched = 'STANDBY', None, set()
        self.maps, self._cells, self.released_sent = {}, {}, set()
        self.out = {m: self.create_publisher(MeshFrame, '/%s/mesh/out' % m, 50) for m in (self.host, self.standby)}
        self.svc = {m: self.create_publisher(String, '/%s/mesh/services' % m, 5) for m in (self.host, self.standby)}
        for m in (self.host, self.standby):
            self.create_subscription(MeshFrame, '/%s/mesh/in' % m, lambda f, m=m: self.on_frame(m, f), 100)
            self.create_subscription(HeightMap, '/%s/map/height' % m, self.on_map, 2)
        self.create_timer(1.0, self.advertise)
        self.create_timer(0.5, self.tick)
        self.create_timer(2.0, self.report)
        self.create_timer(3.0, self.relay_tick)

    @staticmethod
    def offset_passes(line, off, agl):
        t = np.gradient(line, axis=0)
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        n = np.stack([-t[:, 1], t[:, 0]], 1)
        a, b = line + n * off, (line - n * off)[::-1]
        return [(float(x), float(y), float(agl)) for x, y in np.vstack([a[::3], b[::3]])]

    # mesh I/O
    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def advertise(self):
        self.svc[self.host].publish(String(data='+brain'))
        other = self.standby if self.host != self.standby else self.get_parameter('host').value
        if other != self.host:
            self.svc[other].publish(String(data='-brain'))

    def send(self, final, kind, payload):
        self.out[self.host].publish(MeshFrame(final=final, kind=kind, payload=json.dumps(payload)))

    def event(self, level, text):
        self.get_logger().info('[%s] %s' % (level, text))
        self.send('base', 'event', {'level': level, 'source': 'brain@' + self.host, 'text': text})

    def on_frame(self, via, f):
        if via != self.host:
            return
        if f.kind == 'status':
            self.on_status(json.loads(f.payload))
        elif f.kind == 'verify':
            p = json.loads(f.payload)
            if p['id'] not in self.verified:
                self.verified.add(p['id'])
                self.verify_q.append(p)
        elif f.kind == 'alert' and self.phase == 'STANDBY':
            self.phase, self.t_alert = 'DEPLOY', self.now()
            self.event('ALERT', 'Landslide alert received from the camp tower. Deploying the swarm.')

    def on_map(self, m):
        z = np.isfinite(np.asarray(m.z, dtype=np.float32).reshape(m.height, m.width))
        self.maps[m.source] = (m.origin_x, m.origin_y, m.resolution, m.width, m.height, z, m.coverage)

    # drones
    def on_status(self, s):
        d = s['drone']
        if d in self.lost:
            if s['state'] == 'CRASHED' or d in self.crashed or d in self.retired:
                return
            self.lost.discard(d)
            self.plan.add_drone(d, self.roles[d])
            self.event('INFO', '%s is back on the mesh (link restored) and rejoins the plan.' % d)
            if self.roles.get(d) == 'relay' and self.chain:
                self.release_chain()
        self.state[d] = s
        self.seen[d] = self.now()
        if d in self.reserves and d not in self.plan.alive and self.roles[d] == 'scout' and d not in self.chain:
            self.plan.add_drone(d, 'scout')
            self.event('INFO', '%s (reserve from the camp) is on the mesh and joins the search.' % d)
            self.dispatch('%s joined' % d)
        if s['state'] == 'CRASHED':
            self.crashed.add(d)
            self.lose(d, s.get('why') or 'crash reported')
            return
        if d in self.retired:
            return
        if s.get('battery', 1.0) < LOW_BATTERY and self.phase in ('DEPLOY', 'SEARCH'):
            self.retire(d, s)
            return
        t = self.plan.owned(d)
        here, prev = (s['x'], s['y']), self.last_xy.get(d)
        self.last_xy[d] = here
        if (t and t.released and t.role == 'scout' and s['sector_id'] == t.tid and prev and s['agl'] < 35.0
                and math.dist(prev, here) < 40.0):
            self.smap.observe(prev, here, self.footprint, POD)
        if t and t.released and s['sector_id'] == t.tid:
            done = self.plan.progress(d, t.end if s['state'] == 'HOLDING' else s['waypoint_index'])
            if done:
                self.event('INFO', '%s finished %s' % (d, done.tid))
                self.dispatch('%s finished %s' % (d, done.tid))

    def positions(self):
        return {d: (s['x'], s['y']) for d, s in self.state.items() if d not in self.lost}

    def lose(self, d, why):
        if d in self.lost:
            return
        self.lost.add(d)
        self.event('ALERT', '%s LOST (%s).' % (d, why))
        if d == self.host:
            self.host = self.standby
            self.event('ALERT', 'Mapper hosting the planner is down. Planner moved to %s.' % self.host)
        rid = self.plan.lose(d)
        if rid:
            t = self.plan.tasks[rid]
            self.event('WARN', 'Unflown part of %s (from waypoint %d) is back in the pool as %s.' % (t.root, t.start, rid))
        if self.roles.get(d) == 'scout':
            self.reserve_due[d] = self.now() + (0.0 if d in self.crashed else RESERVE_GRACE_S)
        if self.roles.get(d) == 'relay' and self.phase in ('DEPLOY', 'SEARCH'):
            self.relay_down = self.now() + (0.0 if d in self.crashed else RESERVE_GRACE_S)
            self.event('ALERT', 'Relay-Anchor %s down: the 4 km backhaul is gone and the debris field lies beyond a drone '
                                "mesh radio's 500 m reach to the tower. Building a chain of mesh relay stand-ins." % d)
        if d in self.chain:
            del self.chain[d]
        self.dispatch('%s lost' % d)

    def run_verifies(self):
        """Sensor-cued re-tasking: an RGB-only candidate gets a thermal look."""
        if self.phase != 'SEARCH':
            return
        for p in list(self.verify_q):
            busy = {d for d in self.plan.alive if (self.plan.owned(d) or Task('', '', '', [])).kind == 'verify'}
            cands = [d for d in self.plan.alive if self.roles.get(d) == 'scout' and d not in busy and d in self.state
                     and self.state[d].get('z', 0) > 5.0 and (d in self.launched or d in self.reserves)]
            if not cands:
                return
            d = min(cands, key=lambda d: math.hypot(self.state[d]['x'] - p['x'], self.state[d]['y'] - p['y']))
            sx, sy = self.state[d]['x'], self.state[d]['y']
            L = math.hypot(p['x'] - sx, p['y'] - sy) or 1.0
            if L > VERIFY_MAX_M:
                continue
            ux, uy = (p['x'] - sx) / L, (p['y'] - sy) / L
            z = self.cfg['scout_agl_m']
            path = [(p['x'] - 30.0 * ux, p['y'] - 30.0 * uy, z), (p['x'] + 8.0 * ux, p['y'] + 8.0 * uy, z)]
            t = Task('VERIFY-' + p['id'], 'VERIFY-' + p['id'], 'scout', path, kind='verify')
            rid = self.plan.interrupt(d, t)
            self.verify_q.remove(p)
            self.send_path(d, t, quiet=True)
            self.event('INFO', '%s: RGB-only candidate. %s diverts for a thermal re-check (%.0f m away)%s.'
                       % (p['id'], d, L, (', its sweep resumes as %s' % rid) if rid else ''))

    def request_reserves(self):
        for d, due in list(self.reserve_due.items()):
            if d not in self.lost:
                del self.reserve_due[d]                  # it came back before a reserve was needed
                continue
            if self.now() < due:
                continue
            del self.reserve_due[d]
            spare = [r for r in self.reserves if r not in self.requested and r not in self.lost]
            if spare:
                r = spare[0]
                self.requested[r] = d
                self.send('base', 'reserve_request', {'reserve': r, 'replaces': d})
                self.event('ALERT', 'Requesting reserve %s from the camp to replace %s. Until it arrives the others cover the gap.' % (r, d))
            else:
                self.event('WARN', 'No reserve Scouts left at the camp: the remaining drones cover %s\'s work.' % d)

    # planning
    def coverage(self, root):
        t = self.plan.tasks[root]
        a, b, hw = t.geom
        seen = None
        for x0, y0, res, w, h, z, _ in self.maps.values():
            key = (root, x0, y0, w, h)
            if key not in self._cells:
                c = sector_cells(a, b, hw, x0, y0, res, w, h)
                self._cells[key] = (np.array([q[0] for q in c], int), np.array([q[1] for q in c], int))
            ii, jj = self._cells[key]
            if len(ii):
                v = z[ii, jj]
                seen = v if seen is None else (seen | v)
        return float(seen.mean()) if seen is not None and len(seen) else 0.0

    def ready(self, root):
        t = self.plan.tasks[root]
        return (not t.needs_map) or self.coverage(root) >= self.cfg['release_coverage']

    def retire(self, d, s):
        self.retired.add(d)
        rid = self.plan.lose(d)
        self.event('WARN', '%s battery %.0f%%: handing its work back%s and returning to the camp.'
                   % (d, 100 * s['battery'], (' (as %s)' % rid) if rid else ''))
        px, py = self.pads[d]
        self.send(d, 'waypoints', {'sector_id': 'RTB', 'plan_version': 8000, 'x': [s['x'], px], 'y': [s['y'], py],
                                   'z': [35.0, 35.0], 'start_index': 0, 'land_at_end': True, 'altitude_mode': 'AGL'})
        if self.roles.get(d) == 'scout':
            self.reserve_due[d] = self.now()
            self.lost.add(d)
        self.dispatch('%s retired' % d)

    def dispatch(self, reason):
        if self.phase not in ('DEPLOY', 'SEARCH'):
            return
        eligible = {d for d in self.plan.alive if d in self.launched or d in self.reserves}
        tot = max(1e-9, 1.0 - self.smap.pos)

        def value(t):
            return VALUE_M * self.smap.mass_in(t.geom[0], t.geom[1], t.geom[2]) / tot if t.role == 'scout' and t.geom else 0.0
        for d, t in self.plan.assign(self.positions(), self.ready, only=eligible, value_fn=value).items():
            self.send_hold_or_path(d, t)
            self.overwatching.discard(d)
        self.release()
        pos = self.positions()
        for d in sorted(eligible):
            if self.plan.owned(d) or any(t.status == 'OPEN' and t.role == self.roles[d] for t in self.plan.tasks.values()):
                continue
            r = self.plan.steal(d, pos)
            if r:
                v, nt = r
                self.event('INFO', '%s takes the far half of %s from %s (legs %d-%d), so both finish together.'
                           % (d, v.root, v.owner, nt.start, nt.end - 1))
                self.send_path(v.owner, v, quiet=True)
                self.send_path(d, nt)
                self.overwatching.discard(d)
            elif self.roles[d] == 'mapper' and d not in self.overwatching and self.phase == 'SEARCH':
                if not self.refine_added:
                    self.add_refinement()
                    return self.dispatch('refine')
                self.overwatch(d)
        if self.plan.finished() and self.phase == 'SEARCH':
            self.return_all()

    def send_hold_or_path(self, d, t):
        if t.needs_map and not self.ready(t.root):
            a = t.path[t.start]
            self.send(d, 'waypoints', {'sector_id': 'HOLD-' + t.tid, 'plan_version': self.plan.version, 'x': [a[0]], 'y': [a[1]],
                                       'z': [self.cfg['hold_agl_m'] + self.layer(d)], 'start_index': 0, 'land_at_end': False, 'altitude_mode': 'AGL'})
            self.event('INFO', '%s -> holds over %s until the lidar map covers it' % (d, t.root))
        else:
            self.send_path(d, t)

    def send_path(self, d, t, quiet=False):
        mode = 'AGL_GROUND' if t.role == 'mapper' else 'AGL'
        path = t.path[:t.end]
        dz = self.layer(d)
        self.send(d, 'waypoints', {'sector_id': t.tid, 'plan_version': self.plan.version, 'x': [q[0] for q in path],
                                   'y': [q[1] for q in path], 'z': [float(q[2]) + dz for q in path], 'start_index': max(t.start, t.done),
                                   'land_at_end': False, 'altitude_mode': mode})
        t.released = True
        if quiet:
            return
        what = 'lidar mapping pass' if t.role == 'mapper' else 'search sweep'
        self.event('INFO', '%s -> %s %s (%d legs from #%d, %.0f m above the %s)' % (
            d, what, t.tid, t.end - t.start, t.start, t.path[0][2], 'ground' if mode == 'AGL_GROUND' else 'mapped surface'))

    def add_refinement(self):
        self.refine_added = True
        line = np.array(self.lay['corridor']['line'], float)
        mid = len(line) // 2
        for k, part in enumerate((line[:mid + 1], line[mid:])):
            path = self.offset_passes(part, 72.0, self.cfg['mapper_agl_m'])
            self.plan.add_task('MR%d' % (k + 1), 'mapper', path, geom=(path[0][:2], path[len(path) // 2 - 1][:2], 60.0))
        self.event('INFO', 'Main lidar passes done: Mappers add edge passes (+-72 m) to thicken the map before overwatch.')

    def layer(self, d):
        if self.roles.get(d) != 'scout':
            return 0.0
        return 3.0 * ((int(d.rsplit('_', 1)[1]) - 1) % 4)

    def overwatch(self, d):
        line = self.lay['corridor']['line']
        k = sorted(m for m in self.roles if self.roles[m] == 'mapper').index(d)
        q = line[int((k + 1) * (len(line) - 1) / 3)]
        self.overwatching.add(d)
        self.send(d, 'waypoints', {'sector_id': 'OVERWATCH', 'plan_version': self.plan.version + 500 + k, 'x': [q[0]], 'y': [q[1]],
                                   'z': [self.cfg['mapper_agl_m'] + 20.0], 'start_index': 0, 'land_at_end': False,
                                   'altitude_mode': 'AGL_GROUND'})
        self.event('INFO', '%s finished mapping: overwatch %d m over the corridor, a high mesh hop and a spare Brain host '
                           'on station (its lidar rests).' % (d, self.cfg['mapper_agl_m'] + 20))

    def release(self):
        for t in self.plan.releasable(self.ready):
            if t.needs_map and t.root not in self.released_sent:
                self.released_sent.add(t.root)
                self.event('INFO', 'Lidar map covers %s (%.0f%%): Scouts cleared to sweep it %d m above the real surface.'
                           % (t.root, 100 * self.coverage(t.root), self.cfg['scout_agl_m']))
            self.send_path(t.owner, t)

    def return_all(self):
        self.phase = 'RTB'
        self.event('INFO', 'Search complete: %.0f%% of the corridor swept. All drones returning to the camp.' % (100 * self.plan.coverage('scout')))
        for k, d in enumerate(sorted(d for d in self.state if d not in self.lost)):
            st, (px, py) = self.state[d], self.pads[d]
            z = 30.0 + 7.0 * k
            self.send(d, 'waypoints', {'sector_id': 'RTB', 'plan_version': 9000 + k, 'x': [st['x'], px], 'y': [st['y'], py],
                                       'z': [z, z], 'start_index': 0, 'land_at_end': True, 'altitude_mode': 'AGL'})

    def tick(self):
        t = self.now()
        if self.phase == 'DEPLOY':
            dt = t - self.t_alert
            order = [(0.0, self.relays), (5.0, [d for d in self.roles if self.roles[d] == 'mapper' and d not in self.reserves]),
                     (10.0, [d for d in self.roles if self.roles[d] == 'scout' and d not in self.reserves])]
            for t0, group in order:
                if dt >= t0 and not set(group) <= self.launched:
                    self.launched |= set(group)
                    if group is self.relays:
                        self.relay_tick()
                    else:
                        self.dispatch('deploy')
            if dt >= 10.0:
                self.phase = 'SEARCH'
                self.dispatch('search')
        if self.phase in ('DEPLOY', 'SEARCH'):
            self.release()
            for d in list(self.seen):
                if d not in self.lost and t - self.seen[d] > self.cfg['heartbeat_timeout_s']:
                    self.lose(d, 'silent on the mesh for %.0f s' % (t - self.seen[d]))
            self.request_reserves()
            self.run_verifies()
            idle = [d for d in self.plan.alive if not self.plan.owned(d) and (d in self.launched or d in self.reserves)]
            open_roles = {x.role for x in self.plan.tasks.values() if x.status == 'OPEN'}
            if self.phase == 'SEARCH' and any(d not in self.overwatching or self.roles[d] in open_roles for d in idle):
                self.dispatch('rebalance')
            if self.plan.finished() and self.phase == 'SEARCH':
                self.return_all()
        if self.phase == 'RTB':
            live = [d for d in self.state if d not in self.lost]
            if live and all(self.state[d]['state'] == 'LANDED' for d in live):
                self.phase = 'COMPLETE'
                self.event('INFO', 'All drones landed at the camp. Mission complete.')

    def relay_tick(self):
        if self.phase not in ('DEPLOY', 'SEARCH'):
            return
        tw = self.lay['tower']
        pts = [(s['x'], s['y']) for d, s in self.state.items()
               if d not in self.lost and self.roles.get(d) != 'relay' and d not in self.chain and s['z'] > 8]
        if not pts:
            c = self.lay['corridor']['line'][len(self.lay['corridor']['line']) // 2]
            pts = [tuple(c)]
        cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
        cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
        gx, gy = cx, cy
        if self.terrain is not None:
            top = (tw['x'], tw['y'], tw['z'])
            for k in range(11):
                gx, gy = cx + (tw['x'] - cx) * k / 10, cy + (tw['y'] - cy) * k / 10
                z = self.terrain.surface(gx, gy, ground_only=True)[0] + self.cfg['relay_agl_m']
                if self.terrain.line_of_sight((gx, gy, z), top):
                    break
        for r in self.relays:
            if r not in self.lost:
                self.send(r, 'waypoints', {'sector_id': 'RELAY', 'plan_version': 0, 'x': [gx], 'y': [gy], 'z': [self.cfg['relay_agl_m']],
                                           'start_index': 0, 'land_at_end': False, 'altitude_mode': 'AGL_GROUND'})
        self.chain_tick(pts)

    def chain_tick(self, pts):
        """Relay-Anchor down: stand-ins hold evenly spaced points on the line from the tower to the middle of the swarm,."""
        if self.relay_down is None or self.now() < self.relay_down or any(r not in self.lost for r in self.relays):
            return
        tw = self.lay['tower']
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        dist = math.hypot(cx - tw['x'], cy - tw['y'])
        need = max(0, math.ceil(dist / RELAY_HOP_M) - 1)
        while len(self.chain) < need:
            spare = [r for r in self.reserves if r not in self.requested and r not in self.lost and r not in self.plan.alive]
            idle_m = sorted(m for m in self.overwatching if m not in self.lost and m not in self.chain and m != self.host)
            if spare:
                r = spare[0]
                self.requested[r] = self.relays[0]
                self.chain[r] = 'reserve'
                self.send('base', 'reserve_request', {'reserve': r, 'replaces': self.relays[0]})
                self.event('ALERT', 'Requesting reserve %s from the camp as a mesh relay stand-in (%d of %d hops to the tower).'
                           % (r, len(self.chain), need))
            elif idle_m:
                m = idle_m[0]
                self.overwatching.discard(m)
                self.plan.lose(m)
                self.chain[m] = 'mapper'
                self.event('ALERT', '%s leaves overwatch to hold a mesh relay point (%d of %d hops to the tower).' % (m, len(self.chain), need))
            else:
                break
        near = lambda d: math.hypot(self.state[d]['x'] - tw['x'], self.state[d]['y'] - tw['y']) if d in self.state else 0.0  # noqa: E731
        ds = sorted(self.chain, key=near)
        for k, d in enumerate(ds):
            f = (k + 1) / (len(ds) + 1)
            z = self.cfg['relay_agl_m'] if self.chain[d] == 'reserve' else self.cfg['mapper_agl_m'] + 20.0
            self.send(d, 'waypoints', {'sector_id': 'RELAY', 'plan_version': 0, 'x': [tw['x'] + (cx - tw['x']) * f],
                                       'y': [tw['y'] + (cy - tw['y']) * f], 'z': [z], 'start_index': 0, 'land_at_end': False,
                                       'altitude_mode': 'AGL_GROUND'})

    def release_chain(self):
        for d, how in self.chain.items():
            if d not in self.lost and d in self.state:
                self.plan.add_drone(d, 'mapper' if how == 'mapper' else 'scout')
        self.event('INFO', 'Relay-Anchor back on the mesh: stand-ins %s return to their own work.' % ', '.join(sorted(self.chain)))
        self.chain.clear()
        self.relay_down = None
        self.dispatch('relay back')

    def report(self):
        tasks = [{'id': t.tid, 'root': t.root, 'role': t.role, 'status': t.status, 'owner': t.owner, 'progress': round(t.progress, 3),
                  'released': t.released, 'needs_map': t.needs_map, 'map_coverage': round(self.coverage(t.root), 3) if t.needs_map else None,
                  'start': t.start, 'end': t.end, 'done': t.done, 'n': len(t.path), 'root_progress': round(self.plan.root_progress(t.root), 3),
                  'geom': t.geom} for t in self.plan.tasks.values()]
        self.send('base', 'plan', {'phase': self.phase, 'host': self.host, 'version': self.plan.version,
                                   'coverage': round(self.plan.coverage('scout'), 3), 'map_task_coverage': round(self.plan.coverage('mapper'), 3),
                                   'overwatch': sorted(self.overwatching), 'retired': sorted(self.retired),
                                   'pos': round(self.smap.pos, 4),
                                   'sector_mass': {t.tid: round(self.smap.mass_in(*t.geom), 4) for t in self.plan.tasks.values()
                                                   if t.tid == t.root and t.role == 'scout' and t.geom},
                                   'tasks': tasks, 'lost': sorted(self.lost),
                                   'map_coverage': {k: round(m[6], 3) for k, m in self.maps.items()}})


def main():
    rclpy.init()
    rclpy.spin(Brain())


if __name__ == '__main__':
    main()
