"""Turn the Fusion per-body STL export into Gazebo meshes for the ResQMesh quad."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
EXP = os.path.join(SIM, 'cad_export')
OUT = os.path.join(SIM, 'models', 'resqmesh_quad', 'meshes')
os.makedirs(OUT, exist_ok=True)

STL = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def load(path):
    b = open(path, 'rb').read()
    n = int.from_bytes(b[80:84], 'little')
    return np.frombuffer(b[84:84 + n * 50], dtype=STL)['v'].astype(float)  # (n, 3, 3)


def decimate(tris, cell):
    v = tris.reshape(-1, 3)
    key = np.floor(v / cell).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    cnt = np.bincount(inv)
    rep = np.stack([np.bincount(inv, v[:, k]) / cnt for k in range(3)], 1)   # cluster centroid
    f = inv.reshape(-1, 3)
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = np.unique(np.sort(f[keep], 1), axis=0, return_index=True)[1]
    f = inv.reshape(-1, 3)[keep][np.sort(f)]
    return rep[f]


def save(path, tris):
    tris = np.asarray(tris, dtype='<f4')
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    nrm = np.cross(e1, e2)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=STL)
    rec['n'], rec['v'] = nrm, tris
    with open(path, 'wb') as f:
        f.write(b'resqmesh'.ljust(80, b' '))
        f.write(len(tris).to_bytes(4, 'little'))
        f.write(rec.tobytes())


man = json.load(open(os.path.join(EXP, 'manifest.json')))
T = json.load(open(os.path.join(EXP, 'transforms.json')))
groups = {}
for e in man['bodies']:
    v = load(os.path.join(EXP, 'bodies', e['file'])).reshape(-1, 3)
    M = np.array(T[e['occurrence']]).reshape(4, 4)
    w = (M[:3, :3] @ v.T).T + M[:3, 3] * 10.0          # fusion world, mm (transform translation is cm)
    g = w[:, [2, 0, 1]] / 1000.0                        # gazebo axes, metres
    groups.setdefault(e['group'], []).append(g.reshape(-1, 3, 3))
groups = {k: np.concatenate(v) for k, v in groups.items()}

motors = sorted(k for k in groups if k.startswith('motor_'))
axes = np.array([groups[m].reshape(-1, 3)[:, :2].mean(0) for m in motors])
mount_z = min(groups[m].reshape(-1, 3)[:, 2].min() for m in motors)
origin = np.array([axes[:, 0].mean(), axes[:, 1].mean(), mount_z])
groups = {k: v - origin for k, v in groups.items()}
axes = axes - origin[:2]

body = np.concatenate([groups[k] for k in groups if not k.startswith('prop_') and k != 'battery'])
body = decimate(body, 0.0015)
save(os.path.join(OUT, 'body.stl'), body)
save(os.path.join(OUT, 'battery.stl'), decimate(groups['battery'], 0.0015))

p = groups['prop_1']
pc = p.reshape(-1, 3)[:, :2].mean(0)
hub = axes[np.argmin(np.linalg.norm(axes - pc, axis=1))]
prop = p - np.array([hub[0], hub[1], 0.0])
prop_z = prop.reshape(-1, 3)[:, 2].min()
prop = prop - np.array([0, 0, prop_z])
prop = decimate(prop, 0.0012)
save(os.path.join(OUT, 'prop.stl'), prop)                    # the CAD prop turns counter-clockwise
cw = prop[:, ::-1].copy()                                    # mirror image (and winding) = clockwise prop
cw[..., 1] *= -1
save(os.path.join(OUT, 'prop_cw.stl'), cw)

prop_r = np.linalg.norm(prop.reshape(-1, 3)[:, :2], axis=1).max()
bv = body.reshape(-1, 3)
ROLE_DIR = os.path.join(EXP, 'roles')
roles = {}
if os.path.isdir(ROLE_DIR):
    for f in os.listdir(OUT):
        if '__' in f:
            os.remove(os.path.join(OUT, f))
    pay = json.load(open(os.path.join(ROLE_DIR, 'payloads.json')))
    for role, spec in pay.items():
        parts = []
        for part in spec['parts']:
            allv, files, by_col = [], [], {}
            for fi in part['files']:
                t = load(os.path.join(ROLE_DIR, fi['file']))
                t = (t.reshape(-1, 3)[:, [2, 0, 1]] / 1000.0 - origin).reshape(-1, 3, 3)
                by_col.setdefault(fi['colour'], []).append(decimate(t, 0.0008))
            for col, ts in by_col.items():
                t = np.concatenate(ts)
                name = fi['file'].split('__')[0] + '__' + fi['file'].split('__')[1] + '__' + col + '.stl'
                save(os.path.join(OUT, name), t)
                files.append({'mesh': name, 'colour': col})
                allv.append(t.reshape(-1, 3))
            v = np.concatenate(allv)
            parts.append({'part': part['part'], 'files': files,
                          'bbox_m': [np.round(v.min(0), 4).tolist(), np.round(v.max(0), 4).tolist()]})
        roles[role] = {'hide': spec['hide'], 'parts': parts}

geo = {
    'frame': 'gazebo FLU, metres, origin = centre of motor axes at motor mounting face',
    'origin_in_gazebo_axes_before_shift_m': np.round(origin, 5).tolist(),
    'roles': roles,
    'motor_xy_m': {m: [round(float(a), 4) for a in ax] for m, ax in zip(motors, axes)},
    'prop_plane_z_m': round(float(prop_z), 4),
    'prop_radius_m': round(float(prop_r), 4),
    'body_bbox_m': [np.round(bv.min(0), 4).tolist(), np.round(bv.max(0), 4).tolist()],
    'battery_bbox_m': [np.round(groups['battery'].reshape(-1, 3).min(0), 4).tolist(),
                       np.round(groups['battery'].reshape(-1, 3).max(0), 4).tolist()],
    'triangles': {'body': int(len(body)), 'prop': int(len(prop))},
}
json.dump(geo, open(os.path.join(EXP, 'geometry.json'), 'w'), indent=1)
print('geometry.json: %d role(s), body %d triangles' % (len(roles), len(body)))
