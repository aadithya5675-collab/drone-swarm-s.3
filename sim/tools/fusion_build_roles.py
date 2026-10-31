"""Fusion API script: build the three ResQMesh drones on the team's frame "assembly final"."""
import json
import math
import os

import adsk.core
import adsk.fusion

def sim_dir():
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        return os.environ.get('RESQMESH_SIM', os.path.expanduser(r'~\Desktop\HackOrbital-DroneSwarm\sim'))


OUT = os.path.join(sim_dir(), 'cad_export', 'roles')
BASE_NAME = 'assembly final'
P3 = adsk.core.Point3D.create
V3 = adsk.core.Vector3D.create
TMP = adsk.fusion.TemporaryBRepManager.get()

LOOK = {
    'carbon': ('Carbon Fiber - Plain', (30, 30, 32), 'carbon'),
    'pcb': ('Plastic - Glossy (Green)', (20, 90, 50), 'pcb'),
    'pcb_black': ('Plastic - Glossy (Black)', (25, 25, 25), 'black'),
    'alu': ('Aluminum - Anodized Glossy (Grey)', (150, 150, 155), 'alu'),
    'alu_dark': ('Aluminum - Anodized Rough (Grey)', (85, 85, 90), 'alu_dark'),
    'alu_red': ('Aluminum - Anodized Glossy (Red)', (170, 30, 30), 'red'),
    'alu_blue': ('Aluminum - Anodized Glossy (Blue)', (30, 70, 150), 'blue'),
    'black': ('Plastic - Matte (Black)', (20, 20, 20), 'black'),
    'white': ('Plastic - Glossy (White)', (235, 235, 235), 'white'),
    'yellow': ('Plastic - Glossy (Yellow)', (230, 190, 20), 'yellow'),
    'rubber': ('Rubber - Soft', (35, 35, 35), 'rubber'),
    'tpu_orange': ('Plastic - Matte (Red)', (220, 100, 30), 'orange'),
    'glass': ('Glass (Grey)', (60, 70, 80), 'glass'),
    'window': ('Plastic - Glossy (Black)', (15, 15, 18), 'window'),
    'gold': ('Gold - Polished', (210, 170, 60), 'gold'),
    'lipo': ('Plastic - Glossy (Blue)', (30, 60, 140), 'lipo'),
    'silver': ('Aluminum - Polished', (200, 200, 205), 'silver'),
}


FRAME_TOP_PLATE_Y = 3.64878      # top face of the top plate
FRAME_BOTTOM_Y = -0.10198        # underside of the bottom plate
FRAME_ARM_BOTTOM_Y = 0.09802     # underside of the arms
FRAME_NUT_TOP_Y = 0.94878
STANDOFF_XZ = ((1.0, -2.39), (1.0, 2.6), (-1.0, -2.4), (-1.0, 2.6))


def box(x0, x1, y0, y1, z0, z1):
    c = P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return [TMP.createBox(adsk.core.OrientedBoundingBox3D.create(c, V3(1, 0, 0), V3(0, 1, 0), x1 - x0, y1 - y0, z1 - z0))]


def cyl(p0, p1, r0, r1=None):
    return [TMP.createCylinderOrCone(P3(*p0), r0, P3(*p1), r0 if r1 is None else r1)]


def sphere(c, r):
    return [TMP.createSphere(P3(*c), r)]


def union(bodies):
    b = bodies[0]
    for o in bodies[1:]:
        TMP.booleanOperation(b, o, adsk.fusion.BooleanTypes.UnionBooleanType)
    return [b]


