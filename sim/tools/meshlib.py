"""Tiny mesh toolkit (numpy only): primitive solids as triangle arrays, transforms, merging, binary STL."""
import math

import numpy as np

STL = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def save_stl(path, tris):
    tris = np.asarray(tris, dtype='<f4').reshape(-1, 3, 3)
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    nrm = np.cross(e1, e2)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=STL)
    rec['n'], rec['v'] = nrm, tris
    with open(path, 'wb') as f:
        f.write(b'resqmesh'.ljust(80, b' '))
        f.write(len(tris).to_bytes(4, 'little'))
        f.write(rec.tobytes())


def quad(a, b, c, d):
    return [(a, b, c), (a, c, d)]


def box(sx, sy, sz):
    x, y = sx / 2, sy / 2
    p = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, sz), (x, -y, sz), (x, y, sz), (-x, y, sz)]
    f = quad(p[0], p[3], p[2], p[1]) + quad(p[4], p[5], p[6], p[7]) + quad(p[0], p[1], p[5], p[4]) + \
        quad(p[1], p[2], p[6], p[5]) + quad(p[2], p[3], p[7], p[6]) + quad(p[3], p[0], p[4], p[7])
    return np.array(f, float)


def cylinder(r, h, n=8, r_top=None):
    r_top = r if r_top is None else r_top
    out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        b0, b1 = (r * math.cos(a0), r * math.sin(a0), 0), (r * math.cos(a1), r * math.sin(a1), 0)
        t0, t1 = (r_top * math.cos(a0), r_top * math.sin(a0), h), (r_top * math.cos(a1), r_top * math.sin(a1), h)
        out += quad(b0, b1, t1, t0)
        out.append(((0, 0, 0), b1, b0))
        if r_top > 0:
            out.append(((0, 0, h), t0, t1))
    return np.array(out, float)


def cone(r, h, n=8):
    return cylinder(r, h, n, r_top=0.0)


def hip_roof(sx, sy, h, overhang=0.4):
    """Hip roof (Kerala tiled roof) over a sx*sy footprint, base at z = 0."""
    x, y = sx / 2 + overhang, sy / 2 + overhang
    ridge = max(0.0, (sx - sy) / 2) if sx >= sy else 0.0
    if sx >= sy:
        r0, r1 = (-ridge, 0, h), (ridge, 0, h)
    else:
        rr = (sy - sx) / 2
        r0, r1 = (0, -rr, h), (0, rr, h)
    c = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0)]
    if sx >= sy:
        f = [(c[0], c[1], r1), (c[0], r1, r0), (c[2], c[3], r0), (c[2], r0, r1), (c[1], c[2], r1), (c[3], c[0], r0)]
    else:
        f = [(c[1], c[2], r1), (c[1], r1, r0), (c[3], c[0], r0), (c[3], r0, r1), (c[0], c[1], r0), (c[2], c[3], r1)]
    f += [(c[0], c[2], c[1]), (c[0], c[3], c[2])]
    return np.array(f, float)


def rock(r, seed, n_lat=4, n_lon=6):
    """Lumpy boulder: a coarse UV sphere with deterministic radial noise, flattened a little."""
    rng = np.random.default_rng(seed)
    noise = rng.uniform(0.7, 1.15, (n_lat + 1, n_lon))
    pts = {}
    for i in range(n_lat + 1):
        th = math.pi * i / n_lat
        for j in range(n_lon):
            ph = 2 * math.pi * j / n_lon
            k = noise[i, j] if 0 < i < n_lat else noise[i, 0]
            pts[i, j] = (r * k * math.sin(th) * math.cos(ph), r * k * math.sin(th) * math.sin(ph), 0.7 * r * k * math.cos(th))
    f = []
    for i in range(n_lat):
        for j in range(n_lon):
            a, b, c, d = pts[i, j], pts[i, (j + 1) % n_lon], pts[i + 1, (j + 1) % n_lon], pts[i + 1, j]
            f += quad(a, d, c, b)
    return np.array(f, float)


def rot_z(t, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return t @ R.T


def rot_xyz(t, roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    R = np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                  [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                  [-sp, cp * sr, cp * cr]])
    return t @ R.T


def place(t, x, y, z, yaw=0.0):
    return rot_z(t, yaw) + np.array([x, y, z])


def segment(p0, p1, r, n=6):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    L = np.linalg.norm(d)
    c = cylinder(r, L, n)
    zc = d / L
    ref = np.array([1.0, 0, 0]) if abs(zc[0]) < 0.9 else np.array([0, 1.0, 0])
    xc = np.cross(ref, zc)
    xc /= np.linalg.norm(xc)
    yc = np.cross(zc, xc)
    return c @ np.stack([xc, yc, zc]) + p0


def ribbon(center, width, heights_fn, lift=0.0, n_across=6, profile=None):
    """Strip mesh draped on the terrain along a polyline (rivers, roads, mud flow)."""
    center = np.asarray(center, float)
    w = np.broadcast_to(np.asarray(width, float), (len(center),))
    tang = np.gradient(center, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
    grid = []
    for k in range(n_across + 1):
        s = -0.5 + k / n_across
        xy = center + nrm * (s * w)[:, None]
        z = heights_fn(xy[:, 0], xy[:, 1]) + lift + (profile(s) if profile else 0.0)
        grid.append(np.column_stack([xy, z]))
    f = []
    for k in range(n_across):
        a, b = grid[k], grid[k + 1]
        for i in range(len(center) - 1):
            f += quad(a[i], a[i + 1], b[i + 1], b[i])
    return np.array(f, float)


def merge(parts):
    parts = [p for p in parts if len(p)]
    return np.concatenate(parts) if parts else np.zeros((0, 3, 3))


def double_sided(t):
    t = np.asarray(t, float)
    return np.concatenate([t, t[:, ::-1]]) if len(t) else t
