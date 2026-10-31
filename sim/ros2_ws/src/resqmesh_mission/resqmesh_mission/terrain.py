"""What the swarm knows about the ground."""
import math

import numpy as np

FOREST_MARGIN = 26.0


class Terrain:
    def __init__(self, prior_path):
        d = np.load(prior_path)
        self.px0, self.py0, self.pres = float(d['x0']), float(d['y0']), float(d['res'])
        self.prior = d['z'].astype(np.float32)
        self.live = {}           # source -> (x0, y0, res, w, h, z[h, w])

    # layers
    def update_live(self, msg):
        z = np.asarray(msg.z, dtype=np.float32).reshape(msg.height, msg.width)
        self.live[msg.source] = (msg.origin_x, msg.origin_y, msg.resolution, msg.width, msg.height, z)

    def prior_z(self, x, y):
        j, i = (x - self.px0) / self.pres, (y - self.py0) / self.pres
        i0, j0 = int(math.floor(i)), int(math.floor(j))
        if not (0 <= i0 < self.prior.shape[0] - 1 and 0 <= j0 < self.prior.shape[1] - 1):
            return 0.0
        fi, fj = i - i0, j - j0
        p = self.prior
        return float(p[i0, j0] * (1 - fi) * (1 - fj) + p[i0 + 1, j0] * fi * (1 - fj) + p[i0, j0 + 1] * (1 - fi) * fj
                     + p[i0 + 1, j0 + 1] * fi * fj)

    def live_z(self, x, y, radius=1):
        best = None
        for x0, y0, res, w, h, z in self.live.values():
            j, i = int((x - x0) / res), int((y - y0) / res)
            if 0 <= i < h and 0 <= j < w:
                win = z[max(0, i - radius):i + radius + 1, max(0, j - radius):j + radius + 1]
                if np.isfinite(win).any():
                    v = float(np.nanmax(win))
                    best = v if best is None else max(best, v)
        return best

    def live_median(self, x, y, radius=3):
        vals = []
        for x0, y0, res, w, h, z in self.live.values():
            j, i = int((x - x0) / res), int((y - y0) / res)
            if 0 <= i < h and 0 <= j < w:
                win = z[max(0, i - radius):i + radius + 1, max(0, j - radius):j + radius + 1]
                vals.extend(win[np.isfinite(win)].tolist())
        return float(np.median(vals)) if vals else None

    def ground_estimate(self, x, y):
        v = self.live_z(x, y)
        if v is None:
            v = self.live_median(x, y)
        return v if v is not None else self.prior_z(x, y)

    def surface(self, x, y, ground_only=False):
        v = self.live_z(x, y)
        if v is not None:
            return v, True
        margin = 0.0 if ground_only or math.hypot(x, y) < 130.0 else FOREST_MARGIN   # the camp clearing is surveyed
        return self.prior_z(x, y) + margin, False

    def max_along(self, p0, p1, step=4.0, lookahead=0.0, ground_only=False):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        n = max(1, int((L + lookahead) / step))
        top, known = -1e9, True
        for k in range(n + 1):
            t = k * step / L if L > 0 else 0.0
            v, kn = self.surface(p0[0] + dx * t, p0[1] + dy * t, ground_only)
            top, known = max(top, v), known and kn
        return top, known

    def line_of_sight(self, a, b, clearance=2.0, step=12.0):
        L = math.dist(a[:2], b[:2])
        n = max(2, int(L / step))
        for k in range(1, n):
            t = k / n
            x, y, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
            if self.prior_z(x, y) + clearance > z:
                return False
        return True
