"""Tests for the Bayesian search map."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resqmesh_mission'))

from search_map import SearchMap  # noqa: E402

LINE = [(0, 0), (0, 400)]


def test_prior_is_a_distribution_inside_the_corridor():
    m = SearchMap(LINE, 50, houses=[(10, 200)])
    assert abs(m.p.sum() - 1) < 1e-9 and m.p[~m.mask].sum() == 0 and m.pos < 1e-9


def test_sweeping_everything_twice_drives_pos_up_like_search_theory():
    m = SearchMap(LINE, 50)
    for x in range(-45, 50, 10):
        m.observe((x, -10), (x, 410), 12, 0.8)
    assert 0.8 <= m.pos < 0.97
    for x in range(-45, 50, 10):
        m.observe((x, -10), (x, 410), 12, 0.8)
    assert m.pos >= 0.96                        # two passes: >= 1 - 0.2^2


def test_sector_mass_follows_the_houses():
    m = SearchMap(LINE, 50, houses=[(0, 350)])
    assert m.mass_in((0, 300), (0, 400), 50) > m.mass_in((0, 0), (0, 100), 50)


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f()
            print('ok', n)
