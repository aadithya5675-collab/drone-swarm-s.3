"""Mass, centre of mass and inertia for each ResQMesh role, from CAD envelopes + vehicle_params.yaml masses."""
import json
import os

import numpy as np
import yaml

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def box_inertia(m, size):
    x, y, z = size
    return np.diag([m * (y * y + z * z), m * (x * x + z * z), m * (x * x + y * y)]) / 12.0


def parts_for(role, geo, par):
    b = par['base']
    out = []
    span = 2 * max(abs(v) for xy in geo['motor_xy_m'].values() for v in xy)
    out.append(('frame', b['frame_kg'], [0, 0, 0.005], [span, span, 0.03]))
    for k, (x, y) in geo['motor_xy_m'].items():
        out.append((k, b['motor_kg'], [x, y, 0.012], [0.028, 0.028, 0.032]))
        out.append(('prop_' + k[-1], b['prop_kg'], [x, y, geo['prop_plane_z_m'] + 0.004], [0.09, 0.09, 0.008]))
    spec = geo['roles'][role]
    if '4s lipo' not in spec['hide']:
        lo, hi = np.array(geo['battery_bbox_m'])
        out.append(('battery', b['battery_kg'], ((lo + hi) / 2).tolist(), (hi - lo).tolist()))
    for p in spec['parts']:
        if role == 'mapper' and 'thermal' in p['part'].lower():
            continue                     # no camera on the Mapper (see gen_models.py)
        lo, hi = np.array(p['bbox_m'])
        size = hi - lo
        if p['part'].startswith('Landing gear'):
            size = size * np.array([1.0, 1.0, 0.6])
        out.append((p['part'], par['payload_kg'][p['part']], ((lo + hi) / 2).tolist(), size.tolist()))
    return out


def mass_props(role):
    geo = json.load(open(os.path.join(SIM, 'cad_export', 'geometry.json')))
    par = yaml.safe_load(open(os.path.join(SIM, 'config', 'vehicle_params.yaml')))
    parts = parts_for(role, geo, par)
    m = sum(p[1] for p in parts)
    com = sum(p[1] * np.array(p[2]) for p in parts) / m
    I = np.zeros((3, 3))
    for _, mi, c, s in parts:
        d = np.array(c) - com
        I += box_inertia(mi, s) + mi * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return {'mass_kg': round(float(m), 4), 'com_m': np.round(com, 4).tolist(),
            'inertia': {k: float('%.4g' % I[i, j]) for k, (i, j) in
                        {'ixx': (0, 0), 'iyy': (1, 1), 'izz': (2, 2), 'ixy': (0, 1), 'ixz': (0, 2), 'iyz': (1, 2)}.items()},
            'parts': [(p[0], p[1]) for p in parts]}


if __name__ == '__main__':
    for r in ('scout', 'mapper', 'relay'):
        mp = mass_props(r)
        print(r, mp['mass_kg'], 'kg  com', mp['com_m'], ' I', mp['inertia'])
