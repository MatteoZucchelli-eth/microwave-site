import bpy, math, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

CX = -0.06
ITEMS = ('robot', 'plug_lid', 'pretzel', 'espresso')
PEN = None

def postit(txt, loc, rot=0.05, color='#FFF07A', size=0.075, fs=0.013, on='door'):
    """loc on door front plane (y=-0.2155) unless given full xyz"""
    global PEN
    PEN = (PEN or 0) + 1
    x, z = loc; y = (-0.2152 - PEN * 0.0011) if on == 'door' else on
    n = box('note', (x, y, z), (size, 0.0008, size), mat('postit' + color, color, rough=0.85))
    n.rotation_euler = (0, rot, 0)
    t = text('notetxt', txt, (x, y - 0.0009, z), fs, mat('pen', '#1A2A7A', rough=0.6), font=HAND)
    t.rotation_euler = (math.pi / 2, rot, 0); return n

def breakroom(wall='#D9DDD6', counter='#B8B4AA', props=True, cabinet=False, exit_sign=False):
    box('counter', (0, 0.3, -0.02), (4, 4, 0.04), mat('lam', counter, rough=0.5))
    box('wall', (0, 0.33, 1.0), (4, 0.02, 2.2), mat('paint', wall, rough=0.9))
    if props:
        cyl('towel', (0.42, 0.1, 0.13), 0.055, 0.26, mat('towel', '#F4F2EC', rough=0.95), bevel=0.003)
        cyl('towelcore', (0.42, 0.1, 0.13), 0.02, 0.262, mat('core', '#8A6A44', rough=0.9))
        cyl('mug1', (-0.42, -0.12, 0.05), 0.04, 0.1, mat('mugw', '#FFFFFF', rough=0.15, coat=0.5), bevel=0.003)
        text('mugtxt', 'WORLD’S OK-EST\nENGINEER', (-0.42, -0.161, 0.05), 0.0095, mat('mugink', '#222222'), font=SANS)
    if cabinet:
        box('cab', (0, 0.15, 0.78), (1.6, 0.36, 0.5), mat('cabm', '#E7E3DA', rough=0.5), bevel=0.004)
        for x in (-0.4, 0.4):
            box('cabh', (x, -0.035, 0.6), (0.12, 0.015, 0.012), mat('cabhd', '#9A9A9A', metal=1, rough=0.3))
    if exit_sign:
        box('exit', (-0.6, 0.31, 0.75), (0.3, 0.03, 0.12), mat('exb', '#111111'))
        text('exitt', 'EXIT', (-0.6, 0.293, 0.75), 0.07, emission('exg', '#29FF6A', 5), font=SANS)
        light('AREA', (-0.6, 0.2, 0.7), 0.6, '#29FF6A', size=0.3, rot=(math.pi / 2, 0, 0))

def fluo(energy=170, color='#E6F4FF', pos=(0, -0.6, 1.6)):
    light('AREA', pos, energy, color, size=1.6, size_y=0.3, target=empty('t', (0, 0, 0.1)))

def v01():
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.9, light_power=5)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((0.08, -0.95, 0.3), (CX + 0.05, 0, 0.15), lens=40, fstop=6)

def v02():  # tight on window
    world((0.75, 0.8, 0.8), 0.32); breakroom(props=False); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.3, light_power=6)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((-0.02, -0.62, 0.17), (CX + 0.02, 0, 0.15), lens=55, fstop=4, focus=empty('f', (CX, -0.02, 0.1)))

def v03():  # door open, morning sun
    world((0.8, 0.85, 0.9), 0.6); breakroom()
    light('SUN', (0, 0, 2), 6, '#FFE2B0', rot=(1.1, 0.0, -0.9))
    fluo(80)
    microwave(style='beige', disp='DONE', door=78, items=ITEMS, plate_rot=0.2, light_power=4)
    camera((0.38, -0.85, 0.36), (CX, -0.05, 0.11), lens=42, fstop=5.6, focus=empty('f', (CX, -0.02, 0.08)))

def v04():  # night, lights off
    world((0.003, 0.004, 0.006), 1); breakroom(exit_sign=True)
    microwave(style='beige', disp='2:14', items=ITEMS, plate_rot=1.2, light_power=8)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((0.1, -1.0, 0.3), (CX + 0.02, 0, 0.17), lens=38, fstop=4, focus=empty('f', (CX, -0.2, 0.15)))

def v05():  # foil-wrapped sosta
    world((0.75, 0.8, 0.8), 0.32); breakroom(props=False); fluo()
    microwave(style='beige', disp='0:30', items=('robot', 'plug_foil', 'pretzel', 'espresso'), door=95, plate_rot=1.9, light_power=4)
    camera((0.25, -0.7, 0.3), (CX, -0.02, 0.1), lens=50, fstop=4, focus=empty('f', (CX, -0.02, 0.06)))

def v06():  # post-it = latest blog post
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.6, light_power=5)
    postit('NEW POST:\nwhy robots\nneed jokes →', (0.03, 0.235), size=0.09, fs=0.0115)
    camera((0.06, -0.9, 0.28), (CX + 0.06, 0, 0.16), lens=42, fstop=6)

