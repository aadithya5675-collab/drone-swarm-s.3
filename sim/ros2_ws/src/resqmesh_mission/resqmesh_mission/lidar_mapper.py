"""3D lidar mapping on a Mapper (runs on the Mapper's Jetson)."""
import json
import math

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2

from resqmesh_interfaces.msg import HeightMap

from .gz_feed import cloud_feed, cloud_xyz
from .geo import quat_to_rot

VOX = 0.5
CELL = 2.0
DRONE_R, DRONE_DZ = 3.0, 2.5
AIR_MARGIN = 60.0
MOUNT = (np.array([0.0251, 0.0, -0.0765]), np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]))   # = the Fusion Mapper v2


class LidarMapper(Node):
    def __init__(self):
        super().__init__('lidar_mapper')
        for k, v in (('drone', 'mapper_1'), ('layout', ''), ('publish_hz', 0.5), ('prior', ''), ('gz_prefix', ''),
                     ('swarm', 'scout_1,scout_2,scout_3,scout_4,mapper_1,mapper_2,relay_1')):
            self.declare_parameter(k, v)
        self.drone = self.get_parameter('drone').value
        lay = json.load(open(self.get_parameter('layout').value))
        line = np.array(lay['corridor']['line'])
        self.line, self.hw = line, lay['corridor']['half_width']
        hw = lay['corridor']['half_width'] + 60.0
        self.x0, self.y0 = float(line[:, 0].min() - hw), float(line[:, 1].min() - hw)
        self.w = int((line[:, 0].max() + hw - self.x0) / CELL) + 1
        self.h = int((line[:, 1].max() + hw - self.y0) / CELL) + 1
        self.grid = np.full((self.h, self.w), -np.inf, np.float32)
        # corridor cells (for the coverage number)
        jj, ii = np.meshgrid(np.arange(self.w), np.arange(self.h))
        cx, cy = self.x0 + (jj + 0.5) * CELL, self.y0 + (ii + 0.5) * CELL
        d = np.min(np.stack([np.hypot(cx - p[0], cy - p[1]) for p in line[::2]]), axis=0)
        self.corr = d < lay['corridor']['half_width']
        self.vox = np.empty(0, np.int64)
        self.vox_new = []
        self.points = 0
        self.pose = None
        self.create_subscription(PoseStamped, '/%s/pose_enu' % self.drone, self.on_pose, qos_profile_sensor_data)
        self.others = {}
        for d in self.get_parameter('swarm').value.split(','):
            if d and d != self.drone:
                self.create_subscription(PoseStamped, '/%s/pose_enu' % d, lambda m, d=d: self.others.__setitem__(
                    d, (m.pose.position.x, m.pose.position.y, m.pose.position.z)), qos_profile_sensor_data)
        pr = self.get_parameter('prior').value
        self.prior = np.load(pr) if pr else None
        self.feed = cloud_feed(self.get_parameter('gz_prefix').value + '/lidar_3d/scan/points')
        self.create_timer(0.1, self.poll_feed)
        t0 = self.get_clock().now().nanoseconds * 1e-9
        self.warm = (t0 + 10.0, t0 + 22.0)
        self.hm_pub = self.create_publisher(HeightMap, '/%s/map/height' % self.drone, 2)
        self.cloud_pub = self.create_publisher(PointCloud2, '/%s/map/cloud' % self.drone, 2)
        self.create_timer(1.0 / self.get_parameter('publish_hz').value, self.publish)

    def on_pose(self, m):
        p, q = m.pose.position, m.pose.orientation
        self.pose = (np.array([p.x, p.y, p.z]), np.array(quat_to_rot(q.w, q.x, q.y, q.z)))
        near = float(np.min(np.hypot(self.line[:, 0] - p.x, self.line[:, 1] - p.y))) < self.hw + 80.0
        agl = p.z - self.ground(p.x, p.y)
        over = near and 8.0 < agl < 58.0
        now = self.get_clock().now().nanoseconds * 1e-9
        self.feed.set(over or self.warm[0] < now < self.warm[1])

    def poll_feed(self):
        m = self.feed.take()
        if m is not None:
            self.on_cloud(cloud_xyz(m[0]))

    def ground(self, x, y):
        if self.prior is None:
            return 0.0
        p = self.prior
        j = min(max(int((x - float(p['x0'])) / float(p['res'])), 0), p['z'].shape[1] - 1)
        i = min(max(int((y - float(p['y0'])) / float(p['res'])), 0), p['z'].shape[0] - 1)
        return float(p['z'][i, j])

    def static_mask(self, w, pos):
        keep = w[:, 2] < pos[2] - 2.0
        for ox, oy, oz in self.others.values():
            near = (np.abs(w[:, 2] - oz) < DRONE_DZ) & ((w[:, 0] - ox) ** 2 + (w[:, 1] - oy) ** 2 < DRONE_R ** 2)
            keep &= ~near
        if self.prior is not None:
            p = self.prior
            jj = np.clip(((w[:, 0] - float(p['x0'])) / float(p['res'])).astype(int), 0, p['z'].shape[1] - 1)
            ii = np.clip(((w[:, 1] - float(p['y0'])) / float(p['res'])).astype(int), 0, p['z'].shape[0] - 1)
            keep &= w[:, 2] < p['z'][ii, jj] + AIR_MARGIN
        return keep

    def on_cloud(self, pts):
        if self.pose is None or self.pose[0][2] < 8.0:
            return
        if len(pts) == 0:
            return
        r = np.linalg.norm(pts, axis=1)
        pts = pts[(r > 0.4) & (r < 69.0)]
        t, R = MOUNT
        body = pts @ R.T + t
        pos, Rw = self.pose
        world = body @ Rw.T + pos
        world = world[self.static_mask(world, pos)]
        if len(world) == 0:
            return
        self.points += len(world)
        k = np.floor(world / VOX).astype(np.int64) + (1 << 20)
        self.vox_new.append((k[:, 0] << 42) | (k[:, 1] << 21) | k[:, 2])
        j = ((world[:, 0] - self.x0) / CELL).astype(int)
        i = ((world[:, 1] - self.y0) / CELL).astype(int)
        ok = (i >= 0) & (i < self.h) & (j >= 0) & (j < self.w)
        i, j, z = i[ok], j[ok], world[ok, 2].astype(np.float32)
        np.maximum.at(self.grid, (i, j), z)                     # highest return per cell

    def publish(self):
        m = HeightMap(source=self.drone, origin_x=self.x0, origin_y=self.y0, resolution=CELL, width=self.w, height=self.h)
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = 'world'
        g = np.where(np.isfinite(self.grid), self.grid, np.nan)
        m.z = g.ravel().tolist()
        m.coverage = float(np.isfinite(g[self.corr]).mean()) if self.corr.any() else 0.0
        m.points_total = int(self.points)
        self.hm_pub.publish(m)
        if self.vox_new:
            self.vox = np.unique(np.concatenate([self.vox] + self.vox_new))
            self.vox_new = []
        if len(self.vox):
            m21 = (1 << 21) - 1
            k = np.stack([(self.vox >> 42) & m21, (self.vox >> 21) & m21, self.vox & m21], 1) - (1 << 20)
            v = ((k + 0.5) * VOX).astype(np.float32)
            if len(v) > 60000:
                v = v[np.random.default_rng(0).choice(len(v), 60000, replace=False)]
            hdr = m.header
            fields = [PointField(name=n, offset=4 * k, datatype=PointField.FLOAT32, count=1) for k, n in enumerate('xyz')]
            self.cloud_pub.publish(point_cloud2.create_cloud(hdr, fields, v.tolist()))


def main():
    rclpy.init()
    rclpy.spin(LidarMapper())


if __name__ == '__main__':
    main()
