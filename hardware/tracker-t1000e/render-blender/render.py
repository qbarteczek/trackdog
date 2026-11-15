import bpy, math, os, sys
from mathutils import Vector

D = os.path.dirname(os.path.abspath(__file__))
ujecie = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'iso'

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

MAT = {  # kolor bazowy, chropowatość, przezroczystość
    'podstawa': ((0.10, 0.45, 0.48, 1), 0.45, 1.0),
    'ramka':    ((0.95, 0.50, 0.06, 1), 0.40, 1.0),
    'karta':    ((0.012, 0.012, 0.014, 1), 0.65, 1.0),
    'listwy':   ((0.02, 0.02, 0.02, 1), 0.55, 1.0),
    'paski':    ((0.55, 0.45, 0.30, 1), 0.85, 0.55),
}
obj = {}
for n, (kol, rough, alfa) in MAT.items():
    bpy.ops.wm.stl_import(filepath=f'{D}/{n}.stl')
    o = bpy.context.selected_objects[0]; o.name = n
    m = bpy.data.materials.new(n); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = kol
    b.inputs['Roughness'].default_value = rough
    b.inputs['Alpha'].default_value = alfa
    o.data.materials.append(m)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    obj[n] = o

# rozstrzelenie: ramka i karta w górę, listwy wysunięte
if ujecie == 'rozstrzelony':
    obj['ramka'].location.z += 28
    obj['karta'].location.z += 14
    obj['listwy'].location.y -= 45
    obj['paski'].hide_render = True

# podłoże (tylko w ujęciach od góry) i światło
if ujecie in ('iso', 'gora', 'rozstrzelony', 'bok'):
    bpy.ops.mesh.primitive_plane_add(size=2000, location=(45, 30, -0.05 if ujecie != 'rozstrzelony' else -0.05))
    p = bpy.context.object; mp = bpy.data.materials.new('tlo'); mp.use_nodes = True
    mp.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.92, 0.91, 0.89, 1)
    mp.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    p.data.materials.append(mp)
w = bpy.data.worlds.new('swiat'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.95, 0.95, 0.96, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
for loc, en, size in [((-60, -120, 200), 9e5, 180), ((220, 160, 120), 4e5, 160), ((45, 30, -200), 2.5e5, 200)]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object; L.data.energy = en; L.data.size = size
    L.rotation_euler = (Vector((45, 30, 8)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

# kamera
srodek = Vector((45.8, 30.8, 8))
UJ = {   # kierunek patrzenia (od kamery do środka), ortograficzna?, skala orto / odległość
    'iso':          ((-1.0, -1.25, -0.95), False, 270),
    'gora':         ((0, 0, -1), True, 120),
    'spod':         ((0.35, -0.55, 1.0), False, 260),
    'bok':          ((0, -1, -0.12), True, 125),
    'rozstrzelony': ((-1.0, -1.3, -0.8), False, 330),
}
kier, orto, d = UJ[ujecie]
kier = Vector(kier).normalized()
bpy.ops.object.camera_add(location=srodek - kier * d)
cam = bpy.context.object; sc.camera = cam
cam.rotation_euler = kier.to_track_quat('-Z', 'Y').to_euler()
cam.data.clip_start = 1; cam.data.clip_end = 5000
if orto:
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = d
else:
    cam.data.lens = 50

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 32
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1200, 860
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Standard'
sc.view_settings.exposure = -0.35
sc.render.filepath = f'{D}/render_{ujecie}.png'
bpy.ops.render.render(write_still=True)
print('ZAPISANO', sc.render.filepath)
