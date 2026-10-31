"""Sensor data straight from Gazebo over gz-transport, without a ros_gz bridge process."""
import threading
import time
import types

import numpy as np
from gz.msgs10.image_pb2 import Image
from gz.msgs10.pointcloud_packed_pb2 import PointCloudPacked
from gz.transport13 import Node

_NODE = None


def _node():
    global _NODE
    if _NODE is None:
        _NODE = Node()
    return _NODE


class GzFeed:
    def __init__(self, topic, msg_type):
        self.topic, self.type = topic, msg_type
        self.on = False
        self.lock = threading.Lock()
        self.latest = None
        self.count = 0

    def set(self, want):
        if want and not self.on:
            self.on = bool(_node().subscribe(self.type, self.topic, self._cb))
        elif not want and self.on:
            _node().unsubscribe(self.topic)
            self.on = False
            with self.lock:
                self.latest = None

    def _cb(self, msg):
        with self.lock:
            self.latest = (msg, time.monotonic())
            self.count += 1

    def take(self):
        with self.lock:
            m, self.latest = self.latest, None
        return m


def image_feed(topic):
    return GzFeed(topic, Image)


def cloud_feed(topic):
    return GzFeed(topic, PointCloudPacked)


def as_image(m):
    return types.SimpleNamespace(data=m.data, width=m.width, height=m.height)


def cloud_xyz(m):
    off = {f.name: f.offset for f in m.field}
    n, step = m.width * m.height, m.point_step
    if n == 0 or step == 0:
        return np.zeros((0, 3), np.float32)
    buf = np.frombuffer(m.data, dtype=np.uint8)[:n * step].reshape(n, step)
    xyz = np.stack([np.ascontiguousarray(buf[:, off[c]:off[c] + 4]).view(np.float32).ravel() for c in 'xyz'], 1)
    return xyz[np.isfinite(xyz).all(axis=1)]
