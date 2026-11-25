"""Composite a frame the way the browser will, and draw hotspots.
   python tools/composite_check.py <preset> <turntable_frame> <closed|door_frame>
   closed:     fg_closed + objects/*/closed       door frame i: bg + objects/*/open + door/i
   -> public/render/<preset>/composite_*.png (+ check_*.png with hotspots)"""
import sys, json, os
from PIL import Image, ImageDraw
preset, f, d = sys.argv[1], int(sys.argv[2]), sys.argv[3]; R = f'public/render/{preset}'
h = json.load(open(f'{R}/hotspots.json')); closed = d == 'closed'
img = Image.open(f'{R}/{"fg_closed" if closed else "bg"}.webp').convert('RGBA'); W, H = img.size
objs = sorted(h['objects'].items(), key=lambda kv: -kv[1][f % len(kv[1])][4])          # far -> near
for pid, boxes in objs:
    p = f'{R}/objects/{pid}/{"closed" if closed else "open"}/{f:03d}.webp'
    if os.path.exists(p): img = Image.alpha_composite(img, Image.open(p).convert('RGBA'))
if not closed: img = Image.alpha_composite(img, Image.open(f'{R}/door/{int(d):02d}.webp').convert('RGBA'))
ann = img.copy(); da = ImageDraw.Draw(ann)
for pid, boxes in objs:
    x0, y0, x1, y1, _ = boxes[f % len(boxes)]
    da.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], outline=(255, 0, 80, 255)); da.text((x0 * W + 2, y0 * H + 1), pid, fill=(255, 0, 80, 255))
for k in ('display', 'open_button'):
    da.polygon([(x * W, y * H) for x, y in h[k]], outline=(0, 160, 255, 255))
da.polygon([(x * W, y * H) for x, y in h['postit'][0 if closed else int(d)]], outline=(0, 200, 0, 255))
tag = f'{f:03d}_{d}'
img.convert('RGB').save(f'{R}/composite_{tag}.png'); ann.convert('RGB').save(f'{R}/check_{tag}.png')
