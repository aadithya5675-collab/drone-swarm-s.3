"""Export the simulated drones to GLB for the web dashboard (three.js)."""
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(SIM, 'models')
OUT = os.path.join(SIM, 'dashboard', 'app', 'public', 'models')
ROLES = {'scout': 'resqmesh_scout', 'mapper': 'resqmesh_mapper', 'relay': 'resqmesh_relay'}


def pose_mat(text):
    v = [float(x) for x in (text or '0 0 0 0 0 0').split()] + [0.0] * 6
    x, y, z, r, p, w = v[:6]
    m = trimesh.transformations.euler_matrix(r, p, w, 'sxyz')
    m[:3, 3] = (x, y, z)
    return m


def resolve(uri):
    if uri.startswith('model://'):
        return os.path.join(MODELS, *uri[len('model://'):].split('/'))
    return uri


def material(vis):
    m = vis.find('material')
    rgba, metal, rough, emis = [0.5, 0.5, 0.5, 1.0], 0.0, 0.6, None
    if m is not None:
        d = m.find('diffuse')
        if d is not None:
            rgba = [float(x) for x in d.text.split()][:4]
        e = m.find('emissive')
        if e is not None:
            emis = [float(x) for x in e.text.split()][:3]
        me, ro = m.find('pbr/metal/metalness'), m.find('pbr/metal/roughness')
        metal = float(me.text) if me is not None else metal
        rough = float(ro.text) if ro is not None else rough
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[int(255 * min(1, max(0, c))) for c in rgba], metallicFactor=metal, roughnessFactor=rough,
        emissiveFactor=emis, name=vis.get('name'))


def geometry(vis):
    g = vis.find('geometry')
    if g is None:
        return None
    if g.find('mesh') is not None:
        path = resolve(g.find('mesh/uri').text.strip())
        if not os.path.exists(path):
            print('  missing mesh', path, file=sys.stderr)
            return None
        mesh = trimesh.load(path, force='mesh')
        sc = g.find('mesh/scale')
        if sc is not None:
            mesh.apply_scale([float(x) for x in sc.text.split()])
        return mesh
    if g.find('sphere') is not None:
        return trimesh.creation.icosphere(subdivisions=2, radius=float(g.find('sphere/radius').text))
    if g.find('cylinder') is not None:
        return trimesh.creation.cylinder(radius=float(g.find('cylinder/radius').text), height=float(g.find('cylinder/length').text), sections=24)
    if g.find('box') is not None:
        return trimesh.creation.box(extents=[float(x) for x in g.find('box/size').text.split()])
    return None


def export(role, model):
    sdf = ET.parse(os.path.join(MODELS, model, 'model.sdf')).getroot()
    mdl = sdf.find('model')
    scene = trimesh.Scene()
    zup_to_yup = trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])
    n = 0
    for link in mdl.findall('link'):
        L = pose_mat(link.findtext('pose'))
        for vis in link.findall('visual'):
            mesh = geometry(vis)
            if mesh is None:
                continue
            mesh.visual = trimesh.visual.TextureVisuals(material=material(vis))
            T = zup_to_yup @ L @ pose_mat(vis.findtext('pose'))
            node = vis.get('name')
            while node in scene.graph.nodes:
                node += '_'
            scene.add_geometry(mesh, node_name=node, geom_name=node, transform=T)
            n += 1
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, role + '.glb')
    scene.export(path)
    ext = scene.extents
    print('%-7s %3d parts  %.3f x %.3f x %.3f m  -> %s (%d kB)' % (role, n, ext[0], ext[2], ext[1], os.path.relpath(path, SIM),
                                                                    os.path.getsize(path) // 1024))


if __name__ == '__main__':
    for r, m in ROLES.items():
        export(r, m)