def cut(target, tools):
    b = target[0]
    for t in tools:
        TMP.booleanOperation(b, t, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    return [b]


def rbox(x0, x1, y0, y1, z0, z1, r, axis='y'):
    r = min(r, (x1 - x0) / 2 - 1e-3, (y1 - y0) / 2 - 1e-3, (z1 - z0) / 2 - 1e-3)
    if axis == 'y':
        parts = box(x0 + r, x1 - r, y0, y1, z0, z1) + box(x0, x1, y0, y1, z0 + r, z1 - r)
        parts += [cyl((x, y0, z), (x, y1, z), r)[0] for x in (x0 + r, x1 - r) for z in (z0 + r, z1 - r)]
    elif axis == 'z':
        parts = box(x0 + r, x1 - r, y0, y1, z0, z1) + box(x0, x1, y0 + r, y1 - r, z0, z1)
        parts += [cyl((x, y, z0), (x, y, z1), r)[0] for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r)]
    else:
        parts = box(x0, x1, y0 + r, y1 - r, z0, z1) + box(x0, x1, y0, y1, z0 + r, z1 - r)
        parts += [cyl((x0, y, z), (x1, y, z), r)[0] for y in (y0 + r, y1 - r) for z in (z0 + r, z1 - r)]
    return union(parts)


def transform(bodies, m):
    for b in bodies:
        TMP.transform(b, m)
    return bodies


def rot_x(deg, about):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(deg), V3(1, 0, 0), P3(*about))
    return m


def fc_stack():
    """SpeedyBee F405 Mini 20x20 stack: BLS 35A 4-in-1 ESC (lower) + F405 FC (upper), soft-mounted on rubber."""
    holes = [(x, 0.1 + z) for x in (-1.0, 1.0) for z in (-1.0, 1.0)]
    g = []
    for y in (1.0, 1.85):
        pcb = box(-1.35, 1.35, y, y + 0.16, -1.25, 1.45)
        g.append(('pcb_black', cut(pcb, [cyl((x, y - 0.01, z), (x, y + 0.17, z), 0.22)[0] for x, z in holes])))
    g.append(('alu_dark', union([box(-0.45 + dx, -0.15 + dx, 1.16, 1.26, -0.85 + dz, -0.45 + dz)[0]
                                 for dx in (0, 0.6) for dz in (0, 1.5)])))                     # ESC MOSFETs
    g.append(('silver', box(-0.35, 0.35, 2.01, 2.09, -0.25, 0.45)))                           # STM32F405
    g.append(('black', box(0.85, 1.35, 2.01, 2.25, -0.35, 0.55)))                             # USB-C
    g.append(('rubber', union([cyl((x, FRAME_NUT_TOP_Y, z), (x, 2.1, z), 0.22)[0] for x, z in holes])))   # grommets, on the nuts
    g.append(('black', cyl((-0.6, 1.5, -1.8), (0.6, 1.5, -1.8), 0.45)))                       # 35V 470uF cap
    g.append(('silver', union([cyl((x, 1.08, -1.68), (x, 1.08, -1.25), 0.05)[0] for x in (-0.3, 0.3)])))  # its leads, to the ESC pads
    g.append(('gold', box(-1.35, -1.25, 1.16, 1.2, -1.1, 1.3)))                               # motor pads
    return g


def gnss_mast(base_y, z=-3.4, tab=None, tab_y0=None):
    g = [('carbon', box(-0.69, 0.69, base_y - 0.2 if tab_y0 is None else tab_y0, base_y, tab[0], tab[1]))] if tab else []
    return g + [('black', rbox(-0.6, 0.6, base_y, base_y + 0.8, z - 0.6, z + 0.6, 0.2)),           # hinge base
            ('carbon', cyl((0, base_y + 0.8, z), (0, base_y + 6.0, z), 0.3)),                     # 6 mm CF tube
            ('black', cyl((0, base_y + 6.0, z), (0, base_y + 6.5, z), 0.6)),                      # puck clamp
            ('white', union(cyl((0, base_y + 6.5, z), (0, base_y + 7.2, z), 1.9) +
                            cyl((0, base_y + 7.2, z), (0, base_y + 7.6, z), 1.9, 1.5))),           # puck + dome
            ('tpu_orange', cyl((0.7, base_y + 7.6, z + 0.9), (0.7, base_y + 7.68, z + 0.9), 0.15))]   # status LED, on the dome top


ARM_LEG = [(sx * 4.5, sz * (1.11 + 5.77 * 4.5 / 6.88)) for sx in (-1, 1) for sz in (-1, 1)]


