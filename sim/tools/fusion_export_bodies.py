"""Fusion API script: export every body of "assembly final" as STL plus a manifest (cad_export/)."""
import json
import os
import re

import adsk.core
import adsk.fusion


def sim_dir():
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        return os.environ.get('RESQMESH_SIM', os.path.expanduser(r'~\Desktop\HackOrbital-DroneSwarm\sim'))


def group_of(path):
    if path.startswith('Gemfan Hurricane 51466 (1)'):
        return None                                    # hidden duplicate props in the frame file
    if re.match(r'P[1-4]:1$', path):
        return 'prop_' + path[1]
    if path.startswith('racerstarBR2205Simplified:'):
        return 'motor_' + path.split(':')[1][0]
    if path.startswith(('4s lipo', 'Battery pad', 'Battery strap')):
        return 'battery'
    if path.startswith(('m3 press nut', 'Broached Hexagon')):
        return None                                    # fasteners
    return 'frame'


def run(_context: str):
    app = adsk.core.Application.get()
    doc = next(d for d in app.documents if d.name == 'assembly final' and d.isSaved)
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    out = os.path.join(sim_dir(), 'cad_export')
    em = design.exportManager
    bodies = []
    for o in design.rootComponent.allOccurrences:
        g = group_of(o.fullPathName)
        if g is None:
            continue
        for b in o.bRepBodies:
            fn = '%03d_%s.stl' % (len(bodies) + 1, g)
            opt = em.createSTLExportOptions(b, os.path.join(out, 'bodies', fn))
            opt.isBinaryFormat = True
            opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementLow
            em.execute(opt)
            bb = b.boundingBox
            bodies.append({'file': fn, 'group': g, 'occurrence': o.fullPathName, 'body': b.name,
                           'bbox_cm': [bb.minPoint.asArray(), bb.maxPoint.asArray()], 'volume_cm3': b.volume})
    json.dump({'units_note': 'bbox in cm (Fusion internal); STL in mm, body-local', 'up_axis': 'Y', 'bodies': bodies},
              open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    print('exported', len(bodies), 'bodies')
