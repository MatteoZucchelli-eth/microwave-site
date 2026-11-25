"""Composite a frame from the sprite sheets + manifest exactly like app.js does, and draw the hotspots.
   python tools/composite_check.py <preset> <view A|B> <turntable_frame> [door_frame|closed]
   -> out/<preset>/check/<view>_<frame>_<door>.png (plain) and ..._hot.png (with hotspots)"""
import sys, json, os
from PIL import Image, ImageDraw
preset, view, f = sys.argv[1], sys.argv[2], int(sys.argv[3]); door = sys.argv[4] if len(sys.argv) > 4 else 'closed'
pub = f'public/render/{preset}'; man = json.load(open(f'{pub}/manifest.json')); m = man['views'][view]
sheets = {}
def sheet(n):
    if n not in sheets: sheets[n] = Image.open(f'{pub}/{n}').convert('RGBA')
    return sheets[n]
def piece(img, layer, i):
    r = layer['rects'][i]
    if r: img.alpha_composite(sheet(layer['sheet']).crop((r[0], r[1], r[0] + r[2], r[1] + r[3])), (r[4], r[5]))
closed = view == 'A' and door == 'closed'
img = Image.open(f'{pub}/{"A_fg_closed" if closed else view + "_bg"}.webp').convert('RGBA')
ids = list(man['objects'])
for pid in sorted(ids, key=lambda k: -man['objects'][k][view]['boxes'][f][4]):
    o = man['objects'][pid][view]; piece(img, o['closed' if closed else 'open'], f)
if view == 'A' and not closed: piece(img, man['door'], int(door))
os.makedirs(f'out/{preset}/check', exist_ok=True); tag = f'out/{preset}/check/{view}_{f:03d}_{door}'
img.convert('RGB').save(tag + '.png')
W, H = img.size; d = ImageDraw.Draw(img)
for pid in ids:
    x0, y0, x1, y1, _ = man['objects'][pid][view]['boxes'][f]
    d.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], outline=(255, 0, 80, 255)); d.text((x0 * W + 2, y0 * H + 1), pid, fill=(255, 0, 80, 255))
for k, c in (('display', (0, 160, 255)), ('open_button', (0, 160, 255)), ('cavity', (255, 160, 0)), ('focus', (160, 0, 255))):
    d.polygon([(x * W, y * H) for x, y in m[k]], outline=c + (255,))
bx, by, bw, bh = m['base']; d.rectangle([bx, by, bx + bw, by + bh], outline=(255, 0, 0, 255))
if view == 'A': d.polygon([(x * W, y * H) for x, y in man['door']['postit'][0 if closed else int(door)]], outline=(0, 200, 0, 255))
img.convert('RGB').save(tag + '_hot.png')
