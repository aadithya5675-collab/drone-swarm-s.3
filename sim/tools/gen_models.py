"""Generate the three ResQMesh Gazebo models (scout, mapper, relay) from the CAD-derived geometry."""
import json
import math
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mass_props import mass_props  # noqa: E402

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = json.load(open(os.path.join(SIM, 'cad_export', 'geometry.json')))
par = yaml.safe_load(open(os.path.join(SIM, 'config', 'vehicle_params.yaml')))
P = par['propulsion']
S = par['sensors']
PITCH = {'scout': par['roles']['scout']['cam_pitch_rad']}

# colour tags written by fusion_build_roles.py (LOOK table) -> Gazebo RGB
COLOUR = {'carbon': (0.13, 0.13, 0.14), 'pcb': (0.08, 0.35, 0.2), 'black': (0.08, 0.08, 0.08), 'alu': (0.62, 0.62, 0.64),
          'alu_dark': (0.33, 0.33, 0.35), 'red': (0.67, 0.12, 0.12), 'blue': (0.12, 0.27, 0.58), 'white': (0.92, 0.92, 0.92),
          'yellow': (0.9, 0.75, 0.08), 'rubber': (0.14, 0.14, 0.14), 'orange': (0.86, 0.4, 0.12), 'glass': (0.2, 0.24, 0.28),
          'window': (0.05, 0.05, 0.06), 'gold': (0.82, 0.67, 0.24), 'lipo': (0.12, 0.24, 0.55), 'silver': (0.78, 0.78, 0.8)}
FRAME_GREY = (0.22, 0.22, 0.24)
ORIGIN = geo['origin_in_gazebo_axes_before_shift_m']


def fusion_to_gz(p_cm):
    x, y, z = p_cm
    return (z / 100.0 - ORIGIN[0], x / 100.0 - ORIGIN[1], y / 100.0 - ORIGIN[2])


MOUNTS = {('scout', 'rgb_camera'): (-0.9, 4.294, 4.907), ('scout', 'thermal_camera'): (0.9, 4.517, 4.576),
          ('mapper', 'lidar_3d'): (0.0, -7.05, 2.6)}

m = geo['motor_xy_m']
fr = next(k for k, (x, y) in m.items() if x > 0 and y < 0)
rl = next(k for k, (x, y) in m.items() if x < 0 and y > 0)
fl = next(k for k, (x, y) in m.items() if x > 0 and y > 0)
rr = next(k for k, (x, y) in m.items() if x < 0 and y < 0)
ROTORS = [(fr, 'ccw'), (rl, 'ccw'), (fl, 'cw'), (rr, 'cw')]
PROP_Z = geo['prop_plane_z_m']


PBR = {'carbon': (0.35, 0.42), 'alu': (0.9, 0.32), 'alu_dark': (0.85, 0.4), 'silver': (0.95, 0.25), 'gold': (0.9, 0.3),
       'glass': (0.1, 0.08), 'window': (0.2, 0.05), 'pcb': (0.15, 0.5), 'rubber': (0.0, 0.9), 'lipo': (0.05, 0.55)}
ROLE_GLOW = {'scout': (1.0, 0.71, 0.28), 'mapper': (0.22, 0.84, 1.0), 'relay': (0.70, 0.62, 1.0)}   # = dashboard colours


def material(rgb, tag=None, emissive=None):
    r, g, b = rgb
    metal, rough = PBR.get(tag, (0.0, 0.6))
    e = '<emissive>%.2f %.2f %.2f 1</emissive>' % emissive if emissive else ''
    return ('<material><ambient>{0:.2f} {1:.2f} {2:.2f} 1</ambient><diffuse>{0:.2f} {1:.2f} {2:.2f} 1</diffuse>'
            '<specular>0.3 0.3 0.3 1</specular>{3}<pbr><metal><metalness>{4:.2f}</metalness><roughness>{5:.2f}</roughness>'
            '</metal></pbr></material>').format(r, g, b, e, metal, rough)


def mesh_visual(name, uri, rgb, pose='0 0 0 0 0 0', tag=None):
    return ('<visual name="%s"><pose>%s</pose><geometry><mesh><uri>%s</uri></mesh></geometry>%s</visual>'
            % (name, pose, uri, material(rgb, tag)))