def v07():  # post-its as navigation
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='MENU', items=ITEMS, plate_rot=0.4, light_power=5)
    for txt, pos, r, c in [('ABOUT', (-0.19, 0.25), -0.08, '#FFF07A'), ('BLOG', (-0.11, 0.255), 0.06, '#FF9EC7'),
                           ('CV', (-0.035, 0.248), -0.04, '#9EE6FF'), ('X', (0.045, 0.255), 0.1, '#B8F59E')]:
        postit(txt, pos, r, c, size=0.062, fs=0.014)
    camera((0.02, -0.9, 0.3), (CX + 0.05, 0, 0.16), lens=42, fstop=6)

def v08():  # 3/4 side with breakroom context
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.7, light_power=5)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((-0.75, -0.75, 0.32), (0.0, 0, 0.14), lens=38, fstop=5.6)

def v09():  # running, warm glow
    world((0.25, 0.27, 0.28), 0.5); breakroom(); fluo(60)
    microwave(style='beige', disp='0:42', items=ITEMS, plate_rot=2.4, light_power=12, light_color=(1, 0.72, 0.38))
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((0.06, -0.9, 0.24), (CX + 0.05, 0, 0.15), lens=42, fstop=4, focus=empty('f', (CX, -0.2, 0.15)))

def v10():  # from above, post-it on top
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.7, light_power=5)
    n = box('notetop', (-0.05, -0.05, 0.3105), (0.1, 0.1, 0.0008), mat('pt', '#FFF07A', rough=0.85)); n.rotation_euler = (0, 0, 0.15)
    t = text('nt', 'property of\nMATTEO\ndo not take', (-0.05, -0.05, 0.312), 0.014, mat('pen2', '#1A2A7A'), font=HAND, rot=(0, 0, 0.15))
    camera((0.1, -0.5, 0.62), (-0.03, -0.06, 0.2), lens=42, fstop=6)

def v11():  # gritty green fluorescent
    world((0.35, 0.45, 0.38), 0.4); breakroom(wall='#B9C2AE', counter='#8F8C80'); fluo(170, '#CFFFE0')
    microwave(style='beige', disp='0:00', items=ITEMS, plate_rot=1.0, light_power=4, dirty=True)
    postit('WHO TOOK\nMY\nPRETZEL?', (0.035, 0.24), size=0.08, fs=0.012)
    camera((0.1, -0.88, 0.27), (CX + 0.05, 0, 0.15), lens=40, fstop=5.6)

def v12():  # wide breakroom
    world((0.75, 0.8, 0.8), 0.32); breakroom(cabinet=True); fluo(220, pos=(0, -0.8, 1.8))
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.9, light_power=5)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((0.05, -1.2, 0.4), (0.0, 0, 0.27), lens=30, fstop=8)

def v13():  # dirty cavity, door open
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='0:00', door=88, items=ITEMS, plate_rot=0.5, light_power=4, dirty=True)
    camera((0.32, -0.75, 0.3), (CX, -0.03, 0.12), lens=42, fstop=5.6)

def v14():  # back in 5, door ajar
    world((0.75, 0.8, 0.8), 0.32); breakroom(); fluo()
    microwave(style='beige', disp='5:00', door=14, items=ITEMS, plate_rot=0.3, light_power=5)
    postit('BACK IN\n5 MIN', (0.035, 0.24), rot=-0.1)
    camera((0.25, -0.9, 0.3), (CX + 0.05, 0, 0.15), lens=42, fstop=6)

def v15():  # macro on post-it
    world((0.75, 0.8, 0.8), 0.32); breakroom(props=False); fluo()
    microwave(style='beige', disp='0:30', items=ITEMS, plate_rot=0.9, light_power=5)
    postit('LABEL\nYOUR\nFOOD!', (0.04, 0.24))
    camera((0.16, -0.48, 0.27), (0.03, -0.21, 0.235), lens=85, fstop=2.2, focus=empty('f', (0.04, -0.216, 0.24)))

def v16():  # warm, designed breakroom
    world((0.95, 0.88, 0.78), 0.6); breakroom(wall='#EADBC6', counter='#C98F5E')
    light('AREA', (-1.0, -0.9, 1.1), 260, '#FFE9CC', size=1.4, target=empty('t', (0, 0, 0.15)))
    microwave(style='beige', disp='HI', items=ITEMS, plate_rot=0.8, light_power=5)
    postit('make things\nfor the\nworld', (0.04, 0.24), color='#FFB37A', fs=0.012)
    camera((0.12, -0.9, 0.28), (CX + 0.05, 0, 0.15), lens=42, fstop=4, focus=empty('f', (CX, -0.2, 0.15)))

V = {i + 1: f for i, f in enumerate([v01, v02, v03, v04, v05, v06, v07, v08, v09, v10, v11, v12, v13, v14, v15, v16])}

if __name__ == '__main__':
    a = sys.argv[1:]; ids = [int(x) for x in a[0].split(',')]; res = int(a[1]); spp = int(a[2]); out = a[3]
    for i in ids:
        PEN = 0; s = reset(); objects_mats(); V[i](); s.view_settings.exposure = -0.35
        s.render.resolution_x = res; s.render.resolution_y = int(res * 0.68); s.cycles.samples = spp
        s.render.filepath = f'{out}/v{i:02d}.png'; t = time.time()
        bpy.ops.render.render(write_still=True); print(f'RENDERED {i} {time.time() - t:.1f}s', flush=True)
