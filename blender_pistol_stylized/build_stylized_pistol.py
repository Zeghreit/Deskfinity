import bpy, bmesh, math, sys
from mathutils import Vector
OUT = "/home/user/Deskfinity/blender_pistol_stylized"
MODE = sys.argv[-1]          # "test" or "final"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
S = 400.0
def P(x, y): return ((x-700)/S, (420-y)/S)   # concept px -> (X, Z)

def srgb(h):
    c = [int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in c)
def mat(name, hexc, metal=0.25, rough=0.45, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]; c = srgb(hexc)
    b.inputs["Base Color"].default_value = (*c,1)
    b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*c,1); b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (*c,1)
    return m
M = dict(navy=mat("Navy","2e3352"), dark=mat("DarkNavy","1d2036",0.3,0.5),
         mid=mat("BlueGrey","7a809c"), light=mat("LightGrey","b4b9cc",0.2,0.4),
         white=mat("White","e9ebf3",0.0,0.35), orange=mat("Orange","e2782a",0.1,0.4),
         black=mat("Slot","0c0d16",0.0,0.7))
parts = []
def finish(o, m, bevel=0.006, seg=2):
    o.data.materials.append(M[m])
    if bevel:
        bv = o.modifiers.new("Bevel","BEVEL"); bv.width = bevel; bv.segments = seg
        bv.limit_method = 'ANGLE'; bv.angle_limit = math.radians(30); bv.harden_normals = True
    for p in o.data.polygons: p.use_smooth = True
    parts.append(o); return o
def prism(name, pts, hw, m, bevel=0.006, yoff=0.0):
    """Extrude side-view polygon (concept px) to half-width hw (px), centred on Y=yoff."""
    me = bpy.data.meshes.new(name); bm = bmesh.new(); h = hw/S
    xz = [P(*p) for p in pts]
    f = [bm.verts.new((x, yoff-h, z)) for x,z in xz]
    b = [bm.verts.new((x, yoff+h, z)) for x,z in xz]
    bm.faces.new(f); bm.faces.new(b[::-1]); n = len(xz)
    for i in range(n):
        j = (i+1)%n; bm.faces.new((f[i], f[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    return finish(o, m, bevel)
def mirror_pair(name, pts, hw_in, hw_out, m, bevel=0.003):
    """Thin decal-like plate on both sides between |y|=hw_in..hw_out."""
    mid = (hw_in+hw_out)/2/S; th = (hw_out-hw_in)/2
    return [prism(f"{name}_{s}", pts, th, m, bevel, s*mid) for s in ("L","R") for _ in [0]] if False else \
           [prism(f"{name}_L", pts, th, m, bevel, -mid), prism(f"{name}_R", pts, th, m, bevel, mid)]
def cylY(name, cx, cy, r, hw, m, verts=48, bevel=0.004):
    x,z = P(cx,cy)
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r/S, depth=2*hw/S, location=(x,0,z), rotation=(math.pi/2,0,0))
    o = bpy.context.object; o.name = name; return finish(o, m, bevel)
def cylX(name, x0, x1, cy, r, m, verts=24):
    a,z = P(x0,cy); b,_ = P(x1,cy)
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r/S, depth=b-a, location=((a+b)/2,0,z), rotation=(0,math.pi/2,0))
    o = bpy.context.object; o.name = name; return finish(o, m, 0.003)
def bolt(name, cx, cy, r, hw, m="mid"):
    cylY(name+"_head", cx, cy, r, hw, m, 24, 0.003)
def cut(target, cutter):
    bm = target.modifiers.new("Cut","BOOLEAN"); bm.object = cutter; bm.solver = 'EXACT'
    cutter.hide_render = True; cutter.hide_viewport = True; parts.remove(cutter)
    target.modifiers.move(len(target.modifiers)-1, 0)
def curve(name, pts, radius, m, flat=1.0):
    cu = bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.bevel_depth = radius/S
    cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts)-1)
    for bp,(px,py) in zip(sp.bezier_points, pts):
        x,z = P(px,py); bp.co = (x,0,z); bp.handle_left_type = bp.handle_right_type = 'AUTO'
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); o.scale.y = flat
    o.data.materials.append(M[m]); parts.append(o); return o