def light_visuals(role):
    out = []
    for k, (x, y) in geo['motor_xy_m'].items():
        rgb = (1.0, 1.0, 1.0) if x < 0 else ((1.0, 0.08, 0.05) if y > 0 else (0.1, 1.0, 0.2))
        out.append('<visual name="led_%s"><pose>%.4f %.4f -0.0067 0 0 0</pose><geometry><box><size>0.009 0.006 0.0035</size></box>'
                   '</geometry>%s<cast_shadows>false</cast_shadows></visual>' % (k, 0.8 * x, 0.8 * y, material(rgb, None, rgb)))   # under the arm
    mast = next(p['bbox_m'] for p in geo['roles'][role]['parts'] if p['part'].startswith('M10 GNSS'))
    cx, cy, top = (mast[0][0] + mast[1][0]) / 2, (mast[0][1] + mast[1][1]) / 2, mast[1][2]
    out.append('<visual name="role_beacon"><pose>%.4f %.4f %.4f 0 0 0</pose><geometry><cylinder><radius>0.016</radius>'
               '<length>0.007</length></cylinder></geometry>%s<cast_shadows>false</cast_shadows></visual>'
               % (cx, cy, top + 0.005, material(ROLE_GLOW[role], None, ROLE_GLOW[role])))
    return ''.join(out)


DEG_PER_M = 9.0e-6


def noise(sd, bias_sd=0.0):
    b = '<bias_mean>0</bias_mean><bias_stddev>%g</bias_stddev>' % bias_sd if bias_sd else ''
    return '<noise type="gaussian"><mean>0</mean><stddev>%g</stddev>%s</noise>' % (sd, b)


COMMON_SENSORS = """
      <sensor name="air_pressure_sensor" type="air_pressure">
        <gz_frame_id>base_link</gz_frame_id><always_on>1</always_on><update_rate>50</update_rate>
        <air_pressure><pressure>{p}</pressure></air_pressure>
      </sensor>
      <sensor name="magnetometer_sensor" type="magnetometer">
        <gz_frame_id>base_link</gz_frame_id><always_on>1</always_on><update_rate>100</update_rate>
        <magnetometer><x>{m}</x><y>{m}</y><z>{m}</z></magnetometer>
      </sensor>
      <sensor name="imu_sensor" type="imu">
        <gz_frame_id>base_link</gz_frame_id><always_on>1</always_on><update_rate>250</update_rate>
        <imu>
          <angular_velocity><x>{g}</x><y>{g}</y><z>{g}</z></angular_velocity>
          <linear_acceleration><x>{a}</x><y>{a}</y><z>{a}</z></linear_acceleration>
        </imu>
      </sensor>
      <sensor name="navsat_sensor" type="navsat">
        <gz_frame_id>base_link</gz_frame_id><always_on>1</always_on><update_rate>10</update_rate>
        <navsat>
          <position_sensing><horizontal>{gh}</horizontal><vertical>{gv}</vertical></position_sensing>
          <velocity_sensing><horizontal>{vh}</horizontal><vertical>{vv}</vertical></velocity_sensing>
        </navsat>
      </sensor>""".format(p=noise(3), m=noise(3e-7), g=noise(0.0008726646), a=noise(0.00637),
                     gh=noise(0.03 * DEG_PER_M, 0.7 * DEG_PER_M), gv=noise(0.05, 1.2), vh=noise(0.05), vv=noise(0.08))


def gear_bbox(role):
    return next(p['bbox_m'] for p in geo['roles'][role]['parts'] if p['part'].startswith('Landing gear'))


def mount_pose(role, sensor, pitch=0.0, roll=0.0):
    x, y, z = fusion_to_gz(MOUNTS[(role, sensor)])
    return '%.4f %.4f %.4f %.4f %.4f 0' % (x, y, z, roll, pitch)


