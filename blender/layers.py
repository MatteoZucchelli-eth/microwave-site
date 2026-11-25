"""Layer render pipeline for the homepage, built from scenes_breakroom.v01.

  python blender/layers.py <pass> [view] [id] [--preset lo|hi] [--frames N]

Two camera views:
  A  the wide breakroom shot (v01). States: closed, door opening/closing.
  B  frontal close-up of the open cavity. The page zooms A -> B once the door is open.

passes (frames go to out/<preset>/, published files to public/render/<preset>/):
  bg <A|B>          static background, no objects (A: door hidden, B: door open)  -> <V>_bg.webp
  closed            A, exact closed-door frame, no objects                        -> A_fg_closed.webp
  door              A, door + post-it with alpha, closed -> open                  -> A_door.webp (sheet)
  object <A|B> <id> one plate object over the turntable loop (shadow catcher):
                      A: open + closed (seen through the closed door's holes)     -> A_open_<id>.webp, A_closed_<id>.webp
                      B: open                                                     -> B_open_<id>.webp
  ref               full stills to check compositing against                      -> out/<preset>/ref_*.webp
  hero <id>         page header image of one object (high res)                    -> public/img/hero_<id>.webp
  all               everything, one process per pass
  manifest          rebuild manifest.json from out/<preset>/meta/

Static frames are overscanned (OVERSCAN x the base framing) so the render fills any viewport: the page around
the microwave is the render itself. Animated layers are rendered per frame as a tight crop (Cycles border)
and packed into one sprite sheet per sequence; manifest.json says where each piece goes.

Compositing (browser):  A closed  = A_fg_closed + A_closed_*            (objects far -> near by depth)
                        A opening = A_bg + A_open_* + A_door[i]
                        B open    = B_bg + B_open_*
Why A_fg_closed is a full frame: the door mesh averages the lit cavity in linear HDR before tone mapping;
alpha-compositing 8-bit layers can't reproduce that.
Display / post-it text are HTML overlays on the quads in manifest.json.
"""
import bpy, math, sys, os, json, time, importlib, glob
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lib
from lib import reset, objects_mats, world, microwave, box, mat
from scenes_breakroom import breakroom, fluo, CX

PRESETS = {'lo': dict(res=480, spp=32, sheet=2048), 'hi': dict(res=1920, spp=256, sheet=8192)}
ASPECT = 0.68
OVERSCAN = (1.6, 3.0)   # static frames cover this much more than the base framing (tall phones .. 21:9)
FRAMES = 120            # turntable loop length
DOOR_FRAMES = 24
DOOR_OPEN = 78          # degrees, matches v03
PLATE_ROT0 = 0.9
SLOT_R = 0.075; N_SLOTS = 4
# v01 used light_power=5 + near-white enamel: fine behind the closed mesh, blown out (clipped white) with the door open
INTERIOR_LIGHT = 0.75
ENAMEL = '#B8AD97'
VIEWS = {
    'A': dict(loc=(0.08, -0.95, 0.3), target=(CX + 0.05, 0, 0.15), lens=40, fstop=6, focus=None),
    'B': dict(loc=(CX, -0.6, 0.18), target=(CX, -0.02, 0.1), lens=50, fstop=8, focus=(CX, -0.015, 0.05)),
}
PROJECTS = json.load(open(os.path.join(ROOT, 'public', 'projects.json')))
LIVE = [p['id'] for p in PROJECTS if not p.get('hidden')]


# ---------- scene ----------
def build(view):
    s = reset(); objects_mats()
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    _, plate = microwave(style='beige', disp='', items=(), plate_rot=PLATE_ROT0, light_power=INTERIOR_LIGHT)
    en = bpy.data.materials['enamel'].node_tree.nodes['Principled BSDF']
    en.inputs['Base Color'].default_value = lib.hexc(ENAMEL); en.inputs['Roughness'].default_value = 0.4
    items = {}
    for p in PROJECTS:
        if p.get('hidden'): continue
        fn = importlib.import_module('objects.' + p['id']).build
        a = p['slot'] * math.tau / N_SLOTS
        # face outward from the plate centre (models face -y): each object faces the camera as it passes the front
        items[p['id']] = fn((math.cos(a) * SLOT_R, math.sin(a) * SLOT_R, 0.003), p.get('scale', 1.0), a + math.pi / 2, plate)
    hinge = bpy.data.objects['hinge']
    glass_to_alpha(bpy.data.materials['doorglass'])
    # blank post-it (text is an HTML overlay), parented to the door so it swings with it
    note = box('note', (0.04, -0.2163, 0.24), (0.075, 0.0008, 0.075), mat('postit', '#FFF07A', rough=0.85))
    note.rotation_euler = (0, 0.05, 0)
    bpy.context.view_layer.update()
    note.parent = hinge; note.matrix_parent_inverse = hinge.matrix_world.inverted()
    v = VIEWS[view]
    cam = lib.camera(v['loc'], v['target'], lens=v['lens'], fstop=v['fstop'],
                     focus=lib.empty('focus', v['focus']) if v['focus'] else None)
    cam.data.sensor_fit = 'HORIZONTAL'; cam.data.lens = v['lens'] / OVERSCAN[0]   # same framing, wider canvas
    if view == 'B': hinge.rotation_euler.z = -math.radians(DOOR_OPEN)
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

