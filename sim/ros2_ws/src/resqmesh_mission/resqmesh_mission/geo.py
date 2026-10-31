"""Frames and geodesy: PX4 to ENU attitude, WGS84 radii, ENU to latitude/longitude."""
import math

EARTH_R = 6378137.0                         # WGS84 semi-major axis
WGS84_E2 = 6.69437999014e-3                 # WGS84 first eccentricity squared
PX4_EARTH_R = 6371000.0


def wgs84_radii(lat_deg):
    w = math.sqrt(1.0 - WGS84_E2 * math.sin(math.radians(lat_deg)) ** 2)
    return EARTH_R * (1.0 - WGS84_E2) / w ** 3, EARTH_R / w


def px4_scale(lat_deg):
    m, n = wgs84_radii(lat_deg)
    return n / PX4_EARTH_R, m / PX4_EARTH_R


def enu_to_latlon(x, y, lat0, lon0):
    m, n = wgs84_radii(lat0)
    lat = lat0 + math.degrees(y / m)
    lon = lon0 + math.degrees(x / (n * math.cos(math.radians(lat0))))
    return lat, lon


def quat_to_rot(w, x, y, z):
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def camera_rot(pitch):
    c, s = math.cos(pitch), math.sin(pitch)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def ned_frd_to_enu_flu(q):
    w, x, y, z = q
    s = math.sqrt(0.5)
    a = (0.0, s, s, 0.0)
    b = (0.0, 1.0, 0.0, 0.0)    # FLU -> FRD (180 deg about x)
    return qmul(qmul(a, (w, x, y, z)), b)


def qmul(p, q):
    w1, x1, y1, z1 = p
    w2, x2, y2, z2 = q
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)