def landing_gear(foot_y):
    g = []
    for x, z in ARM_LEG:
        sx, sz = math.copysign(1, x), math.copysign(1, z)
        top = (x, -0.45, z)
        bot = (x + sx * 1.2, foot_y + 0.45, z + sz * 1.2)
        leg = lambda: cyl(top, bot, 0.3)  # noqa: E731
        g.append(('black', cut(rbox(x - 0.55, x + 0.55, -0.55, FRAME_ARM_BOTTOM_Y, z - 0.55, z + 0.55, 0.15), leg())))  # arm clamp, bored
        g.append(('carbon', leg()))
        g.append(('tpu_orange', cut(union(sphere(bot, 0.5) + cyl((bot[0], foot_y, bot[2]), (bot[0], foot_y + 0.3, bot[2]), 0.6)),
                                    leg())))                                                  # TPU foot, bored
    return g


def top_adapter():
    T = FRAME_TOP_PLATE_Y
    return [('silver', union([cyl((x, T, z), (x, 4.25, z), 0.25)[0] for x, z in STANDOFF_XZ] +
                             [cyl((x, 3.0, z), (x, T, z), 0.13)[0] for x, z in STANDOFF_XZ])),     # M3 M-F 6 mm, thread into the standoff
            ('carbon', rbox(-4.2, 4.2, 4.25, 4.45, -4.45, 3.0, 0.4))]


def jetson(y0, flip=False, dz=0.0):
    s = -1 if flip else 1
    Y = lambda a: y0 + s * a  # noqa: E731
    lo = lambda a, b: (min(Y(a), Y(b)), max(Y(a), Y(b)))  # noqa: E731
    g = jetson_parts(Y, lo)
    if dz:
        m = adsk.core.Matrix3D.create()
        m.translation = V3(0, 0, dz)
        g = [(k, transform(b, m)) for k, b in g]
    return g


def jetson_parts(Y, lo):
    g = [('silver', union([cyl((x, Y(0), z), (x, Y(0.4), z), 0.2)[0] for x in (-3.6, 3.6) for z in (-2.3, 1.6)]))]
    g.append(('pcb', box(-4.2, 4.2, *lo(0.4, 0.56), -2.6, 2.05)))                               # carrier PCB
    g.append(('black', box(-3.48, 3.48, *lo(0.56, 0.72), -2.55, -2.05)))                         # SO-DIMM socket
    g.append(('pcb', box(-3.48, 3.48, *lo(0.72, 0.84), -2.55, 1.95)))                            # module PCB
    g.append(('alu_dark', union(box(-3.0, 3.0, *lo(0.84, 1.2), -2.2, 1.6) +
                                [box(x - 0.06, x + 0.06, *lo(1.19, 2.4), -2.2, 1.6)[0]
                                 for x in [-2.7 + 0.6 * k for k in range(10)]])))                 # finned heatsink, one machined part
    g.append(('silver', box(3.55, 4.2, *lo(0.56, 1.25), -2.6, -1.2)))                            # USB 3.0 x1 (beside the module)
    g.append(('white', union([box(x - 0.6, x + 0.6, *lo(0.56, 0.72), 1.55, 2.0)[0] for x in (-1.5, 1.5)])))  # 2x CSI (low-profile FPC)
    g.append(('black', box(-4.2, -3.55, *lo(0.56, 0.9), -0.4, 0.6)))                             # power in
    return g