def sizes(preset):
    W0 = preset['res']; H0 = round(W0 * ASPECT)
    return round(W0 * OVERSCAN[0]), round(H0 * OVERSCAN[1]), W0, H0

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
    Wf, Hf, _, _ = sizes(preset)
    s.render.resolution_x = Wf; s.render.resolution_y = Hf; s.render.resolution_percentage = 100
    s.cycles.samples = preset['spp']
    s.render.film_transparent = transparent; s.cycles.film_transparent_glass = transparent
    im = s.render.image_settings; im.file_format = 'WEBP'; im.color_mode = 'RGBA' if transparent else 'RGB'; im.quality = 90

def render(s, path, rect=None):
    """rect = (x0, y0, x1, y1) in full-frame px, top-left origin: renders only that crop (exact, verified)"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = s.render; W, H = r.resolution_x, r.resolution_y
    r.use_border = r.use_crop_to_border = rect is not None
    if rect:   # +1/4 px: Blender turns border fractions back into pixels with float error; this lands on the intended
        x0, y0, x1, y1 = rect   # pixel whether it rounds or truncates. Size is verified below.
        e = 0.25
        r.border_min_x, r.border_max_x = (x0 + e) / W, (x1 + e) / W
        r.border_min_y, r.border_max_y = (H - y1 + e) / H, (H - y0 + e) / H
    r.filepath = path; bpy.ops.render.render(write_still=True)
    if rect:
        got = Image.open(path).size
        assert got == (x1 - x0, y1 - y0), f'crop {rect} rendered as {got}'


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

def world_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        if o.hide_render or o.type not in ('MESH', 'CURVE', 'FONT'): continue
        oe = o.evaluated_get(dg); me = oe.to_mesh()
        if me and len(me.vertices):
            v = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', v); v = v.reshape(-1, 3)
            mw = np.array(oe.matrix_world); out.append(v @ mw[:3, :3].T + mw[:3, 3])
        oe.to_mesh_clear()
    return np.concatenate(out)

def front_quad(o, M):
    """screen quad (TL, TR, BR, BL), normalized, of a box's camera-facing (-y) face"""
    mw = np.array(o.matrix_world); bb = np.array([list(c) for c in o.bound_box])
    f = bb[np.isclose(bb[:, 1], bb[:, 1].min())]
    f = f[np.lexsort((f[:, 0], -f[:, 2]))]                     # top row first, then left->right
    q, _ = project(M, f @ mw[:3, :3].T + mw[:3, 3])
    tl, tr, bl, br = q[0], q[1], q[2], q[3]
    return [r5(p) for p in (tl, tr, br, bl)]

def px_rect(q, Wf, Hf, pad=(2, 2, 2, 2)):
    """normalized points -> integer px rect (x0, y0, x1, y1), padded (l, t, r, b), clipped; None if off-frame"""
    x0 = max(0, math.floor(q[:, 0].min() * Wf) - pad[0]); y0 = max(0, math.floor(q[:, 1].min() * Hf) - pad[1])
    x1 = min(Wf, math.ceil(q[:, 0].max() * Wf) + pad[2]); y1 = min(Hf, math.ceil(q[:, 1].max() * Hf) + pad[3])
    return (x0, y0, x1, y1) if x1 - x0 > 1 and y1 - y0 > 1 else None

r5 = lambda a: [round(float(x), 5) for x in a]


