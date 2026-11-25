import bpy, math, random, os
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
from mathutils import Vector

MONO = os.path.join(FONTS, 'DejaVuSansMono-Bold.ttf')
SANS = os.path.join(FONTS, 'Inter-Bold.otf')
HAND = os.path.join(FONTS, 'ComicRelief-Regular.ttf')

def hexc(h, a=1.0):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (a,)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'  # switch to 'GPU' + set compute_device_type (METAL/OPTIX/CUDA) in prefs
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 8; s.cycles.transmission_bounces = 8; s.cycles.transparent_max_bounces = 16
    s.view_settings.view_transform = 'AgX'
    try: s.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    w = bpy.data.worlds.new('W'); s.world = w; w.use_nodes = True
    return s

def world(color=(0.05, 0.05, 0.05), strength=1.0, stars=False):
    w = bpy.context.scene.world; nt = w.node_tree; bg = nt.nodes['Background']
    bg.inputs[0].default_value = color + (1,) if len(color) == 3 else color
    bg.inputs[1].default_value = strength
    if stars:
        n = nt.nodes; v = n.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = 260
        r = n.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position = 0.0; r.color_ramp.elements[0].color = (1, 1, 1, 1)
        r.color_ramp.elements[1].position = 0.035; r.color_ramp.elements[1].color = (0, 0, 0, 1)
        tc = n.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Generated'], v.inputs['Vector'])
        nt.links.new(v.outputs['Distance'], r.inputs[0]); nt.links.new(r.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.5

# ---------- materials ----------
def mat(name, color=(0.8, 0.8, 0.8, 1), rough=0.5, metal=0.0, emit=None, es=0.0, trans=0.0, coat=0.0, ior=1.45, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    if isinstance(color, str): color = hexc(color)
    p.inputs['Base Color'].default_value = color
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['IOR'].default_value = ior
    p.inputs['Transmission Weight'].default_value = trans
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Alpha'].default_value = alpha
    if emit is not None:
        if isinstance(emit, str): emit = hexc(emit)
        p.inputs['Emission Color'].default_value = emit
        p.inputs['Emission Strength'].default_value = es
    return m

def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.remove(nt.nodes['Principled BSDF'])
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = hexc(color) if isinstance(color, str) else color
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes['Material Output'].inputs[0]); return m

def proc_mat(name, kind, c1, c2, rough=0.5, metal=0.0, scale=10.0, coat=0.0):
    """wood / brick(tiles) / noise / brushed / checker"""
    m = mat(name, rough=rough, metal=metal, coat=coat)
    nt = m.node_tree; n = nt.nodes; p = n['Principled BSDF']
    tc = n.new('ShaderNodeTexCoord'); mp = n.new('ShaderNodeMapping'); nt.links.new(tc.outputs['Object'], mp.inputs[0])
    c1 = hexc(c1) if isinstance(c1, str) else c1; c2 = hexc(c2) if isinstance(c2, str) else c2
    if kind == 'wood':
        mp.inputs['Scale'].default_value = (scale, scale * 0.15, scale * 0.15)
        t = n.new('ShaderNodeTexWave'); t.inputs['Scale'].default_value = 1.5; t.inputs['Distortion'].default_value = 6
        t.inputs['Detail'].default_value = 3
        nt.links.new(mp.outputs[0], t.inputs['Vector'])
        r = n.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].color = c1; r.color_ramp.elements[1].color = c2
        nt.links.new(t.outputs['Fac'], r.inputs[0]); nt.links.new(r.outputs[0], p.inputs['Base Color'])
    elif kind == 'tiles':
        mp.inputs['Scale'].default_value = (scale, scale, scale)
        t = n.new('ShaderNodeTexBrick'); t.inputs['Color1'].default_value = c1; t.inputs['Color2'].default_value = c1
        t.inputs['Mortar'].default_value = c2; t.inputs['Mortar Size'].default_value = 0.025
        t.inputs['Brick Width'].default_value = 1.0; t.inputs['Row Height'].default_value = 1.0; t.offset = 0.0
        nt.links.new(mp.outputs[0], t.inputs['Vector']); nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        rr = n.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.08; rr.inputs['To Max'].default_value = 0.7
        nt.links.new(t.outputs['Fac'], rr.inputs[0]); nt.links.new(rr.outputs[0], p.inputs['Roughness'])
        b = n.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.3; b.invert = True
        nt.links.new(t.outputs['Fac'], b.inputs['Height']); nt.links.new(b.outputs[0], p.inputs['Normal'])
    elif kind in ('noise', 'brushed'):
        mp.inputs['Scale'].default_value = (scale, scale * (40 if kind == 'brushed' else 1), scale)
        t = n.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value = 4; t.inputs['Detail'].default_value = 8
        nt.links.new(mp.outputs[0], t.inputs['Vector'])
        r = n.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].color = c1; r.color_ramp.elements[1].color = c2
        nt.links.new(t.outputs['Fac'], r.inputs[0]); nt.links.new(r.outputs[0], p.inputs['Base Color'])
        if kind == 'brushed':
            rr = n.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = rough * 0.6; rr.inputs['To Max'].default_value = rough * 1.4
            nt.links.new(t.outputs['Fac'], rr.inputs[0]); nt.links.new(rr.outputs[0], p.inputs['Roughness'])
    elif kind == 'checker':
        mp.inputs['Scale'].default_value = (scale, scale, scale)
        t = n.new('ShaderNodeTexChecker'); t.inputs['Color1'].default_value = c1; t.inputs['Color2'].default_value = c2
        t.inputs['Scale'].default_value = 1
        nt.links.new(mp.outputs[0], t.inputs['Vector']); nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    return m