# ================= UPPER: top bar, core, body =================
prism("TopBar", [(715,68),(1395,68),(1405,78),(1405,124),(1393,137),(715,137)], 58, "light", 0.01)
prism("FrontSight", [(1333,70),(1350,50),(1386,50),(1386,70)], 18, "navy")
prism("Core", [(590,128),(1335,128),(1335,168),(590,168)], 48, "navy")
for i in range(5):   # dark vent slits under the top bar
    x = 1040+i*58; mirror_pair(f"CoreSlit{i}", [(x,143),(x+42,143),(x+42,156),(x,156)], 47, 50, "black", 0.001)
mirror_pair("TopBarHighlight", [(722,128),(1390,128),(1384,135),(722,135)], 57, 60, "white", 0.001)
prism("UpperBody", [(645,163),(1398,163),(1405,172),(1405,288),(1396,297),(1240,297),(1240,255),(645,255)], 68, "light", 0.01)
prism("OrangeStripe", [(660,158),(1398,158),(1404,166),(1404,170),(660,170)], 70, "orange", 0.003)
# dark barrel housing panel (wider -> sits over light body)
prism("BarrelHousing", [(700,240),(872,240),(903,196),(1236,196),(1268,293),(1345,293),(1345,350),(1330,368),(960,372),(700,372)], 74, "navy", 0.008)
# ITA slots: light frames + black grilles on both sides
slots = [[(925,290),(958,230),(1003,230),(970,290)],
         [(982,290),(1012,232),(1032,232),(1002,290)],
         [(1043,290),(1072,232),(1108,232),(1079,290)],
         [(1093,290),(1135,226),(1186,226),(1226,290)]]
for i,s in enumerate(slots):
    mirror_pair(f"SlotFrame{i}", s, 73, 77, "light", 0.002)
    cx = sum(p[0] for p in s)/4; cy = sum(p[1] for p in s)/4
    inner = [(cx+(x-cx)*0.84, cy+(y-cy)*0.8) for x,y in s]
    mirror_pair(f"SlotGrille{i}", inner, 74, 78, "black", 0.001)
# trapezoid notch on light body front
mirror_pair("FrontNotch", [(1290,272),(1306,240),(1392,240),(1402,272)], 67, 70, "navy", 0.002)
mirror_pair("FrontNotchIn", [(1300,272),(1312,247),(1386,247),(1394,272)], 68, 71, "light", 0.002)
# small details on housing
for i,(x0,x1) in enumerate([(985,1030),(1040,1060),(1070,1115)]):
    mirror_pair(f"Dash{i}", [(x0,349),(x1,349),(x1,357),(x0,357)], 73, 76.5, "mid", 0.001)
mirror_pair("WhiteLight", [(1240,370),(1288,370),(1288,379),(1240,379)], 50, 58, "white", 0.001)
prism("OrangeTab", [(1328,296),(1350,296),(1352,318),(1340,326),(1328,320)], 20, "orange")
cylY("OrangeDot", 805, 270, 13, 78, "orange", 24)
# bottom rail
prism("BottomRail", [(950,368),(1322,368),(1322,388),(1302,410),(950,410)], 52, "dark", 0.006)

# ================= REAR TOP: receiver block, angled plate, sight =================
prism("ReceiverBlock", [(365,135),(600,135),(600,155),(572,230),(365,230)], 60, "navy", 0.008)
prism("ReceiverPlate", [(415,112),(570,115),(558,140),(548,160),(415,160)], 63, "mid", 0.006)
mirror_pair("ReceiverOrange", [(588,146),(600,146),(574,230),(562,230)], 59, 63, "orange", 0.001)
bolt("ReceiverBolt", 590, 212, 9, 63, "dark")
prism("AngledPlateOrange", [(546,55),(741,55),(750,67),(750,120),(660,162)], 62, "orange", 0.006)
prism("AngledPlate", [(560,57),(737,57),(744,69),(744,115),(662,153)], 66, "light", 0.006)
bolt("PlateBolt", 718, 95, 11, 68, "navy")
prism("RearSight", [(266,166),(284,154),(330,154),(332,214),(266,214)], 28, "mid")
mirror_pair("RearSightOrange", [(282,158),(298,158),(298,182),(282,182)], 27, 30, "orange", 0.001)
cylX("SightStem", 330, 368, 185, 10, "dark")
curve("OrangeHook", [(338,212),(305,232),(318,268),(362,272)], 7, "orange")
mirror_pair("OrangeLine", [(525,272),(535,262),(700,262),(700,272)], 66, 69, "orange", 0.001)

