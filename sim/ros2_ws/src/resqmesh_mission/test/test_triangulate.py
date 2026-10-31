"""Tests for multi-view triangulation."""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resqmesh_mission'))

from triangulate import triangulate  # noqa: E402

P = np.array([10.0, 20.0, 3.0])          # a person lying on debris 3 m above the old DEM


def ray(cam, noise_deg=0.0, rng=None):
    d = P - cam
    d /= np.linalg.norm(d)
    if noise_deg:
        d = d + np.radians(noise_deg) * rng.standard_normal(3)
        d /= np.linalg.norm(d)
    return (*cam, *d)


def ground_drop(r, z):
    o, d = np.array(r[:3]), np.array(r[3:])
    s = (z - o[2]) / d[2]
    return o + s * d


def test_two_passes_from_opposite_sides_meet_at_the_person():
    rng = np.random.default_rng(1)
    north = [np.array([10.0 + dx, -10.0, 21.0]) for dx in (-12, -6, 0, 6, 12)]     # pass looking north
    south = [np.array([10.0 + dx, 50.0, 21.0]) for dx in (-12, -6, 0, 6, 12)]      # pass looking south
    rays = [ray(c, 0.4, rng) for c in north + south]
    a, b = ground_drop(rays[2], 0.0), ground_drop(rays[7], 0.0)
    assert np.hypot(*(a - b)[:2]) > 10.0
    x, y, z, rms, spread, used = triangulate(rays, (10.0, 20.0, 0.0))
    assert math.hypot(x - P[0], y - P[1]) < 1.0 and used == len(rays)


def test_a_single_moving_pass_has_enough_baseline():
    rng = np.random.default_rng(2)
    cams = [np.array([-15.0 + 3.0 * k, -12.0, 18.0]) for k in range(9)]              # 24 m along track
    x, y, *_ = triangulate([ray(c, 0.3, rng) for c in cams], (10.0, 24.0, 0.0))    # ground guess 4 m off
    assert math.hypot(x - P[0], y - P[1]) < 2.0


def test_a_stray_ray_does_not_drag_the_fix():
    rng = np.random.default_rng(3)
    cams = [np.array([10.0 + dx, -10.0, 21.0]) for dx in (-12, -6, 0, 6, 12)] + [np.array([30.0, 40.0, 21.0])]
    rays = [ray(c, 0.3, rng) for c in cams]
    o = np.array([40.0, 40.0, 21.0])
    bad = (o - np.array([60.0, 0.0, 0.0])) * -1.0
    rays.append((*o, *(bad / np.linalg.norm(bad))))                                  # points somewhere else
    x, y, *_ = triangulate(rays, (10.0, 20.0, 0.0))
    assert math.hypot(x - P[0], y - P[1]) < 2.0


def test_parallel_rays_carry_no_depth():
    cams = [np.array([0.0, -10.0, 21.0]), np.array([0.05, -10.0, 21.0])]
    assert triangulate([ray(c) for c in cams], (10.0, 20.0, 0.0)) is None


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f()
            print('ok', n)
