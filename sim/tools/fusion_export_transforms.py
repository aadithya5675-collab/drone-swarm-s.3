"""Fusion API script: write every occurrence's transform of "assembly final" to cad_export/transforms.json."""
import json
import os

import adsk.core
import adsk.fusion


def sim_dir():
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        return os.environ.get('RESQMESH_SIM', os.path.expanduser(r'~\Desktop\HackOrbital-DroneSwarm\sim'))


def run(_context: str):
    app = adsk.core.Application.get()
    doc = next(d for d in app.documents if d.name == 'assembly final' and d.isSaved)
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    out = {o.fullPathName: list(o.transform2.asArray()) for o in design.rootComponent.allOccurrences}
    json.dump(out, open(os.path.join(sim_dir(), 'cad_export', 'transforms.json'), 'w'), indent=0)
    print(len(out), 'transforms')
