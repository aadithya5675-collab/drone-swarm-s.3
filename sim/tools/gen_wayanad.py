"""Generate the Wayanad world: real valley terrain, villages, forest, camp and debris path."""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshlib as ml  # noqa: E402

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TER = os.path.join(SIM, 'terrain')
MOD = os.path.join(SIM, 'models')
ap = argparse.ArgumentParser()
ap.add_argument('--seed', type=int, default=7)
args = ap.parse_args()
rng = np.random.default_rng(args.seed)

L = json.load(open(os.path.join(TER, 'layout.json')))
H0 = np.load(os.path.join(TER, 'dem_enu.npy'))           # row 0 = north edge, col 0 = west edge
SIZE, N = L['size'], L['n']
CAMP = np.array(L['camp'])                                # camp in DEM-ENU (relative to lat0/lon0)
R_E = 6378137.0
CELL = SIZE / (N - 1)


def to_world(p):
    return np.asarray(p, float) - CAMP


def grid_xy():
    xs = np.linspace(-SIZE / 2, SIZE / 2, N) - CAMP[0]
    ys = np.linspace(SIZE / 2, -SIZE / 2, N) - CAMP[1]
    return np.meshgrid(xs, ys)


XX, YY = grid_xy()


def sample(H, x, y, order=1):
    x, y = np.asarray(x, float), np.asarray(y, float)
    j = (x + CAMP[0] + SIZE / 2) / CELL
    i = (SIZE / 2 - (y + CAMP[1])) / CELL
    return ndimage.map_coordinates(H, [np.atleast_1d(i), np.atleast_1d(j)], order=order, mode='nearest').reshape(x.shape)