def screen_mat(name, metal_color='#151515', holes=60):
    """perforated microwave door mesh: holes transparent with slight reflection"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; n = nt.nodes
    p = n['Principled BSDF']; p.inputs['Base Color'].default_value = hexc(metal_color)
    p.inputs['Metallic'].default_value = 0.6; p.inputs['Roughness'].default_value = 0.45
    tr = n.new('ShaderNodeBsdfTransparent'); tr.inputs[0].default_value = (0.92, 0.92, 0.88, 1)
    gl = n.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.04
    mixg = n.new('ShaderNodeMixShader'); mixg.inputs[0].default_value = 0.12
    nt.links.new(tr.outputs[0], mixg.inputs[1]); nt.links.new(gl.outputs[0], mixg.inputs[2])
    tc = n.new('ShaderNodeTexCoord'); mp = n.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (holes, holes * 0.7, 1)
    nt.links.new(tc.outputs['UV'], mp.inputs[0])
    sep = n.new('ShaderNodeSeparateXYZ'); nt.links.new(mp.outputs[0], sep.inputs[0])
    fx = n.new('ShaderNodeMath'); fx.operation = 'FRACT'; fy = n.new('ShaderNodeMath'); fy.operation = 'FRACT'
    nt.links.new(sep.outputs[0], fx.inputs[0]); nt.links.new(sep.outputs[1], fy.inputs[0])
    cb = n.new('ShaderNodeCombineXYZ'); nt.links.new(fx.outputs[0], cb.inputs[0]); nt.links.new(fy.outputs[0], cb.inputs[1])
    sub = n.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (0.5, 0.5, 0)
    nt.links.new(cb.outputs[0], sub.inputs[0])
    ln = n.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(sub.outputs[0], ln.inputs[0])
    lt = n.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = 0.36
    nt.links.new(ln.outputs['Value'], lt.inputs[0])
    mix = n.new('ShaderNodeMixShader'); nt.links.new(lt.outputs[0], mix.inputs[0])
    nt.links.new(p.outputs[0], mix.inputs[1]); nt.links.new(mixg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], n['Material Output'].inputs[0]); return m

# ---------- geometry helpers ----------
def setmat(o, m):
    o.data.materials.clear(); o.data.materials.append(m); return o

def box(name, loc, size, m=None, bevel=0.0, seg=3, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = seg; b.limit_method = 'NONE'
    if m: setmat(o, m)
    if parent: o.parent = parent
    return o

def cyl(name, loc, r, h, m=None, rot=(0, 0, 0), verts=48, bevel=0.0, parent=None, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot, vertices=verts)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=h, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object; o.name = name
    if bevel > 0:
        b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 3; b.limit_method = 'ANGLE'
    bpy.ops.object.shade_smooth()
    if m: setmat(o, m)
    if parent: o.parent = parent
    return o

def sph(name, loc, r, m=None, scale=(1, 1, 1), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
    o = bpy.context.object; o.name = name; o.scale = scale; bpy.ops.object.shade_smooth()
    if m: setmat(o, m)
    if parent: o.parent = parent
    return o

def rbox(name, loc, size, m=None, level=2, parent=None):
    """soft rounded box via subdivision"""
    o = box(name, loc, size, m)
    b = o.modifiers.new('bev', 'BEVEL'); b.width = min(size) * 0.25; b.segments = 2; b.limit_method = 'NONE'
    s = o.modifiers.new('sub', 'SUBSURF'); s.levels = level; s.render_levels = level
    bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o

def boolean(o, cutter, op='DIFFERENCE'):
    md = o.modifiers.new('bool', 'BOOLEAN'); md.operation = op; md.object = cutter; md.solver = 'EXACT'
    cutter.hide_render = True; cutter.hide_viewport = True
    # move boolean before bevel? keep order: bool after bevel is fine visually
    return md

def text(name, s, loc, size, m, font=MONO, rot=(math.pi / 2, 0, 0), extrude=0.0, align='CENTER', parent=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = s; cu.size = size; cu.align_x = align; cu.align_y = 'CENTER'
    cu.extrude = extrude; cu.font = bpy.data.fonts.load(font, check_existing=True)
    o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot; cu.materials.append(m)
    if parent: o.parent = parent
    return o

def curve(name, pts, bevel, m, cyclic=False, parent=None, order=4):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = bevel; cu.bevel_resolution = 6
    sp = cu.splines.new('NURBS'); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (p[0], p[1], p[2], 1)
    sp.use_cyclic_u = cyclic; sp.use_endpoint_u = not cyclic; sp.order_u = order; sp.resolution_u = 16
    o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o); cu.materials.append(m)
    if parent: o.parent = parent
    return o

def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot
    if parent: o.parent = parent
    return o

def light(kind, loc, energy, color=(1, 1, 1), size=0.5, rot=None, target=None, size_y=None, spot=None):
    ld = bpy.data.lights.new('L', kind); ld.energy = energy
    ld.color = color[:3] if not isinstance(color, str) else hexc(color)[:3]
    if kind == 'AREA':
        ld.size = size
        if size_y: ld.shape = 'RECTANGLE'; ld.size_y = size_y
    elif kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
        if spot: ld.spot_size = spot
    o = bpy.data.objects.new('L', ld); bpy.context.collection.objects.link(o); o.location = loc
    o.visible_camera = False
    if rot: o.rotation_euler = rot
    if target is not None:
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return o

def camera(loc, target, lens=50, fstop=None, focus=None, kind='PERSP', ortho=1.0, fisheye=False):
    cd = bpy.data.cameras.new('C'); cd.lens = lens; cd.type = kind; cd.ortho_scale = ortho
    cd.clip_start = 0.005
    if fisheye:
        cd.type = 'PANO'; cd.panorama_type = 'FISHEYE_EQUISOLID'; cd.fisheye_lens = lens; cd.fisheye_fov = math.radians(170)
    o = bpy.data.objects.new('C', cd); bpy.context.collection.objects.link(o); o.location = loc
    t = target if not isinstance(target, tuple) else empty('camT', target)
    c = o.constraints.new('TRACK_TO'); c.target = t; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    if fstop:
        cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop
        cd.dof.focus_object = focus if focus is not None else t
    bpy.context.scene.camera = o; return o

# ---------- characters / objects on the plate ----------
INK = None
def objects_mats():
    global M
    M = dict(
        lime=mat('lime', '#C6F24E', rough=0.35, coat=0.6),
        ink=mat('ink', '#141414', rough=0.25, coat=0.5),
        white=mat('whiteg', '#FFFFFF', rough=0.15),
        prong=mat('prong', '#D9D9D9', rough=0.18, metal=1.0),
        rob_dark=mat('robdark', '#2A2B2E', rough=0.35, metal=0.4),
        rob_light=mat('roblight', '#B9BCC2', rough=0.3, metal=0.85),
        visor=mat('visor', '#050505', rough=0.05, coat=1.0),
        rob_led=emission('robled', '#5FD4FF', 6),
        dough=proc_mat('dough', 'noise', '#7A3A10', '#B5651D', rough=0.35, scale=30, coat=0.8),
        salt=mat('salt', '#F4F1EA', rough=0.6),
        ceramic=mat('ceramic', '#F7F5F0', rough=0.12, coat=0.6),
        coffee=mat('coffee', '#2B1608', rough=0.1),
        crema=mat('crema', '#A9672F', rough=0.4),
    )
    return M

def plug_mascot(loc, s=1.0, rotz=0, parent=None):
    root = empty('plug', loc, (0, 0, rotz), parent)
    h = 0.062 * s
    b = rbox('plugBody', (0, 0, h * 0.5), (0.05 * s, 0.042 * s, h), M['lime'], parent=root)
    for dx in (-0.011, 0.011):
        box('prong', (dx * s, 0, h + 0.012 * s), (0.006 * s, 0.003 * s, 0.026 * s), M['prong'], bevel=0.0008, parent=root)
        sph('eye', (dx * 0.95 * s, -0.0205 * s, h * 0.6), 0.0052 * s, M['ink'], scale=(1, 0.55, 1.15), parent=root)
        sph('hl', (dx * 0.95 * s + 0.0016 * s, -0.0232 * s, h * 0.6 + 0.0022 * s), 0.0014 * s, M['white'], parent=root)
    curve('smile', [(-0.007 * s, -0.0212 * s, h * 0.40), (0, -0.0225 * s, h * 0.33), (0.007 * s, -0.0212 * s, h * 0.40)], 0.0011 * s, M['ink'], parent=root, order=3)
    curve('cable', [(0, 0.02 * s, 0.01 * s), (0, 0.04 * s, 0.004 * s), (0.02 * s, 0.05 * s, 0.003 * s), (0.035 * s, 0.03 * s, 0.003 * s), (0.03 * s, 0.01 * s, 0.003 * s)], 0.003 * s, M['ink'], parent=root)
    return root

def robot(loc, s=1.0, rotz=0, parent=None, wave=False):
    """small humanoid in the spirit of a compact research humanoid (dark/silver)"""
    r = empty('robot', loc, (0, 0, rotz), parent); k = 0.105 * s
    D, L, V = M['rob_dark'], M['rob_light'], M['visor']
    # feet
    for sx in (-1, 1):
        x = sx * 0.12 * k
        rbox('foot', (x, -0.03 * k, 0.025 * k), (0.11 * k, 0.24 * k, 0.05 * k), D, parent=r)
        cyl('shin', (x, 0, 0.2 * k), 0.045 * k, 0.28 * k, L, parent=r)
        sph('knee', (x, 0, 0.36 * k), 0.055 * k, D, parent=r)
        cyl('thigh', (x, 0, 0.5 * k), 0.06 * k, 0.26 * k, D, parent=r)
    rbox('pelvis', (0, 0, 0.64 * k), (0.34 * k, 0.18 * k, 0.1 * k), L, parent=r)
    rbox('torso', (0, 0, 0.8 * k), (0.36 * k, 0.2 * k, 0.26 * k), D, parent=r)
    rbox('chest', (0, -0.09 * k, 0.83 * k), (0.24 * k, 0.04 * k, 0.14 * k), L, parent=r)
    box('led', (0, -0.112 * k, 0.86 * k), (0.12 * k, 0.004 * k, 0.012 * k), M['rob_led'], parent=r)
    cyl('neck', (0, 0, 0.96 * k), 0.035 * k, 0.06 * k, L, parent=r)
    sph('head', (0, 0, 1.06 * k), 0.1 * k, D, scale=(0.95, 0.9, 1.0), parent=r)
    sph('face', (0, -0.035 * k, 1.06 * k), 0.08 * k, V, scale=(1.0, 0.75, 0.85), parent=r)
    cyl('lidar', (0, 0, 1.16 * k), 0.035 * k, 0.03 * k, L, parent=r)
    for sx in (-1, 1):
        x = sx * 0.23 * k
        sph('shoulder', (x, 0, 0.88 * k), 0.055 * k, L, parent=r)
        if wave and sx == 1:
            cyl('uarm', (x + 0.06 * k, 0, 0.98 * k), 0.035 * k, 0.2 * k, D, rot=(0, -0.6, 0), parent=r)
            cyl('farm', (x + 0.1 * k, -0.02 * k, 1.16 * k), 0.032 * k, 0.2 * k, L, rot=(0, -0.15, 0), parent=r)
            sph('hand', (x + 0.115 * k, -0.02 * k, 1.28 * k), 0.04 * k, D, parent=r)
        else:
            cyl('uarm', (x + sx * 0.01 * k, 0, 0.76 * k), 0.035 * k, 0.2 * k, D, parent=r)
            cyl('farm', (x + sx * 0.015 * k, -0.03 * k, 0.58 * k), 0.032 * k, 0.2 * k, L, rot=(0.25, 0, 0), parent=r)
            sph('hand', (x + sx * 0.015 * k, -0.055 * k, 0.47 * k), 0.04 * k, D, parent=r)
    return r

def pretzel(loc, s=1.0, rotz=0, parent=None):
    r = empty('pretzel', loc, (0, 0, rotz), parent)
    inner = empty('pz', (0, 0, 0.034 * s), (math.radians(78), 0, 0), r)
    k = 0.03 * s
    loop = [(0, 0.5), (-0.45, 1.0), (-1.1, 0.85), (-1.3, 0.1), (-0.9, -0.75), (0, -1.0), (0.9, -0.75), (1.3, 0.1), (1.1, 0.85), (0.45, 1.0)]
    curve('loop', [(x * k, y * k, 0) for x, y in loop], 0.0072 * s, M['dough'], cyclic=True, parent=inner)
    curve('armL', [(0.15 * k, 0.55 * k, 0.0), (0.05 * k, 0.3 * k, 0.009 * s), (-0.35 * k, -0.2 * k, 0.004 * s), (-0.8 * k, -0.68 * k, 0)], 0.0066 * s, M['dough'], parent=inner)
    curve('armR', [(-0.15 * k, 0.55 * k, 0.0), (-0.05 * k, 0.3 * k, -0.004 * s), (0.35 * k, -0.2 * k, 0.004 * s), (0.8 * k, -0.68 * k, 0)], 0.0066 * s, M['dough'], parent=inner)
    rnd = random.Random(3)
    for i in range(22):
        a = rnd.random() * math.tau; rr = rnd.uniform(0.6, 1.15) * k
        o = box('salt', (math.cos(a) * rr, math.sin(a) * rr * 0.95, 0.0075 * s), (0.0018 * s,) * 3, M['salt'], parent=inner)
        o.rotation_euler = (rnd.random(), rnd.random(), rnd.random())
    return r

def espresso(loc, s=1.0, rotz=0, parent=None):
    r = empty('espresso', loc, (0, 0, rotz), parent)
    cyl('saucer', (0, 0, 0.003 * s), 0.03 * s, 0.006 * s, M['ceramic'], bevel=0.002 * s, parent=r)
    cup = cyl('cup', (0, 0, 0.021 * s), 0.014 * s, 0.03 * s, M['ceramic'], r2=0.019 * s, parent=r)
    inn = cyl('cupin', (0, 0, 0.026 * s), 0.012 * s, 0.03 * s, None, r2=0.0168 * s, parent=r)
    boolean(cup, inn)
    cyl('coffee', (0, 0, 0.032 * s), 0.0163 * s, 0.002 * s, M['crema'], parent=r)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.0075 * s, minor_radius=0.0022 * s, location=(0.021 * s, 0, 0.022 * s), rotation=(math.pi / 2, 0, 0))
    h = bpy.context.object; bpy.ops.object.shade_smooth(); setmat(h, M['ceramic']); h.parent = r
    return r

def sticker(parent, loc, rot, txt, w=0.03, h=0.02):
    b = box('sticker', loc, (w, 0.0006, h), mat('stk', '#FFFFFF', rough=0.5), parent=parent); b.rotation_euler = rot
    t = text('stktxt', txt, (loc[0], loc[1] - 0.0008, loc[2]), h * 0.26, mat('stkred', '#D62828', rough=0.5), font=SANS, parent=parent)
    t.rotation_euler = (rot[0] + math.pi / 2, rot[1], rot[2]); return b

def plug_lid(loc, s=1.0, rotz=0, parent=None):
    r = empty('plugLid', loc, (0, 0, rotz), parent)
    plug_mascot((0, 0, 0), s * 0.9, 0, r)
    d = sph('dome', (0, 0, 0), 0.05 * s, mat('lidp', (0.9, 0.95, 1.0, 1), rough=0.12, trans=1.0, ior=1.45), scale=(1, 1, 1.25), parent=r)
    cut = box('domecut', (0, 0, -0.05 * s), (0.2 * s, 0.2 * s, 0.1 * s), parent=r); boolean(d, cut)
    so = d.modifiers.new('sol', 'SOLIDIFY'); so.thickness = 0.0012 * s
    cyl('knobLid', (0, 0, 0.064 * s), 0.008 * s, 0.006 * s, mat('lidk', '#D9D9D9', rough=0.3), parent=r)
    sticker(r, (0, -0.042 * s, 0.032 * s), (-0.5, 0, 0), "DON'T\nOPEN YET", 0.04 * s, 0.024 * s)
    return r

def plug_foil(loc, s=1.0, rotz=0, parent=None):
    r = empty('plugFoil', loc, (0, 0, rotz), parent)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=0.034 * s, location=(0, 0, 0.032 * s))
    f = bpy.context.object; f.scale = (1, 0.9, 1.05); f.parent = r
    tx = bpy.data.textures.new('crumple', 'VORONOI'); tx.noise_scale = 0.006 * s
    dm = f.modifiers.new('disp', 'DISPLACE'); dm.texture = tx; dm.strength = 0.004 * s; dm.texture_coords = 'GLOBAL'
    tx2 = bpy.data.textures.new('crumple2', 'CLOUDS'); tx2.noise_scale = 0.012 * s
    dm2 = f.modifiers.new('disp2', 'DISPLACE'); dm2.texture = tx2; dm2.strength = 0.006 * s; dm2.texture_coords = 'GLOBAL'
    setmat(f, mat('foil', '#D8DADC', rough=0.22, metal=1.0))
    box('prong', (-0.006 * s, 0, 0.072 * s), (0.005 * s, 0.003 * s, 0.014 * s), M['prong'], parent=r)
    sticker(r, (0, -0.032 * s, 0.035 * s), (0, 0, 0), "SOON", 0.03 * s, 0.016 * s)
    return r

PLATE_ITEMS = {'plug_lid': plug_lid, 'plug_foil': plug_foil, 'plug': plug_mascot, 'robot': robot, 'pretzel': pretzel, 'espresso': espresso}

# ---------- microwave ----------
STYLES = {
    'black':   dict(body='#18191B', rough=0.25, metal=0.2, coat=0.6, panel='#0C0C0C', frame='#141414', disp='#FF5A2B', bevel=0.012),
    'steel':   dict(body='brushed:#9EA2A6:#C9CCCF', rough=0.28, metal=1.0, panel='#151618', frame='#111111', disp='#6DD8FF', bevel=0.01),
    'wood':    dict(body='wood:#3D2210:#6E4220', rough=0.45, metal=0.0, coat=0.3, panel='#C9A86A', frame='#2A1A0E', disp='#FF7A1A', bevel=0.008, knobs=True, panel_metal=0.6),
    'beige':   dict(body='#D8CDB4', rough=0.55, metal=0.0, panel='#BFB49A', frame='#CFC4AB', disp='#59F07A', bevel=0.006),
    'mint':    dict(body='#A8DCC8', rough=0.3, metal=0.0, coat=0.8, panel='#F2EFE6', frame='#A8DCC8', disp='#2A2A2A', bevel=0.045, knobs=True, lcd=True),
    'commercial': dict(body='brushed:#8E9296:#B7BABD', rough=0.22, metal=1.0, panel='#1A1A1A', frame='#8E9296', disp='#FF2A2A', bevel=0.004),
    'toy':     dict(body='#FF4F6D', rough=0.35, metal=0.0, coat=0.4, panel='#FFD23F', frame='#3FA9FF', disp='#111111', bevel=0.03, knobs=True, lcd=True, toybtn=True),
    'lime':    dict(body='#C6F24E', rough=0.3, metal=0.0, coat=0.7, panel='#141414', frame='#141414', disp='#C6F24E', bevel=0.02),
}

def body_mat(st, name):
    b = st['body']
    if b.startswith('brushed:'):
        _, c1, c2 = b.split(':'); return proc_mat(name, 'brushed', c1, c2, rough=st['rough'], metal=st['metal'], scale=3)
    if b.startswith('wood:'):
        _, c1, c2 = b.split(':'); return proc_mat(name, 'wood', c1, c2, rough=st['rough'], scale=6, coat=st.get('coat', 0))
    return mat(name, b, rough=st['rough'], metal=st['metal'], coat=st.get('coat', 0))

def microwave(origin=(0, 0, 0), style='black', door=0.0, items=('plug', 'robot', 'pretzel', 'espresso'),
              plate_rot=0.0, disp='MATTEO', light_on=True, light_power=6.0, light_color=(1.0, 0.82, 0.55),
              cut=False, top_cut=False, scale=1.0, item_scale=1.0, single=None, dirty=False):
    st = STYLES[style]; root = empty('mw', origin); root.scale = (scale,) * 3
    bm = body_mat(st, 'body_' + style)
    W, H, D = 0.5, 0.3, 0.38
    body = box('body', (0, 0, H / 2), (W, D, H), bm, bevel=st['bevel'], seg=6, parent=root)
    cx0, cx1, cz0, cz1 = -0.23, 0.11, 0.03, 0.27
    cav = box('cav', (0.5 * (cx0 + cx1), -0.02, 0.5 * (cz0 + cz1)), (cx1 - cx0, 0.37 + 0.04, cz1 - cz0), parent=root)
    boolean(body, cav)
    inner = box('cavliner', (0.5 * (cx0 + cx1), -0.015, 0.5 * (cz0 + cz1)), (cx1 - cx0 - 0.002, 0.37, cz1 - cz0 - 0.002),
                (proc_mat('enameld', 'noise', '#E9E6DE', '#8A6A3A', rough=0.4, scale=7) if dirty else mat('enamel', '#E9E6DE', rough=0.35)), parent=root)
    if dirty:
        nt = inner.data.materials[0].node_tree; rmp = [n for n in nt.nodes if n.type == 'VALTORGB'][0].color_ramp
        rmp.elements[0].position = 0.63; rmp.elements[1].position = 0.7
    innc = box('cavlinercut', (0.5 * (cx0 + cx1), -0.03, 0.5 * (cz0 + cz1)), (cx1 - cx0 - 0.006, 0.37, cz1 - cz0 - 0.006), parent=root)
    boolean(inner, innc)
    inner.modifiers['bool'].solver = 'EXACT'
    # wave guide cover (mica)
    box('mica', (cx1 - 0.002, 0.02, 0.2), (0.002, 0.07, 0.05), mat('mica', '#BFA77A', rough=0.6), parent=root)
    # plate
    pc = (0.5 * (cx0 + cx1), -0.015, cz0 + 0.004)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.08, minor_radius=0.004, location=pc)
    ring = bpy.context.object; setmat(ring, mat('ringm', '#2a2a2a', rough=0.5)); ring.parent = root
    plate_root = empty('plateRoot', (pc[0], pc[1], pc[2] + 0.009), (0, 0, plate_rot), root)
    pl = cyl('plate', (0, 0, 0), 0.135, 0.006, mat('glass', (0.95, 0.98, 0.97, 1), rough=0.02, trans=1.0, ior=1.5), bevel=0.0025, verts=96, parent=plate_root)
    surf = 0.003
    if single:
        PLATE_ITEMS[single]((0, 0, surf), 1.6 * item_scale, 0, plate_root)
    else:
        n = len(items)
        for i, it in enumerate(items):
            a = i * math.tau / n
            fn = PLATE_ITEMS[it]
            sc = item_scale * (1.0 if it != 'robot' else 1.05)
            fn((math.cos(a) * 0.075, math.sin(a) * 0.075, surf), sc, -plate_rot, plate_root)
    # door
    hinge = empty('hinge', (-0.25, -0.19, 0), (0, 0, -math.radians(door)), root)
    fm = mat('frame', st['frame'], rough=0.3, metal=0.1 if style not in ('steel', 'commercial') else 1.0, coat=0.4) if not st['frame'].startswith('#8E') else bm
    if style in ('mint', 'toy', 'lime'): fm = bm if style != 'toy' else mat('frame', st['frame'], rough=0.35, coat=0.4)
    dW = 0.372; dx = 0.5 * dW + 0.002
    fr = box('door', (dx, -0.011, 0.15), (dW, 0.02, 0.286), fm, bevel=min(0.006, st['bevel']), seg=4, parent=hinge)
    win = box('win', (dx - 0.022, -0.011, 0.15), (0.27, 0.05, 0.19), parent=hinge)
    boolean(fr, win)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(dx - 0.022, -0.006, 0.15), rotation=(math.pi / 2, 0, 0))
    scr = bpy.context.object; scr.scale = (0.27, 0.19, 1); setmat(scr, screen_mat('screen', '#101010' if style != 'toy' else '#3FA9FF', 70)); scr.parent = hinge
    bpy.ops.mesh.primitive_plane_add(size=1, location=(dx - 0.022, -0.0175, 0.15), rotation=(math.pi / 2, 0, 0))
    gls = bpy.context.object; gls.scale = (0.272, 0.192, 1)
    gm = mat('doorglass', (1, 1, 1, 1), rough=0.0, trans=1.0, ior=1.5); setmat(gls, gm); gls.parent = hinge
    if style not in ('mint', 'toy'):
        box('handle', (dW - 0.02, -0.03, 0.15), (0.014, 0.02, 0.2), mat('handle', '#C9CCCF' if style in ('steel', 'commercial') else st['frame'], rough=0.25, metal=1 if style in ('steel', 'commercial') else 0.2), bevel=0.005, parent=hinge)
    else:
        box('handle', (dW - 0.015, -0.028, 0.15), (0.02, 0.018, 0.08), mat('handle', '#F2EFE6' if style == 'mint' else '#FFD23F', rough=0.3), bevel=0.008, parent=hinge)
    # panel
    if cut:
        st = dict(st, knobs=False); disp = ''
    pm = mat('panel', st['panel'], rough=0.2, metal=st.get('panel_metal', 0.0), coat=0.5)
    if not cut: box('panel', (0.185, -0.192, 0.15), (0.11, 0.006, 0.28), pm, bevel=0.003, parent=root)
    lcd = st.get('lcd', False)
    if not cut: dispbg = box('dispbg', (0.185, -0.196, 0.245), (0.09, 0.003, 0.03), mat('dispbg', '#9DB08A' if lcd else '#050505', rough=0.08, coat=1.0), bevel=0.002, parent=root)
    if disp:
        tm = mat('lcdtxt', st['disp'], rough=0.5) if lcd else emission('vfd', st['disp'], 9 if light_on else 6)
        fs = 0.016 if len(disp) <= 6 else 0.012
        text('disp', disp, (0.185, -0.1985, 0.2445), fs, tm, font=MONO, parent=root)
    if st.get('knobs'):
        km = mat('knob', '#E8E2D2' if style != 'toy' else '#3FA9FF', rough=0.25, metal=0.0, coat=0.5)
        for z in (0.17, 0.09):
            k = cyl('knob', (0.185, -0.205, z), 0.026 if style == 'toy' else 0.022, 0.018, km, rot=(math.pi / 2, 0, 0), bevel=0.003, parent=root)
            box('tick', (0.185, -0.2145, z + 0.012), (0.003, 0.002, 0.012), mat('tick', '#222222'), parent=root)
    elif not cut:
        bmat = mat('btn', '#2A2A2A' if style not in ('beige',) else '#E6DDC8', rough=0.35, coat=0.3)
        for i in range(4):
            for j in range(3):
                box('btn', (0.155 + j * 0.03, -0.197, 0.2 - i * 0.026), (0.024, 0.006, 0.018), bmat, bevel=0.003, parent=root)
        box('start', (0.185, -0.197, 0.065), (0.084, 0.007, 0.022), mat('startb', st['disp'] if style == 'lime' else '#3A3A3A', rough=0.3, coat=0.5), bevel=0.004, parent=root)
        box('open', (0.185, -0.197, 0.035), (0.084, 0.007, 0.018), bmat, bevel=0.004, parent=root)
    # feet
    for fx in (-0.21, 0.21):
        for fy in (-0.15, 0.15):
            cyl('foot', (fx, fy, 0.004), 0.012, 0.012, mat('rub', '#111111', rough=0.8), parent=root)
    body.location.z += 0.008; inner.location.z += 0.0
    # interior light
    if light_on:
        L = light('AREA', (0, 0, 0), light_power * 1.6, light_color, size=0.16)
        L.parent = root; L.location = (0.5 * (cx0 + cx1), 0.02, cz1 - 0.004)
        L2 = light('AREA', (0, 0, 0), light_power * 0.6, light_color, size=0.08)
        L2.parent = root; L2.location = (cx1 - 0.01, 0.04, 0.2); L2.rotation_euler = (0, -math.pi / 2, 0)
    if cut or top_cut:
        cutter = box('cutter', (0, 0, 0), (1, 1, 1), parent=root)
        if cut:
            cutter.location = (0.5 + cx1 + 0.008, 0, 0.522)
        else:
            cutter.location = (0, 0, 0.5 + cz1 - 0.005)
        for o in ((body, inner, fr, scr, gls) if top_cut else (body,)):
            boolean(o, cutter)
    return root, plate_root
