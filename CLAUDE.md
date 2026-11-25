# Matteo's personal site — "the breakroom microwave"

Read this first. It is the brief for building the site from scratch in this repo.

## Who it's for / tone
- Owner: Matteo Zucchelli. Motto: **make things for the world**.
- Wants visitors (tech people) to think "this guy is interesting". Builder with taste, funny, a little genius — *not* "the robotics expert".
- Tone: ironic, minimal, polished, hacker. An average-looking site is a failure.
- Preference: minimal, clean solutions. No framework bloat, no gratuitous dependencies.

## The concept
The homepage is a **photoreal close-up of a beige office-breakroom microwave** (see `reference/06-base.png`).
A glass turntable inside rotates. The objects on the plate are the navigation:

| Object on plate | Goes to | Notes |
|---|---|---|
| Humanoid robot (G1-style) | CV / robotics projects | replace placeholder with Unitree's official G1 meshes (unitree_ros on GitHub) |
| sosta plug mascot (lime #C6F24E), uncovered (`objects/sosta.py`) | nothing yet ("soon" tooltip) | startup can't be shown publicly yet |
| Pretzel | Brezel (German-learning app) | |
| Espresso cup | About (personal section) | |

A **post-it** on the door shows the latest blog post title (see `reference/06-live-note.png`) and links to it.
The panel display shows a timer.

## Interaction flow
1. **Land:** door closed, plate turning, display counts down `0:05` → doubles as the asset loader.
2. **Ding:** door pops open (short swing), interior light spills out. Returning visitors skip the countdown; the `OPEN` button on the panel also opens it.
3. **Door open:** objects are clickable. Hover = object lifts slightly + handwritten label. Click = its page.
4. **Back:** door closes, plate keeps turning.
Objects are **not** clickable while the door is closed (keeps the reveal).

## Rendering architecture (key decision)
Real-time WebGL won't match Cycles. So everything is **pre-rendered in Blender Cycles** and composited in the browser on a `<canvas>`, in **layers**, so adding a project = rendering one object only:

1. `bg/` — cavity, plate, room, lighting. Turntable loop, N frames (start N=120). Rendered once.
2. `objects/<id>/` — one object alone on its plate slot, transparent background + shadow/reflection catcher, same camera/lights/frames.
3. `fg_closed/`, `fg_open/` — door (glass, perforated mesh, post-it area), panel; plus a one-off `door_anim/` sequence (closed→open, ~24 frames) and a light-spill layer.
4. Export per frame the **2D screen bounding box of each object** → `hotspots.json`; invisible hit areas track them.

- More projects than plate slots (~4–5): swap objects while they pass behind (back of the plate, out of view) → endless carousel.
- Post-it text is HTML/CSS laid over the render with matching perspective (so it updates without re-rendering).
- Output frames as WebP/AVIF sprite sheets or a short video per layer; preload, keep the homepage fast on mobile.

## Content model
`public/projects.json`: `{ id, title, url, object: "blender/objects/<id>.py", slot, hidden? }`.
Adding a project = add a model script + one entry + run `render_object <id>` + push.
Blog: markdown posts; latest title feeds the post-it; auto-post to X on publish (later, via a Vercel cron/serverless function).
Contact CTA: LinkedIn.

## Blender assets in this repo
- `blender/lib.py` — microwave (parametric), materials (perforated door mesh, glass, enamel), plate, robot, plug mascot, `plug_lid` (covered sosta, dropped), `plug_foil`, pretzel, espresso, post-it helpers, camera/lights. Pure Python (`bpy`), procedural, no external assets.
- `blender/scenes_breakroom.py` — the 16 breakroom variants; **`v01` is the chosen base**, `v06` = live-note post-it, `v03` = door open lighting.
- Run: `pip install bpy` (needs the Python version bpy targets) or Blender's bundled Python:
  `python blender/scenes_breakroom.py 1 900 48 out/` → renders variant 1 at 900px, 48 samples.
- Switch Cycles to GPU on this machine (Metal / OptiX / CUDA) — the scripts default to CPU.
- Models are placeholders built from primitives; lighting carries the realism. Improve geometry where it shows.

## Render pipeline (built)
- Setup: `uv venv -p 3.11 .venv && uv pip install -p .venv -r requirements-render.txt` (bpy 5.0.1 = Python 3.11). Uses OptiX if present.
- `.venv/bin/python blender/layers.py all [--preset lo|hi]` (~10 min lo). Single passes: `bg A|B`, `closed`, `door`, `ref`, `object A|B <id>` (= render_object; run it for both views), `manifest`. Frames go to `out/<preset>/` (gitignored), published files to `public/render/<preset>/`.
- Two cameras: **A** wide breakroom shot (closed + door anim), **B** frontal close-up of the open cavity. The page zooms A→B after the door opens.
- Static frames (`A_bg`, `A_fg_closed`, `B_bg`) are overscanned (`OVERSCAN` = 1.6×2.8 the base framing) so the render fills any viewport: the page around the microwave is the render. Animated layers render as per-frame crops (Cycles border, verified pixel-exact) packed into one sprite sheet per sequence: `A_door`, `A_closed_<id>`, `A_open_<id>`, `B_open_<id>`. `manifest.json` has the views (size, base framing, focus/cavity/display/OPEN quads), sheet rects, per-frame object boxes + depth, post-it quads.
- Composite: A closed = `A_fg_closed` + `A_closed_*`; A door anim = `A_bg` + `A_open_*` (far→near) + `A_door[i]`; B = `B_bg` + `B_open_*`. Why the exact closed frame: the mesh averages the lit cavity in HDR, 8-bit alpha-over can't.
- Check: `.venv/bin/python tools/composite_check.py lo <A|B> <frame> [closed|door_frame]` → `out/lo/check/`, compare with `out/lo/ref_*.webp`.

## Site (step 2)
- No build step, no dependencies: `public/` is the web root (`index.html`, `style.css`, `app.js`, `fonts/`, `projects.json`, `render/`). Dev: `python3 -m http.server 8000 -d public`.
- `app.js`: full-page canvas; each view is composed offscreen from its sheets, then drawn with a layout that shows the base framing without ever cropping the focus (A: microwave, B: cavity). States: closed → opening (door) → zoomin (A scales onto the cavity while B fades in, aligned on the cavity rect) → open (B) → zoomout → closing → closed.
- Display / post-it / OPEN button are HTML mapped onto their quads (homography, `matrix3d`). Objects are hit-tested per pixel in B (shadows ignored); hotspots are real `<a>` links. Close: Esc, OPEN, or "close the door".
- Countdown = loader: A closed sheets first; display holds `0:01` until everything is in. `localStorage['mw-seen']` skips the countdown; after the first open the display shows the time.

## Deploy
Static site (no bundler; Vercel serves `public/`) → GitHub repo → import in Vercel → custom domain.

## Order of work
1. Repo + layer render pipeline (bg / object / fg / hotspots) from `scenes_breakroom.v01`, low-res first.
2. Canvas compositor + door flow + hotspots, with low-res frames.
3. Pages: CV, Brezel, About, blog. Post-it overlay.
4. Final-quality renders, compression, mobile check.
5. Deploy to Vercel.