# ================= FRAME, COVER, TRIGGER, DIAL =================
frame = prism("Frame", [(292,345),(320,236),(960,236),(960,375),(830,440),(800,460),(650,500),(625,527),(410,527),(330,520),(300,470)], 62, "navy", 0.008)
hole = prism("TriggerHoleCut", [(440,385),(588,385),(600,398),(600,494),(586,506),(447,506),(434,492)], 120, "navy", 0)
cut(frame, hole)
cover = prism("GreyCover", [(398,330),(438,298),(480,285),(955,285),(955,398),(940,430),(830,430),(812,398),(790,356),(720,346),(522,346),(498,334),(468,346),(442,372),(434,468),(400,472)], 77, "mid", 0.008)
for i in range(2):
    y = 401+i*13; mirror_pair(f"CoverStripe{i}", [(838,y),(946,y),(941,y+7),(843,y+7)], 76, 79, "white", 0.0)
prism("SlotPlate", [(325,300),(345,258),(470,258),(482,270),(482,300)], 66, "light", 0.006)
mirror_pair("SlotPlateSlot", [(348,278),(460,278),(460,292),(348,292)], 65, 68, "dark", 0.001)
prism("Trigger", [(466,393),(496,398),(482,428),(480,458),(497,490),(470,482),(459,446)], 14, "light", 0.004)
prism("Hammer", [(244,350),(302,384),(304,402),(278,398)], 16, "light", 0.004)
for n,(x,y) in enumerate([(318,405),(318,475)]):
    bolt(f"FrameBolt{n}", x, y, 15, 66, "mid"); bolt(f"FrameBoltIn{n}", x, y, 7, 68, "dark")
# orange L-trace
mirror_pair("OrangeTraceA", [(600,376),(812,376),(812,386),(600,386)], 76, 79, "orange", 0.0)
mirror_pair("OrangeTraceB", [(600,376),(611,376),(611,410),(600,410)], 76, 79, "orange", 0.0)
# dial assembly
prism("DialMount", [(650,398),(830,382),(858,440),(832,510),(705,556),(650,550)], 64, "navy", 0.008)
gear = cylY("DialGear", 722, 465, 82, 72, "dark", 48)
for k in range(14):
    a = math.radians(150 + k*10); x,z = P(722,465)
    bpy.ops.mesh.primitive_cube_add(location=(x+math.cos(a)*84/S, 0, z+math.sin(a)*88/S), rotation=(0,-a,0))
    t = bpy.context.object; t.name = f"GearTooth{k}"; t.scale = (7/S, 71/S, 5/S); bpy.ops.object.transform_apply(scale=True)
    finish(t, "dark", 0)
cylY("DialRingOrange", 722, 465, 78, 80, "orange", 64)
cylY("DialDisk", 722, 465, 70, 83, "light", 64)
cylY("DialCenter", 722, 465, 33, 86, "orange", 48)
mirror_pair("DialChevron", [(818,465),(828,452),(838,465),(832,465),(828,459),(824,465)], 64, 67, "orange", 0.0)

from mathutils import Matrix
for side in (-1, 1):
    bpy.ops.object.text_add()
    t = bpy.context.object; t.name = f"DialText{side}"; t.data.body = "1045-R"
    t.data.size = 21/S; t.data.extrude = 0.0015; t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'
    x,z = P(774,465); t.location = (x, side*(83/S+0.002), z)
    rx = Matrix.Rotation(-side*math.pi/2, 4, 'X'); ry = Matrix.Rotation(-side*math.pi/2, 4, 'Y')
    t.rotation_euler = (ry @ rx).to_euler()
    t.data.materials.append(M["dark"]); parts.append(t)
    if 'NoLines' not in bpy.data.collections:
        sc.collection.children.link(bpy.data.collections.new('NoLines'))
    sc.collection.objects.unlink(t); bpy.data.collections['NoLines'].objects.link(t)