def sensor_head(z_front=4.515, pitch=34.0, cy=5.3):
    cz = z_front - 1.1
    h = [('black', rbox(-2.0, 2.0, cy - 0.9, cy + 0.9, z_front - 2.2, z_front, 0.35, axis='z'))]  # housing
    h.append(('glass', cyl((-0.9, cy, z_front), (-0.9, cy, z_front + 0.55), 0.62)))              # IMX219 M12 lens
    h.append(('black', cyl((-0.9, cy, z_front + 0.55), (-0.9, cy, z_front + 0.7), 0.7)))         # lens ring
    h.append(('alu_dark', box(0.35, 1.45, cy - 0.55, cy + 0.55, z_front, z_front + 0.25)))      # Lepton bezel
    h.append(('glass', box(0.55, 1.25, cy - 0.35, cy + 0.35, z_front + 0.25, z_front + 0.3)))   # germanium window
    h.append(('white', cyl((1.65, cy + 0.6, z_front), (1.65, cy + 0.6, z_front + 0.05), 0.1)))   # status LED
    rotated = [(k, transform(b, rot_x(pitch, (0, cy, cz)))) for k, b in h]
    bracket = [('carbon', cut(box(-0.7, 0.7, 4.45, cy - 0.1, 1.6, 2.05), [TMP.copy(rotated[0][1][0])]))]
    return bracket + rotated


LIDAR_STANDOFF_XZ = [(x, z) for x in (-3.0, 3.0) for z in (-3.2, 3.0)]   # outside the Jetson carrier (z -2.6..2.05)


def livox_mid360_under():
    g = [('silver', union([cyl((x, -0.7, z), (x, -3.5, z), 0.25)[0] for x, z in LIDAR_STANDOFF_XZ]))]
    g.append(('carbon', rbox(-3.8, 3.8, -3.8, -3.5, -3.8, 3.8, 0.6)))                            # mount plate
    g.append(('alu', rbox(-3.25, 3.25, -6.0, -3.8, -3.25, 3.25, 0.8)))                           # body
    g.append(('window', cyl((0, -6.0, 0), (0, -9.2, 0), 3.0)))                                   # optical window
    g.append(('alu', cyl((0, -9.2, 0), (0, -9.8, 0), 3.15, 2.9)))                                # end cap
    g.append(('black', cyl((0, -4.8, -3.25), (0, -4.8, -4.1), 0.55)))                            # M12 connector
    sensor = rot_x(-90.0, (0, 0, 0))                                 # axis -Y (down) -> +Z (forward)
    t = adsk.core.Matrix3D.create()
    t.translation = V3(0, -7.05, -5.0)                               # top of the body on the plate, centred
    sensor.transformBy(t)
    return g[:2] + [(k, transform(b, sensor)) for k, b in g[2:]]


def lipo_top():
    T = FRAME_TOP_PLATE_Y
    pad = cut(box(-1.75, 1.75, T, 3.95, -2.4, 5.1), [cyl((x, 3.6, z), (x, 4.0, z), 0.34)[0] for x in (-1.0, 1.0) for z in (-2.4, 2.6)])
    return [('rubber', pad),                                                                     # grip pad, holes over the screw heads
            ('lipo', rbox(-1.75, 1.75, 3.95, 7.45, -2.4, 5.1, 0.35, axis='z')),
            ('black', union(box(-1.85, 1.85, 7.45, 7.6, 0.6, 2.2) + box(-1.85, -1.75, T, 7.6, 0.6, 2.2) +
                            box(1.75, 1.85, T, 7.6, 0.6, 2.2))),                                  # 16 mm strap
            ('yellow', box(-0.8, 0.8, 5.0, 6.0, -3.05, -2.4))]                                   # XT60, clear of the mast hinge


def bottom_adapter():
    B = FRAME_BOTTOM_Y
    holes = lambda r, y0, y1: [cyl((x, y0, z), (x, y1, z), r)[0] for x, z in STANDOFF_XZ]  # noqa: E731
    spacers = cut(union(holes(0.4, B, -0.5)), holes(0.17, B + 0.01, -0.51))
    plate = cut(rbox(-4.2, 4.2, -0.7, -0.5, -3.6, 3.4, 0.4), holes(0.17, -0.49, -0.71))
    screws = union(holes(0.14, -0.7, 1.95) + holes(0.275, -0.98, -0.7))                     # shank into the standoff + head
    return [('silver', spacers), ('carbon', plate), ('black', screws)]


def underslung_jetson():
    return jetson(-0.7, flip=True)


