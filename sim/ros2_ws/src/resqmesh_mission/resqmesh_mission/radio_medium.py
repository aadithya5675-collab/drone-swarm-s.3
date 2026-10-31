"""The radio channel of the disaster mesh (the physics side, not a router)."""
import json
import math
import os
import random
from collections import OrderedDict

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import String

from resqmesh_interfaces.msg import LinkState, MeshFrame

from .terrain import Terrain

RANGE = {('mesh', 'mesh'): 450.0, ('mesh', 'tower'): 500.0, ('relay', 'mesh'): 650.0, ('relay', 'tower'): 4000.0,
         ('relay', 'relay'): 4000.0, ('tower', 'tower'): 0.0}
MIN_Q = 0.12


def kind(n):
    return 'tower' if n == 'tower' else ('relay' if n.startswith('relay') else 'mesh')


def rng_between(a, b):
    ka, kb = kind(a), kind(b)
    return RANGE.get((ka, kb), RANGE.get((kb, ka), 0.0))


class RadioMedium(Node):
    def __init__(self):
        super().__init__('radio_medium')
        for k, v in (('layout', ''), ('prior', ''), ('nodes', 'scout_1,scout_2,scout_3,scout_4,mapper_1,mapper_2,relay_1'),
                     ('seed', 3)):
            self.declare_parameter(k, v)
        lay = json.load(open(self.get_parameter('layout').value))
        self.terrain = Terrain(self.get_parameter('prior').value)
        t = lay['tower']
        self.pos = {'tower': (t['x'], t['y'], t['z'])}
        self.seen = {'tower': 1e18}
        self.rng = random.Random(self.get_parameter('seed').value)
        self.nodes = self.get_parameter('nodes').value.split(',')
        for n in self.nodes:
            self.create_subscription(PoseStamped, '/%s/pose_enu' % n, lambda m, n=n: self.on_pose(n, m), qos_profile_sensor_data)
        self.create_subscription(String, '/mesh/powered_off', self.on_off, 10)
        self.off = set()
        self.rx = {n: self.create_publisher(MeshFrame, '/mesh/rx/%s' % n, 50) for n in self.nodes + ['tower']}
        self.create_subscription(MeshFrame, '/mesh/tx', self.on_tx, 200)
        self.link_pub = self.create_publisher(LinkState, '/mesh/links', 5)
        self.q = {}
        self.create_timer(0.5, self.update_links)
        self.stats = {'tx': 0, 'delivered': 0, 'lost': 0, 'blocked': 0}
        self.flows = {}
        self.los = {}
        self.traffic_pub = self.create_publisher(String, '/mesh/traffic', 5)
        self.create_timer(1.0, self.publish_traffic)
        self.hops = OrderedDict()
        self.status_n = {}
        self.trace_pub = self.create_publisher(String, '/mesh/trace', 50)
        self.create_subscription(String, '/mesh/delivered', self.on_delivered, 100)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_pose(self, n, m):
        p = m.pose.position
        self.pos[n] = (p.x, p.y, p.z)
        self.seen[n] = self.now()

    def on_off(self, m):
        self.off.add(m.data)

    def alive(self, n):
        return n in self.pos and n not in self.off and (self.now() - self.seen.get(n, 0) < 2.0)

    def update_links(self):
        q = {}
        names = [n for n in self.pos if self.alive(n)]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                R = rng_between(a, b)
                if R <= 0:
                    continue
                d = math.dist(self.pos[a], self.pos[b])
                v = max(0.0, 1.0 - (d / R) ** 2)
                los = v <= 0 or self.terrain.line_of_sight(self.pos[a], self.pos[b])
                if not los:
                    v *= 0.25
                q[a, b] = q[b, a] = v
                self.los[a, b] = self.los[b, a] = los
        self.q = q
        ls = LinkState()
        ls.header.stamp = self.get_clock().now().to_msg()
        for (a, b), v in q.items():
            if a < b:
                ls.node_a.append(a)
                ls.node_b.append(b)
                ls.quality.append(float(v))
                ls.distance_m.append(float(math.dist(self.pos[a], self.pos[b])))
        self.link_pub.publish(ls)

    def publish_traffic(self):
        links = [[a, b, round(v, 3), round(math.dist(self.pos[a], self.pos[b]), 1), bool(self.los.get((a, b), True))]
                 for (a, b), v in self.q.items() if a < b]
        flows = [[s, d, k, n] for (s, d, k), n in self.flows.items()]
        self.flows = {}
        nodes = {n: [round(c, 1) for c in p] for n, p in self.pos.items() if self.alive(n)}
        self.traffic_pub.publish(String(data=json.dumps({'links': links, 'flows': flows, 'totals': self.stats, 'nodes': nodes})))

    def note(self, f, dst, result):
        if f.kind in ('hello', 'ack') or f.dst == '*':
            return
        key = (f.origin, f.msg_id)
        t = self.now()
        r = self.hops.get(key)
        if r is None:
            r = self.hops[key] = {'k': f.kind, 't0': t, 'h': [], 'final': f.final, 'p': self.summary(f)}
            while len(self.hops) > 4000:
                self.hops.popitem(last=False)
        r['h'].append([round(t - r['t0'], 2), f.src, dst, result])

    @staticmethod
    def summary(f):
        try:
            p = json.loads(f.payload)
        except ValueError:
            return {}
        if f.kind == 'sighting':
            return {k: p.get(k) for k in ('source_drone', 'x', 'y', 'condition', 'max_temp_k', 'sensor')}
        if f.kind == 'event':
            return {'text': p.get('text', '')[:120]}
        if f.kind == 'waypoints':
            return {'sector': p.get('sector_id'), 'n': len(p.get('x', []))}
        if f.kind == 'status':
            return {'drone': p.get('drone'), 'state': p.get('state')}
        return {}

    def on_delivered(self, m):
        d = json.loads(m.data)
        r = self.hops.pop((d['o'], d['id']), None)
        if r is None:
            return
        if r['k'] == 'status':                 # 1 Hz per drone: trace one in five
            n = self.status_n[d['o']] = self.status_n.get(d['o'], 0) + 1
            if n % 5:
                return
        r.update({'o': d['o'], 'id': d['id'], 'at': d['at'], 'dt': round(self.now() - r['t0'], 2)})
        self.trace_pub.publish(String(data=json.dumps(r)))

    def on_tx(self, f):
        self.stats['tx'] += 1
        if not self.alive(f.src):
            return
        targets = [b for (a, b), v in self.q.items() if a == f.src and v >= MIN_Q] if f.dst == '*' else [f.dst]
        for t in targets:
            v = self.q.get((f.src, t), 0.0)
            if v < MIN_Q or not self.alive(t):
                if f.dst != '*':
                    self.stats['blocked'] += 1
                    self.note(f, t, 'blocked')
                continue
            if self.rng.random() < 0.02 + 0.35 * (1 - v):
                self.stats['lost'] += 1
                self.note(f, t, 'lost')
                continue
            self.stats['delivered'] += 1
            self.note(f, t, 'ok')
            k = (f.src, t, f.kind)
            self.flows[k] = self.flows.get(k, 0) + 1
            self.rx[t].publish(f)


def main():
    rclpy.init()
    rclpy.spin(RadioMedium())


if __name__ == '__main__':
    main()
