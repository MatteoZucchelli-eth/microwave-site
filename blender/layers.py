"""Layer render pipeline for the homepage, built from scenes_breakroom.v01.

  python blender/layers.py <pass> [id] [--preset lo|hi] [--frames N] [--no-render]

passes:
  bg            static background (room, microwave, empty plate)        -> bg.webp
  closed        exact closed-door frame, no objects                     -> fg_closed.webp
  object <id>   one plate object, turntable loop, shadow catcher:
                  open/   as seen with the door open
                  closed/ as seen through the closed door's holes       -> objects/<id>/{open,closed}/NNN.webp
  door          door + post-it with alpha, closed -> open
                (last frame = fg_open)                                  -> door/NN.webp
  ref           full v01-style still (door closed), to check compositing -> ref.webp
  all           everything above for every project in projects.json

The plate is a symmetric disc, so the background is identical on every turntable frame and is rendered once.
Compositing (browser):  closed  = fg_closed + objects/*/closed (far -> near)
                        opening = bg + objects/*/open + door[i];   open = bg + objects/*/open + door[last]
Why fg_closed is a full frame: the lit cavity is brighter than white, and the door mesh averages it in linear HDR
before tone mapping; alpha-compositing 8-bit layers can't reproduce that (window comes out ~40% too dark).
Display text and post-it text are not rendered: their screen quads go to hotspots.json for HTML overlays.
"""
import bpy, math, sys, os, json, time, importlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lib
from lib import reset, objects_mats, world, microwave, box, mat
from scenes_breakroom import breakroom, fluo, CX

PRESETS = {'lo': dict(res=480, spp=32), 'hi': dict(res=1920, spp=256)}
FRAMES = 120            # turntable loop length
DOOR_FRAMES = 24
DOOR_OPEN = 78          # degrees, matches v03
PLATE_ROT0 = 0.9        # v01 composition at frame 0
SLOT_R = 0.075; N_SLOTS = 4
PROJECTS = json.load(open(os.path.join(ROOT, 'projects.json')))


# ---------- scene ----------
def build():
    s = reset(); objects_mats()
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    _, plate = microwave(style='beige', disp='', items=(), plate_rot=PLATE_ROT0, light_power=5)
    items = {}
    for p in PROJECTS:
        if p.get('hidden'): continue
        fn = importlib.import_module('objects.' + p['id']).build
        a = p['slot'] * math.tau / N_SLOTS
        items[p['id']] = fn((math.cos(a) * SLOT_R, math.sin(a) * SLOT_R, 0.003), p.get('scale', 1.0), -PLATE_ROT0, plate)
    hinge = bpy.data.objects['hinge']
    glass_to_alpha(bpy.data.materials['doorglass'])
    # blank post-it (text is an HTML overlay), parented to the door so it swings with it
    note = box('note', (0.04, -0.2163, 0.24), (0.075, 0.0008, 0.075), mat('postit', '#FFF07A', rough=0.85))
    note.rotation_euler = (0, 0.05, 0)
    bpy.context.view_layer.update()
    note.parent = hinge; note.matrix_parent_inverse = hinge.matrix_world.inverted()
    lib.camera((0.08, -0.95, 0.3), (CX + 0.05, 0, 0.15), lens=40, fstop=6)
    s.view_settings.exposure = -0.35
    return s, plate, hinge, note, items


def glass_to_alpha(m):
    """flat door pane: refraction is invisible, so use fresnel(transparent, glossy) -> composites with real alpha.
    (Cycles' 'transparent glass' breaks once the ray continues through the perforated screen behind it.)"""
    nt = m.node_tree; n = nt.nodes; out = n['Material Output']
    tr = n.new('ShaderNodeBsdfTransparent'); gl = n.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.0
    fr = n.new('ShaderNodeFresnel'); fr.inputs['IOR'].default_value = 1.5
    mx = n.new('ShaderNodeMixShader')
    nt.links.new(fr.outputs[0], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])

def tree(o):
    return [o] + list(o.children_recursive)

