"""Tests for the story task planner."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resqmesh_mission'))

from story_plan import TaskPlan  # noqa: E402

LINE = [(0, 0, 18), (100, 0, 18), (100, 20, 18), (0, 20, 18)]
POS = {'scout_1': (0, 0), 'scout_2': (300, 0), 'mapper_1': (0, 0), 'mapper_2': (300, 0)}


def make():
    p = TaskPlan()
    p.add_task('M1', 'mapper', LINE)
    p.add_task('M2', 'mapper', [(x + 300, y, z) for x, y, z in LINE])
    p.add_task('Z1', 'scout', LINE, needs_map=True)
    p.add_task('Z2', 'scout', [(x + 300, y, z) for x, y, z in LINE], needs_map=True)
    for d in ('scout_1', 'scout_2'):
        p.add_drone(d, 'scout')
    for d in ('mapper_1', 'mapper_2'):
        p.add_drone(d, 'mapper')
    return p


def test_scouts_hold_until_mapped():
    p = make()
    ready = set()
    new = p.assign(POS, lambda r: r in ready)
    assert new['scout_1'].tid == 'Z1' and new['scout_2'].tid == 'Z2'
    assert new['mapper_1'].tid == 'M1' and new['mapper_2'].tid == 'M2'
    assert [t.tid for t in p.releasable(lambda r: r in ready)] == ['M1', 'M2']
    ready.add('Z1')
    assert sorted(t.tid for t in p.releasable(lambda r: r in ready)) == ['M1', 'M2', 'Z1']


def test_progress_only_counts_released_paths():
    p = make()
    p.assign(POS, lambda r: False)
    assert p.progress('scout_1', 3) is None          # holding, not flying the sector yet
    assert p.tasks['Z1'].done == 0


def test_lost_scout_remainder_resumes_one_leg_early_and_keeps_map_gate():
    p = make()
    ready = {'Z1'}
    p.assign(POS, lambda r: r in ready)
    for t in p.releasable(lambda r: r in ready):
        t.released = True
    p.progress('scout_1', 3)
    rid = p.lose('scout_1')
    r = p.tasks[rid]
    assert rid == 'Z1.1' and r.start == 2 and r.needs_map and r.status == 'OPEN'
    assert p.tasks['Z1'].status == 'ABANDONED'
    assert p.lose('scout_1') is None                 # idempotent
    assert 'scout_1' not in p.alive


def test_mappers_never_take_scout_work_and_reserve_takes_remainder():
    p = make()
    ready = {'Z1', 'Z2'}
    p.assign(POS, lambda r: r in ready)
    for t in p.releasable(lambda r: r in ready):
        t.released = True
    p.progress('scout_1', 1)
    p.lose('scout_1')
    p.progress('mapper_1', len(LINE))               # mapper_1 is done mapping
    assert 'mapper_1' not in p.assign(POS, lambda r: r in ready)
    p.add_drone('scout_3', 'scout')
    assert p.assign({'scout_3': (0, 0)}, lambda r: r in ready)['scout_3'].tid == 'Z1.1'


def test_optimal_assignment_beats_greedy():
    p = TaskPlan()
    p.add_task('A', 'scout', [(0, 0, 18), (1, 0, 18)])
    p.add_task('B', 'scout', [(100, 0, 18), (101, 0, 18)])
    for d in ('s1', 's2'):
        p.add_drone(d, 'scout')
    new = p.assign({'s1': (10, 0), 's2': (-5, 0)}, lambda r: True)
    assert new['s2'].tid == 'A' and new['s1'].tid == 'B'


def test_work_stealing_splits_on_a_pass_and_coverage_stays_exact():
    p = TaskPlan()
    path = [(x * 10.0, y, 18) for x in range(10) for y in (0, 100)]          # 10 passes, 20 waypoints
    p.add_task('Z', 'scout', path, needs_map=True)
    p.add_drone('s1', 'scout')
    p.add_drone('s2', 'scout')
    p.assign({'s1': (0, 0), 's2': (0, 0)}, lambda r: True)
    p.owned('s1').released = True
    p.progress('s1', 4)
    v, nt = p.steal('s2', {'s2': (90, 0)})
    assert v.tid == 'Z' and nt.owner == 's2' and (nt.start - v.start) % 2 == 0 and v.end == nt.start == 12
    nt.released = True
    p.progress('s1', v.end)
    p.progress('s2', nt.end)
    assert p.finished() and abs(p.coverage() - 1.0) < 1e-9
    assert p.steal('s1', {}) is None                # nothing left to share


def test_finishes_and_coverage_counts_each_root_once():
    p = make()
    ready = {'Z1', 'Z2'}
    for _ in range(20):
        p.assign(POS, lambda r: r in ready)
        for t in p.releasable(lambda r: r in ready):
            t.released = True
        for d in list(p.alive):
            t = p.owned(d)
            if t and t.released:
                p.progress(d, len(t.path))
        if p.finished():
            break
    assert p.finished() and abs(p.coverage() - 1.0) < 1e-9


def test_lost_unreleased_task_restarts_from_its_start():
    p = make()
    p.assign(POS, lambda r: False)
    rid = p.lose('scout_2')
    assert p.tasks[rid].start == 0 and p.tasks[rid].tid == 'Z2.1'


def test_verify_interrupts_and_the_sweep_resumes_later():
    from story_plan import Task
    p = make()
    ready = {'Z1', 'Z2'}
    p.assign(POS, lambda r: r in ready)
    for t in p.releasable(lambda r: r in ready):
        t.released = True
    p.progress('scout_1', 2)
    v = Task('VERIFY-P1', 'VERIFY-P1', 'scout', [(5, 5, 18), (6, 6, 18)], kind='verify')
    rid = p.interrupt('scout_1', v)
    assert p.owned('scout_1').tid == 'VERIFY-P1' and p.tasks[rid].status == 'OPEN' and p.tasks[rid].start == 1
    cov = p.coverage('scout')
    v.released = True
    p.progress('scout_1', 2)                          # re-check flown
    assert p.tasks['VERIFY-P1'].status == 'DONE' and p.coverage('scout') == cov
    assert p.assign(POS, lambda r: r in ready)['scout_1'].tid == rid


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f()
            print('ok', n)
