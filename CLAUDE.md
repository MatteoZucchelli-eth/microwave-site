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
`projects.json`: `{ id, title, url, object: "blender/objects/<id>.py", slot, hidden? }`.
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

## Render pipeline (built, step 1)
- Setup: `uv venv -p 3.11 .venv && uv pip install -p .venv -r requirements-render.txt` (bpy 5.0.1 = Python 3.11). Uses OptiX if present.
- `.venv/bin/python blender/layers.py all [--preset lo|hi]` → `public/render/<preset>/`; single passes: `bg`, `closed`, `door`, `ref`, `object <id>` (= render_object).
- Layers: `bg.webp` (1 frame: the plate is a symmetric disc), `fg_closed.webp` (exact closed-door frame), `door/NN.webp` (alpha, last = fg_open), `objects/<id>/{open,closed}/NNN.webp`, `hotspots.json` (per-frame object boxes + depth, post-it/display/OPEN quads; normalized, top-left origin).
- Composite: closed = `fg_closed` + `objects/*/closed`; opening/open = `bg` + `objects/*/open` (far→near by depth) + `door[i]`. Why not one door layer over everything: the lit cavity is brighter than white and the mesh averages it in HDR, so 8-bit alpha-over makes the closed window ~40% too dark.
- Check: `.venv/bin/python tools/composite_check.py lo <frame> <closed|door_frame>` vs `ref.webp` / `ref_open.webp`.

## Deploy
Static site (Vite or Next.js static export — pick the lighter) → GitHub repo → import in Vercel → custom domain.

## Order of work
1. Repo + layer render pipeline (bg / object / fg / hotspots) from `scenes_breakroom.v01`, low-res first.
2. Canvas compositor + door flow + hotspots, with low-res frames.
3. Pages: CV, Brezel, About, blog. Post-it overlay.
4. Final-quality renders, compression, mobile check.
5. Deploy to Vercel.