def rfd900x():
    g = [('alu_blue', rbox(-1.5, 1.5, 4.45, 5.75, -2.85, 2.85, 0.2, axis='y'))]
    g.append(('alu_blue', union([box(-1.5, 1.5, 5.75, 5.95, z - 0.08, z + 0.08)[0] for z in [-2.4 + 0.6 * k for k in range(9)]])))
    for x in (-0.8, 0.8):
        g.append(('gold', cyl((x, 5.1, 2.85), (x, 5.1, 3.0), 0.3)))                              # RP-SMA, up to the hinge
        g.append(('black', union(cyl((x, 5.1, 3.45), (x, 6.3, 3.45), 0.45) +
                                 cyl((x, 6.3, 3.45), (x, 20.0, 3.45), 0.35, 0.28))))              # 900 MHz dipole
    return g


def mesh_radio():
    g = [('black', rbox(-1.3, 1.3, 5.95, 6.65, -2.6, 2.6, 0.2))]
    for x in (-1.75, 1.75):
        g.append(('gold', cyl((x - math.copysign(0.45, x), 6.3, -1.9), (x - math.copysign(0.3, x), 6.3, -1.9), 0.25)))  # u.FL to the antenna
        g.append(('black', cyl((x, 6.0, -1.9), (x, 17.0, -1.9), 0.3, 0.25)))
    return g


def pi_zero():
    return [('pcb', box(-3.25, 3.25, 6.85, 6.97, -1.0, 2.0)),
            ('silver', box(-0.5, 0.5, 6.97, 7.08, 0.0, 1.0)),                                     # RP3A0 SiP
            ('silver', box(-3.25, -2.6, 6.97, 7.2, -0.6, 0.2)),                                   # micro-USB
            ('silver', union([cyl((x, 4.45, z), (x, 6.85, z), 0.2)[0] for x in (-2.9, 2.9) for z in (-0.65, 1.65)]))]


COMMON = [('SpeedyBee F405 Mini stack 20x20', fc_stack)]
BUTTON_SCREWS = 'Broached Hexagon Socket Button Head Cap Screw ANSI B18.3.4M - M3 x 0.5 x 8 Steel Grade 2 Plain'
COUNTERSUNK_M3X16 = 'Broached Hexagon Socket Flat Countersunk Head Cap Screw ANSI B18.3.5M - M3x16 Steel Grade 2 Plain'
ROLES = {
    'scout': {'hide': [BUTTON_SCREWS],          # the top adapter's M-F spacers take their place
              'parts': COMMON + [('Landing gear (4x CF legs)', lambda: landing_gear(-6.6)),
                                 ('Top adapter plate', top_adapter),
                                 ('NVIDIA Jetson Nano 4GB + carrier', lambda: jetson(4.45, dz=-0.5)),
                                 ('Sensor head: IMX219 RGB + Lepton 3.5 thermal', sensor_head),
                                 ('M10 GNSS + compass on mast', lambda: gnss_mast(4.45, z=-3.75))]},
    'mapper': {'hide': ['4s lipo', 'Battery pad', 'Battery strap 16mm', COUNTERSUNK_M3X16],
               'parts': COMMON + [('Landing gear (4x CF legs, tall)', lambda: landing_gear(-12.0)),
                                  ('4S 1550 mAh LiPo (top mount)', lipo_top),
                                  ('Bottom adapter plate', bottom_adapter),
                                  ('NVIDIA Jetson Nano 4GB + carrier (underslung)', underslung_jetson),
                                  ('Livox Mid-360 3D lidar (inverted, under frame)', livox_mid360_under),   # name kept: mass table key
                                  ('M10 GNSS + compass on mast', lambda: gnss_mast(3.85, z=-3.6, tab=(-4.4, -2.45), tab_y0=FRAME_TOP_PLATE_Y))]},
    'relay': {'hide': [BUTTON_SCREWS],
              'parts': COMMON + [('Landing gear (4x CF legs)', lambda: landing_gear(-6.6)),
                                 ('Top adapter plate', top_adapter),
                                 ('RFD900x long-range modem + 2 dipoles', rfd900x),
                                 ('Wi-Fi/LoRa mesh node + 2 dipoles', mesh_radio),
                                 ('Raspberry Pi Zero 2 W companion', pi_zero),
                                 ('M10 GNSS + compass on mast', lambda: gnss_mast(4.45, z=-3.75))]},
}


