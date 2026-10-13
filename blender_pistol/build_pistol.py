import bpy, math, sys
from mathutils import Vector
OUT = "/home/user/Deskfinity/blender_pistol"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, col, metal=0.0, rough=0.4, emit=None, es=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = es
    return m
M = dict(
    metal=mat("Gunmetal", (0.04,0.045,0.05), 1.0, 0.32),
    white=mat("WhitePanel", (0.82,0.84,0.86), 0.0, 0.35, coat=0.6),
    rubber=mat("GripRubber", (0.02,0.02,0.022), 0.0, 0.85),
    glow=mat("EnergyCyan", (0.0,0.6,1.0), 0.0, 0.2, (0.0,0.75,1.0), 12.0),
    orange=mat("AccentOrange", (1.0,0.32,0.02), 0.2, 0.35, coat=0.5),
    chrome=mat("Chrome", (0.9,0.9,0.92), 1.0, 0.08),
)
parts = []
def finish(o, m, bevel=0.0, seg=3):
    o.data.materials.append(M[m])
    if bevel:
        bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = bevel; bv.segments = seg
        bv.limit_method = 'ANGLE'
    for p in o.data.polygons: p.use_smooth = True
    parts.append(o); return o
def box(name, loc, size, m, bevel=0.02, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = (size[0]/2, size[1]/2, size[2]/2)
    bpy.ops.object.transform_apply(scale=True)
    return finish(o, m, bevel)
def cyl(name, loc, r, depth, m, axis='X', verts=48, bevel=0.0):
    rot = {'X':(0,math.pi/2,0),'Y':(math.pi/2,0,0),'Z':(0,0,0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name
    return finish(o, m, bevel)
def torus(name, loc, R, r, m, axis='X'):
    rot = {'X':(0,math.pi/2,0),'Z':(0,0,0)}[axis]
    bpy.ops.mesh.primitive_torus_add(location=loc, rotation=rot, major_radius=R, minor_radius=r,
                                     major_segments=48, minor_segments=12)
    o = bpy.context.object; o.name = name
    return finish(o, m)
def cut(target, cutter):
    b = target.modifiers.new("Cut", "BOOLEAN"); b.object = cutter; b.operation = 'DIFFERENCE'
    b.solver = 'EXACT'
    cutter.hide_render = True; cutter.display_type = 'WIRE'; parts.remove(cutter)
    target.modifiers.move(len(target.modifiers)-1, 0)

# ---- Receiver / body ----
body = box("Receiver", (0.15,0,0.30), (1.55,0.20,0.26), "metal", 0.025)
shroud = box("TopShroud", (0.35,0,0.53), (1.85,0.26,0.20), "white", 0.035)
# vent slots in shroud
for i in range(6):
    c = box(f"VentCut{i}", (0.55+i*0.11,0,0.53), (0.05,0.4,0.09), "metal", 0)
    cut(shroud, c)
vent_core = box("VentGlowCore", (0.82,0,0.53), (0.7,0.16,0.08), "glow", 0.005)
# side glow strips
for s in (1,-1):
    box(f"GlowStrip{s}", (0.0,s*0.131,0.50), (0.85,0.008,0.025), "glow", 0.002)
    box(f"OrangeTab{s}", (-0.45,s*0.132,0.56), (0.18,0.01,0.05), "orange", 0.004)
    box(f"SidePanel{s}", (0.25,s*0.104,0.28), (0.9,0.012,0.16), "white", 0.01)
# rear fin
box("RearFin", (-0.56,0,0.53), (0.22,0.14,0.16), "metal", 0.03, rot=(0,math.radians(-20),0))
# top rail
box("RailBase", (0.35,0,0.645), (1.1,0.09,0.03), "metal", 0.006)
for i in range(10):
    box(f"RailTooth{i}", (-0.15+i*0.11,0,0.67), (0.05,0.09,0.025), "metal", 0.004)
# sights
box("RearSight", (-0.32,0,0.655), (0.06,0.12,0.06), "metal", 0.008)
box("FrontSight", (1.18,0,0.68), (0.05,0.03,0.07), "metal", 0.008)
cyl("SightDot", (1.18,0,0.70), 0.008, 0.06, "glow", 'Y', 16)

# ---- Barrel assembly ----
cyl("BarrelHousing", (1.38,0,0.42), 0.12, 0.30, "metal", 'X', 6, 0.012)
cyl("Barrel", (1.62,0,0.42), 0.065, 0.55, "chrome")
for i in range(4):
    torus(f"Coil{i}", (1.55+i*0.07,0,0.42), 0.085, 0.014, "glow")
mz = cyl("Muzzle", (1.92,0,0.42), 0.11, 0.10, "metal", 'X', 48, 0.01)
mzc = cyl("MuzzleBore", (1.95,0,0.42), 0.055, 0.2, "metal")
cut(mz, mzc)
cyl("MuzzleGlow", (1.90,0,0.42), 0.054, 0.04, "glow")
# under-barrel emitter
box("UnderRail", (1.0,0,0.15), (0.6,0.14,0.08), "metal", 0.02)
cyl("UnderEmitter", (1.32,0,0.15), 0.035, 0.08, "orange", 'X', 24)

# ---- Grip ----
from mathutils import Matrix
GA = math.radians(16); GC = Vector((-0.30,0,-0.17)); R = Matrix.Rotation(GA, 3, 'Y')
def gp(x,y,z): return tuple(GC + R @ Vector((x,y,z)))
grip = box("Grip", gp(0,0,0), (0.30,0.18,0.80), "rubber", 0.05, rot=(0,GA,0))
for i in range(4):
    c = cyl(f"FingerGroove{i}", gp(0.17,0,0.22-i*0.13), 0.045, 0.4, "metal", 'Y', 32)
    cut(grip, c)
for i in range(7):
    c = box(f"BackGroove{i}", gp(-0.15,0,0.25-i*0.08), (0.04,0.3,0.025), "metal", 0, rot=(0,GA,0))
    cut(grip, c)
for sd in (1,-1):
    box(f"GripCell{sd}", gp(-0.02,sd*0.092,0.02), (0.10,0.01,0.40), "glow", 0.004, rot=(0,GA,0))
box("GripCap", gp(-0.01,0,-0.42), (0.34,0.20,0.07), "white", 0.025, rot=(0,GA,0))
box("GripBand", gp(0,0,0.34), (0.33,0.20,0.06), "orange", 0.01, rot=(0,GA,0))

# ---- Trigger guard (curve) ----
cu = bpy.data.curves.new("GuardCurve", 'CURVE'); cu.dimensions = '3D'
cu.bevel_depth = 0.025; cu.bevel_resolution = 4
sp = cu.splines.new('BEZIER'); pts = [(-0.14,0,0.12),(-0.02,0,-0.15),(0.42,0,-0.13),(0.66,0,0.18)]
sp.bezier_points.add(len(pts)-1)
for bp,p in zip(sp.bezier_points, pts):
    bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
g = bpy.data.objects.new("TriggerGuard", cu); sc.collection.objects.link(g)
g.data.materials.append(M["metal"]); parts.append(g)
box("Trigger", (0.14,0,0.06), (0.05,0.05,0.24), "chrome", 0.015, rot=(0,math.radians(-18),0))

# ---- Parent everything ----
root = bpy.data.objects.new("FuturisticPistol", None); sc.collection.objects.link(root)
for p in parts: p.parent = root

# ---- Scene: floor, lights, camera ----
bpy.ops.mesh.primitive_plane_add(size=30, location=(0,0,-0.665))
fl = bpy.context.object; fl.name = "Floor"; fl.data.materials.append(mat("Floor",(0.06,0.065,0.075),0,0.5))
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.012,0.014,0.02,1)
def light(name, loc, energy, size, col=(1,1,1)):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.color = col
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0.3,0,0.2)) - Vector(loc)).to_track_quat('-Z','Y').to_euler()
light("Key", (2.5,-3.5,3.5), 900, 3)
light("Rim", (-3,3,2.5), 700, 2, (0.5,0.75,1.0))
light("Fill", (-1,-4,0.5), 150, 4, (1,0.85,0.7))
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 55
cam = bpy.data.objects.new("Camera", cam_d); sc.collection.objects.link(cam); sc.camera = cam
def aim(loc, tgt=(0.55,0,0.12)):
    cam.location = loc
    cam.rotation_euler = (Vector(tgt)-Vector(loc)).to_track_quat('-Z','Y').to_euler()

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 64
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'

aim((2.9,-4.6,1.9)); sc.render.filepath = OUT+"/render_34.png"; bpy.ops.render.render(write_still=True)
aim((0.55,-5.2,0.25)); sc.render.filepath = OUT+"/render_side.png"; bpy.ops.render.render(write_still=True)
aim((2.9,-4.6,1.9))
bpy.ops.wm.save_as_mainfile(filepath=OUT+"/futuristic_pistol.blend")
fl.hide_set(True); fl.hide_render = True
bpy.ops.object.select_all(action='DESELECT')
for p in parts: p.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT+"/futuristic_pistol.glb", use_selection=True, export_apply=True)
print("DONE")
