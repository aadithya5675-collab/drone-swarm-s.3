"""Bayesian search map (classic search theory: POC, POD, POS) for the debris corridor."""
import math

import numpy as np


class SearchMap:
    def __init__(self, line, half_width, houses=(), res=8.0, margin=10.0, house_sigma=30.0):
        line = np.asarray(line, float)[:, :2]
        self.line, self.hw, self.res = line, float(half_width), float(res)
        lo, hi = line.min(0) - half_width - margin, line.max(0) + half_width + margin
        self.x0, self.y0 = float(lo[0]), float(lo[1])
        self.w, self.h = int(math.ceil((hi[0] - lo[0]) / res)), int(math.ceil((hi[1] - lo[1]) / res))
        xs = self.x0 + (np.arange(self.w) + 0.5) * res
        ys = self.y0 + (np.arange(self.h) + 0.5) * res
        self.X, self.Y = np.meshgrid(xs, ys)
        d_axis = self._dist_to_line(self.X, self.Y)
        self.mask = d_axis <= half_width
        uniform = self.mask.astype(float)
        axis = np.exp(-0.5 * (d_axis / (0.45 * half_width)) ** 2) * self.mask
        near = np.zeros_like(uniform)
        for hx, hy in houses:
            near += np.exp(-0.5 * ((self.X - hx) ** 2 + (self.Y - hy) ** 2) / house_sigma ** 2)
        near *= self.mask
        parts = [(0.5, uniform), (0.25, axis), (0.25, near)]
        p = sum(wt * a / a.sum() for wt, a in parts if a.sum() > 0)
        self.p = p / p.sum()
        self.p0 = self.p.copy()

    def _dist_to_line(self, X, Y):
        """Distance to the corridor axis; beyond either end of the axis counts as outside (the sectors are flat-ended)."""
        best = np.full(X.shape, np.inf)
        last = len(self.line) - 2
        for k, (a, b) in enumerate(zip(self.line[:-1], self.line[1:])):
            ab = b - a
            L2 = float(ab @ ab) or 1e-9
            tr = ((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / L2
            t = np.clip(tr, 0, 1)
            d = np.hypot(X - (a[0] + t * ab[0]), Y - (a[1] + t * ab[1]))
            if k == 0:
                d = np.where(tr < 0, np.inf, d)
            if k == last:
                d = np.where(tr > 1, np.inf, d)
            best = np.minimum(best, d)
        return best

    def observe(self, a, b, width, pod):
        ax, ay, bx, by = a[0], a[1], b[0], b[1]
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        i0 = max(0, int((min(ay, by) - width - self.y0) / self.res))
        i1 = min(self.h, int((max(ay, by) + width - self.y0) / self.res) + 1)
        j0 = max(0, int((min(ax, bx) - width - self.x0) / self.res))
        j1 = min(self.w, int((max(ax, bx) + width - self.x0) / self.res) + 1)
        if i0 >= i1 or j0 >= j1:
            return
        X, Y = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
        t = np.clip(((X - ax) * (bx - ax) + (Y - ay) * (by - ay)) / L2, 0, 1) if L2 > 1e-9 else 0.0
        d = np.hypot(X - (ax + t * (bx - ax)), Y - (ay + t * (by - ay)))
        hit = d <= width / 2.0
        self.p[i0:i1, j0:j1][hit] *= (1.0 - pod)

    @property
    def pos(self):
        return float(1.0 - self.p.sum())

    def mass_in(self, start, end, half_width):
        sx, sy, ex, ey = start[0], start[1], end[0], end[1]
        L = math.hypot(ex - sx, ey - sy) or 1e-9
        ux, uy = (ex - sx) / L, (ey - sy) / L
        s = (self.X - sx) * ux + (self.Y - sy) * uy
        n = -(self.X - sx) * uy + (self.Y - sy) * ux
        return float(self.p[(s >= 0) & (s <= L) & (np.abs(n) <= half_width)].sum())

    def to_msg(self):
        q = np.clip(self.p / max(self.p0.max(), 1e-12) * 255.0, 0, 255).astype(np.uint8)
        q[~self.mask] = 0
        return {'x0': self.x0, 'y0': self.y0, 'res': self.res, 'w': self.w, 'h': self.h, 'pos': round(self.pos, 4),
                'q': q.ravel().tolist()}