def appearance(design, key):
    lib_name, rgb, _ = LOOK[key]
    a = design.appearances.itemByName(lib_name)
    if a:
        return a
    lib = adsk.core.Application.get().materialLibraries.itemByName('Fusion Appearance Library')
    src = lib.appearances.itemByName(lib_name) if lib else None
    return design.appearances.addByCopy(src, lib_name) if src else None


def upright(vp):
    cam = vp.camera
    cam.target = P3(0, 0, 0)
    cam.eye = P3(45, 30, 45)
    cam.upVector = V3(0, 1, 0)
    cam.isFitView = True
    vp.camera = cam
    vp.refresh()


def safe(name):
    return ''.join(c if c.isalnum() else '_' for c in name).strip('_')


SAVE_AS = {'scout': 'ResQMesh Scout', 'mapper': 'ResQMesh Mapper rev3', 'relay': 'ResQMesh Relay'}


def interference(design, root, base_occ):
    """Fusion's exact interference analysis over every visible solid: role components and the frame's parts."""
    ents = adsk.core.ObjectCollection.create()
    for o in root.occurrences:
        if o != base_occ:
            ents.add(o)
    for o in base_occ.childOccurrences:
        if o.isLightBulbOn:
            ents.add(o)
    inp = design.createInterferenceInput(ents)
    inp.areCoincidentFacesIncluded = False
    out = []
    for r in design.analyzeInterference(inp):
        def nm(e):
            b_ = adsk.fusion.BRepBody.cast(e)
            if b_:
                return (b_.assemblyContext.component.name if b_.assemblyContext else b_.parentComponent.name) + '/' + b_.name
            o_ = adsk.fusion.Occurrence.cast(e)
            return o_.component.name if o_ else '?'
        v = r.interferenceBody.volume * 1000.0
        if v > 1.0:
            out.append((nm(r.entityOne), nm(r.entityTwo), round(v, 1)))
    for a_, b_, v in out:
        print('   INTERFERENCE %.1f mm3: %s <-> %s' % (v, a_, b_))
    return out


def contact_audit(design):
    """Exact load-path check: every visible solid must touch (Fusion minimum distance < 20 um) or overlap another, and."""
    mm = adsk.core.Application.get().measureManager
    bodies = []
    for o in design.rootComponent.allOccurrences:
        if o.isLightBulbOn and o.isVisible:
            bodies += [(o.component.name, b) for b in o.bRepBodies if b.isVisible]
    n = len(bodies)
    bb = [b.boundingBox for _, b in bodies]
    adj, near = [set() for _ in range(n)], {}
    for i in range(n):
        for j in range(i + 1, n):
            a_, c = bb[i], bb[j]
            if (a_.minPoint.x - 0.2 > c.maxPoint.x or c.minPoint.x - 0.2 > a_.maxPoint.x or a_.minPoint.y - 0.2 > c.maxPoint.y or
                    c.minPoint.y - 0.2 > a_.maxPoint.y or a_.minPoint.z - 0.2 > c.maxPoint.z or c.minPoint.z - 0.2 > a_.maxPoint.z):
                continue
            d = mm.measureMinimumDistance(bodies[i][1], bodies[j][1]).value
            if d < 0.002:
                adj[i].add(j)
                adj[j].add(i)
            else:
                near.setdefault(i, []).append((d, j))
                near.setdefault(j, []).append((d, i))
    seen, groups = set(), []
    for s0 in range(n):
        if s0 in seen:
            continue
        st, g = [s0], []
        seen.add(s0)
        while st:
            u = st.pop()
            g.append(u)
            for v in adj[u] - seen:
                seen.add(v)
                st.append(v)
        groups.append(g)
    groups.sort(key=len, reverse=True)
    loose = []
    for g in groups[1:]:
        for u in g:
            gaps = sorted(near.get(u, []))
            loose.append({'component': bodies[u][0], 'body': bodies[u][1].name,
                          'gap_mm': round(gaps[0][0] * 10, 3) if gaps else None,
                          'to': bodies[gaps[0][1]][0] if gaps else None})
    print('   contact: %d solids, %d connected group(s)' % (n, len(groups)))
    for l_ in loose:
        print('   LOOSE %s/%s  gap %s mm to %s' % (l_['component'], l_['body'], l_['gap_mm'], l_['to']))
    return loose


