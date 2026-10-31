"""Ground-team rescue route from the camp: the living first, then the deceased to verify."""
import math

DEBRIS_MPS = 0.6


def tour_length(start, pts, order):
    p, d = start, 0.0
    for i in order:
        d += math.dist(p, pts[i])
        p = pts[i]
    return d


def two_opt(start, pts, order):
    best = list(order)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                if tour_length(start, pts, cand) < tour_length(start, pts, best) - 1e-9:
                    best, improved = cand, True
    return best


def plan(camp, persons):
    """persons: [{'id','x','y','condition'}] -> [{'id','x','y','condition','leg_m','eta_s'}] in visiting order."""
    out, here, t = [], tuple(camp), 0.0
    for group in (['ALIVE'], ['DECEASED_SUSPECTED']):
        ps = [p for p in persons if p['condition'] in group]
        pts = [(p['x'], p['y']) for p in ps]
        order, left, cur = [], set(range(len(ps))), here
        while left:
            k = min(left, key=lambda i: math.dist(cur, pts[i]))
            order.append(k)
            left.discard(k)
            cur = pts[k]
        for k in two_opt(here, pts, order):
            leg = math.dist(here, pts[k])
            t += leg / DEBRIS_MPS
            here = pts[k]
            out.append({'id': ps[k]['id'], 'x': ps[k]['x'], 'y': ps[k]['y'], 'condition': ps[k]['condition'],
                        'leg_m': round(leg, 1), 'eta_s': round(t)})
    return out
