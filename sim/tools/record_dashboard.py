"""Record everything the dashboard shows, so a whole mission can be replayed in the browser without the simulator."""
import base64
import json
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from resqmesh_interfaces.msg import MissionEvent

STRINGS = {'/base/fleet': 0.5, '/base/persons': 0.0, '/base/plan': 1.0, '/base/story': 1.0, '/base/mapimg': 10.0,
           '/base/mesh': 1.0, '/base/vision': 1.0, '/base/cloud': 20.0, '/base/history': 5.0, '/mesh/traffic': 0.0,
           '/mesh/trace': 0.0, '/brain/searchmap': 8.0, '/base/eventlog': 15.0, '/base/rescue': 0.0}
CAMS = ['scout_1', 'scout_2', 'scout_3', 'scout_4']


class Rec(Node):
    def __init__(self, path, minutes):
        super().__init__('dashboard_recorder')
        self.f = open(path, 'w')
        self.t0 = time.time()
        self.end = self.t0 + 60 * minutes
        self.last = {}
        for topic, period in STRINGS.items():
            self.create_subscription(String, topic, lambda m, t=topic, p=period: self.put(t, {'data': m.data}, p), 20)
        self.create_subscription(MissionEvent, '/swarm/events', lambda m: self.put(
            '/swarm/events', {'level': m.level, 'source': m.source, 'text': m.text}, 0.0), 50)
        for c in CAMS:
            topic = '/%s/vision/annotated' % c
            self.create_subscription(CompressedImage, topic, lambda m, t=topic: self.put(
                t, {'format': m.format, 'data': base64.b64encode(bytes(m.data)).decode()}, 0.9), 2)
        self.create_timer(5.0, self.check)

    def put(self, topic, msg, period):
        t = time.time()
        if period and t - self.last.get(topic, 0) < period:
            return
        self.last[topic] = t
        self.f.write(json.dumps({'t': round(t - self.t0, 2), 'topic': topic, 'msg': msg}, separators=(',', ':')) + '\n')

    def check(self):
        self.f.flush()
        if time.time() > self.end:
            raise SystemExit


def main():
    rclpy.init()
    n = Rec(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 25.0)
    try:
        rclpy.spin(n)
    except SystemExit:
        pass
    n.f.close()


if __name__ == '__main__':
    main()