def rgb_camera(role, pitch):
    c = S['rgb_camera']
    return """
      <sensor name="rgb_camera" type="camera">
        <gz_frame_id>rgb_camera</gz_frame_id>
        <pose>{pose}</pose><always_on>1</always_on><update_rate>{rate_hz}</update_rate><visualize>false</visualize>
        <camera>
          <horizontal_fov>{hfov_rad}</horizontal_fov>
          <image><width>{width}</width><height>{height}</height><format>R8G8B8</format></image>
          <clip><near>0.1</near><far>{far_m}</far></clip>
          <noise type="gaussian"><mean>0</mean><stddev>0.007</stddev></noise>
        </camera>
      </sensor>""".format(pose=mount_pose(role, 'rgb_camera', pitch), **c)   # IMX219 read + shot noise, ~2 DN of 255


def thermal_camera(role, pitch):
    c = S['thermal_camera']
    return """
      <sensor name="thermal_camera" type="thermal">
        <gz_frame_id>thermal_camera</gz_frame_id>
        <pose>{pose}</pose><always_on>1</always_on><update_rate>{rate_hz}</update_rate><visualize>false</visualize>
        <camera>
          <horizontal_fov>{hfov_rad}</horizontal_fov>
          <image><width>{width}</width><height>{height}</height><format>L16</format></image>
          <clip><near>0.1</near><far>{far_m}</far></clip>
        </camera>
        <plugin filename="gz-sim-thermal-sensor-system" name="gz::sim::systems::ThermalSensor">
          <min_temp>{min_temp_k}</min_temp><max_temp>{max_temp_k}</max_temp><resolution>0.01</resolution>
        </plugin>
      </sensor>""".format(pose=mount_pose(role, 'thermal_camera', pitch), **c)


def lidar_3d(role):
    c = S['lidar_3d']
    return """
      <sensor name="lidar_3d" type="gpu_lidar">
        <gz_frame_id>lidar_3d</gz_frame_id>
        <pose>{pose}</pose><always_on>1</always_on><update_rate>{rate_hz}</update_rate><visualize>false</visualize>
        <lidar>
          <scan>
            <horizontal><samples>{h_samples}</samples><resolution>1</resolution><min_angle>-3.14159</min_angle><max_angle>3.14159</max_angle></horizontal>
            <vertical><samples>{v_samples}</samples><resolution>1</resolution><min_angle>{v_min_rad}</min_angle><max_angle>{v_max_rad}</max_angle></vertical>
          </scan>
          <range><min>0.30</min><max>{range_max_m}</max><resolution>0.02</resolution></range>
          <noise type="gaussian"><mean>0</mean><stddev>0.02</stddev></noise>
        </lidar>
      </sensor>""".format(pose=mount_pose(role, 'lidar_3d', pitch=math.pi / 2), **c)


ROLE_SENSORS = {
    'scout': lambda: rgb_camera('scout', PITCH['scout']) + thermal_camera('scout', PITCH['scout']),
    'mapper': lambda: lidar_3d('mapper'),
    'relay': lambda: '',
}


def rotor(i, motor, direction):
    x, y = m[motor]
    mass = par['base']['prop_kg']
    r = geo['prop_radius_m']
    ixx = mass * (0.012 ** 2) / 12
    izz = mass * (2 * r) ** 2 / 12
    return """
    <link name="rotor_{i}">
      <pose>{x:.4f} {y:.4f} {z:.4f} 0 0 0</pose>
      <inertial><mass>{mass}</mass><inertia><ixx>{ixx:.3e}</ixx><iyy>{izz:.3e}</iyy><izz>{izz:.3e}</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial>
      {vis}
      <collision name="rotor_{i}_collision"><geometry><box><size>{d:.4f} 0.012 0.002</size></box></geometry></collision>
    </link>
    <joint name="rotor_{i}_joint" type="revolute">
      <parent>base_link</parent><child>rotor_{i}</child>
      <axis><xyz>0 0 1</xyz><limit><lower>-1e+16</lower><upper>1e+16</upper></limit>
        <dynamics><spring_reference>0</spring_reference><spring_stiffness>0</spring_stiffness></dynamics></axis>
    </joint>""".format(i=i, x=x, y=y, z=PROP_Z, mass=mass, ixx=ixx, izz=izz, d=2 * r,
                       vis=mesh_visual('rotor_%d_visual' % i, 'model://resqmesh_quad/meshes/%s.stl'
                                       % ('prop' if direction == 'ccw' else 'prop_cw'), (0.15, 0.6, 0.2)))


