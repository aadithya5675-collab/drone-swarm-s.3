"""Sharper terrain: ground.jpg 2048 -> 4096 px (0.9 m/px over 3.6 km) with fine luminance-only detail."""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(SIM, 'models', 'resqmesh_wayanad_terrain', 'materials', 'textures')
src = os.path.join(T, 'ground_2048.jpg')
if Image.open(os.path.join(T, 'ground.jpg')).size[0] < 4096:      # a fresh texture from gen_wayanad.py
    os.replace(os.path.join(T, 'ground.jpg'), src)
im = Image.open(src).convert('RGB').resize((4096, 4096), Image.BICUBIC)
a = np.asarray(im).astype(np.float32) / 255.0
rng = np.random.default_rng(7)
n1 = ndimage.gaussian_filter(rng.standard_normal((4096, 4096)).astype(np.float32), 1.0)
n2 = ndimage.gaussian_filter(rng.standard_normal((4096, 4096)).astype(np.float32), 4.0)
n1 /= n1.std()
n2 /= n2.std()
green = (a[..., 1] > a[..., 0] * 1.05).astype(np.float32)          # vegetation gets more grain than soil/road
k = 0.05 + 0.05 * green
a *= (1.0 + k[..., None] * (0.7 * n1 + 0.5 * n2)[..., None])
Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(T, 'ground.jpg'), quality=90)
print('ground.jpg 4096 px written')
