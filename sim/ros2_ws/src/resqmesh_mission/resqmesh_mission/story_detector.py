"""On-board vision for the Scouts: thermal and RGB detection, bearing rays to the camp."""
import json
import math
import time
import zlib

import cv2
import numpy as np
import rclpy
import yaml
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from resqmesh_interfaces.msg import HeightMap, MeshFrame

from .gz_feed import as_image, image_feed
from .geo import camera_rot, quat_to_rot
from .terrain import Terrain

HIVIS_LO, HIVIS_HI = np.array([26, 105, 60]), np.array([41, 255, 255])
RGB_MAX_RANGE, RGB_MIN_DIP = 45.0, 0.30
TH_MAX_RANGE, TH_MIN_DIP = 55.0, 0.36
BODY_LEN_M, BODY_AREA_M2 = (0.2, 2.6), 2.5
LEPTON_NETD_K, LEPTON_COL_FPN_K, LEPTON_OFFSET_SD_K = 0.05, 0.03, 1.0


class StoryDetector(Node):
    def __init__(self):
        super().__init__('detector')
        for k, v in (('drone', ''), ('role', 'scout'), ('fleet', ''), ('layout', ''), ('params', ''), ('prior', ''), ('seed', 1),
                     ('gz_prefix', '')):
            self.declare_parameter(k, v)
        g = lambda k: self.get_parameter(k).value  # noqa: E731
        self.drone, self.role = g('drone'), g('role')
        m = yaml.safe_load(open(g('fleet')))['mission']
        self.body_k, self.alive_k = m['thermal_body_k'], m['thermal_alive_k']
        rng = np.random.default_rng(zlib.crc32(self.drone.encode()) ^ int(g('seed')))
        self.lep_rng = rng
        self.lep_offset = float(rng.normal(0.0, LEPTON_OFFSET_SD_K))          # this unit's radiometric error
        self.lep_fpn = None
        par = yaml.safe_load(open(g('params')))
        self.th, self.rgb = par['sensors']['thermal_camera'], par['sensors']['rgb_camera']
        self.pitch = par['roles'][self.role]['cam_pitch_rad']
        lay = json.load(open(g('layout')))
        self.line = np.array(lay['corridor']['line'])
        self.hw = lay['corridor']['half_width'] + 20.0
        self.terrain = Terrain(g('prior'))
        pre = g('gz_prefix')
        self.feeds = {'thermal': image_feed(pre + '/thermal_camera/image'), 'rgb': image_feed(pre + '/rgb_camera/image')}
        self.create_timer(0.1, self.poll_feeds)
        t0 = self.get_clock().now().nanoseconds * 1e-9
        self.warm = (t0 + 10.0, t0 + 22.0)
        for mp in ('mapper_1', 'mapper_2'):
            self.create_subscription(HeightMap, '/%s/map/height' % mp, self.terrain.update_live, 2)
        self.pose = None
        self.hist = []
        self.last = {}
        self.pending = []
        self.rgb_hits = []
        self.th_hits = []
        self.last_rgb = self.last_th = None
        self.stats = {'thermal_frames': 0, 'rgb_frames': 0, 'thermal_blobs': 0, 'rgb_blobs': 0, 'sightings': 0, 'ms': 0.0}
        self.out = self.create_publisher(MeshFrame, '/%s/mesh/out' % self.drone, 20)
        self.ann_pub = self.create_publisher(CompressedImage, '/%s/vision/annotated' % self.drone, 2)
        self.stat_pub = self.create_publisher(String, '/%s/vision/stats' % self.drone, 2)
        self.subs = {}
        self.create_subscription(PoseStamped, '/%s/pose_enu' % self.drone, self.on_pose, qos_profile_sensor_data)
        self.create_timer(1.0, self.publish_annotated)
        self.create_timer(0.5, self.fuse)

    def near_zone(self, x, y, margin):
        return float(np.min(np.hypot(self.line[:, 0] - x, self.line[:, 1] - y))) < self.hw + margin

    def on_pose(self, m):
        p, q = m.pose.position, m.pose.orientation
        self.pose = ((p.x, p.y, p.z), (q.w, q.x, q.y, q.z))
        self.hist.append((time.monotonic(), self.pose))
        if len(self.hist) > 40:
            del self.hist[:len(self.hist) - 40]
        near = self.near_zone(p.x, p.y, 40.0) and p.z > 5.0
        now = self.get_clock().now().nanoseconds * 1e-9
        for k, f in self.feeds.items():
            f.set(near or self.warm[0] < now < self.warm[1])
            if f.on:
                self.subs[k] = True
            else:
                self.subs.pop(k, None)

    def poll_feeds(self):
        for k, handler in (('thermal', self.on_thermal), ('rgb', self.on_rgb)):
            m = self.feeds[k].take()
            if m is None or not self.hist:
                continue
            now_pose = self.pose
            self.pose = min(self.hist, key=lambda h: abs(h[0] - m[1]))[1]
            try:
                handler(as_image(m[0]))
            finally:
                self.pose = now_pose

    # geometry
    def ground_hit(self, u, v, w, h, hfov, max_range=160.0, min_dip=0.05):
        pos, q = self.pose
        f = (w / 2.0) / math.tan(hfov / 2.0)
        ray_c = np.array([1.0, -(u - w / 2.0) / f, -(v - h / 2.0) / f])
        rw = np.array(quat_to_rot(*q)) @ (np.array(camera_rot(self.pitch)) @ ray_c)
        rw /= np.linalg.norm(rw)
        if rw[2] > -min_dip:
            return None
        for s in np.arange(2.0, max_range, 0.75):
            x, y, z = pos[0] + rw[0] * s, pos[1] + rw[1] * s, pos[2] + rw[2] * s
            top = self.terrain.ground_estimate(x, y)
            if z <= top + 0.3:
                return (x, y, (float(pos[0]), float(pos[1]), float(pos[2]), float(rw[0]), float(rw[1]), float(rw[2])), top)
        return None

    # thermal
    def lepton(self, k):
        if self.lep_fpn is None or self.lep_fpn.shape[0] != k.shape[1]:
            self.lep_fpn = self.lep_rng.normal(0.0, LEPTON_COL_FPN_K, k.shape[1]).astype(np.float32)
        out = k + self.lep_offset + self.lep_fpn[None, :] + self.lep_rng.normal(0.0, LEPTON_NETD_K, k.shape).astype(np.float32)
        return np.round(out * 100.0) / 100.0

    def on_thermal(self, img):
        if self.pose is None:
            return
        t0 = self.get_clock().now().nanoseconds
        k = np.frombuffer(bytes(img.data), dtype=np.uint16).reshape(img.height, img.width).astype(np.float32) * 0.01
        k = self.lepton(k)
        mask = (k > self.body_k).astype(np.uint8)
        n, lab, st, cen = cv2.connectedComponentsWithStats(mask, connectivity=4)
        dets = []
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] < 4:
                continue
            tmax = float(k[lab == i].max())
            gp = self.ground_hit(cen[i][0], cen[i][1], img.width, img.height, self.th['hfov_rad'], TH_MAX_RANGE, TH_MIN_DIP)
            box = (int(st[i, 0]), int(st[i, 1]), int(st[i, 2]), int(st[i, 3]))
            size, ok = None, False
            if gp:
                zg = self.terrain.ground_estimate(gp[0], gp[1])
                mpp = math.dist(self.pose[0], (gp[0], gp[1], zg)) * math.tan(self.th['hfov_rad'] / 2.0) / (img.width / 2.0)
                size = max(box[2], box[3]) * mpp
                ok = BODY_LEN_M[0] <= size <= BODY_LEN_M[1] and st[i, cv2.CC_STAT_AREA] * mpp * mpp <= BODY_AREA_M2
            dets.append((box, tmax, gp, size, ok))
            if ok and self.near_zone(gp[0], gp[1], 0.0):
                conf = min(0.97, 0.5 + 0.02 * st[i, cv2.CC_STAT_AREA])
                self.pending.append((self.now(), 'thermal', gp[0], gp[1], conf, tmax))
                self.th_hits.append((self.now(), gp[0], gp[1], gp[2], gp[3]))
        self.stats['thermal_frames'] += 1
        self.stats['thermal_blobs'] += len(dets)
        self.last_th = (k, dets)
        self.stats['ms'] = 0.8 * self.stats['ms'] + 0.2 * (self.get_clock().now().nanoseconds - t0) / 1e6

    # RGB
    def on_rgb(self, img):
        if self.pose is None:
            return
        a = np.frombuffer(bytes(img.data), dtype=np.uint8).reshape(img.height, img.width, 3)
        hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, HIVIS_LO, HIVIS_HI)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        dets = []
        H, W = mask.shape
        for c in cnts:
            area = cv2.contourArea(c)
            x, y, w, h = cv2.boundingRect(c)
            if area < 8 or area > 450 or max(w, h) > 3 * max(1, min(w, h)):
                continue
            x0, y0, x1, y1 = max(0, x - 6), max(0, y - 6), min(W, x + w + 6), min(H, y + h + 6)
            ring = hsv[y0:y1, x0:x1][mask[y0:y1, x0:x1] == 0]
            if len(ring) and float(np.median(ring[:, 1])) >= 105 and 26 <= float(np.median(ring[:, 0])) <= 85:
                continue
            M = cv2.moments(c)
            u, v = (M['m10'] / M['m00'], M['m01'] / M['m00']) if M['m00'] else (x + w / 2, y + h / 2)
            gp = self.ground_hit(u, v, img.width, img.height, self.rgb['hfov_rad'], RGB_MAX_RANGE, RGB_MIN_DIP)
            dets.append(((x, y, w, h), area, gp))
            if gp and self.near_zone(gp[0], gp[1], 0.0):
                self.pending.append((self.now(), 'rgb', gp[0], gp[1], min(0.9, 0.4 + area / 120.0), 0.0))
                self.rgb_hits.append((self.now(), gp[0], gp[1], gp[2], gp[3]))
        self.stats['rgb_frames'] += 1
        self.stats['rgb_blobs'] += len(dets)
        self.last_rgb = (a, dets)

    # fusion + reporting
    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def fuse(self):
        t = self.now()
        self.pending = [p for p in self.pending if t - p[0] < 3.0]
        self.rgb_hits = [h for h in self.rgb_hits if t - h[0] < 4.0]
        self.th_hits = [h for h in self.th_hits if t - h[0] < 3.0]
        used = set()
        for i, (ti, si, xi, yi, ci, tmi) in enumerate(self.pending):
            if i in used:
                continue
            group = [i] + [j for j, p in enumerate(self.pending) if j != i and j not in used and math.hypot(p[2] - xi, p[3] - yi) < 5.0]
            used |= set(group)
            g = [self.pending[j] for j in group]
            sensors = sorted({p[1] for p in g})
            x, y = float(np.mean([p[2] for p in g])), float(np.mean([p[3] for p in g]))
            tmax = max(p[5] for p in g)
            conf = min(0.99, max(p[4] for p in g) + (0.15 if len(sensors) > 1 else 0.0))
            cond = 'UNKNOWN' if tmax <= 0 else ('ALIVE' if tmax >= self.alive_k else 'DECEASED_SUSPECTED')
            if sensors == ['rgb'] and sum(1 for h in self.rgb_hits if t - h[0] < 4.0 and math.hypot(h[1] - x, h[2] - y) < 6.0) < 3:
                continue
            if 'thermal' in sensors and sum(1 for h in self.th_hits if math.hypot(h[1] - x, h[2] - y) < 6.0) < 2:
                continue
            key = (round(x / 6), round(y / 6))
            if t - self.last.get(key, -1e9) < 4.0:
                continue
            self.last[key] = t
            self.stats['sightings'] += 1
            hits = [h for h in self.th_hits + self.rgb_hits if math.hypot(h[1] - x, h[2] - y) < 6.0]
            hits.sort(key=lambda h: h[0])
            hits = [hits[k] for k in sorted({round(i * (len(hits) - 1) / 7) for i in range(8)})] if len(hits) > 8 else hits
            p = {'source_drone': self.drone, 'x': round(x, 2), 'y': round(y, 2), 'confidence': round(conf, 2), 'max_temp_k': round(tmax, 2),
                 'sensor': '+'.join(s for s in ('thermal', 'rgb') if s in sensors), 'condition': cond, 'heat_signature': cond == 'ALIVE',
                 'z': round(float(np.mean([h[4] for h in hits])), 2) if hits else None,
                 'rays': [[round(v, 2) for v in h[3][:3]] + [round(v, 4) for v in h[3][3:]] for h in hits]}
            self.out.publish(MeshFrame(final='base', kind='sighting', payload=json.dumps(p)))
        self.pending = [p for k, p in enumerate(self.pending) if k not in used]

    def publish_annotated(self):
        self.stat_pub.publish(String(data=json.dumps(dict(self.stats, drone=self.drone, sensors_on=sorted(self.subs)))))
        panels = []
        if self.last_rgb is not None:
            a, dets = self.last_rgb
            im = cv2.cvtColor(a, cv2.COLOR_RGB2BGR).copy()
            for (x, y, w, h), area, gp in dets:
                cv2.rectangle(im, (x - 2, y - 2), (x + w + 2, y + h + 2), (0, 255, 255), 1)
                cv2.putText(im, 'PERSON', (x, max(9, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(im, 'RGB IMX219  hi-vis segmentation', (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            panels.append(cv2.resize(im, (320, 240), interpolation=cv2.INTER_AREA))
        if self.last_th is not None:
            k, dets = self.last_th
            lo, hi = 294.0, 312.0
            norm = np.clip((k - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
            im = cv2.resize(cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO), (320, 240), interpolation=cv2.INTER_NEAREST)
            sx, sy = 320 / k.shape[1], 240 / k.shape[0]
            for (x, y, w, h), tmax, gp, size, ok in dets:
                col = ((80, 255, 80) if tmax >= self.alive_k else (200, 200, 200)) if ok else (90, 90, 255)
                cv2.rectangle(im, (int(x * sx) - 2, int(y * sy) - 2), (int((x + w) * sx) + 2, int((y + h) * sy) + 2), col, 1)
                label = ('%.1fC %s %.1fm' % (tmax - 273.15, 'ALIVE' if tmax >= self.alive_k else 'NO LIVE HEAT', size)) if ok else \
                        ('%.1fC not person-sized' % (tmax - 273.15) if size else '%.1fC too far/shallow' % (tmax - 273.15))
                cv2.putText(im, label, (int(x * sx), max(9, int(y * sy) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.33, col, 1, cv2.LINE_AA)
            cv2.putText(im, 'THERMAL Lepton 3.5  %.0f-%.0f C' % (lo - 273.15, hi - 273.15), (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                        (255, 255, 255), 1, cv2.LINE_AA)
            panels.append(im)
        if not panels:
            return
        frame = np.hstack(panels) if len(panels) > 1 else panels[0]
        ok, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            m = CompressedImage(format='jpeg', data=jpg.tobytes())
            m.header.stamp = self.get_clock().now().to_msg()
            m.header.frame_id = self.drone
            self.ann_pub.publish(m)


def main():
    rclpy.init()
    rclpy.spin(StoryDetector())


if __name__ == '__main__':
    main()