def run(_context: str):
    app = adsk.core.Application.get()
    base = next(d for d in app.documents if d.name == BASE_NAME).dataFile
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith('.stl') or f.endswith('.step'):
            os.remove(os.path.join(OUT, f))
    report = {}
    for role, spec in ROLES.items():
        doc = next((d for d in app.documents if d.name == SAVE_AS[role]), None)
        if doc:
            doc.activate()
            design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
            root = design.rootComponent
            base_occ = next(o for o in root.occurrences if o.component.name == BASE_NAME)
            for o in [o for o in root.occurrences if o != base_occ]:
                o.deleteMe()
            role_hidden = {h for r in ROLES.values() for h in r['hide']}
            for o in base_occ.childOccurrences:
                if o.component.name in role_hidden:
                    o.isLightBulbOn = True
        else:
            doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(app.activeProduct)
            root = design.rootComponent
            base_occ = root.occurrences.addByInsert(base, adsk.core.Matrix3D.create(), True)
        hidden = []
        for o in base_occ.childOccurrences:
            if o.component.name in spec['hide']:
                o.isLightBulbOn = False
                hidden.append(o.component.name)
        em = design.exportManager
        report[role] = {'hide': hidden, 'parts': []}
        for name, fn in spec['parts']:
            occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = name
            bf = comp.features.baseFeatures.add()
            bf.startEdit()
            looks = []
            for key, bodies in fn():
                for b in bodies:
                    nb = comp.bRepBodies.add(b, bf)
                    looks.append((nb, key))
            bf.finishEdit()
            # bodies are re-created by the base feature; match them back by order
            for (nb, key), body in zip(looks, comp.bRepBodies):
                ap = appearance(design, key)
                if ap:
                    body.appearance = ap
            # one STL per look so colours survive into Gazebo
            by_look = {}
            for (_, key), body in zip(looks, comp.bRepBodies):
                by_look.setdefault(LOOK[key][2], []).append(body)
            files = []
            for tag, bodies in by_look.items():
                for i, body in enumerate(bodies):
                    fn_ = '%s__%s__%s_%d.stl' % (role, safe(name), tag, i)
                    opt = em.createSTLExportOptions(body, os.path.join(OUT, fn_))
                    opt.isBinaryFormat = True
                    opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementMedium
                    em.execute(opt)
                    files.append({'file': fn_, 'colour': tag})
            bb = occ.boundingBox
            report[role]['parts'].append({'part': name, 'files': files,
                                          'bbox_cm': [bb.minPoint.asArray(), bb.maxPoint.asArray()],
                                          'volume_cm3': sum(b.volume for b in comp.bRepBodies)})
        report[role]['interference'] = interference(design, root, base_occ)
        report[role]['loose'] = contact_audit(design)
        em.execute(em.createSTEPExportOptions(os.path.join(OUT, 'resqmesh_%s.step' % role), root))
        if doc.isSaved and doc.dataFile:
            doc.save('Rebuilt by sim/tools/fusion_build_roles.py: fabrication audit fixes')
        else:
            doc.saveAs(SAVE_AS[role], base.parentFolder, 'Generated by sim/tools/fusion_build_roles.py (fabrication-checked)', '')
        upright(app.activeViewport)
        print(role, ':', len(spec['parts']), 'components,', sum(len(p['files']) for p in report[role]['parts']),
              'bodies, hidden base parts:', hidden or 'none')
    json.dump(report, open(os.path.join(OUT, 'payloads.json'), 'w'), indent=1)