def motor_plugin(i, direction):
    return """
    <plugin filename="gz-sim-multicopter-motor-model-system" name="gz::sim::systems::MulticopterMotorModel">
      <jointName>rotor_{i}_joint</jointName><linkName>rotor_{i}</linkName>
      <turningDirection>{d}</turningDirection>
      <timeConstantUp>{time_constant_up}</timeConstantUp><timeConstantDown>{time_constant_down}</timeConstantDown>
      <maxRotVelocity>{max_rot_velocity}</maxRotVelocity><motorConstant>{motor_constant}</motorConstant>
      <momentConstant>{moment_constant}</momentConstant>
      <commandSubTopic>command/motor_speed</commandSubTopic><motorNumber>{i}</motorNumber>
      <rotorDragCoefficient>{rotor_drag_coefficient}</rotorDragCoefficient>
      <rollingMomentCoefficient>{rolling_moment_coefficient}</rollingMomentCoefficient>
      <rotorVelocitySlowdownSim>10</rotorVelocitySlowdownSim><motorType>velocity</motorType>
    </plugin>""".format(i=i, d=direction, **P)


def model_sdf(role):
    mp = mass_props(role)
    I = mp['inertia']
    spec = geo['roles'][role]
    vis = []
    for p in spec['parts']:
        if role == 'mapper' and 'thermal' in p['part'].lower():
            continue
        for k, f in enumerate(p['files']):
            vis.append(mesh_visual('%s_%d' % (''.join(c if c.isalnum() else '_' for c in p['part']), k),
                                   'model://resqmesh_quad/meshes/' + f['mesh'], COLOUR[f['colour']], tag=f['colour']))
    battery_under = '4s lipo' not in spec['hide']
    if battery_under:
        vis.append(mesh_visual('battery_under_frame', 'model://resqmesh_quad/meshes/battery.stl', COLOUR['lipo']))
    payload_vis = ''.join(vis) + light_visuals(role)
    glo, ghi = gear_bbox(role)
    corners = [(sx, sy) for sx in (glo[0] + 0.006, ghi[0] - 0.006) for sy in (glo[1] + 0.006, ghi[1] - 0.006)]
    feet = ''.join('<collision name="foot_%d"><pose>%.4f %.4f %.4f 0 0 0</pose><geometry><sphere><radius>0.006</radius></sphere></geometry></collision>'
                   % (k, x, y, glo[2] + 0.006) for k, (x, y) in enumerate(corners))
    blo, bhi = geo['battery_bbox_m'] if battery_under else next(p['bbox_m'] for p in spec['parts'] if 'LiPo' in p['part'])
    body = """
    <link name="base_link">
      <inertial>
        <pose>{cx:.4f} {cy:.4f} {cz:.4f} 0 0 0</pose>
        <mass>{mass}</mass>
        <inertia><ixx>{ixx}</ixx><ixy>{ixy}</ixy><ixz>{ixz}</ixz><iyy>{iyy}</iyy><iyz>{iyz}</iyz><izz>{izz}</izz></inertia>
      </inertial>
      <gravity>true</gravity>
      <enable_wind>true</enable_wind>
      {frame}
      {payload}
      <collision name="battery_collision"><pose>{bx:.4f} {by:.4f} {bz:.4f} 0 0 0</pose><geometry><box><size>{bsx:.4f} {bsy:.4f} {bsz:.4f}</size></box></geometry></collision>
      <collision name="frame_collision"><pose>0 0 0.006 0 0 0</pose><geometry><box><size>0.16 0.16 0.02</size></box></geometry></collision>
      {feet}
      {common}{role_sensors}
    </link>""".format(cx=mp['com_m'][0], cy=mp['com_m'][1], cz=mp['com_m'][2], mass=mp['mass_kg'], frame=mesh_visual(
        'airframe', 'model://resqmesh_quad/meshes/body.stl', FRAME_GREY, tag='carbon'), payload=payload_vis,
        bx=(blo[0] + bhi[0]) / 2, by=(blo[1] + bhi[1]) / 2, bz=(blo[2] + bhi[2]) / 2,
        bsx=bhi[0] - blo[0], bsy=bhi[1] - blo[1], bsz=bhi[2] - blo[2], feet=feet,
        common=COMMON_SENSORS, role_sensors=ROLE_SENSORS[role](), **I)
    rotors = ''.join(rotor(i, mo, d) for i, (mo, d) in enumerate(ROTORS))
    plugins = ''.join(motor_plugin(i, d) for i, (_, d) in enumerate(ROTORS))
    plugins += '\n    <plugin filename="MotorFailurePlugin" name="gz::sim::systems::MotorFailureSystem"/>'   # damage demo
    sdf = """<?xml version="1.0" encoding="UTF-8"?>
<!-- generated by tools/gen_models.py from the team's Fusion frame; masses are PLACEHOLDERS (config/vehicle_params.yaml) -->
<sdf version="1.9">
  <model name="resqmesh_{role}">
    <pose>0 0 {z0:.3f} 0 0 0</pose>
    <self_collide>false</self_collide>
    <static>false</static>{body}{rotors}{plugins}
  </model>
</sdf>
""".format(role=role, z0=-glo[2] + 0.005, body=body, rotors=rotors, plugins=plugins)
    return sdf, mp


