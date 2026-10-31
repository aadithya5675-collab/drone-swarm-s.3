"""Multi-view triangulation of a sighted person from camera bearing rays (pure numpy, unit-tested)."""
import math

import numpy as np

MIN_SPREAD_DEG = 6.0
HUBER_M = 1.5             # residuals beyond this are down-weighted
LAM = 0.02


def spread_deg(dirs):
    d = np.asarray(dirs, float)
    c = np.clip(d @ d.T, -1.0, 1.0)
    return float(np.degrees(np.arccos(c.min()))) if len(d) > 1 else 0.0


def ray_dist(ray, p):
    o, d = np.asarray(ray[:3], float), np.asarray(ray[3:], float)
    d = d / np.linalg.norm(d)
    v = np.asarray(p, float) - o
    s = max(0.0, float(v @ d))
    return float(np.linalg.norm(v - s * d))


def triangulate(rays, guess, iters=4):
    """rays: [(ox, oy, oz, dx, dy, dz), ...]; guess: (x, y, z) ground estimate."""
    R = np.asarray(rays, float)
    if len(R) < 2:
        return None
    o, d = R[:, :3], R[:, 3:]
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    spread = spread_deg(d)
    if spread < MIN_SPREAD_DEG:
        return None
    g = np.asarray(guess, float)
    w = np.ones(len(R))
    p = g.copy()
    for _ in range(iters):
        A = LAM * len(R) * np.eye(3)
        b = LAM * len(R) * g
        for oi, di, wi in zip(o, d, w):
            M = np.eye(3) - np.outer(di, di)
            A += wi * M
            b += wi * M @ oi
        p = np.linalg.solve(A, b)
        r = np.linalg.norm((p - o) - ((p - o) @ d.T).diagonal()[:, None] * d, axis=1)   # point-to-ray distance
        w = np.where(r <= HUBER_M, 1.0, HUBER_M / np.maximum(r, 1e-9))
    used = int((r <= 3 * HUBER_M).sum())
    rms = float(math.sqrt(np.mean(np.minimum(r, 3 * HUBER_M) ** 2)))
    return float(p[0]), float(p[1]), float(p[2]), rms, spread, used
