"""Tests for frames and geodesy."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from resqmesh_mission import coverage, geo  # noqa: E402


def rotate(R, v):
    return [sum(R[i][k] * v[k] for k in range(3)) for i in range(3)]


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def test_px4_attitude_conversion():
    R = geo.quat_to_rot(*geo.ned_frd_to_enu_flu((1.0, 0.0, 0.0, 0.0)))   # PX4 identity: nose north, level
    assert close(rotate(R, [1, 0, 0]), [0, 1, 0]) and close(rotate(R, [0, 0, 1]), [0, 0, 1])
    c = math.sqrt(0.5)
    R = geo.quat_to_rot(*geo.ned_frd_to_enu_flu((c, 0.0, 0.0, c)))       # yaw 90: nose east
    assert close(rotate(R, [1, 0, 0]), [1, 0, 0])


def test_wgs84_radii_and_px4_scale():
    m0, n0 = geo.wgs84_radii(0.0)
    assert abs(m0 - 6335439.3) < 1.0 and abs(n0 - 6378137.0) < 1e-6
    ke, kn = geo.px4_scale(11.4955458)
    assert abs(kn - 0.99482) < 1e-4 and abs(ke - 1.00125) < 1e-4
    lat, _ = geo.enu_to_latlon(0.0, 1000.0, 11.4955458, 76.1562884)
    assert abs((lat - 11.4955458) * math.pi / 180 * 6337966.9 - 1000.0) < 0.01


def test_lawnmower_spans_the_sector():
    pts = coverage.oriented_lawnmower((0, 0), (100, 0), 20, 10, 18)
    ys = sorted({round(p[1], 6) for p in pts})
    assert ys[0] == -20 and ys[-1] == 20 and len(ys) == 5 and all(p[2] == 18 for p in pts)


def test_sector_cells_inside_only():
    cells = coverage.sector_cells((0, 0), (40, 0), 10, -50, -50, 2.0, 50, 50)
    for i, j in cells:
        x, y = -50 + (j + 0.5) * 2.0, -50 + (i + 0.5) * 2.0
        assert 0 <= x <= 40 and abs(y) <= 10
    assert len(cells) == 20 * 10


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f()
            print('ok', n)