def polyline_resample(p, step):
    p = np.asarray(p, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    s = np.arange(0, d[-1], step)
    return np.column_stack([np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]), s


river, river_s = polyline_resample(to_world(L['path']), 4.0)
river = ndimage.gaussian_filter1d(river, 3, axis=0)
tree_r = cKDTree(river)
M_W, C_W = to_world(L['mundakkai']), to_world(L['chooralmala'])
s_m = river_s[tree_r.query(M_W)[1]]
CORR = (s_m - 300.0, s_m + 450.0)                         # search corridor along the river (m of path)
HALF_W = 85.0                                             # corridor half width
corr_mask = (river_s >= CORR[0]) & (river_s <= CORR[1])
corr_pts = river[corr_mask]

# road: follows the valley on the camp's bank, from the camp down to Mundakkai
k_camp = tree_r.query([0, 0])[1]
k_m = tree_r.query(M_W)[1]
seg = river[min(k_m, k_camp):max(k_m, k_camp) + 1]
side = np.sign(np.cross(np.r_[river[k_camp + 1] - river[k_camp], 0], np.r_[-river[k_camp], 0])[2]) or 1.0
tang = np.gradient(seg, axis=0)
tang /= np.linalg.norm(tang, axis=1, keepdims=True)
nrm = np.stack([-tang[:, 1], tang[:, 0]], 1) * side
road = ndimage.gaussian_filter1d(seg + nrm * 45.0, 6, axis=0)
road = np.vstack([[0.0, -20.0], road[::-1] if k_camp > k_m else road])  # starts at the camp gate
road, _ = polyline_resample(road, 6.0)
road = ndimage.gaussian_filter1d(road, 2, axis=0)
tree_road = cKDTree(road)

H = H0.copy()
pts = np.stack([XX.ravel(), YY.ravel()], 1)
d_riv = tree_r.query(pts)[0].reshape(H.shape)
d_road, k_road = tree_road.query(pts)
d_road, k_road = d_road.reshape(H.shape), k_road.reshape(H.shape)
riv_bed = ndimage.minimum_filter(H0, size=5)
H = np.where(d_riv < 14, np.minimum(H, riv_bed - 2.5 * np.clip(1 - d_riv / 14, 0, 1) ** 0.7), H)
road_z = ndimage.gaussian_filter1d(sample(H, road[:, 0], road[:, 1]), 4)
w = np.clip(1 - (d_road - 4) / 10, 0, 1)
H = H * (1 - w) + road_z[k_road] * w
h_camp = float(sample(H0, np.array([0.0]), np.array([0.0]))[0])
d_camp = np.hypot(XX, YY)
w = np.clip(1 - (d_camp - 70) / 45, 0, 1)
H = H * (1 - w) + h_camp * w
H = ndimage.gaussian_filter(H, 0.6)
H_MIN, H_MAX = float(H.min()), float(H.max())


def ground(x, y):
    return sample(H, x, y) - h_camp


slope = np.degrees(np.arctan(np.hypot(*np.gradient(H, CELL))))

TM = os.path.join(MOD, 'resqmesh_wayanad_terrain')
os.makedirs(os.path.join(TM, 'materials', 'textures'), exist_ok=True)
hm = np.round((H - H_MIN) / (H_MAX - H_MIN) * 65535).astype(np.uint16)
Image.fromarray(hm).save(os.path.join(TM, 'materials', 'textures', 'heightmap.png'))

T = 2048
ti = np.linspace(0, N - 1, T)
TI, TJ = np.meshgrid(ti, ti, indexing='ij')
up = lambda a, o=1: ndimage.map_coordinates(a, [TI, TJ], order=o)  # noqa: E731
hT, sT, drT, dwT = up(H), up(slope), up(d_riv), up(d_road)
xT, yT = up(XX), up(YY)
n1 = ndimage.gaussian_filter(rng.standard_normal((T, T)), 6)
n2 = ndimage.gaussian_filter(rng.standard_normal((T, T)), 1.2)
n1 /= n1.std()
n2 /= n2.std()
col = np.zeros((T, T, 3))
forest = np.array([0.13, 0.27, 0.11])
col[:] = forest * (1 + 0.18 * n1[..., None] + 0.12 * n2[..., None])
villages = [M_W, C_W]
d_vil = np.min([np.hypot(xT - v[0], yT - v[1]) for v in villages], axis=0)
nb = ndimage.gaussian_filter(rng.standard_normal((T // 8, T // 8)), 5)
nb = ndimage.zoom(nb / nb.std(), 8, order=1)[:T, :T]       # estate-scale blocks (~150 m)
tea = (sT > 5) & (sT < 28) & (hT < H_MIN + 380) & (d_vil < 1500) & (nb > -0.2) & (drT > 28)
track = np.abs(((hT - H_MIN) / 9.0) % 1.0 - 0.5) < 0.035
tea_c = np.array([0.35, 0.52, 0.15])[None, None] * (0.92 + 0.08 * n2[..., None] + 0.06 * n1[..., None])
col[tea] = tea_c[tea]
col[tea & track] = np.array([0.4, 0.36, 0.27])
TEA_MASK, CLEAR_MASK = tea.copy(), None
clear = (d_vil < 260) & (sT < 18)
col[clear] = (np.array([0.34, 0.44, 0.2]) * (1 + 0.15 * n2[..., None]))[clear]
CLEAR_MASK = clear.copy()
bank = drT < 18
col[bank] = (np.array([0.45, 0.43, 0.38]) * (1 + 0.2 * n2[..., None]))[bank]
water = drT < 6
col[water] = np.array([0.22, 0.3, 0.32])
rd = dwT < 3.0
col[rd] = np.array([0.42, 0.4, 0.37])
camp_pad = np.hypot(xT, yT) < 68
col[camp_pad] = (np.array([0.5, 0.47, 0.42]) * (1 + 0.08 * n2[..., None]))[camp_pad]
hill = ndimage.gaussian_filter(sT, 2)
col *= (0.78 + 0.22 * np.clip(1 - hill / 45, 0, 1))[..., None]
Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(os.path.join(TM, 'materials', 'textures', 'ground.jpg'), quality=92)
Image.new('RGB', (64, 64), (128, 128, 255)).save(os.path.join(TM, 'materials', 'textures', 'flat_normal.png'))

hm_center = -CAMP                                           # DEM grid centre in world coordinates
terrain_sdf = """<?xml version="1.0"?>
<sdf version="1.9">
  <model name="resqmesh_wayanad_terrain">
    <static>true</static>
    <link name="link">
      <!-- collision is a triangle mesh of the same ground (tools/terrain_collision.py): DART's heightmap
           collider gives spurious contacts at this size -->
      <collision name="collision">
        <geometry><mesh><uri>model://resqmesh_wayanad_terrain/meshes/collision.stl</uri></mesh></geometry>
      </collision>
      <visual name="visual">
        <geometry><heightmap>
          <use_terrain_paging>false</use_terrain_paging>
          <texture><diffuse>model://resqmesh_wayanad_terrain/materials/textures/ground.jpg</diffuse>
                   <normal>model://resqmesh_wayanad_terrain/materials/textures/flat_normal.png</normal><size>{s}</size></texture>
          <uri>model://resqmesh_wayanad_terrain/materials/textures/heightmap.png</uri>
          <size>{s} {s} {hz:.2f}</size><pos>{x:.2f} {y:.2f} {z:.2f}</pos>
        </heightmap></geometry>
      </visual>
    </link>
  </model>
</sdf>
""".format(s=SIZE, hz=H_MAX - H_MIN, x=hm_center[0], y=hm_center[1], z=H_MIN - h_camp)


MAT = {'wall_white': (0.9, 0.89, 0.85), 'wall_cream': (0.88, 0.8, 0.62), 'wall_blue': (0.62, 0.74, 0.82),
       'wall_pink': (0.86, 0.68, 0.66), 'wall_yellow': (0.9, 0.82, 0.45), 'roof_tile': (0.6, 0.25, 0.14),
       'roof_slab': (0.55, 0.55, 0.53), 'trunk': (0.3, 0.22, 0.14), 'leaf': (0.1, 0.3, 0.1),
       'leaf_light': (0.22, 0.42, 0.14), 'palm': (0.26, 0.44, 0.16), 'water': (0.25, 0.38, 0.42),
       'road': (0.32, 0.31, 0.3), 'mud': (0.36, 0.27, 0.18), 'mud_wet': (0.27, 0.2, 0.13), 'rock': (0.47, 0.45, 0.42),
       'log': (0.33, 0.24, 0.16), 'concrete': (0.66, 0.65, 0.62), 'steel': (0.6, 0.61, 0.63), 'red': (0.75, 0.1, 0.08),
       'white': (0.93, 0.93, 0.93), 'tent_orange': (0.9, 0.45, 0.12), 'tent_blue': (0.15, 0.35, 0.65),
       'tent_white': (0.92, 0.92, 0.9), 'olive': (0.3, 0.33, 0.2), 'pad': (0.2, 0.2, 0.22), 'pad_mark': (0.95, 0.75, 0.1),
       'black': (0.08, 0.08, 0.08), 'glass': (0.2, 0.3, 0.35), 'rubble': (0.55, 0.52, 0.48)}


def material(m, emissive=None):
    r, g, b = MAT[m]
    e = '<emissive>%s 1</emissive>' % emissive if emissive else ''
    return ('<material><ambient>{0:.3f} {1:.3f} {2:.3f} 1</ambient><diffuse>{0:.3f} {1:.3f} {2:.3f} 1</diffuse>'
            '<specular>0.05 0.05 0.05 1</specular>{e}</material>').format(r, g, b, e=e)


def write_model(name, groups, collide=None, pose=(0, 0, 0, 0), static=True, extra=''):
    """groups: {material: triangles}. Meshes are written in the model frame."""
    d = os.path.join(MOD, name, 'meshes')
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    vis, col = [], []
    for m, t in groups.items():
        if t is None or len(t) == 0:
            continue
        ml.save_stl(os.path.join(d, m + '.stl'), t)
        uri = 'model://%s/meshes/%s.stl' % (name, m)
        vis.append('<visual name="%s"><geometry><mesh><uri>%s</uri></mesh></geometry>%s</visual>' % (m, uri, material(m)))
        if collide is None or m in collide:
            col.append('<collision name="c_%s"><geometry><mesh><uri>%s</uri></mesh></geometry></collision>' % (m, uri))
    x, y, z, yaw = pose
    sdf = ('<?xml version="1.0"?>\n<sdf version="1.9"><model name="%s"><static>%s</static><pose>%.3f %.3f %.3f 0 0 %.4f</pose>'
           '<link name="link">%s%s</link>%s</model></sdf>\n') % (name, 'true' if static else 'false', x, y, z, yaw,
                                                                 ''.join(vis), ''.join(col), extra)
    open(os.path.join(MOD, name, 'model.sdf'), 'w').write(sdf)
    open(os.path.join(MOD, name, 'model.config'), 'w').write(
        '<?xml version="1.0"?><model><name>%s</name><version>1.0</version><sdf version="1.9">model.sdf</sdf>'
        '<author><name>Team Apex (generated)</name></author></model>\n' % name)
    return name


TILE = 400.0


def tile_of(x, y):
    return int(math.floor(x / TILE)), int(math.floor(y / TILE))


def slope_at(x, y):
    return float(sample(slope, np.array([x]), np.array([y]))[0])


def house_mesh(rng_, w_, d_, storeys):
    hh = 3.1 * storeys
    walls = ml.box(w_, d_, hh)
    if rng_.random() < 0.7:
        roof = ml.double_sided(ml.place(ml.hip_roof(w_, d_, 1.8 + 0.3 * rng_.random()), 0, 0, hh))
        rkey = 'roof_tile'
    else:
        roof = ml.place(ml.box(w_ + 0.4, d_ + 0.4, 0.25), 0, 0, hh)
        rkey = 'roof_slab'
    porch = ml.place(ml.box(w_ * 0.5, 2.0, 0.2), 0, -d_ / 2 - 1.0, 2.7)
    return walls, roof, rkey, porch


def site_ok(x, y, min_road=7, min_riv=24, max_slope=16):
    return (slope_at(x, y) < max_slope and tree_road.query([x, y])[0] > min_road and tree_r.query([x, y])[0] > min_riv
            and math.hypot(x, y) > 110)


houses, placed = [], []
for cx, cy, n_h, rad in ((M_W[0], M_W[1], 70, 300), (C_W[0], C_W[1], 55, 260)):
    tries = 0
    while n_h > 0 and tries < 6000:
        tries += 1
        a, r = rng.uniform(0, 2 * math.pi), rad * math.sqrt(rng.random())
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        if not site_ok(x, y) or any(math.hypot(x - p[0], y - p[1]) < 15 for p in placed):
            continue
        k = tree_road.query([x, y])[1]
        t = road[min(k + 1, len(road) - 1)] - road[max(k - 1, 0)]
        yaw = math.atan2(t[1], t[0]) + (math.pi / 2 if rng.random() < 0.5 else 0) + rng.normal(0, 0.15)
        placed.append((x, y))
        houses.append({'x': x, 'y': y, 'yaw': yaw, 'w': rng.uniform(7, 12), 'd': rng.uniform(6, 9),
                       'storeys': 2 if rng.random() < 0.25 else 1,
                       'wall': rng.choice(['wall_white', 'wall_cream', 'wall_blue', 'wall_pink', 'wall_yellow'])})
        n_h -= 1
for k in range(0, len(road), 9):                           # a few houses along the road
    x, y = road[k] + rng.normal(0, 4, 2)
    o = np.array([-(road[min(k + 1, len(road) - 1)] - road[k])[1], (road[min(k + 1, len(road) - 1)] - road[k])[0]])
    o = o / (np.linalg.norm(o) + 1e-9) * rng.choice([-14, 14])
    x, y = x + o[0], y + o[1]
    if site_ok(x, y) and not any(math.hypot(x - p[0], y - p[1]) < 15 for p in placed):
        placed.append((x, y))
        houses.append({'x': x, 'y': y, 'yaw': rng.uniform(0, 3.14), 'w': rng.uniform(7, 10), 'd': rng.uniform(6, 8),
                       'storeys': 1, 'wall': rng.choice(['wall_white', 'wall_cream'])})


def in_corridor(x, y, margin=0.0):
    d, k = tree_r.query([x, y])
    return CORR[0] - margin <= river_s[k] <= CORR[1] + margin and d < HALF_W + margin


def in_flow(x, y):
    d, k = tree_r.query([x, y])
    return d < flow_width(river_s[k]) / 2


S_END = river_s[tree_r.query(C_W)[1]] + 40.0


def flow_width(s):
    if s > S_END:
        return 0.0
    if s < CORR[0]:
        return 80.0 + 20 * math.sin(s / 90)
    if s <= CORR[1]:
        return 2 * HALF_W - 25 + 18 * math.sin(s / 70)
    return 70.0


village_groups, corridor_houses = {}, []
for i, h in enumerate(houses):
    z = float(ground(np.array([h['x']]), np.array([h['y']]))[0]) - 0.3
    walls, roof, rkey, porch = house_mesh(rng, h['w'], h['d'], h['storeys'])
    h['z'] = z
    if in_flow(h['x'], h['y']):
        name = 'resqmesh_house_%03d' % i
        write_model(name, {h['wall']: ml.merge([ml.rot_z(walls, 0), ml.rot_z(porch, 0)]), rkey: roof},
                    pose=(h['x'], h['y'], z, h['yaw']))
        corridor_houses.append(dict(h, name=name, roof=rkey))
    else:
        vt = village_groups.setdefault(tile_of(h['x'], h['y']), {})
        vt.setdefault(h['wall'], []).append(ml.place(ml.merge([walls, porch]), h['x'], h['y'], z, h['yaw']))
        vt.setdefault(rkey, []).append(ml.place(roof, h['x'], h['y'], z, h['yaw']))
village_models = [write_model('resqmesh_village_%d_%d' % (tx + 50, ty + 50), {k: ml.merge(v) for k, v in g.items()})
                  for (tx, ty), g in village_groups.items()]

def tree_mesh(rng_):
    h_ = rng_.uniform(10, 24)
    trunk = ml.cylinder(0.22 + 0.02 * h_, h_ * 0.7, 5)
    lobes = []
    for k in range(rng_.integers(2, 4)):
        rr = h_ * rng_.uniform(0.16, 0.24)
        lobes.append(ml.place(ml.rock(rr, int(rng_.integers(1e9)), 3, 5), *rng_.normal(0, rr * 0.5, 2), h_ * rng_.uniform(0.66, 0.86)))
    return trunk, ml.merge(lobes)


def land(x, y):
    i = int(np.clip((SIZE / 2 - (y + CAMP[1])) / SIZE * (T - 1), 0, T - 1))
    j = int(np.clip((x + CAMP[0] + SIZE / 2) / SIZE * (T - 1), 0, T - 1))
    return 'tea' if TEA_MASK[i, j] else ('clear' if CLEAR_MASK[i, j] else 'forest')


def palm_mesh(rng_):
    h_ = rng_.uniform(8, 15)
    lean = rng_.normal(0, 0.08)
    trunk = ml.rot_xyz(ml.cylinder(0.18, h_, 6, 0.14), lean, 0, 0)
    top = np.array([0, -math.sin(lean) * h_, math.cos(lean) * h_])
    fronds = []
    for k in range(7):
        a = 2 * math.pi * k / 7
        tip = top + np.array([3.2 * math.cos(a), 3.2 * math.sin(a), -1.4])
        fronds.append(ml.double_sided(ml.segment(top, tip, 0.35, 3)))
    return trunk, ml.merge(fronds)


forest_tiles = {}
corr_trees = {'trunk': [], 'leaf': [], 'palm': []}
d_house = cKDTree(np.array(placed)) if placed else None
n_tree = 0
for _ in range(60000):
    if n_tree > 7000:
        break
    x, y = rng.uniform(-SIZE / 2, SIZE / 2) - CAMP[0], rng.uniform(-SIZE / 2, SIZE / 2) - CAMP[1]
    if abs(x + CAMP[0]) > SIZE / 2 - 40 or abs(y + CAMP[1]) > SIZE / 2 - 40 or math.hypot(x, y) < 120:
        continue
    dr, dd = tree_r.query([x, y])[0], tree_road.query([x, y])[0]
    if dr < 12 or dd < 6:
        continue
    dview = min(math.hypot(x, y), tree_r.query([x, y])[0])
    if dview > 900 and rng.random() < 0.6:                 # thinner far from the valley floor and camp
        continue
    near_house = d_house is not None and d_house.query([x, y])[0] < 25
    lc = land(x, y)
    if lc == 'tea' and rng.random() > 0.05:
        continue
    if lc == 'clear' and not near_house and rng.random() > 0.15:
        continue
    z = float(ground(np.array([x]), np.array([y]))[0]) - 0.2
    tgt = corr_trees if in_flow(x, y) else forest_tiles.setdefault(tile_of(x, y), {'trunk': [], 'leaf': [], 'leaf_light': [], 'palm': []})
    if near_house:                                         # coconut / areca palms around homes
        t_, c_ = palm_mesh(rng)
        tgt['trunk'].append(ml.place(t_, x, y, z, rng.uniform(0, 6.28)))
        tgt['palm'].append(ml.place(c_, x, y, z, rng.uniform(0, 6.28)))
    else:
        t_, c_ = tree_mesh(rng)
        tgt['trunk'].append(ml.place(t_, x, y, z, 0))
        key = 'leaf' if (rng.random() < 0.65 or tgt is corr_trees) else 'leaf_light'
        tgt[key].append(ml.place(c_, x, y, z, rng.uniform(0, 6.28)))
    n_tree += 1
forest_models = [write_model('resqmesh_forest_%d_%d' % (tx + 50, ty + 50), {k: ml.merge(v) for k, v in g.items()}, collide=[])
                 for (tx, ty), g in forest_tiles.items()]
write_model('resqmesh_corridor_trees', {k: ml.merge(v) for k, v in corr_trees.items()}, collide=[])

river_mesh = ml.ribbon(river[::2], 11.0, ground, lift=-1.4, n_across=3)
road_mesh = ml.ribbon(road, 5.0, ground, lift=0.08, n_across=2)
write_model('resqmesh_wayanad_river_road', {'water': river_mesh, 'road': road_mesh}, collide=[])

kb = tree_r.query(C_W)[1]
bp = river[kb]
bt = river[min(kb + 2, len(river) - 1)] - river[max(kb - 2, 0)]
byaw = math.atan2(bt[1], bt[0]) + math.pi / 2
bz = float(ground(np.array([bp[0] + 20 * math.cos(byaw)]), np.array([bp[1] + 20 * math.sin(byaw)]))[0])
deck = ml.box(34, 6.5, 0.6)
rails = ml.merge([ml.place(ml.box(34, 0.25, 1.1), 0, y_, 0.6) for y_ in (-3.1, 3.1)])
piers = ml.merge([ml.place(ml.box(1.4, 6, 8), x_, 0, -8) for x_ in (-8, 8)])
write_model('resqmesh_chooralmala_bridge', {'concrete': ml.merge([deck, piers]), 'white': rails},
            pose=(bp[0], bp[1], bz - 0.4, byaw))

debris = []
s0 = max(river_s[0], CORR[0] - 900)
seg_len = 60.0
s_cuts = np.arange(s0, S_END, seg_len)
for k, a in enumerate(s_cuts):
    b = min(a + seg_len + 4, S_END)
    m_ = (river_s >= a) & (river_s <= b)
    if m_.sum() < 3:
        continue
    c = river[m_]
    wid = np.array([flow_width(s) for s in river_s[m_]])
    thick = 2.2 if CORR[0] <= a <= CORR[1] else 1.4
    lumpy = lambda x, y: ground(x, y) + 0.5 * np.sin(x / 9.0 + 1.3 * np.cos(y / 11.0)) * np.cos(y / 8.0)  # noqa: E731
    mud = ml.ribbon(c, wid, lumpy, lift=0.15, n_across=16, profile=lambda s, t=thick: t * (1 - (2 * s) ** 2) ** 0.6)
    wet = ml.ribbon(c, wid * 0.25, ground, lift=0.25, n_across=3, profile=lambda s, t=thick: t * 1.02)
    rocks, logs = [], []
    for _ in range(int(len(c) * (5.0 if CORR[0] <= a <= CORR[1] else 2.0))):
        i_ = rng.integers(len(c))
        off = rng.uniform(-0.45, 0.45) * wid[i_]
        tg = c[min(i_ + 1, len(c) - 1)] - c[max(i_ - 1, 0)]
        nv = np.array([-tg[1], tg[0]]) / (np.linalg.norm(tg) + 1e-9)
        x, y = c[i_] + nv * off
        z = float(ground(np.array([x]), np.array([y]))[0]) + thick * (1 - (2 * off / wid[i_]) ** 2) * 0.8
        if rng.random() < 0.7:
            rocks.append(ml.place(ml.rot_xyz(ml.rock((rng.uniform(0.3, 1.0) if rng.random() < 0.7 else rng.uniform(1.0, 3.5)), int(rng.integers(1e9))), *rng.uniform(0, 3, 3)), x, y, z))
        else:
            ln = rng.uniform(4, 11)
            a_ = rng.uniform(0, 6.28)
            logs.append(ml.segment((x, y, z + 0.3), (x + ln * math.cos(a_), y + ln * math.sin(a_), z + 0.3 + rng.normal(0, 0.6)), 0.25, 6))
    name = 'resqmesh_debris_%02d' % k
    write_model(name, {'mud': mud, 'mud_wet': wet, 'rock': ml.merge(rocks) if rocks else None, 'log': ml.merge(logs) if logs else None},
                collide=['mud', 'rock'])
    debris.append({'name': name, 's0': float(a), 's1': float(b), 'in_corridor': bool(CORR[0] <= a <= CORR[1]),
                   'center': [float(c[len(c) // 2][0]), float(c[len(c) // 2][1])], 'thickness': thick})

collapsed = []
for h in corridor_houses:
    wall_bits = [ml.place(ml.rot_xyz(ml.box(rng.uniform(2, h['w'] * 0.6), 0.25, rng.uniform(1, 2.5)), rng.uniform(-0.5, 0.5),
                                     rng.uniform(-0.3, 0.3), 0), rng.uniform(-3, 3), rng.uniform(-3, 3), 0, rng.uniform(0, 6.28))
                 for _ in range(4)]
    slab = ml.place(ml.rot_xyz(ml.box(h['w'] * 0.9, h['d'] * 0.8, 0.3), rng.uniform(0.2, 0.5), rng.uniform(-0.3, 0.3), 0), 0, 0, 0.8)
    rub = [ml.place(ml.rock(rng.uniform(0.4, 1.0), int(rng.integers(1e9))), *rng.uniform(-4, 4, 2), 0.3) for _ in range(10)]
    name = h['name'].replace('house', 'collapsed')
    write_model(name, {h['wall']: ml.merge(wall_bits), h['roof']: slab, 'rubble': ml.merge(rub)},
                pose=(h['x'] + rng.normal(0, 3), h['y'] + rng.normal(0, 3), h['z'] + 1.0, h['yaw'] + rng.normal(0, 0.5)))
    collapsed.append(name)

PADS = {'scout_1': (-21, -14), 'scout_2': (-14, -14), 'scout_3': (-7, -14), 'scout_4': (0, -14),
        'mapper_1': (7, -14), 'mapper_2': (14, -14), 'relay_1': (21, -14)}


def tower_mesh():
    """30 m three-section lattice telecom tower: tapered square legs, K/X bracing every 3 m, platform,."""
    st, red = [], []
    H_T, b0, b1 = 30.0, 2.2, 0.6
    half = lambda z: b0 + (b1 - b0) * z / H_T  # noqa: E731
    lv = np.arange(0, H_T + 0.01, 3.0)
    for k in range(len(lv) - 1):
        z0, z1 = lv[k], lv[k + 1]
        h0, h1 = half(z0), half(z1)
        tgt = red if int(z0 // 6) % 2 == 0 else st
        for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
            tgt.append(ml.segment((sx * h0, sy * h0, z0), (sx * h1, sy * h1, z1), 0.09, 6))
        ring = [(h1, h1), (h1, -h1), (-h1, -h1), (-h1, h1)]
        prev = [(h0, h0), (h0, -h0), (-h0, -h0), (-h0, h0)]
        for q in range(4):
            a, b = ring[q], ring[(q + 1) % 4]
            tgt.append(ml.segment((*a, z1), (*b, z1), 0.04, 4))
            pa, pb = prev[q], prev[(q + 1) % 4]
            tgt.append(ml.segment((*pa, z0), (*b, z1), 0.03, 4))
            tgt.append(ml.segment((*pb, z0), (*a, z1), 0.03, 4))
    plat = ml.place(ml.box(2.6, 2.6, 0.12), 0, 0, H_T)
    rail = ml.merge([ml.segment((x0, y0, H_T + 1.1), (x1, y1, H_T + 1.1), 0.03, 4) for (x0, y0), (x1, y1) in
                     (((-1.3, -1.3), (1.3, -1.3)), ((1.3, -1.3), (1.3, 1.3)), ((1.3, 1.3), (-1.3, 1.3)), ((-1.3, 1.3), (-1.3, -1.3)))])
    mast = ml.segment((0, 0, H_T), (0, 0, H_T + 6), 0.08, 8)
    panels = ml.merge([ml.place(ml.box(0.35, 0.15, 1.6), 1.1 * math.cos(a), 1.1 * math.sin(a), H_T + 0.8, a)
                       for a in (0.3, 0.3 + 2.094, 0.3 + 4.189)])
    dishes = ml.merge([ml.place(ml.rot_xyz(ml.cylinder(0.6, 0.3, 12, 0.2), 0, math.pi / 2, 0), 0.9, y_, 24.0, -2.2)
                       for y_ in (-0.4, 0.5)])
    beacon = ml.place(ml.cylinder(0.15, 0.3, 8), 0, 0, H_T + 6)
    shelter = ml.place(ml.box(3.2, 2.4, 2.6), 4.0, 0, 0)
    return {'steel': ml.merge(st + [plat, rail, mast]), 'red': ml.merge(red + [beacon]), 'white': ml.merge([panels, dishes]),
            'concrete': ml.merge([shelter, ml.place(ml.box(6, 6, 0.4), 0, 0, -0.2)])}


TOWER = (0.0, 18.0)
write_model('resqmesh_central_tower', tower_mesh(), pose=(TOWER[0], TOWER[1], 0.0, 0.3), collide=['concrete', 'steel'])


def tent(w_, d_, h_):
    roof = ml.double_sided(ml.place(ml.hip_roof(w_, d_, h_ * 0.45, 0.2), 0, 0, h_ * 0.55))
    return ml.box(w_, d_, h_ * 0.55), roof


camp = {k: [] for k in ('tent_white', 'tent_blue', 'tent_orange', 'pad', 'pad_mark', 'concrete', 'steel', 'black', 'olive', 'white')}
b_, r_ = tent(16, 9, 4.2)                                   # command post
camp['tent_white'].append(ml.place(b_, -32, 6, 0))
camp['tent_blue'].append(ml.place(r_, -32, 6, 0))
for k in range(6):                                          # relief / medical tents
    b_, r_ = tent(7, 5, 3.0)
    x_, y_ = -48 + 9 * (k % 3), -32 - 8 * (k // 3)
    camp['tent_white' if k < 2 else 'tent_orange'].append(ml.place(b_, x_, y_, 0))
    camp['tent_orange'].append(ml.place(r_, x_, y_, 0))
for name, (x_, y_) in PADS.items():                         # drone pads
    camp['pad'].append(ml.place(ml.box(3.2, 3.2, 0.08), x_, y_, 0))
    camp['pad_mark'].append(ml.place(ml.box(1.6, 0.18, 0.1), x_, y_, 0))
    camp['pad_mark'].append(ml.place(ml.box(0.18, 1.6, 0.1), x_, y_, 0))
camp['concrete'].append(ml.place(ml.cylinder(11, 0.15, 24), 38, 24, 0))   # helipad
camp['white'].append(ml.place(ml.box(0.8, 6, 0.18), 36, 24, 0))
camp['white'].append(ml.place(ml.box(0.8, 6, 0.18), 40, 24, 0))
camp['white'].append(ml.place(ml.box(4, 0.8, 0.18), 38, 24, 0))
for x_, y_ in ((-55, 25), (30, -30), (-10, 40), (50, 0)):  # floodlight masts
    camp['steel'].append(ml.place(ml.cylinder(0.12, 9, 6), x_, y_, 0))
    camp['black'].append(ml.place(ml.box(1.4, 0.4, 0.8), x_, y_, 9))
camp['olive'].append(ml.place(ml.box(2.2, 1.2, 1.4), -18, 22, 0))        # generator
for k in range(8):                                          # relief supply stacks
    camp['tent_white'].append(ml.place(ml.box(1.2, 1.0, 0.9), -8 + 1.3 * (k % 4), 30 + 1.1 * (k // 4), 0))
write_model('resqmesh_rescue_camp', {k: ml.merge(v) for k, v in camp.items()}, collide=['tent_white', 'concrete', 'olive'])

gen_thermal = ('<model name="camp_generator_heat"><static>true</static><pose>-18 22 1.5 0 0 0</pose><link name="l">'
               '<visual name="exhaust"><geometry><cylinder><radius>0.15</radius><length>0.8</length></cylinder></geometry>'
               '%s<plugin filename="gz-sim-thermal-system" name="gz::sim::systems::Thermal"><temperature>343</temperature>'
               '</plugin></visual></link></model>') % material('black')

FUEL = 'https://fuel.gazebosim.org/1.0/OpenRobotics/models/'
fuel_items = [('Ambulance', 'ambulance_1', (32, -2, 0, 1.57)), ('Fire truck', 'fire_truck_1', (44, -8, 0, 1.57)),
              ('Pickup', 'pickup_1', (26, 8, 0, 3.0)), ('Pickup', 'pickup_2', (-62, -6, 0, 0.2)),
              ('ground_station', 'ground_station_1', (-24, 10, 0, 0)), ('Jersey Barrier', 'barrier_1', (12, -38, 0, 0)),
              ('Jersey Barrier', 'barrier_2', (18, -38, 0, 0)), ('Standing person', 'rescuer_1', (-26, -2, 0, 2.0)),
              ('Standing person', 'rescuer_2', (-6, -20, 0, 1.2)), ('Standing person', 'rescuer_3', (10, -19, 0, 1.9))]

lat_c = L['lat0'] + math.degrees(CAMP[1] / R_E)
lon_c = L['lon0'] + math.degrees(CAMP[0] / (R_E * math.cos(math.radians(L['lat0']))))
open(os.path.join(TM, 'model.sdf'), 'w').write(terrain_sdf)
open(os.path.join(TM, 'model.config'), 'w').write('<?xml version="1.0"?><model><name>resqmesh_wayanad_terrain</name><version>1.0</version>'
                                                  '<sdf version="1.9">model.sdf</sdf></model>\n')


def inc(name, pose=None, uri=None, as_name=None):
    p = '<pose>%.2f %.2f %.2f 0 0 %.3f</pose>' % pose if pose else ''
    n = '<name>%s</name>' % as_name if as_name else ''
    return '    <include>%s<uri>%s</uri>%s</include>' % (n, uri or 'model://' + name, p)


includes = [inc('resqmesh_wayanad_terrain')] + [inc(m) for m in village_models + forest_models] + [
            inc('resqmesh_corridor_trees'), inc('resqmesh_wayanad_river_road'), inc('resqmesh_chooralmala_bridge'),
            inc('resqmesh_rescue_camp'), inc('resqmesh_central_tower')]
includes += [inc(h['name']) for h in corridor_houses]
for model, nm, (x_, y_, z_, yaw) in fuel_items:
    includes.append(inc(None, (x_, y_, z_, yaw), FUEL + model.replace(' ', '%20'), nm))
world = """<?xml version="1.0" ?>
<!-- generated by tools/gen_wayanad.py --seed {seed}; terrain: AWS Terrain Tiles (SRTM, Mapzen terrarium) -->
<sdf version="1.9">
  <world name="resqmesh_wayanad">
    <physics name="4ms" type="ignored">
      <max_step_size>0.004</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>250</real_time_update_rate>
    </physics>
    <gravity>0 0 -9.8</gravity>
    <magnetic_field>6e-06 2.3e-05 -4.2e-05</magnetic_field>
    <atmosphere type="adiabatic"><temperature>296.15</temperature></atmosphere>
    <!-- SW monsoon, ~3.2 m/s from WSW; gusts in config/gz_server.config -->
    <wind><linear_velocity>3.0 1.2 0</linear_velocity></wind>
    <scene>
      <ambient>0.38 0.42 0.50 1</ambient>
      <background>0.62 0.74 0.86 1</background>
      <shadows>true</shadows>
      <grid>false</grid>
      <sky></sky>
    </scene>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 300 0 0 0</pose>
      <diffuse>1.0 0.92 0.80 1</diffuse>
      <specular>0.25 0.24 0.22 1</specular>
      <direction>-0.62 0.42 -0.66</direction>
    </light>
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>{lat:.7f}</latitude_deg>
      <longitude_deg>{lon:.7f}</longitude_deg>
      <elevation>{elev:.1f}</elevation>
    </spherical_coordinates>
{inc}
    {gen}
  </world>
</sdf>
""".format(seed=args.seed, lat=lat_c, lon=lon_c, elev=h_camp, inc='\n'.join(includes), gen=gen_thermal)
open(os.path.join(SIM, 'worlds', 'resqmesh_wayanad.sdf'), 'w').write(world)

corr_line = river[corr_mask]
cs = river_s[corr_mask]
n_sec = 4
sectors = []
for k in range(n_sec):
    a, b = CORR[0] + k * (CORR[1] - CORR[0]) / n_sec, CORR[0] + (k + 1) * (CORR[1] - CORR[0]) / n_sec
    m_ = (cs >= a) & (cs <= b)
    p0, p1 = corr_line[m_][0], corr_line[m_][-1]
    sectors.append({'id': 'Z%d' % (k + 1), 'start': p0.round(1).tolist(), 'end': p1.round(1).tolist(), 'half_width': HALF_W})
step = 8
gx = np.arange(-SIZE / 2 - CAMP[0], SIZE / 2 - CAMP[0], step)
gy = np.arange(-SIZE / 2 - CAMP[1], SIZE / 2 - CAMP[1], step)
GX, GY = np.meshgrid(gx, gy)
prior = ndimage.gaussian_filter(sample(H0, GX, GY) - h_camp, 2)  # pre-disaster, coarse: what a rescue team has
np.savez_compressed(os.path.join(SIM, 'config', 'dem_prior.npz'), x0=gx[0], y0=gy[0], res=step, z=prior.astype(np.float32))
tx_ = np.arange(-SIZE / 2 - CAMP[0], SIZE / 2 - CAMP[0], 2.0)
ty_ = np.arange(-SIZE / 2 - CAMP[1], SIZE / 2 - CAMP[1], 2.0)
TXX, TYY = np.meshgrid(tx_, ty_)
np.savez_compressed(os.path.join(SIM, 'config', 'ground_truth.npz'), x0=tx_[0], y0=ty_[0], res=2.0,
                    z=(sample(H, TXX, TYY) - h_camp).astype(np.float32))   # SIM ONLY: exact simulated ground
info = {
    'world': 'resqmesh_wayanad', 'seed': args.seed,
    'origin': {'lat': lat_c, 'lon': lon_c, 'alt': h_camp},
    'tower': {'x': TOWER[0], 'y': TOWER[1], 'z': 30.0},
    'pads': {k: list(v) for k, v in PADS.items()},
    'mundakkai': M_W.round(1).tolist(), 'chooralmala': C_W.round(1).tolist(),
    'river': river[::5].round(1).tolist(), 'river_s': river_s[::5].round(1).tolist(),
    'corridor': {'s0': CORR[0], 's1': CORR[1], 'half_width': HALF_W, 'line': corr_line[::3].round(1).tolist()},
    'sectors': sectors,
    'landslide': {'debris': debris, 'remove': [h['name'] for h in corridor_houses] + ['resqmesh_corridor_trees', 'resqmesh_chooralmala_bridge'],
                  'collapsed': collapsed, 'houses': [{'name': h['name'], 'x': h['x'], 'y': h['y']} for h in corridor_houses],
                  'bridge': bp.round(1).tolist()},
}
json.dump(info, open(os.path.join(SIM, 'config', 'wayanad.json'), 'w'), indent=1)
print('terrain %.0f..%.0f m (camp %.0f m, %.6f N %.6f E)' % (H_MIN, H_MAX, h_camp, lat_c, lon_c))
print('houses: %d in villages, %d in the flow path; trees %d; debris segments %d (%d in corridor)'
      % (len(houses) - len(corridor_houses), len(corridor_houses), n_tree, len(debris), sum(d['in_corridor'] for d in debris)))
print('corridor %.0f..%.0f m along the river, mundakkai at %s; camp-to-Mundakkai %.0f m'
      % (CORR[0], CORR[1], M_W.round(0), np.linalg.norm(M_W)))

import terrain_collision  # noqa: E402
terrain_collision.main()

# textured debris / rubble visuals (see tools/texture_scene.py)
import texture_scene  # noqa: E402
texture_scene.main()

# PBR finish on the generated models (see tools/polish_materials.py)
import polish_materials  # noqa: E402
polish_materials.main()

# 4096 px ground texture with fine detail (see tools/ground_detail.py)
import ground_detail  # noqa: E402,F401
