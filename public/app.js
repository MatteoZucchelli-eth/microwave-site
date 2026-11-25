// The breakroom microwave. Composites pre-rendered Cycles layers (sprite sheets) on a full-page canvas.
//   view A (wide):  closed  = A_fg_closed + A_closed_<id>        opening/closing = A_bg + A_open_<id> + A_door[i]
//   view B (close): open    = B_bg + B_open_<id>
//   A -> B: once the door is open, A zooms onto the cavity while B fades in, both aligned on the cavity opening.
// Objects are drawn far -> near by the per-frame depth in manifest.json. See blender/layers.py.

const R = 'render/lo/';
const REV_S = 7;            // seconds per plate revolution
const DOOR_FPS = 30;
const ZOOM_MS = 1400;
const COUNTDOWN_S = 5;
const LIFT = 3;             // hover lift, render px
const POST = { title: 'NEW POST:\nwhy robots\nneed jokes →', url: '/blog' };   // step 3: latest blog post
const seen = localStorage.getItem('mw-seen') === '1';

const $ = (id) => document.getElementById(id);
const stage = $('stage'), cv = $('cv'), ctx = cv.getContext('2d');
const json = (p) => fetch(p).then((r) => r.json());
const [man, projects] = await Promise.all([json(R + 'manifest.json'), json('projects.json')]);
const N = man.frames, D = man.door_frames, V = man.views;
const ids = projects.filter((p) => !p.hidden && man.objects[p.id]?.A && man.objects[p.id]?.B).map((p) => p.id);
const meta = Object.fromEntries(projects.map((p) => [p.id, p]));
const obj = (id, v) => man.objects[id][v];

// ---------- loading: a dozen sprite sheets; the countdown is the loader ----------
const img = {};
const load = (name) => new Promise((ok) => {
  const im = new Image(); im.src = R + name;
  im.decode().then(() => ok((img[name] = im)), () => ok(null));     // failed sheet -> skipped when drawing
});
const closedReady = Promise.all(['A_fg_closed.webp', ...ids.map((id) => obj(id, 'A').closed.sheet)].map(load));
const allReady = closedReady.then(() => Promise.all(
  ['A_bg.webp', man.door.sheet, 'B_bg.webp', ...ids.flatMap((id) => [obj(id, 'A').open.sheet, obj(id, 'B').open.sheet])].map(load)));
let spinning = false, allLoaded = false, t0 = performance.now();
closedReady.then(() => { spinning = true; t0 = performance.now(); });
allReady.then(() => { allLoaded = true; });

// ---------- per-view offscreen composition ----------
const off = {};
for (const v of ['A', 'B']) { const c = document.createElement('canvas'); c.width = V[v].w; c.height = V[v].h; off[v] = c.getContext('2d'); }
function piece(c, sheet, r, dy = 0) {   // r = [sx, sy, w, h, dx, dy] from the packer
  const im = img[sheet]; if (!im || !r) return;
  c.drawImage(im, r[0], r[1], r[2], r[3], r[4], r[5] - dy, r[2], r[3]);
}
const order = (v, f) => ids.slice().sort((a, b) => obj(b, v).boxes[f][4] - obj(a, v).boxes[f][4]);   // far -> near
function compose(v, f, door) {   // door: -1 = exact closed frame (A only), else door frame index
  const c = off[v], closed = v === 'A' && door < 0;
  const bg = img[closed ? 'A_fg_closed.webp' : `${v}_bg.webp`]; if (!bg) return false;
  c.drawImage(bg, 0, 0);
  for (const id of order(v, f)) {
    const layer = closed ? obj(id, 'A').closed : obj(id, v).open;
    piece(c, layer.sheet, layer.rects[f], v === 'B' ? lift[id] : 0);
  }
  if (v === 'A' && door >= 0) piece(c, man.door.sheet, man.door.rects[door]);
  return true;
}

