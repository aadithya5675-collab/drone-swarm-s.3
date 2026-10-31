"""The landslide: debris flow down the valley, swept houses and forest, ten people in the debris."""
import glob
import json
import math
import os
import random
import subprocess
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
RANDY = glob.glob(os.path.expanduser('~/.gz/fuel/fuel.gazebosim.org/openrobotics/models/rescue%20randy/*/'))


def gz_create(world, sdf):
    sdf = sdf.replace('\n', ' ').replace('"', '\\"')
    return subprocess.run(['gz', 'service', '-s', '/world/%s/create' % world, '--reqtype', 'gz.msgs.EntityFactory',
                           '--reptype', 'gz.msgs.Boolean', '--timeout', '8000', '--req', 'sdf: "%s"' % sdf],
                          capture_output=True, text=True).returncode == 0


def gz_remove(world, name):
    return subprocess.run(['gz', 'service', '-s', '/world/%s/remove' % world, '--reqtype', 'gz.msgs.Entity',
                           '--reptype', 'gz.msgs.Boolean', '--timeout', '5000', '--req', 'name: "%s" type: MODEL' % name],
                          capture_output=True, text=True).returncode == 0


STL = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def load_stl(path):
    b = open(path, 'rb').read()
    n = int.from_bytes(b[80:84], 'little')
    return np.frombuffer(b[84:84 + n * 50], dtype=STL)['v'].astype(float)


def top_surface(tris, x, y):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    v0, v1, v2 = c[:, :2] - a[:, :2], b[:, :2] - a[:, :2], np.array([x, y]) - a[:, :2]
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    den[den == 0] = 1e-12
    u, v = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
    m = (u >= 0) & (v >= 0) & (u + v <= 1)
    if not m.any():
        return None
    return float((a[m, 2] + u[m] * (c[m, 2] - a[m, 2]) + v[m] * (b[m, 2] - a[m, 2])).max())


def include(name, model, pose=None):
    p = '<pose>%.2f %.2f %.2f 0 0 %.3f</pose>' % pose if pose else ''
    return '<sdf version="1.9"><include><name>%s</name><uri>model://%s</uri>%s</include></sdf>' % (name, model, p)


def person_sdf(pid, x, y, z, yaw, max_temp, buried, roll):
    """Rescue Randy is modelled standing (origin at the feet): roll +-90 deg lays him on his back or front."""
    base = sorted(RANDY)[-1]
    mesh = 'file://' + os.path.join(base, 'meshes', 'rescue_randy.dae')
    tex = os.path.join(base, 'materials', 'textures')
    cover = ''
    if buried:
        cover = ('<visual name="mud"><pose>0 0.12 0.45 0 0 0</pose><geometry><box><size>0.9 0.5 1.0</size></box></geometry>'
                 '<material><ambient>0.33 0.25 0.17 1</ambient><diffuse>0.33 0.25 0.17 1</diffuse></material></visual>')
    return """<sdf version="1.9"><model name="{n}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} {roll:.3f} 0 {yaw:.3f}</pose>
<link name="body"><visual name="randy"><geometry><mesh><uri>{mesh}</uri></mesh></geometry>
<material><diffuse>1 1 1</diffuse><pbr><metal><albedo_map>{tex}/rescue_randy_albedo.png</albedo_map>
<normal_map>{tex}/rescue_randy_normal.png</normal_map></metal></pbr></material>
<plugin filename="gz-sim-thermal-system" name="gz::sim::systems::Thermal">
<heat_signature>{tex}/RescueRandy_Thermal.png</heat_signature><max_temp>{t:.2f}</max_temp></plugin></visual>
<collision name="c"><pose>0 0 0.9 0 0 0</pose><geometry><box><size>0.6 0.35 1.8</size></box></geometry></collision>{cover}</link></model></sdf>""".format(
        n=pid, x=x, y=y, z=z, yaw=yaw, mesh=mesh, tex=tex, t=max_temp, cover=cover, roll=roll)


