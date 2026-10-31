"""Task allocation for the swarm: optimal assignment, work stealing and re-planning."""
import math
from dataclasses import dataclass, field

UNREADY = 1e5
MIN_STEAL_LEGS = 6
IDLE = 1e7


@dataclass
class Task:
    tid: str
    root: str
    role: str                     # 'scout' | 'mapper'
    path: list
    needs_map: bool = False
    start: int = 0
    done: int = 0
    end: int = -1                 # exclusive; -1 = len(path)
    status: str = 'OPEN'          # OPEN | ASSIGNED | DONE | ABANDONED
    owner: str = ''
    released: bool = False
    geom: tuple = field(default=None)
    kind: str = 'sweep'

    def __post_init__(self):
        if self.end < 0:
            self.end = len(self.path)

    @property
    def progress(self):
        n = self.end - self.start
        return 1.0 if n <= 0 else min(1.0, max(0, self.done - self.start) / n)

    @property
    def remaining(self):
        return max(0, self.end - self.done)


class TaskPlan:
    def __init__(self):
        self.tasks = {}
        self.roles = {}               # drone -> role
        self.alive = set()
        self.version = 0
        self._chain = {}

    # setup
    def add_task(self, tid, role, path, needs_map=False, geom=None):
        self.tasks[tid] = Task(tid, tid, role, list(path), needs_map, geom=geom)
        self._chain[tid] = 0

    def add_drone(self, name, role):
        self.roles[name] = role
        self.alive.add(name)

    def _new_id(self, root):
        self._chain[root] += 1
        return '%s.%d' % (root, self._chain[root])

    # queries
    def owned(self, drone):
        return next((t for t in self.tasks.values() if t.owner == drone and t.status == 'ASSIGNED'), None)

    def finished(self):
        return all(t.status in ('DONE', 'ABANDONED') for t in self.tasks.values())

    def _flown(self, root):
        iv = sorted((t.start, min(t.done, t.end)) for t in self.tasks.values() if t.root == root and t.done > t.start)
        tot, cur_a, cur_b = 0, None, None
        for a, b in iv:
            if cur_b is None or a > cur_b:
                tot += 0 if cur_b is None else cur_b - cur_a
                cur_a, cur_b = a, b
            else:
                cur_b = max(cur_b, b)
        return tot + (0 if cur_b is None else cur_b - cur_a)

    def root_progress(self, root):
        return min(1.0, self._flown(root) / max(1, len(self.tasks[root].path)))

    def coverage(self, role=None):
        roots = [t for t in self.tasks.values() if t.tid == t.root and t.kind == 'sweep' and (role is None or t.role == role)]
        tot = sum(len(t.path) for t in roots)
        return 0.0 if tot == 0 else sum(min(self._flown(t.tid), len(t.path)) for t in roots) / tot

    # allocation
    @staticmethod
    def _best_assignment(drones, tasks, cost):
        """Exact min-cost matching of drones to distinct tasks (each drone gets one if any is left)."""
        n, m = len(drones), len(tasks)
        memo = {}

        def go(i, used):
            if i == n:
                return 0.0, ()
            key = (i, used)
            if key in memo:
                return memo[key]
            free = [j for j in range(m) if not used >> j & 1]
            c, rest = go(i + 1, used)
            best = (c + (IDLE if free else 0.0), (None,) + rest)
            for j in free:
                c, rest = go(i + 1, used | 1 << j)
                c += cost(drones[i], tasks[j])
                if c < best[0]:
                    best = (c, (j,) + rest)
            memo[key] = best
            return best

        return go(0, 0)[1]

    def assign(self, positions, ready_fn, only=None, value_fn=None):
        """Give every idle live drone (optionally only those in `only`) a task."""
        new = {}
        idle = [d for d in sorted(self.alive if only is None else self.alive & set(only)) if not self.owned(d)]
        for role in ('mapper', 'scout'):
            ds = [d for d in idle if self.roles[d] == role]
            ts = [t for t in self.tasks.values() if t.status == 'OPEN' and t.role == role]
            if not ds or not ts:
                continue
            ts = sorted(ts, key=lambda t: (t.needs_map and not ready_fn(t.root), t.tid))[:12]

            def cost(d, t):
                px, py = positions.get(d, (0.0, 0.0))[:2]
                q = t.path[t.start]
                v = value_fn(t) if value_fn else 0.0
                return (UNREADY if t.needs_map and not ready_fn(t.root) else 0.0) + math.hypot(q[0] - px, q[1] - py) - v

            for d, j in zip(ds, self._best_assignment(ds, ts, cost)):
                if j is None:
                    continue
                t = ts[j]
                t.status, t.owner, t.released = 'ASSIGNED', d, False
                new[d] = t
        if new:
            self.version += 1
        return new

    def steal(self, drone, positions):
        """Idle `drone` takes the far half of the busiest released same-role task."""
        if drone not in self.alive or self.owned(drone):
            return None
        role = self.roles[drone]
        px, py = positions.get(drone, (0.0, 0.0))[:2]
        cands = [t for t in self.tasks.values() if t.status == 'ASSIGNED' and t.released and t.role == role
                 and t.owner != drone and t.remaining >= MIN_STEAL_LEGS]
        if not cands:
            return None
        v = max(cands, key=lambda t: (t.remaining, -math.hypot(t.path[t.end - 1][0] - px, t.path[t.end - 1][1] - py)))
        m = v.done + v.remaining // 2
        m += (m - v.start) % 2
        if m >= v.end or m <= v.done:
            return None
        work = sum(math.dist(v.path[i][:2], v.path[i + 1][:2]) for i in range(m, v.end - 1))
        if math.hypot(v.path[m][0] - px, v.path[m][1] - py) > work:
            return None
        nt = Task(self._new_id(v.root), v.root, v.role, v.path, v.needs_map, start=m, done=m, end=v.end, geom=v.geom,
                  status='ASSIGNED', owner=drone)
        v.end = m
        self.tasks[nt.tid] = nt
        self.version += 1
        return v, nt

    def interrupt(self, drone, task):
        """Divert `drone` to `task` now; its current task's unflown remainder goes back to the pool."""
        rid = None
        t = self.owned(drone)
        if t is not None:
            t.status = 'ABANDONED'
            if t.done < t.end:
                resume = max(t.start, t.done - 1) if t.released else t.start
                rid = self._new_id(t.root)
                self.tasks[rid] = Task(rid, t.root, t.role, t.path, t.needs_map, start=resume, done=resume, end=t.end,
                                       geom=t.geom, kind=t.kind)
            else:
                t.status = 'DONE'
        self._chain.setdefault(task.root, 0)
        task.status, task.owner, task.released = 'ASSIGNED', drone, False
        self.tasks[task.tid] = task
        self.version += 1
        return rid

    def releasable(self, ready_fn):
        return [t for t in self.tasks.values() if t.status == 'ASSIGNED' and not t.released
                and (not t.needs_map or ready_fn(t.root))]

    def progress(self, drone, index):
        t = self.owned(drone)
        if t is None or not t.released:
            return None
        t.done = max(t.done, min(index, t.end))
        if t.done >= t.end:
            t.status = 'DONE'
            return t
        return None

    def lose(self, drone):
        """Drone is gone."""
        if drone not in self.alive:
            return None
        self.alive.discard(drone)
        t = self.owned(drone)
        if t is None:
            return None
        t.status = 'ABANDONED'
        if t.done >= t.end:
            t.status = 'DONE'
            return None
        resume = max(t.start, t.done - 1) if t.released else t.start
        rid = self._new_id(t.root)
        self.tasks[rid] = Task(rid, t.root, t.role, t.path, t.needs_map, start=resume, done=resume, end=t.end, geom=t.geom,
                               kind=t.kind)
        self.version += 1
        return rid
