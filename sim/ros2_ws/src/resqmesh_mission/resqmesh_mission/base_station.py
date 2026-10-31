"""Rescue base at the Chooralmala camp."""
import base64
import json
import math
import os
import subprocess
import zlib

import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import String

from resqmesh_interfaces.msg import HeightMap, MeshFrame, MissionEvent

from .geo import enu_to_latlon
from .rescue_route import DEBRIS_MPS, plan as rescue_plan
from .triangulate import ray_dist, triangulate

REPORTED_MISSING = 6
FUSE_M = 14.0
RAY_M = 3.0
MAX_RAYS = 60

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class BaseStation(Node):
    def __init__(self):
        super().__init__('base_station')
        for k, v in (('fleet', ''), ('layout', ''), ('sim_dir', os.path.expanduser('~/resqmesh/sim'))):
            self.declare_parameter(k, v)
        self.sim = self.get_parameter('sim_dir').value
        fl = yaml.safe_load(open(self.get_parameter('fleet').value))
        self.fleet_cfg = {d['name']: d for d in fl['drones']}
        self.reserves_left = [d['name'] for d in fl['drones'] if d.get('reserve')]
        self.lay = json.load(open(self.get_parameter('layout').value))
        o = self.lay['origin']
        self.lat0, self.lon0 = o['lat'], o['lon']
        self.fleet, self.persons, self.plan, self.maps = {}, [], {}, {}
        self.rays = {}
        self.phase, self.t_alert = 'STANDBY', None
        self.ev_pub = self.create_publisher(MissionEvent, '/swarm/events', 50)
        self.pub = {k: self.create_publisher(String, '/base/' + k, LATCHED if k in ('persons', 'story', 'rescue') else 10)
                    for k in ('fleet', 'persons', 'plan', 'story', 'mapimg', 'mesh', 'cloud', 'vision', 'history', 'eventlog', 'rescue')}
        self.log, self.history, self.totals = [], [], {}
        self.tower_out = self.create_publisher(MeshFrame, '/tower/mesh/out', 20)
        self.create_subscription(MeshFrame, '/tower/mesh/in', self.on_frame, 200)
        self.create_subscription(String, '/disaster/landslide', self.on_landslide, LATCHED)
        self.create_subscription(String, '/swarm/events_raw', self.on_raw, 20)
        for m in ('mapper_1', 'mapper_2'):
            self.create_subscription(HeightMap, '/%s/map/height' % m, self.on_map, 2)
        self.create_timer(0.5, self.publish_fleet)
        self.create_timer(1.0, self.publish_story)
        self.create_timer(3.0, self.publish_map)
        # engineering telemetry for the dashboard (read directly, not over the mesh)
        self.mesh_stats, self.vision, self.clouds = {}, {}, {}
        for n in list(self.fleet_cfg) + ['tower']:
            self.create_subscription(String, '/%s/mesh/stats' % n, self.on_mesh_stats, 5)
            self.create_subscription(String, '/%s/vision/stats' % n, self.on_vision, 5)
        for m in ('mapper_1', 'mapper_2'):
            self.create_subscription(PointCloud2, '/%s/map/cloud' % m, lambda c, m=m: self.clouds.__setitem__(m, c), 1)
        self.create_timer(1.0, self.publish_mesh)
        self.create_timer(4.0, self.publish_cloud)
        self.create_subscription(String, '/mesh/traffic', lambda m: self.totals.update(json.loads(m.data)['totals']), 5)
        self.create_timer(5.0, self.sample_history)
        self.create_timer(3.0, lambda: self.pub['eventlog'].publish(String(data=json.dumps(self.log[-400:]))))
        self.event('INFO', 'Rescue base online at the Chooralmala camp. Swarm on standby on the pads.')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def event(self, level, text, source='base'):
        m = MissionEvent(level=level, source=source, text=text)
        m.header.stamp = self.get_clock().now().to_msg()
        self.ev_pub.publish(m)
        self.log.append({'t': round(self.now() - self.t_alert, 1) if self.t_alert else None, 'level': level, 'source': source,
                         'text': text})

    def sample_history(self):
        if not self.t_alert or self.phase == 'COMPLETE' and self.history and self.history[-1].get('phase') == 'COMPLETE':
            return
        alive = sum(1 for p in self.persons if p['condition'] == 'ALIVE')
        dead = sum(1 for p in self.persons if p['condition'] == 'DECEASED_SUSPECTED')
        mc = list((self.plan.get('map_coverage') or {}).values())
        tot = self.totals
        sent = tot.get('delivered', 0) + tot.get('lost', 0) + tot.get('blocked', 0)
        t = self.now()
        self.history.append({'t': round(t - self.t_alert, 1), 'phase': self.phase, 'found': alive + dead, 'alive': alive, 'dead': dead,
                             'cand': len(self.persons) - alive - dead, 'cov': self.plan.get('coverage') or 0.0, 'pos': self.plan.get('pos'),
                             'map': round(sum(mc) / len(mc), 3) if mc else 0.0,
                             'pdr': round(tot.get('delivered', 0) / sent, 4) if sent else None,
                             'delivered': tot.get('delivered', 0), 'lost': tot.get('lost', 0), 'blocked': tot.get('blocked', 0),
                             'airborne': sum(1 for s in self.fleet.values() if s.get('z', 0) > 3 and s.get('state') not in ('CRASHED', 'LANDED')
                                             and t - s['t'] < 12)})
        self.pub['history'].publish(String(data=json.dumps(self.history)))

    # the disaster
    def on_raw(self, m):
        e = json.loads(m.data)
        self.event(e['level'], e['text'], e.get('source', 'disaster'))

    def on_landslide(self, m):
        if self.phase != 'STANDBY':
            return
        self.phase, self.t_alert = 'DEPLOY', self.now()
        self.event('ALERT', 'District control room: landslide at Mundakkai. Alerting the swarm through the tower.')
        for k in range(3):
            self.create_timer(0.1 + 2.0 * k, self._alert_once)

    def _alert_once(self):
        self.tower_out.publish(MeshFrame(final='*', kind='alert', payload=json.dumps({'what': 'landslide', 'zone': 'Mundakkai'})))

    # mesh in
    def on_frame(self, f):
        p = json.loads(f.payload)
        if f.kind == 'status':
            p['t'] = self.now()
            p['hops'] = f.hops + 1
            self.fleet[p['drone']] = p
        elif f.kind == 'sighting':
            self.fuse(p, f.hops + 1)
        elif f.kind == 'event':
            self.event(p['level'], p['text'], p.get('source', 'swarm'))
        elif f.kind == 'plan':
            self.plan = p
            if p.get('phase') and self.phase != 'COMPLETE':
                self.phase = p['phase'] if p['phase'] != 'STANDBY' else self.phase
            self.pub['plan'].publish(String(data=json.dumps(p)))
            self.check_rechecks(p)
        elif f.kind == 'reserve_request':
            self.launch_reserve(p['reserve'], p['replaces'])

    def merge_duplicates(self, q):
        """Two thermal pins whose running averages drifted within FUSE_M of each other are one person: keep the older."""
        for o in list(self.persons):
            if o is q or o['condition'] == 'UNKNOWN':
                continue
            d = math.hypot(o['x'] - q['x'], o['y'] - q['y'])
            if d >= FUSE_M and not (d < 45.0 and self.rays_meet(self.rays.get(o['id']), q)):
                continue
            keep, drop = (o, q) if o['first_seen'] <= q['first_seen'] else (q, o)
            n = keep['n'] + drop['n']
            keep['xg'] = (keep['xg'] * keep['n'] + drop['xg'] * drop['n']) / n
            keep['yg'] = (keep['yg'] * keep['n'] + drop['yg'] * drop['n']) / n
            keep['n'] = n
            self.add_rays(keep, self.rays.pop(drop['id'], []))
            self.locate(keep)
            keep['max_temp_k'] = max(keep['max_temp_k'], drop['max_temp_k'])
            keep['condition'] = 'ALIVE' if keep['max_temp_k'] >= 303.0 else 'DECEASED_SUSPECTED'
            keep['sensors'] = sorted(set(keep['sensors']) | set(drop['sensors']))
            keep['lat'], keep['lon'] = enu_to_latlon(keep['x'], keep['y'], self.lat0, self.lon0)
            self.persons.remove(drop)
            self.event('INFO', '%s and %s are the same person (pins %.0f m apart, %s): merged into %s.'
                       % (keep['id'], drop['id'], d, 'bearing rays meet' if d >= FUSE_M else 'close', keep['id']))
            return

    # geolocation: multi-view triangulation
    @staticmethod
    def rays_meet(rays, q):
        if not rays or q.get('fix') != 'triangulated':
            return False
        return float(np.median([ray_dist(r, (q['x'], q['y'], q['z'])) for r in rays])) < RAY_M

    def add_rays(self, q, rays):
        r = self.rays.setdefault(q['id'], [])
        r.extend(rays)
        if len(r) > MAX_RAYS:
            del r[20:len(r) - (MAX_RAYS - 20)]

    def locate(self, q):
        q['x'], q['y'], q['fix'] = q['xg'], q['yg'], 'ground'
        rays = self.rays.get(q['id'])
        if not rays:
            return
        r = triangulate(rays, (q['xg'], q['yg'], q.get('zg', 0.0)))
        if r is None:
            return
        x, y, z, rms, spread, used = r
        if rms < 2.5 and used >= 3 and math.hypot(x - q['xg'], y - q['yg']) < 40.0 and -8.0 < z - q.get('zg', z) < 10.0:
            q['x'], q['y'], q['z'], q['fix'] = x, y, z, 'triangulated'
            q['fix_rms_m'], q['fix_spread_deg'], q['fix_rays'] = round(rms, 2), round(spread, 1), used

    def check_rechecks(self, plan):
        for t in plan.get('tasks', []):
            if not t['id'].startswith('VERIFY-') or t['status'] != 'DONE':
                continue
            q = next((q for q in self.persons if q['id'] == t['id'][7:]), None)
            if q and q['condition'] == 'UNKNOWN' and not q.get('rechecked'):
                q['rechecked'] = True
                self.event('INFO', '%s thermal re-check by %s: no heat signature there. Most likely not a person '
                                   '(kept on the board in grey for the ground team).' % (q['id'], t['owner']))
                self.pub['persons'].publish(String(data=json.dumps(self.persons)))

    def fuse(self, s, hops):
        rays = s.get('rays') or []
        own = triangulate(rays, (s['x'], s['y'], s.get('z') or 0.0)) if len(rays) >= 3 else None
        sx, sy = (own[0], own[1]) if own and own[3] < 2.0 and math.hypot(own[0] - s['x'], own[1] - s['y']) < 40.0 else (s['x'], s['y'])
        best = None
        for q in self.persons:
            d = math.hypot(q['x'] - sx, q['y'] - sy)
            if d >= FUSE_M and d < 45.0 and self.rays_meet(rays, q):
                d = FUSE_M * 0.99
            if d < FUSE_M and (best is None or d < best[0]):
                best = (d, q)
        t = self.now()
        if best is None:
            q = {'id': 'PERSON-%02d' % (len(self.persons) + 1), 'x': sx, 'y': sy, 'xg': s['x'], 'yg': s['y'], 'n': 0,
                 'condition': 'UNKNOWN', 'max_temp_k': 0.0, 'sensors': [], 'first_seen': t, 'found_by': s['source_drone'],
                 'via_hops': hops, 'fix': 'ground'}
            self.persons.append(q)
            new = True
        else:
            q, new = best[1], False
        n = q['n']
        q['xg'], q['yg'] = (q['xg'] * n + s['x']) / (n + 1), (q['yg'] * n + s['y']) / (n + 1)
        if s.get('z') is not None:
            q['zg'] = (q.get('zg', s['z']) * n + s['z']) / (n + 1)
        q['n'] = n + 1
        self.add_rays(q, rays)
        self.locate(q)
        q['last_seen'] = t
        parts = s['sensor'].split('+')
        for x in parts:
            if x not in q['sensors']:
                q['sensors'].append(x)
        thermal = 'thermal' in parts and s['max_temp_k'] > 0
        if thermal:
            q['max_temp_k'] = max(q['max_temp_k'], s['max_temp_k'])
            q['condition'] = 'ALIVE' if q['max_temp_k'] >= 303.0 else 'DECEASED_SUSPECTED'
        q['lat'], q['lon'] = enu_to_latlon(q['x'], q['y'], self.lat0, self.lon0)
        q['t_since_alert'] = round(t - self.t_alert, 1) if self.t_alert else None
        if thermal:
            self.merge_duplicates(q)
        if new and not thermal:
            near = any(o is not q and o['condition'] != 'UNKNOWN' and math.hypot(o['x'] - q['x'], o['y'] - q['y']) < 25.0
                       for o in self.persons)
            self.event('INFO', '%s: RGB candidate from %s at %.6f N, %.6f E; %s'
                       % (q['id'], s['source_drone'], q['lat'], q['lon'],
                          'next to a confirmed person, no re-check needed' if near else 'asking the swarm for a thermal re-check'))
            if not near:
                self.tower_out.publish(MeshFrame(final='brain', kind='verify', payload=json.dumps({'id': q['id'], 'x': q['x'], 'y': q['y']})))
        elif new:
            c = q['max_temp_k'] - 273.15
            what = 'ALIVE (body heat %.1f C)' % c if q['condition'] == 'ALIVE' else 'no live heat signature (%.1f C): likely deceased, verify' % c
            self.event('ALERT' if q['condition'] == 'ALIVE' else 'WARN', '%s %s. Found by %s at %.6f N, %.6f E (%d hops to base)'
                       % (q['id'], what, s['source_drone'], q['lat'], q['lon'], hops))
            q['announced'] = q['condition']
        elif thermal and q.get('announced') != q['condition']:
            q['announced'] = q['condition']
            txt = ('ALIVE: body heat %.1f C' % (q['max_temp_k'] - 273.15) if q['condition'] == 'ALIVE'
                   else 'no live heat signature (body %.1f C): likely deceased, verify' % (q['max_temp_k'] - 273.15))
            self.event('ALERT' if q['condition'] == 'ALIVE' else 'WARN', '%s %s' % (q['id'], txt))
        self.pub['persons'].publish(String(data=json.dumps(self.persons)))
        route = rescue_plan((0.0, 0.0), self.persons)
        for r in route:
            r['lat'], r['lon'] = enu_to_latlon(r['x'], r['y'], self.lat0, self.lon0)
        self.pub['rescue'].publish(String(data=json.dumps({'camp': [0.0, 0.0], 'speed_mps': DEBRIS_MPS, 'route': route})))

    # reserves
    def launch_reserve(self, name, replaces):
        if name not in self.reserves_left:
            return
        self.reserves_left.remove(name)
        last = self.fleet.get(replaces, {})
        pad = self.fleet_cfg[name]['pad']
        eta = 35 + math.hypot(last.get('x', 0) - pad[0], last.get('y', -800) - pad[1]) / 10.0
        self.event('ALERT', 'Camp launching reserve %s from its pad to replace %s (on station in ~%.0f s). '
                            'Until then the swarm re-plans around the gap.' % (name, replaces, eta))
        script = os.path.join(self.sim, 'tools', 'launch_drone.sh')
        subprocess.Popen(['bash', script, name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    # dashboard feeds
    def publish_fleet(self):
        t = self.now()
        out = {}
        for d, s in self.fleet.items():
            s = dict(s)
            s['age'] = round(t - s['t'], 1)
            out[d] = s
        self.pub['fleet'].publish(String(data=json.dumps(out)))

    def publish_story(self):
        alive = sum(1 for p in self.persons if p['condition'] == 'ALIVE')
        dead = sum(1 for p in self.persons if p['condition'] == 'DECEASED_SUSPECTED')
        st = {'phase': self.phase, 't_since_alert': round(self.now() - self.t_alert, 1) if self.t_alert else None,
              'persons_found': alive + dead, 'alive': alive, 'deceased_suspected': dead,   # thermal-confirmed
              'unknown': len(self.persons) - alive - dead, 'target': REPORTED_MISSING, 'reserves_at_camp': list(self.reserves_left),
              'brain_host': self.plan.get('host'), 'coverage': self.plan.get('coverage'), 'map_coverage': self.plan.get('map_coverage'),
              'pos': self.plan.get('pos')}
        self.pub['story'].publish(String(data=json.dumps(st)))

    def on_map(self, m):
        self.maps[m.source] = m

    def on_mesh_stats(self, m):
        s = json.loads(m.data)
        s['t'] = self.now()
        self.mesh_stats[s['node']] = s

    def on_vision(self, m):
        s = json.loads(m.data)
        self.vision[s['drone']] = s

    def publish_mesh(self):
        t = self.now()
        nodes = {n: dict(s, age=round(t - s['t'], 1)) for n, s in self.mesh_stats.items()}
        self.pub['mesh'].publish(String(data=json.dumps(nodes)))
        self.pub['vision'].publish(String(data=json.dumps(self.vision)))

    def publish_cloud(self):
        pts = []
        for c in self.clouds.values():
            p = point_cloud2.read_points_numpy(c, field_names=('x', 'y', 'z'), skip_nans=True)
            if len(p):
                pts.append(p)
        if not pts:
            return
        p = np.concatenate(pts)
        q = np.unique(np.round(p / 0.5).astype(np.int32), axis=0)
        if len(q) > 16000:
            q = q[np.random.default_rng(1).choice(len(q), 16000, replace=False)]
        self.pub['cloud'].publish(String(data=json.dumps({'res': 0.5, 'n': int(len(q)), 'p': q.ravel().tolist()})))

    def publish_map(self):
        """Lidar surface map as a small shaded PNG for the dashboard overlay."""
        if not self.maps:
            return
        m0 = next(iter(self.maps.values()))
        z = np.full((m0.height, m0.width), np.nan, np.float32)
        for m in self.maps.values():
            if m.width == m0.width and m.height == m0.height:
                zz = np.asarray(m.z, dtype=np.float32).reshape(m.height, m.width)
                z = np.where(np.isnan(z), zz, np.fmax(z, zz))
        seen = np.isfinite(z)
        if not seen.any():
            return
        lo, hi = np.nanpercentile(z, 2), np.nanpercentile(z, 98)
        v = np.clip((np.nan_to_num(z, nan=lo) - lo) / max(1e-3, hi - lo), 0, 1)
        gy, gx = np.gradient(np.nan_to_num(z, nan=float(lo)))
        shade = np.clip(0.55 + 0.45 * (-gx + gy) / np.sqrt(1 + gx * gx + gy * gy), 0, 1)
        rgb = np.stack([0.25 + 0.55 * v, 0.45 + 0.35 * v, 0.75 - 0.35 * v], -1) * shade[..., None]
        a = np.where(seen, 200, 0).astype(np.uint8)
        img = np.dstack([(rgb * 255).astype(np.uint8), a])[::-1]          # row 0 = north for the canvas
        png = self.to_png(img)
        self.pub['mapimg'].publish(String(data=json.dumps({'x0': m0.origin_x, 'y0': m0.origin_y, 'res': m0.resolution,
                                                           'w': m0.width, 'h': m0.height, 'png': base64.b64encode(png).decode()})))

    @staticmethod
    def to_png(rgba):
        h, w, _ = rgba.shape
        raw = b''.join(b'\x00' + rgba[i].tobytes() for i in range(h))

        def chunk(t, d):
            c = zlib.crc32(t + d) & 0xffffffff
            return len(d).to_bytes(4, 'big') + t + d + c.to_bytes(4, 'big')
        hdr = w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + bytes([8, 6, 0, 0, 0])
        return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', hdr) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')


def main():
    rclpy.init()
    rclpy.spin(BaseStation())


if __name__ == '__main__':
    main()
