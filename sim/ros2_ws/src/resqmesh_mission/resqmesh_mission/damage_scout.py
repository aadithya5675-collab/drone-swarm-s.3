"""Damage a drone in flight: an impact shove plus a failed motor."""
import json
import random
import subprocess
import time

import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

CAUSES = ['struck by a falling tree on the slide margin', 'clipped a sagging power line over the river',
          'hit by debris thrown up by a secondary slide', 'flew into a dead tree hidden in low cloud']


class Damage(Node):
    def __init__(self):
        super().__init__('damage_scout')
        self.declare_parameter('scout', '')
        self.declare_parameter('fleet', '')
        self.declare_parameter('world', 'resqmesh_wayanad')
        self.fleet = None
        self.create_subscription(String, '/base/fleet', self.on_fleet, 5)
        self.ev = self.create_publisher(String, '/swarm/events_raw', 10)
        q = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, '/base/story', lambda m: None, q)

    def on_fleet(self, m):
        self.fleet = json.loads(m.data)


def main():
    rclpy.init()
    n = Damage()
    t0 = time.time()
    while n.fleet is None and time.time() - t0 < 6:
        rclpy.spin_once(n, timeout_sec=0.3)
    cfg = {d['name']: d for d in yaml.safe_load(open(n.get_parameter('fleet').value))['drones']}
    pick = n.get_parameter('scout').value
    if pick in ('', 'any'):
        flying = [d for d, s in (n.fleet or {}).items()
                  if d.startswith('scout') and s.get('state') in ('SEARCHING', 'HOLDING') and s.get('age', 99) < 3]
        if not flying:
            print('no Scout is flying right now')
            return
        pick = random.choice(flying)
    cause = random.choice(CAUSES)
    model = '%s_%d' % (cfg[pick]['model'], cfg[pick]['px4_instance'])
    world = n.get_parameter('world').value
    # impact: a sideways shove on the airframe, then motor 2 dies
    subprocess.run(['gz', 'topic', '-t', '/world/%s/wrench' % world, '-m', 'gz.msgs.EntityWrench', '-p',
                    'entity: {name: "%s::base_link", type: LINK} wrench: {force: {x: 18, y: -12, z: -6}, torque: {x: 0.6, y: 0.4, z: 0.2}}'
                    % model], capture_output=True)
    subprocess.run(['gz', 'topic', '-t', '/model/%s/motor_failure/motor_number' % model, '-m', 'gz.msgs.Int32', '-p', 'data: 2'],
                   capture_output=True)
    text = 'DAMAGE: %s %s - motor 2 failed.' % (pick, cause)
    n.ev.publish(String(data=json.dumps({'level': 'ALERT', 'source': 'incident', 'text': text})))
    print(text)
    t0 = time.time()
    while time.time() - t0 < 1.0:
        rclpy.spin_once(n, timeout_sec=0.1)


if __name__ == '__main__':
    main()