// ---------- layout: show the base framing, but never crop the focus (A: microwave, B: cavity) ----------
const L = { A: {}, B: {} };
const bbox = (q) => { const xs = q.map((p) => p[0]), ys = q.map((p) => p[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; };
let vw = 0, vh = 0, dpr = 1;
const sweep = ids.flatMap((id) => obj(id, 'B').boxes).reduce((u, b) =>
  [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])], [1, 1, 0, 0]);   // where B's objects ever are
function fit() {
  vw = innerWidth; vh = innerHeight; dpr = Math.min(2, devicePixelRatio || 1);
  cv.width = Math.round(vw * dpr); cv.height = Math.round(vh * dpr);
  for (const v of ['A', 'B']) {
    const m = V[v], [bx, by, bw, bh] = m.base;
    let [x0, y0, x1, y1] = v === 'A' ? bbox(m.focus) : sweep;   // B: keep the objects, let the cavity sides crop
    x0 -= 0.04; x1 += 0.04; y0 -= 0.04; y1 += 0.04;
    const fw = (x1 - x0) * m.w, fh = (y1 - y0) * m.h;
    const s = Math.min(Math.max(vw / bw, vh / bh), vw / fw, vh / fh);
    const place = (view, size, c) => size >= view ? Math.min(0, Math.max(view - size, view / 2 - c * size)) : (view - size) / 2;
    L[v] = { s, tx: place(vw, m.w * s, (x0 + x1) / 2), ty: place(vh, m.h * s, (y0 + y1) / 2) };
  }
}
addEventListener('resize', fit); fit();
let edge = '#dcdfdb';
closedReady.then(() => {   // colour for the (rare) area beyond the overscan, sampled from the render's corner
  const c = off.A; c.drawImage(img['A_fg_closed.webp'], 0, 0);
  edge = `rgb(${c.getImageData(1, 1, 1, 1).data.slice(0, 3).join(',')})`; document.body.style.background = edge;
});

// transition: interpolate the on-screen cavity rect from A's to B's; each view is drawn so its cavity lands there
const cavRect = (v, t) => { const [x0, y0, x1, y1] = bbox(V[v].cavity); return { x: ((x0 + x1) / 2) * V[v].w * t.s + t.tx, y: ((y0 + y1) / 2) * V[v].h * t.s + t.ty, w: (x1 - x0) * V[v].w * t.s }; };
function zoomed(v, p) {
  const a = cavRect('A', L.A), b = cavRect('B', L.B), own = v === 'A' ? a : b;
  const w = a.w ** (1 - p) * b.w ** p, x = a.x + (b.x - a.x) * p, y = a.y + (b.y - a.y) * p;
  const s = L[v].s * (w / own.w), cx = (own.x - L[v].tx) / L[v].s, cy = (own.y - L[v].ty) / L[v].s;
  return { s, tx: x - cx * s, ty: y - cy * s };
}
function blit(v, t, alpha = 1) {
  ctx.globalAlpha = alpha;
  ctx.setTransform(t.s * dpr, 0, 0, t.s * dpr, t.tx * dpr, t.ty * dpr);
  ctx.drawImage(off[v].canvas, 0, 0);
  ctx.globalAlpha = 1;
}

// ---------- homography: map an element box (w x h) onto a screen quad ----------
function solve(A, b) {  // gaussian elimination, 8x8
  const n = b.length; A = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c; for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    [A[c], A[p]] = [A[p], A[c]];
    for (let r = 0; r < n; r++) if (r !== c) { const k = A[r][c] / A[c][c]; for (let j = c; j <= n; j++) A[r][j] -= k * A[c][j]; }
  }
  return A.map((r, i) => r[n] / r[i]);
}
const boxes = new WeakMap();
function mapQuad(el, quad, v, t) {
  if (!boxes.has(el)) boxes.set(el, [el.offsetWidth, el.offsetHeight]);
  const [w, h] = boxes.get(el), src = [[0, 0], [w, 0], [w, h], [0, h]];
  const dst = quad.map(([x, y]) => [x * V[v].w * t.s + t.tx, y * V[v].h * t.s + t.ty]); const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, q] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -q * x, -q * y]); b.push(q);
  }
  const m = solve(A, b);
  el.style.transform = `matrix3d(${m[0]},${m[3]},0,${m[6]},${m[1]},${m[4]},0,${m[7]},0,0,1,0,${m[2]},${m[5]},0,1)`;
}
$('postit').href = POST.url; $('postit-text').textContent = POST.title;

