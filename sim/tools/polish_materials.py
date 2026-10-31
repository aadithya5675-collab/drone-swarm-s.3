"""PBR finish for the generated world models (same table gen_wayanad.py uses for new models)."""
import glob
import os
import re

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# material key -> (metalness, roughness, optional new rgb)
PBR = {'water': (0.25, 0.12, (0.29, 0.26, 0.20)),
       'steel': (0.85, 0.35, None), 'glass': (0.4, 0.08, None), 'concrete': (0.0, 0.85, None), 'road': (0.0, 0.8, None),
       'roof_tile': (0.0, 0.62, None), 'roof_slab': (0.05, 0.75, None), 'leaf': (0.0, 0.8, None), 'leaf_light': (0.0, 0.8, None),
       'palm': (0.0, 0.7, None), 'trunk': (0.0, 0.9, None), 'tent_white': (0.0, 0.55, None), 'tent_orange': (0.0, 0.55, None),
       'tent_blue': (0.0, 0.55, None), 'pad': (0.1, 0.6, None), 'red': (0.2, 0.45, None), 'white': (0.1, 0.45, None),
       'wall_white': (0.0, 0.7, None), 'wall_cream': (0.0, 0.7, None), 'wall_blue': (0.0, 0.7, None),
       'wall_pink': (0.0, 0.7, None), 'wall_yellow': (0.0, 0.7, None), 'olive': (0.1, 0.6, None)}


def polish(path):
    s = open(path).read()
    n = 0

    def fix(m):
        nonlocal n
        name, body = m.group(1), m.group(2)
        if name not in PBR or '<pbr>' in body:
            return m.group(0)
        metal, rough, rgb = PBR[name]
        if rgb:
            c = '%.3f %.3f %.3f 1' % rgb
            body = re.sub(r'<ambient>[^<]*</ambient>', '<ambient>%s</ambient>' % c, body)
            body = re.sub(r'<diffuse>[^<]*</diffuse>', '<diffuse>%s</diffuse>' % c, body)
        body = body.replace('<specular>0.05 0.05 0.05 1</specular>', '<specular>0.35 0.35 0.35 1</specular>')
        body = body.replace('</material>', '<pbr><metal><metalness>%.2f</metalness><roughness>%.2f</roughness></metal></pbr></material>'
                            % (metal, rough))
        n += 1
        return '<visual name="%s">%s' % (name, body)

    s = re.sub(r'<visual name="([^"]+)">(.*?</material>)', fix, s, flags=re.S)
    open(path, 'w', newline='\n').write(s)
    return n


def main():
    total = 0
    for d in glob.glob(os.path.join(SIM, 'models', 'resqmesh_*')):
        b = os.path.basename(d)
        if b.startswith(('resqmesh_scout', 'resqmesh_mapper', 'resqmesh_relay', 'resqmesh_debris', 'resqmesh_textures',
                         'resqmesh_quad', 'resqmesh_wayanad_terrain', 'resqmesh_terrain')):
            continue
        p = os.path.join(d, 'model.sdf')
        if os.path.exists(p):
            total += polish(p)
    print('PBR materials on %d visuals' % total)


if __name__ == '__main__':
    main()
