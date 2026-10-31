"""Companion-computer agent for one drone in the Wayanad story (extends the PX4 flight agent)."""
import json
import math
import types

import rclpy
from std_msgs.msg import String

from resqmesh_interfaces.msg import HeightMap, MeshFrame

from .flight_agent import FlightAgent
from .geo import quat_to_rot
from .terrain import Terrain


class DroneAgent(FlightAgent):
    def __init__(self):
        super().__init__()
        self.declare_parameter('prior', '')
        self.terrain = Terrain(self.get_parameter('prior').value)
        self.mode_alt = 'ABS'
        self.agl = []
        self.crash_t = None
        self.why = ''
        self.mesh_out = self.create_publisher(MeshFrame, '/%s/mesh/out' % self.drone, 20)
        self.power_pub = self.create_publisher(String, '/mesh/powered_off', 5)
        self.create_subscription(MeshFrame, '/%s/mesh/in' % self.drone, self.on_mesh, 20)
        for m in ('mapper_1', 'mapper_2'):
            self.create_subscription(HeightMap, '/%s/map/height' % m, self.terrain.update_live, 2)
        self.create_timer(1.0, self.mesh_status)

    # orders
    def on_mesh(self, f):
        if f.kind != 'waypoints' or self.dead:
            return
        p = json.loads(f.payload)
        if p['sector_id'] == self.sector and p['plan_version'] == self.version and p['sector_id'] != 'RELAY':
            return                                   # duplicate delivery
        self.mode_alt = p.get('altitude_mode', 'ABS')
        self.agl = list(p['z'])
        w = types.SimpleNamespace(x=p['x'], y=p['y'], z=p['z'], sector_id=p['sector_id'], plan_version=p['plan_version'],
                                  start_index=p['start_index'], land_at_end=p['land_at_end'])
        self.on_waypoints(w)
        if self.mode == 'HOLDING' and not p['land_at_end']:
            self.mode = 'SEARCHING'

    # terrain following
    def required_z(self, here, goal, agl):
        dx, dy = goal[0] - here[0], goal[1] - here[1]
        L = math.hypot(dx, dy)
        ahead = (here[0] + dx / L * min(L, 30.0), here[1] + dy / L * min(L, 30.0)) if L > 1 else here[:2]
        top, _ = self.terrain.max_along(here[:2], ahead, step=3.0, ground_only=self.mode_alt == 'AGL_GROUND')
        return top + agl

    def next_setpoint(self, here):
        if self.mode_alt in ('AGL', 'AGL_GROUND') and self.path:
            i = min(self.idx, len(self.path) - 1)
            goal = self.path[i]
            agl = self.agl[min(i, len(self.agl) - 1)]
            zr = self.required_z(here, goal, agl)
            if self.land_at_end and self.idx >= len(self.path) - 1 and math.hypot(goal[0] - here[0], goal[1] - here[1]) < 4:
                zr = 6.0                              # over the pad: come down, then land
            self.path[i] = (goal[0], goal[1], zr)
            self.climb_deficit = zr - here[2]
        else:
            self.climb_deficit = 0.0
        return super().next_setpoint(here)

    def advance(self, here, goal):
        c = super().advance(here, goal)
        if self.mode_alt in ('AGL', 'AGL_GROUND') and getattr(self, 'climb_deficit', 0.0) > 5.0 and self.mode in ('SEARCHING', 'RETURNING'):
            c = (here[0], here[1], goal[2])          # surface ahead is higher: climb in place first
            self.carrot = c
        return c

    def control(self):
        super().control()
        if self.dead or self.lp is None or self.att is None or self.mode in ('STAGING', 'LANDED'):
            return
        R = quat_to_rot(*self.att_enu())
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, R[2][2]))))
        here = self.enu()
        sp_z = self.carrot[2] if self.carrot else here[2]
        t = self.get_clock().now().nanoseconds * 1e-9
        self.tilt = tilt
        self.z_hist = [(tt, zz) for tt, zz in getattr(self, 'z_hist', []) if t - tt < 3.0] + [(t, here[2])]
        drop = max(zz for _, zz in self.z_hist) - here[2]
        # down = tumbling AND losing height, or falling fast far below the setpoint
        bad = (tilt > 75 and drop > 5.0) or (here[2] < sp_z - 12 and self.lp.vz > 5.0 and drop > 8.0)
        if bad:
            self.crash_t = self.crash_t or t
            self.why = 'tumbling at %.0f deg' % tilt if tilt > 75 else 'falling at %.0f m/s' % self.lp.vz
            if t - self.crash_t > 1.0:
                self.go_down()
        else:
            self.crash_t = None

    def att_enu(self):
        from .geo import ned_frd_to_enu_flu
        return ned_frd_to_enu_flu(tuple(float(v) for v in self.att.q))

    def go_down(self):
        self.mode = 'CRASHED'
        self.get_logger().error('%s is down (%s)' % (self.drone, self.why))
        for final in ('brain', 'base'):
            self.mesh_out.publish(MeshFrame(final=final, kind='status', payload=json.dumps(self.status_dict())))
        self.dead = True
        timer = self.create_timer(1.5, lambda: (self.power_pub.publish(String(data=self.drone)), timer.cancel()))

    # reports
    def status_dict(self):
        x, y, z = self.enu()
        n = max(1, len(self.path))
        s, _ = self.terrain.surface(x, y)
        return {'drone': self.drone, 'role': self.role, 'state': self.mode, 'x': round(x, 2), 'y': round(y, 2), 'z': round(z, 2),
                'agl': round(z - s, 1), 'battery': round(self.battery, 3), 'sector_id': self.sector,
                'waypoint_index': int(min(self.idx, n)), 'n_waypoints': len(self.path), 'plan_version': int(self.version),
                'why': self.why, 'speed': round(math.hypot(self.lp.vx, self.lp.vy), 1), 'tilt': round(getattr(self, 'tilt', 0.0), 1)}

    def mesh_status(self):
        if self.dead or self.lp is None:
            return
        st = json.dumps(self.status_dict())
        for final in ('brain', 'base'):
            self.mesh_out.publish(MeshFrame(final=final, kind='status', payload=st))


def main():
    rclpy.init()
    rclpy.spin(DroneAgent())


if __name__ == '__main__':
    main()
