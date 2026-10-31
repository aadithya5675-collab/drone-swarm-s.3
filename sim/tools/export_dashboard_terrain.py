"""Height grid for the dashboard's 3D twin (writes dashboard/terrain.json)."""
import json
import os

import numpy as np
from scipy import ndimage

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = json.load(open(os.path.join(SIM, 'dashboard', 'valley.json')))
d = np.load(os.path.join(SIM, 'config', 'ground_truth.npz'))
x0, y0, res, z = float(d['x0']), float(d['y0']), float(d['res']), d['z'].astype(np.float64)
R = 10.0
xs = np.arange(V['x0'], V['x1'] + 0.1, R)
ys = np.arange(V['y0'], V['y1'] + 0.1, R)
X, Y = np.meshgrid(xs, ys)
Z = ndimage.map_coordinates(z, [(Y - y0) / res, (X - x0) / res], order=1, mode='nearest')
out = {'x0': float(xs[0]), 'y0': float(ys[0]), 'res': R, 'w': len(xs), 'h': len(ys), 'z': [round(float(v), 1) for v in Z.ravel()]}
json.dump(out, open(os.path.join(SIM, 'dashboard', 'terrain.json'), 'w'), separators=(',', ':'))
print('terrain.json %dx%d, z %.0f..%.0f m' % (len(xs), len(ys), Z.min(), Z.max()))