class Landslide(Node):
    def __init__(self):
        super().__init__('landslide')
        self.declare_parameter('sim_dir', os.path.expanduser('~/resqmesh/sim'))
        self.declare_parameter('seed', -1)
        self.declare_parameter('speed', 1.0)
        self.declare_parameter('people', 6)
        self.declare_parameter('deceased', 2)
        sim = self.get_parameter('sim_dir').value
        self.info = json.load(open(os.path.join(sim, 'config', 'wayanad.json')))
        seed = self.get_parameter('seed').value
        self.rng = random.Random(None if seed < 0 else seed)
        self.world = self.info['world']
        self.gt = np.load(os.path.join(sim, 'config', 'ground_truth.npz'))
        mods = os.path.join(sim, 'models')
        self.mud = np.concatenate([load_stl(os.path.join(mods, d['name'], 'meshes', m)) for d in self.info['landslide']['debris']
                                   if d['in_corridor'] for m in ('mud.stl', 'mud_wet.stl')
                                   if os.path.exists(os.path.join(mods, d['name'], 'meshes', m))])
        self.run_dir = os.path.expanduser('~/resqmesh/run')
        os.makedirs(self.run_dir, exist_ok=True)
        self.ev = self.create_publisher(String, '/swarm/events_raw', 10)
        self.pub = self.create_publisher(String, '/disaster/landslide', LATCHED)
        self.truth = self.create_publisher(String, '/sim/truth/persons', LATCHED)

    def say(self, text):
        self.get_logger().warn(text)
        self.ev.publish(String(data=json.dumps({'level': 'ALERT', 'source': 'disaster', 'text': text})))

    def ground_z(self, x, y):
        d = self.gt
        j, i = (x - float(d['x0'])) / float(d['res']), (y - float(d['y0'])) / float(d['res'])
        z = d['z']
        i0, j0 = int(i), int(j)
        fi, fj = i - i0, j - j0
        g = (z[i0, j0] * (1 - fi) * (1 - fj) + z[i0 + 1, j0] * fi * (1 - fj) + z[i0, j0 + 1] * (1 - fi) * fj + z[i0 + 1, j0 + 1] * fi * fj)
        return float(g)

    def run(self):
        ls = self.info['landslide']
        dt = 0.5 / self.get_parameter('speed').value
        self.say('02:17 - extreme rain. A hillside above Mundakkai has failed: debris flow coming down the river.')
        corridor_started = bridge_gone = False
        for seg in sorted(ls['debris'], key=lambda d: d['s0']):
            if seg['in_corridor'] and not corridor_started:
                corridor_started = True
                self.say('Debris flow has reached Mundakkai: houses and forest in its path are gone.')
                gz_remove(self.world, 'resqmesh_corridor_trees')
                for h, c in zip(ls['houses'], ls['collapsed']):
                    gz_remove(self.world, h['name'])
                    gz_create(self.world, include(c, c))
            gz_create(self.world, include(seg['name'], seg['name']))
            if not bridge_gone and seg['s1'] >= max(d['s1'] for d in ls['debris']) - 61:
                bridge_gone = True
                gz_remove(self.world, 'resqmesh_chooralmala_bridge')
                self.say('The Chooralmala bridge has been washed away: the valley is cut off by road.')
            time.sleep(dt)
        # people in the debris field
        corr = self.info['corridor']
        line = corr['line']
        people = []
        n_people = self.get_parameter('people').value
        dead = set(self.rng.sample(range(n_people), self.get_parameter('deceased').value))
        k = 0
        while len(people) < n_people and k < 500:
            k += 1
            i = self.rng.randrange(len(line))
            p0, p1 = line[max(i - 1, 0)], line[min(i + 1, len(line) - 1)]
            tx, ty = p1[0] - p0[0], p1[1] - p0[1]
            n = math.hypot(tx, ty) or 1.0
            off = self.rng.uniform(-0.72, 0.72) * corr['half_width']
            x, y = line[i][0] - ty / n * off, line[i][1] + tx / n * off
            if any(math.hypot(x - q['x'], y - q['y']) < 25 for q in people):
                continue
            idx = len(people)
            is_dead = idx in dead
            temp = self.rng.uniform(298.5, 300.0) if is_dead else self.rng.uniform(306.0, 309.5)
            buried = self.rng.random() < 0.35
            top = top_surface(self.mud, x, y)
            if top is None:
                continue
            z = top + 0.12
            pid = 'person_%02d' % (idx + 1)
            # lie along the contour (a body comes to rest across the slope, not up it)
            gx_ = (self.ground_z(x + 2, y) - self.ground_z(x - 2, y)) / 4
            gy_ = (self.ground_z(x, y + 2) - self.ground_z(x, y - 2)) / 4
            yaw = math.atan2(gy_, gx_) + self.rng.uniform(-0.25, 0.25)
            gz_create(self.world, person_sdf(pid, x, y, z, yaw, temp, buried, self.rng.choice([1.5708, -1.5708])))
            people.append({'id': pid, 'x': round(x, 2), 'y': round(y, 2), 'z': round(z, 2), 'alive': not is_dead,
                           'surface_temp_k': round(temp, 2), 'partly_buried': buried})
        self.truth.publish(String(data=json.dumps(people)))
        json.dump(people, open(os.path.join(self.run_dir, 'truth.json'), 'w'), indent=1)
        open(os.path.join(self.run_dir, 'landslide.flag'), 'w').write(str(time.time()))
        self.say('People are missing in the debris field. Rescue base: launch the ResQMesh swarm.')
        self.pub.publish(String(data=json.dumps({'t': time.time(), 'zone': corr, 'sectors': self.info['sectors']})))
        self.get_logger().info('%d people placed (%d dead): truth on /sim/truth/persons' % (len(people), len(dead)))


def main():
    rclpy.init()
    n = Landslide()
    n.run()
    t0 = time.time()
    while time.time() - t0 < 3.0:
        rclpy.spin_once(n, timeout_sec=0.2)


if __name__ == '__main__':
    main()
