"""Collision mesh for the Wayanad terrain."""
import os

import numpy as np

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINE = (-650.0, 320.0, -1350.0, 160.0)


def grid_tris(X, Y, Z, keep=None):
    A = np.stack([X[:-1, :-1], Y[:-1, :-1], Z[:-1, :-1]], -1)
    B = np.stack([X[:-1, 1:], Y[:-1, 1:], Z[:-1, 1:]], -1)
    C = np.stack([X[1:, 1:], Y[1:, 1:], Z[1:, 1:]], -1)
    D = np.stack([X[1:, :-1], Y[1:, :-1], Z[1:, :-1]], -1)
    if keep is not None:
        A, B, C, D = A[keep], B[keep], C[keep], D[keep]
    A, B, C, D = (a.reshape(-1, 3) for a in (A, B, C, D))
    return np.concatenate([np.stack([A, B, C], 1), np.stack([A, C, D], 1)])


def main():
    import sys
    sys.path.insert(0, os.path.join(SIM, 'tools'))
    import meshlib as ml
    d = np.load(os.path.join(SIM, 'config', 'ground_truth.npz'))
    x0, y0, res, z = float(d['x0']), float(d['y0']), float(d['res']), d['z'].astype(np.float64)
    xs, ys = x0 + res * np.arange(z.shape[1]), y0 + res * np.arange(z.shape[0])
    out = []
    # fine: every 2nd sample inside FINE
    jf = np.where((xs >= FINE[0]) & (xs <= FINE[1]))[0][::2]
    i_f = np.where((ys >= FINE[2]) & (ys <= FINE[3]))[0][::2]
    X, Y = np.meshgrid(xs[jf], ys[i_f])
    out.append(grid_tris(X, Y, z[np.ix_(i_f, jf)]))
    fx0, fx1, fy0, fy1 = xs[jf[0]], xs[jf[-1]], ys[i_f[0]], ys[i_f[-1]]
    # coarse: every 6th sample, cells that are not wholly inside the fine patch
    jc, ic = np.arange(0, z.shape[1], 6), np.arange(0, z.shape[0], 6)
    X, Y = np.meshgrid(xs[jc], ys[ic])
    inside = (X[:-1, :-1] >= fx0) & (X[1:, 1:] <= fx1) & (Y[:-1, :-1] >= fy0) & (Y[1:, 1:] <= fy1)
    out.append(grid_tris(X, Y, z[np.ix_(ic, jc)], ~inside))
    tris = np.concatenate(out)
    d_out = os.path.join(SIM, 'models', 'resqmesh_wayanad_terrain', 'meshes')
    os.makedirs(d_out, exist_ok=True)
    ml.save_stl(os.path.join(d_out, 'collision.stl'), tris)
    print('terrain collision mesh: %d triangles (fine %.0fx%.0f m at %.0f m)' % (len(tris), fx1 - fx0, fy1 - fy0, 2 * res))


if __name__ == '__main__':
    main()