# ================= GRIP =================
prism("GripBack", [(240,393),(300,418),(332,450),(332,500),(272,524),(226,576),(208,640),(208,712),(242,770),(170,800),(118,800),(60,712),(98,552),(138,488)], 66, "navy", 0.01)
mirror_pair("GripPanel", [(252,438),(298,458),(292,516),(242,560),(216,622),(212,700),(228,752),(176,776),(152,722),(152,566),(190,486)], 64, 70, "mid", 0.006)
bolt("GripPanelScrew", 243, 428, 5, 71, "dark"); bolt("GripPanelScrew2", 188, 520, 5, 71, "dark")
prism("GripBottomBar", [(200,752),(422,752),(422,784),(200,784)], 32, "dark", 0.005)
def ngon(cx, cy, r, n, rot=0): return [(cx+r*math.cos(rot+2*math.pi*i/n), cy+r*math.sin(rot+2*math.pi*i/n)) for i in range(n)]
prism("BottomPlateA", ngon(206,766,24,8,math.pi/8), 40, "navy", 0.005)
bolt("BottomBoltA", 206, 766, 9, 42, "mid")
prism("BottomPlateB", ngon(352,752,36,6), 44, "navy", 0.006)
bolt("BottomBoltB", 352, 752, 12, 46, "mid")
strap = curve("FrontStrap", [(452,512),(468,560),(438,620),(398,690),(378,740),(352,756)], 21, "navy", 1.4)
for k,(x,y,ang) in enumerate([(433,598,-60),(424,618,-60),(414,639,-60)]):
    a,z = P(x,y)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=24/S, depth=22/S, location=(a,0,z), rotation=(0,math.radians(ang+90),0))
    o = bpy.context.object; o.name = f"OrangeWrap{k}"; o.scale.y = 1.3; finish(o, "orange", 0.006)

# ================= assemble =================
root = bpy.data.objects.new("StylizedPistol", None); sc.collection.objects.link(root)
for p in parts: p.parent = root

# ---- look & render ----
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (*srgb("dfe3ee"),1); bg.inputs[1].default_value = 0.35
def light(name, loc, energy, size):
    d = bpy.data.lights.new(name,'AREA'); d.energy = energy; d.size = size
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0.2,0,0)) - Vector(loc)).to_track_quat('-Z','Y').to_euler()
light("Key", (1.5,-4,4), 380, 4); light("Fill", (-3,-3,0.5), 110, 4); light("Rim", (-1,4,3), 300, 3)
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.use_denoising = True
sc.cycles.samples = 24 if MODE == "test" else 96
sc.view_settings.view_transform = 'Standard'
sc.render.use_freestyle = True; sc.render.line_thickness_mode = 'ABSOLUTE'; sc.render.line_thickness = 1.6
ls = sc.view_layers[0].freestyle_settings.linesets[0]
ls.select_by_visibility = True; ls.select_by_collection = True; ls.collection = bpy.data.collections['NoLines']; ls.collection_negation = 'EXCLUSIVE'; ls.select_silhouette = ls.select_border = ls.select_crease = True
if ls.linestyle is None: ls.linestyle = bpy.data.linestyles.new('Line')
ls.linestyle.color = srgb("151726"); sc.view_layers[0].freestyle_settings.crease_angle = math.radians(140)
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Camera", cam_d); sc.collection.objects.link(cam); sc.camera = cam
CX, CZ = (720-700)/S, (420-425)/S   # concept centre
def shot(path, loc, ortho=None, lens=50, res=(1440,840), tgt=None):
    cam_d.type = 'ORTHO' if ortho else 'PERSP'
    if ortho: cam_d.ortho_scale = ortho
    cam_d.lens = lens; cam.location = loc
    cam.rotation_euler = (Vector(tgt or (CX,0,CZ))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
import os; os.makedirs(OUT, exist_ok=True)
if MODE!="probe": shot(OUT+"/side_ortho.png", (CX,-10,CZ), ortho=1440/S)
if MODE != "test":
    shot(OUT+"/render_34.png", (3.0,-4.6,1.5), lens=48, res=(1600,1000), tgt=(0.22,0,-0.1))
    shot(OUT+"/render_34_back.png", (-2.6,4.8,1.3), lens=48, res=(1600,1000), tgt=(-0.12,0,-0.1))
    shot(OUT+"/render_top.png", (CX,-0.001,8), ortho=1440/S)
    bpy.ops.wm.save_as_mainfile(filepath=OUT+"/stylized_pistol.blend")
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts: p.select_set(True)
    bpy.ops.export_scene.gltf(filepath=OUT+"/stylized_pistol.glb", use_selection=True, export_apply=True)
print("DONE")
