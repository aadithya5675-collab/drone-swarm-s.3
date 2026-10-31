"""Flight agent for one drone: flies the planner's waypoints with PX4 offboard control over uXRCE-DDS."""
import math

import rclpy
from geometry_msgs.msg import PoseStamped
from px4_msgs.msg import (OffboardControlMode, TrajectorySetpoint, VehicleAttitude, VehicleCommand,
                          VehicleLocalPosition, VehicleStatus)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from resqmesh_interfaces.msg import DroneState, Waypoints

from .geo import ned_frd_to_enu_flu, px4_scale

PX4_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)
LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
CORNER_M = 6.0
PX4_TIMEOUT_S = 5.0
YAW_SLEW = 40.0
DRAIN = {'scout': 1 / 1700.0, 'mapper': 1 / 1650.0, 'relay': 1 / 2400.0}


class FlightAgent(Node):
    def __init__(self):
        super().__init__('flight_agent')
        for k, v in (('drone', ''), ('role', ''), ('px4_ns', ''), ('px4_instance', 1), ('spawn_x', 0.0),
                     ('spawn_y', 0.0), ('cruise_speed', 7.0), ('origin_lat', 11.4955458)):
            self.declare_parameter(k, v)
        g = lambda k: self.get_parameter(k).value  # noqa: E731
        self.drone, self.role, self.ns = g('drone'), g('role'), g('px4_ns') or g('drone')
        self.sys_id = int(g('px4_instance')) + 1
        self.sx, self.sy, self.speed = float(g('spawn_x')), float(g('spawn_y')), float(g('cruise_speed'))
        self.ke, self.kn = px4_scale(float(g('origin_lat')))      # PX4 local metres -> true (WGS84) metres
        self.lp = self.att = self.status = None
        self.lp_time = 0.0
        self.path, self.idx, self.carrot = [], 0, None
        self.yaw_sp = None
        self.sector, self.version, self.land_at_end, self.start_index = '', 0, False, 0
        self.mode = 'STAGING'
        self.ticks = 0
        self.battery = 1.0
        self.dead = False
        self.px4_quiet = False
        self.subs_ready = False
        self.offboard_pub = self.sp_pub = self.cmd_pub = None     # created once PX4's topic names are known
        self.t_start = self.get_clock().now().nanoseconds * 1e-9
        self.state_pub = self.create_publisher(DroneState, '/%s/state' % self.drone, 10)
        self.pose_pub = self.create_publisher(PoseStamped, '/%s/pose_enu' % self.drone, 10)
        self.create_subscription(Waypoints, '/%s/waypoints' % self.drone, self.on_waypoints, LATCHED)
        self.create_subscription(String, '/sim/kill', self.on_kill, 10)
        self.create_timer(1.0, self.find_px4_topics)
        self.create_timer(0.1, self.control)
        self.create_timer(0.5, self.heartbeat)

    def _versioned(self, names, pre):
        hits = sorted(n for n in names if n == pre or (n.startswith(pre + '_v') and n[len(pre) + 2:].isdigit()))
        return hits[-1] if hits else None        # highest version

    def find_px4_topics(self):
        if self.subs_ready:
            return
        names = [n for n, _ in self.get_topic_names_and_types()]
        outs = {'vehicle_local_position': (VehicleLocalPosition, self.on_lp),
                'vehicle_attitude': (VehicleAttitude, self.on_att), 'vehicle_status': (VehicleStatus, self.on_status)}
        ins = {'offboard_control_mode': OffboardControlMode, 'trajectory_setpoint': TrajectorySetpoint,
               'vehicle_command': VehicleCommand}
        found_out = {k: self._versioned(names, '/%s/fmu/out/%s' % (self.ns, k)) for k in outs}
        found_in = {k: self._versioned(names, '/%s/fmu/in/%s' % (self.ns, k)) for k in ins}
        if not all(found_out.values()):
            return
        waited = self.get_clock().now().nanoseconds * 1e-9 - self.t_start
        if not all(found_in.values()) and waited < 15.0:
            return
        for k, (typ, cb) in outs.items():
            self.create_subscription(typ, found_out[k], cb, PX4_QOS)
            self.get_logger().info('PX4 %s <- %s' % (k, found_out[k]))
        topic = {k: found_in[k] or '/%s/fmu/in/%s' % (self.ns, k) for k in ins}
        self.offboard_pub = self.create_publisher(OffboardControlMode, topic['offboard_control_mode'], PX4_QOS)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, topic['trajectory_setpoint'], PX4_QOS)
        self.cmd_pub = self.create_publisher(VehicleCommand, topic['vehicle_command'], PX4_QOS)
        self.get_logger().info('PX4 commands -> %s' % ', '.join(topic.values()))
        self.subs_ready = True

    def on_lp(self, m):
        self.lp = m
        self.lp_time = self.get_clock().now().nanoseconds * 1e-9

    def on_att(self, m):
        self.att = m

    def on_status(self, m):
        self.status = m

    # frames
    def enu(self):
        return (self.lp.y * self.ke + self.sx, self.lp.x * self.kn + self.sy, -self.lp.z)

    def ned(self, p):
        return [float((p[1] - self.sy) / self.kn), float((p[0] - self.sx) / self.ke), float(-p[2])]

    # commands
    def command(self, cmd, p1=0.0, p2=0.0):
        m = VehicleCommand(command=cmd, param1=float(p1), param2=float(p2), target_system=self.sys_id, target_component=1,
                           source_system=1, source_component=1, from_external=True)
        m.timestamp = self.get_clock().now().nanoseconds // 1000
        self.cmd_pub.publish(m)

    def on_waypoints(self, w):
        if self.dead:
            return
        pts = list(zip(w.x, w.y, w.z))
        if w.sector_id == 'RELAY' and self.path and self.sector == 'RELAY':
            self.path = pts                      # just move the hold point
            return
        self.path, self.idx = pts, int(w.start_index)
        self.sector, self.version, self.land_at_end, self.start_index = w.sector_id, w.plan_version, w.land_at_end, int(w.start_index)
        self.carrot = None
        if self.mode in ('SEARCHING', 'HOLDING', 'RETURNING'):
            self.mode = 'RETURNING' if w.land_at_end else 'SEARCHING'

    def on_kill(self, m):
        if m.data == self.drone and not self.dead:
            self.get_logger().warn('KILLED for the failure demo: going silent')
            self.dead = True

    # main loop (10 Hz)
    def control(self):
        if self.dead or self.lp is None:
            return
        self.ticks += 1
        now_us = self.get_clock().now().nanoseconds // 1000
        here = self.enu()
        self.publish_pose(here)
        self.battery = max(0.0, self.battery - DRAIN.get(self.role, 0.001) * 0.1 * (self.mode != 'STAGING'))
        if self.mode == 'LANDED':
            return
        self.offboard_pub.publish(OffboardControlMode(timestamp=now_us, position=True))
        target = self.next_setpoint(here)
        self.sp_pub.publish(TrajectorySetpoint(timestamp=now_us, position=self.ned(target),
                                               yaw=float(self.yaw_cmd(here, target)),
                                               velocity=[math.nan] * 3, acceleration=[math.nan] * 3))
        if self.mode == 'STAGING' and self.path and self.ticks > 15:
            self.command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1, 6)       # PX4 custom mode 6 = offboard
            self.command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1)
            if self.status and self.status.arming_state == VehicleStatus.ARMING_STATE_ARMED:
                self.mode = 'TAKEOFF'
        elif self.mode == 'TAKEOFF' and abs(here[2] - self.path[min(self.idx, len(self.path) - 1)][2]) < 1.5:
            self.mode = 'SEARCHING' if self.sector not in ('RELAY',) else 'HOLDING'
            if self.land_at_end:
                self.mode = 'RETURNING'
        elif self.mode == 'RETURNING' and self.idx >= len(self.path) and here[2] < 9.0:
            self.command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
            if self.status and self.status.arming_state != VehicleStatus.ARMING_STATE_ARMED:
                self.mode = 'LANDED'

    def next_setpoint(self, here):
        if not self.path:
            return (self.sx, self.sy, 0.0) if self.mode == 'STAGING' else here
        if self.mode in ('STAGING', 'TAKEOFF'):
            first = self.path[min(self.idx, len(self.path) - 1)]
            return (self.sx, self.sy, first[2])                       # climb straight up first
        if self.sector == 'RELAY':
            self.idx = 1
            return self.advance(here, self.path[0])
        if self.idx >= len(self.path):
            if self.mode == 'SEARCHING':
                self.mode = 'HOLDING'
            return self.path[-1]
        goal = self.path[self.idx]
        sp = self.advance(here, goal)
        if self.idx < len(self.path) - 1 and math.dist(here[:2], goal[:2]) < CORNER_M and abs(here[2] - goal[2]) < 4.0:
            self.idx += 1
        elif math.dist(here, goal) < 3.0 and math.dist(sp, goal) < 0.01:
            self.idx += 1
        return sp

    def advance(self, here, goal):
        c = self.carrot or here
        d = math.dist(c, goal)
        step = self.speed * 0.1
        c = goal if d <= step else tuple(ci + (gi - ci) * step / d for ci, gi in zip(c, goal))
        if math.dist(c, here) > 12.0:
            c = tuple(hi + (ci - hi) * 12.0 / math.dist(c, here) for hi, ci in zip(here, c))
        self.carrot = c
        return c

    def yaw_cmd(self, here, target):
        """Heading setpoint slewed at YAW_SLEW from the measured heading: a light quad saturates its mixer."""
        want = self.yaw_for(here, target)
        if math.isnan(want) or self.att is None:
            return want if self.yaw_sp is None else self.yaw_sp
        w, x, y, z = (float(v) for v in self.att.q)
        cur = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        sp = cur if self.yaw_sp is None else self.yaw_sp
        wrap = lambda a: (a + math.pi) % (2 * math.pi) - math.pi  # noqa: E731
        lead = wrap(sp - cur)
        if abs(lead) > 0.6:
            sp = cur + math.copysign(0.6, lead)          # never run far ahead of the airframe
        step = math.radians(YAW_SLEW) * 0.1
        sp = wrap(sp + max(-step, min(step, wrap(want - sp))))
        self.yaw_sp = sp
        return sp

    @staticmethod
    def yaw_for(here, target):
        # PX4 yaw is NED: 0 = north, +pi/2 = east. Face along the direction of travel.
        dx, dy = target[0] - here[0], target[1] - here[1]
        if math.hypot(dx, dy) < 0.5:
            return math.nan
        return math.atan2(dx, dy)

    # outputs
    def publish_pose(self, here):
        if self.att is None:
            return
        m = PoseStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = 'world'
        m.pose.position.x, m.pose.position.y, m.pose.position.z = here
        w, x, y, z = ned_frd_to_enu_flu(tuple(float(v) for v in self.att.q))
        m.pose.orientation.w, m.pose.orientation.x, m.pose.orientation.y, m.pose.orientation.z = w, x, y, z
        self.pose_pub.publish(m)

    def heartbeat(self):
        if self.lp is None or (self.dead and not self.px4_quiet):
            return
        gap = self.get_clock().now().nanoseconds * 1e-9 - self.lp_time
        if gap > PX4_TIMEOUT_S:
            if not self.px4_quiet:
                self.get_logger().error('no data from PX4 for %.0f s: holding fire until it comes back' % gap)
                self.px4_quiet = self.dead = True
            return
        if self.px4_quiet:
            self.get_logger().warn('PX4 data is back: resuming')
            self.px4_quiet = self.dead = False
        x, y, z = self.enu()
        n = max(1, len(self.path))
        m = DroneState(drone=self.drone, role=self.role, state=self.mode, x=x, y=y, z=z, battery=float(self.battery),
                       sector_id=self.sector, sector_progress=float(min(1.0, self.idx / n)),
                       waypoint_index=int(min(self.idx, n)), plan_version=int(self.version))
        m.header.stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(m)


def main():
    rclpy.init()
    rclpy.spin(FlightAgent())


if __name__ == '__main__':
    main()