def parked_sdf(role):
    full, _ = model_sdf(role)
    import re
    vis = re.findall(r'<visual name="[^"]*">.*?</visual>', full, re.S)
    rot = [(m[mo], d) for mo, d in ROTORS]
    body = [v for v in vis if 'rotor_' not in v and 'led_' not in v and 'role_beacon' not in v]   # powered off: lights dark
    props = ''.join('<visual name="prop_%d"><pose>%.4f %.4f %.4f 0 0 %.2f</pose>%s'
                    % (i, xy[0], xy[1], PROP_Z, 0.4 * i, re.search(r'<geometry>.*</visual>', vis[-1], re.S).group(0))
                    for i, (xy, d) in enumerate(rot))
    glo = gear_bbox(role)[0]
    return ('<?xml version="1.0"?>\n<sdf version="1.9"><model name="resqmesh_%s_parked"><static>true</static>'
            '<pose>0 0 %.3f 0 0 0</pose><link name="base_link">%s%s</link></model></sdf>\n') % (role, -glo[2] + 0.005, ''.join(body), props)


CONFIG = """<?xml version="1.0"?>
<model>
  <name>resqmesh_{role}</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <author><name>Team Apex</name></author>
  <description>ResQMesh {role}: the team's 5-inch Fusion frame with the {role} payload. Masses are placeholders.</description>
</model>
"""

if __name__ == '__main__':
    out = {}
    base_cfg = os.path.join(SIM, 'models', 'resqmesh_quad', 'model.config')
    open(base_cfg, 'w').write(CONFIG.format(role='quad (shared meshes)'))
    for role in ('scout', 'mapper', 'relay'):
        d = os.path.join(SIM, 'models', 'resqmesh_' + role)
        os.makedirs(d, exist_ok=True)
        sdf, mp = model_sdf(role)
        open(os.path.join(d, 'model.sdf'), 'w').write(sdf)
        open(os.path.join(d, 'model.config'), 'w').write(CONFIG.format(role=role))
        dp = os.path.join(SIM, 'models', 'resqmesh_%s_parked' % role)
        os.makedirs(dp, exist_ok=True)
        open(os.path.join(dp, 'model.sdf'), 'w').write(parked_sdf(role))
        open(os.path.join(dp, 'model.config'), 'w').write(CONFIG.format(role=role + ' (parked)').replace('resqmesh_%s<' % (role + ' (parked)'), 'resqmesh_%s_parked<' % role))
        hover = mp['mass_kg'] * 9.81 / 4
        tmax = P['motor_constant'] * P['max_rot_velocity'] ** 2
        out[role] = dict(mp, hover_thrust_per_motor_n=round(hover, 3), max_thrust_per_motor_n=round(tmax, 3),
                         thrust_to_weight=round(tmax / hover, 2))
        print('%-6s mass %.3f kg  T/W %.2f  com %s' % (role, mp['mass_kg'], tmax / hover, mp['com_m']))
    json.dump(out, open(os.path.join(SIM, 'config', 'mass_props.json'), 'w'), indent=1)
