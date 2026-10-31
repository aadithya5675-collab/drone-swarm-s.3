"""Sector geometry: lawnmower passes along a sector and the grid cells inside it."""
import math


def oriented_lawnmower(start, end, half_width, spacing, z):
    ax, ay = end[0] - start[0], end[1] - start[1]
    L = math.hypot(ax, ay)
    ux, uy = ax / L, ay / L
    nx, ny = -uy, ux
    passes = max(1, int(math.ceil(2 * half_width / spacing)))
    pts = []
    for k in range(passes + 1):
        off = -half_width + k * 2 * half_width / passes
        a = (start[0] + nx * off, start[1] + ny * off, z)
        b = (end[0] + nx * off, end[1] + ny * off, z)
        pts += [a, b] if k % 2 == 0 else [b, a]
    return pts


def sector_cells(start, end, half_width, x0, y0, res, w, h):
    """Indices (i, j) of grid cells inside an oriented sector rectangle (for map-coverage checks)."""
    ax, ay = end[0] - start[0], end[1] - start[1]
    L = math.hypot(ax, ay)
    ux, uy = ax / L, ay / L
    out = []
    i0 = max(0, int((min(start[1], end[1]) - half_width - y0) / res))
    i1 = min(h, int((max(start[1], end[1]) + half_width - y0) / res) + 1)
    j0 = max(0, int((min(start[0], end[0]) - half_width - x0) / res))
    j1 = min(w, int((max(start[0], end[0]) + half_width - x0) / res) + 1)
    for i in range(i0, i1):
        for j in range(j0, j1):
            px, py = x0 + (j + 0.5) * res - start[0], y0 + (i + 0.5) * res - start[1]
            s, t = px * ux + py * uy, -px * uy + py * ux
            if 0 <= s <= L and abs(t) <= half_width:
                out.append((i, j))
    return out