def setup(s, preset, transparent):
    cp = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA', 'METAL', 'HIP', 'ONEAPI'):
        try:
            cp.compute_device_type = kind; cp.get_devices()
            if any(d.type == kind for d in cp.devices): break
        except TypeError: pass
    gpu = False
    for d in cp.devices: d.use = d.type == cp.compute_device_type; gpu |= d.use and d.type != 'CPU'
    s.cycles.device = 'GPU' if gpu else 'CPU'
    s.render.resolution_x = preset['res']; s.render.resolution_y = int(preset['res'] * 0.68)
    s.cycles.samples = preset['spp']
    s.render.film_transparent = transparent; s.cycles.film_transparent_glass = transparent
    im = s.render.image_settings; im.file_format = 'WEBP'; im.color_mode = 'RGBA' if transparent else 'RGB'; im.quality = 90

def render(s, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s.render.filepath = path; bpy.ops.render.render(write_still=True)


# ---------- projection ----------
def cam_matrix(s):
    dg = bpy.context.evaluated_depsgraph_get(); cam = s.camera.evaluated_get(dg)
    P = cam.calc_matrix_camera(dg, x=s.render.resolution_x, y=s.render.resolution_y)
    return np.array(P @ cam.matrix_world.inverted())

def project(M, pts):
    """world pts (n,3) -> normalized screen (n,2), origin top-left, plus clip w (depth)"""
    h = np.c_[pts, np.ones(len(pts))] @ M.T
    xy = h[:, :2] / h[:, 3:4]
    return np.c_[(xy[:, 0] + 1) / 2, (1 - xy[:, 1]) / 2], h[:, 3]

def world_verts(objs, step=1):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        if o.hide_render or o.type not in ('MESH', 'CURVE', 'FONT'): continue
        oe = o.evaluated_get(dg); me = oe.to_mesh()
        if me and len(me.vertices):
            v = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', v); v = v.reshape(-1, 3)[::step]
            mw = np.array(oe.matrix_world); out.append(v @ mw[:3, :3].T + mw[:3, 3])
        oe.to_mesh_clear()
    return np.concatenate(out)

def front_quad(o, M):
    """screen quad (TL, TR, BR, BL) of a box's camera-facing (-y) face"""
    mw = np.array(o.matrix_world); bb = np.array([list(c) for c in o.bound_box])
    f = bb[np.isclose(bb[:, 1], bb[:, 1].min())]
    f = f[np.lexsort((f[:, 0], -f[:, 2]))]                     # top row first, then left->right
    q, _ = project(M, f @ mw[:3, :3].T + mw[:3, 3])
    tl, tr, bl, br = q[0], q[1], q[2], q[3]
    return [[round(float(a), 5) for a in p] for p in (tl, tr, br, bl)]

r5 = lambda a: [round(float(x), 5) for x in a]


# ---------- passes ----------
def solo(keep, catch=True):
    """only `keep` visible to camera; everything else catches shadows (or is camera-invisible)"""
    keep = set(keep)
    for o in bpy.data.objects:
        if o.type not in ('MESH', 'CURVE', 'FONT') or o.hide_render: continue
        if o in keep: continue
        if catch: o.is_shadow_catcher = True
        else: o.visible_camera = False; o.visible_transmission = False   # seen through glass -> alpha 0

def hide(objs):
    """hide; returns what was visible before, so it can be unhidden"""
    vis = [o for o in objs if not o.hide_render]
    for o in vis: o.hide_render = True
    return vis

def door_as_holdout(door):
    """closed door that only lets the object through its holes: metal/frame/post-it cut out (holdout), holes transparent.
    The door lights the object like the real closed door; catchers become plain holdouts (shadows aren't visible
    through the mesh, and the door's own shadow is already in fg_closed)."""
    for o in bpy.data.objects:
        if o.is_shadow_catcher: o.is_shadow_catcher = False; o.is_holdout = True
    for o in door:
        o.hide_render = False
        if o.type not in ('MESH', 'CURVE', 'FONT'): continue
        names = [m.name for m in o.data.materials if m]
        if 'doorglass' in names: o.hide_render = True
        elif 'screen' in names:
            nt = bpy.data.materials['screen'].node_tree; n = nt.nodes
            final = n['Material Output'].inputs[0].links[0].from_node
            ho = n.new('ShaderNodeHoldout'); nt.links.new(ho.outputs[0], final.inputs[1])
            for m in n:
                if m.type == 'MIX_SHADER' and m is not final: m.inputs[0].default_value = 0.0   # holes: no glossy
        else: o.is_holdout = True

def pass_bg(preset, out, **_):
    s, plate, hinge, note, items = build(); setup(s, preset, False)
    hide(tree(hinge)); [hide(tree(r)) for r in items.values()]
    render(s, f'{out}/bg.webp')

def pass_ref(preset, out, **_):
    """full stills to check compositing against: door closed / door open"""
    s, plate, hinge, *_ = build(); setup(s, preset, False); render(s, f'{out}/ref.webp')
    hinge.rotation_euler.z = -math.radians(DOOR_OPEN); render(s, f'{out}/ref_open.webp')

def pass_closed(preset, out, **_):
    """exact closed-door frame without objects (objects/<id>/closed/ composite over it)"""
    s, plate, hinge, note, items = build(); setup(s, preset, False)
    [hide(tree(r)) for r in items.values()]
    render(s, f'{out}/fg_closed.webp')

def pass_object(preset, out, pid, frames=FRAMES, no_render=False, **_):
    s, plate, hinge, note, items = build(); setup(s, preset, True)
    door = [note] + hide(tree(hinge))
    for k, r in items.items():
        if k != pid: hide(tree(r))
    me = tree(items[pid]); solo(me)
    for o in bpy.data.objects:   # the glass plate can't be a catcher (records transmission) or an occluder (casts its
        # own shadow onto the catchers): drop it, so the object's shadow lands on the cavity floor, seen through the plate in bg
        if o.type == 'MESH' and o.data.materials and o.data.materials[0] and o.data.materials[0].name in ('glass', 'ringm'):
            o.hide_render = True
    bpy.context.view_layer.update(); M = cam_matrix(s)
    # object is rigid on the plate: cache its verts in plate space, rotate per frame
    pinv = np.array(plate.matrix_world.inverted())
    loc = world_verts(me, step=1); loc = loc @ pinv[:3, :3].T + pinv[:3, 3]
    origin = np.array(plate.matrix_world.inverted() @ items[pid].matrix_world.translation)
    note.hide_render = True
    boxes = []
    for f in range(frames):
        plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames
        bpy.context.view_layer.update(); pm = np.array(plate.matrix_world)
        q, _ = project(M, loc @ pm[:3, :3].T + pm[:3, 3])
        _, w = project(M, (origin @ pm[:3, :3].T + pm[:3, 3])[None])
        boxes.append(r5([*q.min(0), *q.max(0), w[0]]))         # x0 y0 x1 y1 depth
        if not no_render:
            t = time.time(); render(s, f'{out}/objects/{pid}/open/{f:03d}.webp')
            print(f'{pid} open {f + 1}/{frames} {time.time() - t:.2f}s', flush=True)
    if not no_render:
        clean_catcher(f'{out}/objects/{pid}/open')
        door_as_holdout(door)
        for f in range(frames):
            plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames
            render(s, f'{out}/objects/{pid}/closed/{f:03d}.webp')
            print(f'{pid} closed {f + 1}/{frames}', flush=True)
        bake_closed_delta(out, pid)
    json.dump({'frames': frames, 'boxes': boxes}, open(f'{out}/objects/{pid}/hotspots.json', 'w'))
    merge(out)

def clean_catcher(d, floor=14):
    """Catchers also record the object's faint indirect occlusion on every wall (~3% per object, it stacks across
    objects). Drop shadow-only pixels (black) below `floor` alpha, rescale the rest: contact shadows stay."""
    from PIL import Image
    for fn in sorted(os.listdir(d)):
        im = np.asarray(Image.open(f'{d}/{fn}').convert('RGBA'), np.float32).copy()
        sh = im[..., :3].max(-1) < 4
        im[..., 3] = np.where(sh, np.clip((im[..., 3] - floor) * 255 / (255 - floor), 0, 255), im[..., 3])
        Image.fromarray(im.astype(np.uint8), 'RGBA').save(f'{d}/{fn}', quality=90, exact=True)

def bake_closed_delta(out, pid):
    """The closed layer's alpha is hole-coverage x object. Plain 'over' would keep the bright interior behind the object;
    the right result is fg_closed + a*(obj - bg). Baking c = obj - bg + fg_closed makes plain 'over' compute exactly that."""
    from PIL import Image
    bg = np.asarray(Image.open(f'{out}/bg.webp').convert('RGB'), np.int16)
    fg = np.asarray(Image.open(f'{out}/fg_closed.webp').convert('RGB'), np.int16)
    d = f'{out}/objects/{pid}/closed'
    for fn in sorted(os.listdir(d)):
        im = np.asarray(Image.open(f'{d}/{fn}').convert('RGBA'), np.int16).copy()
        im[..., :3] = np.clip(im[..., :3] - bg + fg, 0, 255)
        Image.fromarray(im.astype(np.uint8), 'RGBA').save(f'{d}/{fn}', quality=90, exact=True)

def ease_pop(t):  # ease-out-back: fast swing, small bounce on the stop
    c = 1.4; t -= 1; return 1 + (c + 1) * t ** 3 + c * t ** 2

def pass_door(preset, out, no_render=False, **_):
    s, plate, hinge, note, items = build(); setup(s, preset, True)
    [hide(tree(r)) for r in items.values()]
    solo(tree(hinge), catch=False)
    bpy.context.view_layer.update(); M = cam_matrix(s)
    static = {'display': front_quad(bpy.data.objects['dispbg'], M), 'open_button': front_quad(bpy.data.objects['open'], M)}
    quads, angles = [], []
    for i in range(DOOR_FRAMES):
        a = DOOR_OPEN * ease_pop(i / (DOOR_FRAMES - 1)); angles.append(round(a, 2))
        hinge.rotation_euler.z = -math.radians(a); bpy.context.view_layer.update()
        quads.append(front_quad(note, M))
        if not no_render: render(s, f'{out}/door/{i:02d}.webp')
    json.dump({'frames': DOOR_FRAMES, 'angles': angles, 'postit': quads, **static}, open(f'{out}/door/hotspots.json', 'w'))
    merge(out)

def merge(out):
    """hotspots.json = everything the compositor needs, in normalized screen coords (0..1, top-left origin)"""
    h = {'objects': {}}
    for p in PROJECTS:
        f = f'{out}/objects/{p["id"]}/hotspots.json'
        if os.path.exists(f): h['objects'][p['id']] = json.load(open(f))['boxes']
    f = f'{out}/door/hotspots.json'
    if os.path.exists(f): h.update(json.load(open(f)))
    h['turntable_frames'] = next((len(v) for v in h['objects'].values()), 0)
    json.dump(h, open(f'{out}/hotspots.json', 'w'))


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    preset = PRESETS[opt('--preset', 'lo')]; name = opt('--preset', 'lo')
    out = os.path.join(ROOT, 'public', 'render', name); os.makedirs(out, exist_ok=True)
    kw = dict(preset=preset, out=out, frames=int(opt('--frames', FRAMES)), no_render='--no-render' in a)
    json.dump({'w': preset['res'], 'h': int(preset['res'] * 0.68), 'turntable_frames': kw['frames'], 'door_frames': DOOR_FRAMES},
              open(f'{out}/manifest.json', 'w'))
    p = a[0]; t = time.time()
    if p == 'bg': pass_bg(**kw)
    elif p == 'ref': pass_ref(**kw)
    elif p == 'closed': pass_closed(**kw)
    elif p == 'door': pass_door(**kw)
    elif p == 'object': pass_object(pid=a[1], **kw)
    elif p == 'all':
        # one process per pass: every build() resets Blender, and a crash only loses one pass
        import subprocess
        extra = a[1:]
        jobs = [['ref'], ['bg'], ['closed'], ['door']] + [['object', q['id']] for q in PROJECTS if not q.get('hidden')]
        for j in jobs: subprocess.run([sys.executable, __file__, *j, *extra], check=True)
    print(f'DONE {p} {time.time() - t:.1f}s')
