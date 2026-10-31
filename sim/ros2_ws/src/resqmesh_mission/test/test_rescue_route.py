"""Tests for the rescue route."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resqmesh_mission'))

from rescue_route import plan  # noqa: E402


def test_alive_before_deceased_and_tour_is_short():
    ps = [{'id': 'D', 'x': 10, 'y': 0, 'condition': 'DECEASED_SUSPECTED'},
          {'id': 'A1', 'x': 100, 'y': 0, 'condition': 'ALIVE'}, {'id': 'A2', 'x': 50, 'y': 0, 'condition': 'ALIVE'},
          {'id': 'U', 'x': 5, 'y': 5, 'condition': 'UNKNOWN'}]
    r = plan((0, 0), ps)
    assert [p['id'] for p in r] == ['A2', 'A1', 'D']          # unconfirmed RGB candidates are not dispatched
    assert r[-1]['eta_s'] > r[0]['eta_s'] and abs(r[0]['leg_m'] - 50) < 1e-6


if __name__ == '__main__':
    test_alive_before_deceased_and_tour_is_short()
    print('ok')
