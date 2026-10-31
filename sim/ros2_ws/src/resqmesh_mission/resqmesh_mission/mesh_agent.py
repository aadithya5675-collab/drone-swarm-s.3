"""Mesh router on one node (every drone's companion computer, and the camp tower)."""
import json
import random
from collections import OrderedDict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from resqmesh_interfaces.msg import MeshFrame

HELLO_S, EXPIRE_S, RETRY_S, MAX_AGE_S = 1.0, 6.0, 0.6, 180.0
ETX_WINDOW_S, MAX_COST = 6.0, 40.0


class MeshAgent(Node):
    def __init__(self):
        super().__init__('mesh_agent')
        self.declare_parameter('node', 'scout_1')
        self.declare_parameter('services', '')
        self.me = self.get_parameter('node').value
        self.svcs = set(s for s in self.get_parameter('services').value.split(',') if s)
        self.routes = {}                         # dest -> (cost, next_hop, t_learned, hops)
        self.heard = {}
        self.neigh = {}                          # neighbour -> t_last_hello
        self.queue = OrderedDict()
        self.seen = OrderedDict()                # duplicate filter
        self.msg_id = random.randrange(1 << 30)
        self.powered = True
        self.tx = self.create_publisher(MeshFrame, '/mesh/tx', 200)
        self.app_in = self.create_publisher(MeshFrame, '/%s/mesh/in' % self.me, 100)
        self.stat_pub = self.create_publisher(String, '/%s/mesh/stats' % self.me, 2)
        self.deliv_pub = self.create_publisher(String, '/mesh/delivered', 50)     # for the packet tracer (dashboard)
        self.create_subscription(MeshFrame, '/mesh/rx/%s' % self.me, self.on_rx, 200)
        self.create_subscription(MeshFrame, '/%s/mesh/out' % self.me, self.on_app, 100)
        self.create_subscription(String, '/%s/mesh/services' % self.me, self.on_services, 10)
        self.create_subscription(String, '/mesh/powered_off', self.on_off, 10)
        self.create_timer(HELLO_S * random.uniform(0.9, 1.1), self.hello)
        self.create_timer(0.2, self.pump)
        self.create_timer(2.0, self.stats)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_off(self, m):
        if m.data == self.me:
            self.powered = False
            self.get_logger().warn('radio off: node lost')

    def on_services(self, m):
        name = m.data[1:]
        (self.svcs.add if m.data[0] == '+' else self.svcs.discard)(name)

    # routing
    def table(self):
        t = self.now()
        tab = {self.me: [0.0, 0]}
        for s in self.svcs:
            tab[s] = [0.0, 0]
        for d, (c, nh, tl, h) in list(self.routes.items()):
            if t - tl > EXPIRE_S or t - self.neigh.get(nh, 0) > EXPIRE_S:
                del self.routes[d]
            else:
                tab[d] = [round(c, 2), h]
        return tab

    def etx(self, nb):
        t = self.now()
        hs = [x for x in self.heard.get(nb, []) if t - x < ETX_WINDOW_S]
        self.heard[nb] = hs
        r = min(1.0, len(hs) * HELLO_S / ETX_WINDOW_S)
        return 1.0 / max(r * r, 1.0 / MAX_COST)

    def hello(self):
        if not self.powered:
            return
        self.send_raw(MeshFrame(src=self.me, dst='*', origin=self.me, final='*', kind='hello', ttl=1,
                                payload=json.dumps(self.table())))

    def learn(self, nb, tab):
        t = self.now()
        self.neigh[nb] = t
        self.heard.setdefault(nb, []).append(t)
        link = self.etx(nb)
        for d, v in tab.items():
            if d == self.me or d in self.svcs:
                continue
            c, h = (v[0], v[1]) if isinstance(v, list) else (float(v), int(v))
            cost, hops = c + link, h + 1
            if cost > MAX_COST or hops > 15:     # avoid counting to infinity through a dead node
                continue
            cur = self.routes.get(d)
            if cur is None or cur[1] == nb or cost < 0.9 * cur[0] or t - cur[2] > EXPIRE_S:
                self.routes[d] = (cost, nb, t, hops)

    # frames
    def send_raw(self, f):
        if self.powered:
            f.src = self.me
            self.tx.publish(f)

    def on_app(self, f):
        self.msg_id = (self.msg_id + 1) % (1 << 31)
        f.origin, f.msg_id, f.hops = self.me, self.msg_id, 0
        f.ttl = f.ttl or (4 if f.final == '*' else 12)
        if f.final == '*':
            self.flood(f, first=True)
        else:
            self.queue[(f.origin, f.msg_id)] = [f, self.now(), 0.0]

    def flood(self, f, first=False):
        key = (f.origin, f.msg_id)
        if key in self.seen:
            return
        self.mark(key)
        if not first:
            self.app_in.publish(f)
        if f.ttl > 1:
            g = MeshFrame(dst='*', origin=f.origin, final='*', kind=f.kind, msg_id=f.msg_id, ttl=f.ttl - 1,
                          hops=f.hops + 1, payload=f.payload)
            self.send_raw(g)

    def mark(self, key):
        self.seen[key] = self.now()
        while len(self.seen) > 5000:
            self.seen.popitem(last=False)

    def on_rx(self, f):
        if not self.powered:
            return
        if f.kind == 'hello':
            self.learn(f.src, json.loads(f.payload))
            return
        if f.kind == 'ack':
            self.queue.pop((f.origin, f.msg_id), None)
            return
        if f.final == '*':
            self.flood(f)
            return
        # unicast data: ACK the hop, then deliver or forward
        self.send_raw(MeshFrame(dst=f.src, origin=f.origin, final=f.src, kind='ack', msg_id=f.msg_id, ttl=1))
        key = (f.origin, f.msg_id)
        if key in self.seen:
            return
        self.mark(key)
        if f.final == self.me or f.final in self.svcs:
            self.deliver(f)
        elif f.ttl > 1:
            g = MeshFrame(origin=f.origin, final=f.final, kind=f.kind, msg_id=f.msg_id, ttl=f.ttl - 1,
                          hops=f.hops + 1, payload=f.payload)
            self.queue[key] = [g, self.now(), 0.0]

    def deliver(self, f):
        self.app_in.publish(f)
        self.deliv_pub.publish(String(data=json.dumps({'o': f.origin, 'id': int(f.msg_id), 'k': f.kind, 'at': self.me,
                                                       'final': f.final, 'hops': int(f.hops)})))

    def pump(self):
        """Try every queued frame: send to the best next hop if there is one (store-and-forward otherwise)."""
        if not self.powered:
            return
        t = self.now()
        tab = self.table()
        for key, item in list(self.queue.items()):
            f, t0, tl = item
            if t - t0 > MAX_AGE_S:
                del self.queue[key]
                continue
            if f.final in self.svcs or f.final == self.me:
                self.deliver(f)
                del self.queue[key]
                continue
            if f.final not in tab or t - tl < RETRY_S:
                continue
            f.dst = self.routes[f.final][1]
            item[2] = t
            self.send_raw(f)

    def stats(self):
        self.stat_pub.publish(String(data=json.dumps({'node': self.me, 'neighbours': sorted(n for n, tl in self.neigh.items()
                                                                                       if self.now() - tl < EXPIRE_S),
                                                      'routes': {d: [r[3], r[1]] for d, r in self.routes.items()},
                                                      'cost': {d: round(r[0], 2) for d, r in self.routes.items()},
                                                      'etx': {n: round(self.etx(n), 2) for n in self.neigh
                                                              if self.now() - self.neigh[n] < EXPIRE_S},
                                                      'queued': len(self.queue), 'services': sorted(self.svcs)})))


def main():
    rclpy.init()
    rclpy.spin(MeshAgent())


if __name__ == '__main__':
    main()