// ---------- state: closed -> opening -> zoomin -> open -> zoomout -> closing -> closed ----------
let state = 'closed', tState = 0, openedOnce = false; const tLand = performance.now();
let hovered = null; const lift = Object.fromEntries(ids.map((id) => [id, 0]));
const openBtn = $('open-btn');
function setState(s) {
  state = s; tState = performance.now();
  stage.classList.toggle('open', s === 'open');
  openBtn.setAttribute('aria-label', s === 'closed' ? 'Open the microwave door' : 'Close the microwave door');
  if (s === 'opening' || s === 'open') { localStorage.setItem('mw-seen', '1'); openedOnce = true; }
  if (s !== 'open') setHover(null);
}
function toggleDoor() {
  if (state === 'closed' && allLoaded) setState('opening');
  else if (state === 'open') setState('zoomout');
}
openBtn.addEventListener('click', toggleDoor);
$('close').addEventListener('click', toggleDoor);
addEventListener('keydown', (e) => { if (e.key === 'Escape' && state === 'open') toggleDoor(); });

// ---------- display: countdown, then the time ----------
const digits = $('digits'), pad = (n) => String(n).padStart(2, '0');
function updateDisplay(now) {
  let txt, blink = false;
  if (!openedOnce) {
    const left = Math.max(0, Math.ceil(COUNTDOWN_S - (now - tLand) / 1000));
    if (seen) txt = allLoaded ? '0:00' : '----';
    else if (left > 0) txt = `0:0${left}`;
    else { txt = allLoaded ? '0:00' : '0:01'; blink = !allLoaded; }   // holds on 0:01 until the last sheet is in
  } else {
    const d = new Date(); txt = `${d.getHours()}${d.getSeconds() % 2 ? ' ' : ':'}${pad(d.getMinutes())}`;
  }
  if (digits.textContent !== txt) digits.textContent = txt;
  digits.classList.toggle('blink', blink);
}

// ---------- hotspots (view B) ----------
const hot = $('hot'); const links = {};
for (const id of ids) {
  const p = meta[id], a = document.createElement('a');
  a.href = p.url || '#'; a.setAttribute('aria-label', p.url ? p.title : `${p.title}: not public yet`);
  a.innerHTML = `<span class="label">${p.title}</span>`;
  a.addEventListener('focus', () => setHover(id)); a.addEventListener('blur', () => setHover(null));
  a.addEventListener('click', (e) => { if (!p.url) { e.preventDefault(); nope(id); } });
  hot.append(a); links[id] = a;
}
function nope(id) { const a = links[id]; a.classList.remove('nope'); void a.offsetWidth; a.classList.add('nope'); }
function setHover(id) {
  if (hovered === id) return; hovered = id;
  for (const k of ids) links[k].classList.toggle('on', k === id);
  stage.classList.toggle('hovering', !!id);
}
const probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true }); probe.canvas.width = probe.canvas.height = 1;
let curF = 0;
function hit(clientX, clientY) {   // nearest object whose own pixels (not its shadow) are under the pointer
  const t = L.B, x = (clientX - t.tx) / t.s, y = (clientY - t.ty) / t.s, f = curF;
  for (const id of order('B', f).reverse()) {
    const [x0, y0, x1, y1] = obj(id, 'B').boxes[f], ly = y + lift[id], o = obj(id, 'B').open, r = o.rects[f], im = img[o.sheet];
    if (!r || !im || x < x0 * V.B.w || x > x1 * V.B.w || ly < y0 * V.B.h || ly > y1 * V.B.h) continue;
    const sx = r[0] + Math.floor(x - r[4]), sy = r[1] + Math.floor(ly - r[5]);
    if (sx < r[0] || sy < r[1] || sx >= r[0] + r[2] || sy >= r[1] + r[3]) continue;
    probe.clearRect(0, 0, 1, 1); probe.drawImage(im, sx, sy, 1, 1, 0, 0, 1, 1);
    const [cr, cg, cb, ca] = probe.getImageData(0, 0, 1, 1).data;
    if (ca > 128 && Math.max(cr, cg, cb) > 10) return id;
  }
  return null;
}
stage.addEventListener('pointermove', (e) => {
  if (state !== 'open' || e.pointerType === 'touch') return;
  if (e.target !== cv) return setHover(null);
  setHover(hit(e.clientX, e.clientY));
});
stage.addEventListener('pointerleave', () => setHover(null));
cv.addEventListener('click', (e) => {
  if (state === 'closed') return toggleDoor();   // click anywhere to open
  if (state !== 'open') return;
  const id = hit(e.clientX, e.clientY); if (!id) return;
  if (meta[id].url) location.href = meta[id].url; else nope(id);
});
if (matchMedia('(pointer: coarse)').matches) document.body.classList.add('touch');