# ---------- helpers ----------
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
    through the mesh, and the door's own shadow is already in A_fg_closed)."""
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
                # holes fully clear: their tint is already in A_fg_closed; as alpha it would veil the window per object
                if m.type == 'BSDF_TRANSPARENT': m.inputs[0].default_value = (1, 1, 1, 1)
        else: o.is_holdout = True

def drop_plate():
    """the glass plate can't be a catcher (records transmission). Make it a holdout: nothing is drawn over the plate
    (in the bg it's a dark mirror that hides shadows anyway), and shadows seen through it can't be cut off by the crop"""
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.materials and o.data.materials[0] and o.data.materials[0].name in ('glass', 'ringm'):
            o.is_shadow_catcher = False; o.is_holdout = True; o.visible_shadow = False

def view_meta(view, s, M, Wf, Hf, W0, H0):
    o = bpy.data.objects
    return {'w': Wf, 'h': Hf, 'base': [(Wf - W0) // 2, (Hf - H0) // 2, W0, H0],
            'focus': front_quad(o['body'] if view == 'A' else o['cavliner'], M),
            'cavity': front_quad(o['cavliner'], M),
            'display': front_quad(o['dispbg'], M), 'open_button': front_quad(o['open'], M)}

def save_meta(out, name, d):
    os.makedirs(f'{out}/meta', exist_ok=True); json.dump(d, open(f'{out}/meta/{name}.json', 'w'))


# ---------- post-processing on crops ----------

def clean_catcher(paths, floor=14):
    """Catchers also record the object's faint indirect occlusion on every wall (~3% per object, it stacks across
    objects). Drop shadow-only pixels (black) below `floor` alpha, rescale the rest: contact shadows stay."""
    for p in paths:
        im = np.asarray(Image.open(p).convert('RGBA'), np.float32).copy()
        sh = im[..., :3].max(-1) < 4
        im[..., 3] = np.where(sh, np.clip((im[..., 3] - floor) * 255 / (255 - floor), 0, 255), im[..., 3])
        Image.fromarray(im.astype(np.uint8), 'RGBA').save(p, lossless=True)

def bake_closed_delta(paths, rects, pub):
    """The closed layer's alpha is hole-coverage x object. Plain 'over' would keep the bright interior behind the object;
    the right result is fg_closed + a*(obj - bg). Baking c = obj - bg + fg_closed makes plain 'over' compute exactly that."""
    bg = np.asarray(Image.open(f'{pub}/A_bg.webp').convert('RGB'), np.int16)
    fg = np.asarray(Image.open(f'{pub}/A_fg_closed.webp').convert('RGB'), np.int16)
    for p, (x0, y0, x1, y1) in zip(paths, rects):
        im = np.asarray(Image.open(p).convert('RGBA'), np.int16).copy()
        im[..., :3] = np.clip(im[..., :3] - bg[y0:y1, x0:x1] + fg[y0:y1, x0:x1], 0, 255)
        Image.fromarray(im.astype(np.uint8), 'RGBA').save(p, lossless=True)

def pack(paths, rects, sheet_path, max_w):
    """shelf-pack cropped frames into one sheet. returns per frame [sx, sy, w, h, dx, dy] (dx, dy = full-frame px)"""
    ims = [Image.open(p).convert('RGBA') if p else None for p in paths]
    x = y = shelf = 0; place = []
    for im in ims:
        if im is None: place.append(None); continue
        w, h = im.size
        if x + w > max_w: x = 0; y += shelf; shelf = 0
        place.append((x, y)); x += w + 1; shelf = max(shelf, h + 1)
    W = max((p[0] + im.size[0] for p, im in zip(place, ims) if im), default=1)
    H = max((p[1] + im.size[1] for p, im in zip(place, ims) if im), default=1)
    sheet = Image.new('RGBA', (W, H))
    out = []
    for im, pl, r in zip(ims, place, rects):
        if im is None: out.append(None); continue
        sheet.paste(im, pl); out.append([pl[0], pl[1], im.size[0], im.size[1], r[0], r[1]])
    sheet.save(sheet_path, quality=88, method=6)
    return out


# ---------- passes ----------
def pass_bg(view, preset, out, pub, **_):
    s, plate, hinge, note, items = build(view); setup(s, preset, False)
    if view == 'A': hide(tree(hinge))
    [hide(tree(r)) for r in items.values()]
    bpy.context.view_layer.update(); Wf, Hf, W0, H0 = sizes(preset)
    save_meta(out, f'view_{view}', view_meta(view, s, cam_matrix(s), Wf, Hf, W0, H0))
    render(s, f'{pub}/{view}_bg.webp')

def pass_closed(preset, out, pub, **_):
    s, plate, hinge, note, items = build('A'); setup(s, preset, False)
    [hide(tree(r)) for r in items.values()]
    render(s, f'{pub}/A_fg_closed.webp')

def pass_ref(preset, out, pub, **_):
    """full stills to check compositing against"""
    s, plate, hinge, *_ = build('A'); setup(s, preset, False); render(s, f'{out}/ref_A_closed.webp')
    hinge.rotation_euler.z = -math.radians(DOOR_OPEN); render(s, f'{out}/ref_A_open.webp')
    s, *_ = build('B'); setup(s, preset, False); render(s, f'{out}/ref_B.webp')

def pass_object(view, pid, preset, out, pub, frames=FRAMES, **_):
    s, plate, hinge, note, items = build(view); setup(s, preset, True)
    door = [note] + hide(tree(hinge)) if view == 'A' else []      # B: the open door stays (catcher, occludes)
    for k, r in items.items():
        if k != pid: hide(tree(r))
    me = tree(items[pid]); solo(me); drop_plate()
    bpy.context.view_layer.update(); M = cam_matrix(s); Wf, Hf, W0, H0 = sizes(preset)
    # object is rigid on the plate: cache its verts in plate space, rotate per frame
    pinv = np.array(plate.matrix_world.inverted())
    loc = world_verts(me) @ pinv[:3, :3].T + pinv[:3, 3]
    origin = np.array(plate.matrix_world.inverted() @ items[pid].matrix_world.translation)
    note.hide_render = True
    boxes, rects = [], []
    for f in range(frames):
        plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames
        bpy.context.view_layer.update(); pm = np.array(plate.matrix_world)
        q, _ = project(M, loc @ pm[:3, :3].T + pm[:3, 3])
        _, w = project(M, (origin @ pm[:3, :3].T + pm[:3, 3])[None])
        boxes.append(r5([*q.min(0), *q.max(0), w[0]]))         # x0 y0 x1 y1 depth (object only, for hit-testing)
        bw, bh = (q[:, 0].max() - q[:, 0].min()) * Wf, (q[:, 1].max() - q[:, 1].min()) * Hf
        rects.append(px_rect(q, Wf, Hf, pad=(int(bw * .3) + 3, 3, int(bw * .3) + 3, int(bh * .25) + 4)))   # + shadow
    d = f'{out}/frames/{view}_{pid}'
    open_p = [f'{d}/open/{f:03d}.webp' for f in range(frames)]
    for f in range(frames):
        plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames
        render(s, open_p[f], rects[f]); print(f'{view} {pid} open {f + 1}/{frames}', flush=True)
    clean_catcher(open_p)
    meta = {'boxes': boxes, 'open': {'sheet': f'{view}_open_{pid}.webp',
                                     'rects': pack(open_p, rects, f'{pub}/{view}_open_{pid}.webp', preset['sheet'])}}
    if view == 'A':
        door_as_holdout(door)
        closed_p = [f'{d}/closed/{f:03d}.webp' for f in range(frames)]
        for f in range(frames):
            plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames
            render(s, closed_p[f], rects[f]); print(f'{view} {pid} closed {f + 1}/{frames}', flush=True)
        bake_closed_delta(closed_p, rects, pub)
        meta['closed'] = {'sheet': f'A_closed_{pid}.webp', 'rects': pack(closed_p, rects, f'{pub}/A_closed_{pid}.webp', preset['sheet'])}
    save_meta(out, f'obj_{view}_{pid}', meta)

def ease_pop(t):  # ease-out-back: fast swing, small bounce on the stop
    c = 1.4; t -= 1; return 1 + (c + 1) * t ** 3 + c * t ** 2

def pass_door(preset, out, pub, **_):
    s, plate, hinge, note, items = build('A'); setup(s, preset, True)
    [hide(tree(r)) for r in items.values()]
    door = tree(hinge); solo(door, catch=False)
    bpy.context.view_layer.update(); M = cam_matrix(s); Wf, Hf, _, _ = sizes(preset)
    quads, angles, paths, rects = [], [], [], []
    for i in range(DOOR_FRAMES):
        a = DOOR_OPEN * ease_pop(i / (DOOR_FRAMES - 1)); angles.append(round(a, 2))
        hinge.rotation_euler.z = -math.radians(a); bpy.context.view_layer.update()
        quads.append(front_quad(note, M))
        q, _ = project(M, world_verts(door)); r = px_rect(q, Wf, Hf, pad=(3, 3, 3, 3)); rects.append(r)
        p = f'{out}/frames/A_door/{i:02d}.webp' if r else None; paths.append(p)
        if r: render(s, p, r)
    save_meta(out, 'door', {'angles': angles, 'postit': quads, 'sheet': 'A_door.webp',
                            'rects': pack(paths, rects, f'{pub}/A_door.webp', preset['sheet'])})

def pass_hero(pid, out, frames=FRAMES, **_):
    """page header image: the object from view B, at the turntable frame where it faces the camera, high res,
    transparent with its soft shadow -> public/img/hero_<id>.webp"""
    preset = dict(PRESETS['hi'], spp=128)
    s, plate, hinge, note, items = build('B'); setup(s, preset, True)
    for k, r in items.items():
        if k != pid: hide(tree(r))
    me = tree(items[pid]); solo(me); drop_plate(); note.hide_render = True
    bpy.context.view_layer.update(); M = cam_matrix(s); Wf, Hf, _, _ = sizes(preset)
    pinv = np.array(plate.matrix_world.inverted()); loc = world_verts(me) @ pinv[:3, :3].T + pinv[:3, 3]
    origin = np.array(plate.matrix_world.inverted() @ items[pid].matrix_world.translation)
    def at(f):
        plate.rotation_euler.z = PLATE_ROT0 + math.tau * f / frames; bpy.context.view_layer.update()
        return np.array(plate.matrix_world)
    f = min(range(frames), key=lambda f: project(M, (origin @ at(f)[:3, :3].T + at(f)[:3, 3])[None])[1][0])   # nearest
    pm = at(f); q, _ = project(M, loc @ pm[:3, :3].T + pm[:3, 3])
    bw, bh = (q[:, 0].ptp()) * Wf, (q[:, 1].ptp()) * Hf
    rect = px_rect(q, Wf, Hf, pad=(int(bw * .35), int(bh * .08), int(bw * .35), int(bh * .22)))
    path = os.path.join(ROOT, 'public', 'img', f'hero_{pid}.webp'); render(s, path, rect)
    clean_catcher([path])
    Image.open(path).save(path, quality=86, method=6)

def manifest(preset, out, pub, frames=FRAMES, **_):
    """manifest.json = everything the browser needs. Quads/boxes normalized (0..1, top-left); rects in px."""
    rd = lambda n: json.load(open(f'{out}/meta/{n}.json')) if os.path.exists(f'{out}/meta/{n}.json') else None
    man = {'frames': frames, 'door_frames': DOOR_FRAMES, 'views': {v: rd(f'view_{v}') for v in VIEWS},
           'door': rd('door'), 'objects': {}}
    for pid in LIVE:
        man['objects'][pid] = {v: rd(f'obj_{v}_{pid}') for v in VIEWS}
    json.dump(man, open(f'{pub}/manifest.json', 'w'), separators=(',', ':'))


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    name = opt('--preset', 'lo'); preset = PRESETS[name]
    out = os.path.join(ROOT, 'out', name); pub = os.path.join(ROOT, 'public', 'render', name)
    os.makedirs(out, exist_ok=True); os.makedirs(pub, exist_ok=True)
    kw = dict(preset=preset, out=out, pub=pub, frames=int(opt('--frames', FRAMES)))
    p = a[0]; t = time.time()
    if p == 'bg': pass_bg(a[1], **kw)
    elif p == 'closed': pass_closed(**kw)
    elif p == 'door': pass_door(**kw)
    elif p == 'ref': pass_ref(**kw)
    elif p == 'object': pass_object(a[1], a[2], **kw)
    elif p == 'manifest': manifest(**kw)
    elif p == 'hero': pass_hero(a[1], **kw)
    elif p == 'all':
        # one process per pass: every build() resets Blender, and a crash only loses one pass
        import subprocess
        extra = [x for x in a[1:]]
        jobs = [['ref'], ['bg', 'A'], ['bg', 'B'], ['closed'], ['door']] + \
               [['object', v, pid] for v in VIEWS for pid in LIVE]
        for j in jobs: subprocess.run([sys.executable, __file__, *j, *extra], check=True)
    if p not in ('manifest', 'hero'): manifest(**kw)
    print(f'DONE {p} {time.time() - t:.1f}s')