// ---------- render loop ----------
const ease = (p) => p < 0.5 ? 4 * p * p * p : 1 - (-2 * p + 2) ** 3 / 2;
const show = (el, on) => el.classList.toggle('off', !on);
function frame(now) {
  requestAnimationFrame(frame);
  if (!img['A_fg_closed.webp']) return;
  const f = spinning ? Math.floor(((now - t0) / 1000 / REV_S) * N) % N : 0; curF = f;
  const el = now - tState;

  // advance the state machine
  if (state === 'closed' && allLoaded && !openedOnce && (seen || (now - tLand) / 1000 >= COUNTDOWN_S + 0.4)) setState('opening');   // ding
  if ((state === 'opening' || state === 'closing') && el / 1000 * DOOR_FPS >= D) setState(state === 'opening' ? 'zoomin' : 'closed');
  else if ((state === 'zoomin' || state === 'zoomout') && el >= ZOOM_MS) setState(state === 'zoomin' ? 'open' : 'closing');
  const t = now - tState;   // elapsed in the (possibly new) state
  const i = Math.min(D - 1, Math.floor(t / 1000 * DOOR_FPS));
  for (const id of ids) lift[id] += ((hovered === id ? LIFT : 0) - lift[id]) * 0.25;
  stage.classList.toggle('openable', state === 'closed' && allLoaded);

  // draw
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = edge; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.imageSmoothingQuality = 'high';
  let view = 'A', tA = L.A, door = -1;
  if (state === 'opening') door = i;
  else if (state === 'closing') door = D - 1 - i;
  if (state === 'zoomin' || state === 'zoomout') {
    const p = ease(Math.min(1, t / ZOOM_MS)), q = state === 'zoomin' ? p : 1 - p;
    compose('A', f, D - 1); compose('B', f, -1);
    blit('A', zoomed('A', q)); blit('B', zoomed('B', q), Math.min(1, Math.max(0, (q - 0.15) / 0.6)));
    view = null;
  } else if (state === 'open') { view = 'B'; compose('B', f, -1); blit('B', L.B); }
  else { compose('A', f, door); blit('A', tA); }

  // overlays
  const inA = view === 'A', inB = view === 'B';
  show($('display'), inA || inB); show(openBtn, inA || inB); show($('postit'), inA);
  if (inA || inB) { mapQuad($('display'), V[view].display, view, L[view]); mapQuad(openBtn, V[view].open_button, view, L[view]); }
  if (inA) mapQuad($('postit'), man.door.postit[Math.max(0, door)], 'A', tA);
  if (inB) for (const id of ids) {
    const [x0, y0, x1, y1] = obj(id, 'B').boxes[f], t = L.B, s = links[id].style;
    s.left = x0 * V.B.w * t.s + t.tx + 'px'; s.top = (y0 * V.B.h - lift[id]) * t.s + t.ty + 'px';
    s.width = (x1 - x0) * V.B.w * t.s + 'px'; s.height = (y1 - y0) * V.B.h * t.s + 'px';
  }
  updateDisplay(now);
}
requestAnimationFrame(frame);
