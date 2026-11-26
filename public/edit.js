// Owner-only editor for the coffee blog. Visitors never see it: it does nothing unless the mw_owner hint cookie is
// set (only after GitHub sign-in at /login), and then only if the server confirms the signed session.
// Saving commits Markdown to the repo (api/posts.js); Vercel rebuilds, live in ~1 min.
(async () => {
  if (!document.cookie.split('; ').includes('mw_owner=1')) return;
  const me = await fetch('/api/auth/me').catch(() => null);
  if (!me || !me.ok) return;

  const kind = document.body.className, file = document.body.dataset.file;
  const api = (method, body, q = '') => fetch('/api/posts' + q, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body && JSON.stringify(body),
  }).then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }));
  const el = (tag, attrs = {}, ...kids) => { const e = Object.assign(document.createElement(tag), attrs); e.append(...kids); return e; };
  const today = () => new Date().toISOString().slice(0, 10);
  const slugify = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'untitled';

  // front matter <-> { meta (ordered), body }
  function parse(text) {
    const meta = new Map(); let body = text;
    if (text.startsWith('---\n')) {
      const end = text.indexOf('\n---\n', 4);
      if (end > 0) {
        for (const line of text.slice(4, end).split('\n')) { const i = line.indexOf(':'); if (i > 0) meta.set(line.slice(0, i).trim(), line.slice(i + 1).trim()); }
        body = text.slice(end + 5).replace(/^\n/, '');
      }
    }
    return { meta, body };
  }
  const serialize = (meta, body) => `---\n${[...meta].filter(([, v]) => v !== '').map(([k, v]) => `${k}: ${v}`).join('\n')}\n---\n\n${body.trim()}\n`;

  // ---------- owner bar ----------
  const bar = el('div', { className: 'owner-bar' });
  const btn = (label, fn) => bar.append(el('button', { type: 'button', textContent: label, onclick: fn }));
  if (kind === 'post' && file) btn('✎ edit', () => open(file));
  if (kind === 'coffee' && file) btn('✎ edit about', () => open(file));
  btn('+ new post', () => open(null));
  btn('all posts', list);
  btn('log out', async () => { await fetch('/api/auth/logout', { method: 'POST' }); location.reload(); });
  document.body.append(bar);

  // ---------- editor ----------
  async function open(path) {
    let meta = new Map([['title', '']]), body = '', sha = null;
    if (path) {
      const r = await api('GET', null, `?path=${encodeURIComponent(path)}`);
      if (!r.ok) return alert(`Could not load: ${r.data.error || r.status}`);
      ({ meta, body } = parse(r.data.text)); sha = r.data.sha;
    }
    const isAbout = path === 'content/pages/coffee.md', isNew = !path;
    const key = `mw-backup:${path || 'new'}`, backup = JSON.parse(localStorage.getItem(key) || 'null');

    const title = el('input', { className: 'ed-title', placeholder: 'Title', value: meta.get('title') || '' });
    const date = el('input', { type: 'date', value: isNew ? today() : (path.match(/(\d{4}-\d{2}-\d{2})/) || [])[1] || '', disabled: !isNew });
    const slug = el('input', { placeholder: 'url-slug', value: isNew ? '' : (path.match(/\d{4}-\d{2}-\d{2}-(.+)\.md$/) || [])[1] || '', disabled: !isNew });
    const draft = el('input', { type: 'checkbox', checked: meta.get('draft') === 'true' });
    const text = el('textarea', { className: 'ed-body', placeholder: 'Write. Markdown works: ## heading, **bold**, [link](https://…), - lists.', value: body });
    const status = el('p', { className: 'ed-status' });
    let slugTouched = !isNew, dirty = false;
    slug.oninput = () => { slugTouched = true; };
    title.oninput = () => { if (!slugTouched) slug.value = slugify(title.value); save_local(); };
    text.oninput = save_local;
    function save_local() { dirty = true; localStorage.setItem(key, JSON.stringify({ title: title.value, body: text.value, at: Date.now() })); }
    if (backup && (backup.body !== body || backup.title !== (meta.get('title') || ''))) {
      const restore = el('button', { type: 'button', textContent: `restore unsaved text from ${new Date(backup.at).toLocaleString()}`,
        onclick: () => { title.value = backup.title; text.value = backup.body; if (!slugTouched) slug.value = slugify(title.value); restore.remove(); dirty = true; } });
      status.append(restore);
    }

    const save = el('button', { type: 'button', className: 'ed-save', textContent: isNew ? 'publish' : 'save' });
    const cancel = el('button', { type: 'button', textContent: 'close' });
    const del = el('button', { type: 'button', className: 'ed-del', textContent: 'delete' });
    draft.onchange = () => { save.textContent = draft.checked ? 'save draft' : isNew ? 'publish' : 'save'; };
    draft.onchange();

    save.onclick = async () => {
      if (!isAbout && !title.value.trim()) return (status.textContent = 'Needs a title.');
      if (!text.value.trim()) return (status.textContent = 'Nothing to save yet.');
      const target = path || `content/coffee/${date.value}-${slugify(slug.value || title.value)}.md`;
      meta.set('title', title.value.trim().replace(/\n/g, ' '));
      if (!isAbout) { if (draft.checked) meta.set('draft', 'true'); else meta.delete('draft'); }
      save.disabled = true; status.textContent = 'saving…';
      const r = await api('PUT', { path: target, text: serialize(meta, text.value), ...(sha && { sha }) });
      save.disabled = false;
      if (!r.ok) return (status.textContent = `Not saved: ${r.data.error || r.status}`);
      sha = r.data.sha; path = target; dirty = false; localStorage.removeItem(key);
      status.textContent = draft.checked ? 'Draft saved (not public). Find it under "all posts".'
        : 'Saved. Vercel is rebuilding: live in about a minute.';
    };
    cancel.onclick = () => { if (!dirty || confirm('Close without saving? (a local backup is kept)')) modal.remove(); };
    del.onclick = async () => {
      if (!confirm('Delete this post for good?')) return;
      const r = await api('DELETE', { path, sha });
      if (!r.ok) return (status.textContent = `Not deleted: ${r.data.error || r.status}`);
      localStorage.removeItem(key); status.textContent = 'Deleted. Gone from the site after the rebuild.';
      setTimeout(() => (location.href = '/coffee/'), 1500);
    };

    const row = el('div', { className: 'ed-row' });
    if (!isAbout) row.append(el('label', {}, 'date ', date), el('label', {}, '/coffee/', slug), el('label', { className: 'ed-check' }, draft, ' draft (not public)'));
    const actions = el('div', { className: 'ed-actions' }, save, cancel); if (path && !isAbout) actions.append(del);
    const modal = el('div', { className: 'ed-modal' }, el('div', { className: 'ed-sheet' },
      el('p', { className: 'ed-kicker' }, isAbout ? 'the about, on top of /coffee' : isNew ? 'new post' : 'editing'), title, row, text, actions, status));
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') cancel.onclick();
      if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); save.onclick(); }
    });
    document.body.append(modal); (isNew ? title : text).focus();
  }

  async function list() {
    const r = await api('GET');
    if (!r.ok) return alert(`Could not list posts: ${r.data.error || r.status}`);
    const ul = el('ul', { className: 'ed-list' });
    for (const p of r.data) ul.append(el('li', {}, el('button', { type: 'button', textContent: p.name.replace(/\.md$/, ''), onclick: () => { modal.remove(); open(p.path); } })));
    if (!r.data.length) ul.append(el('li', { textContent: 'no posts yet' }));
    const modal = el('div', { className: 'ed-modal', onclick: (e) => e.target === modal && modal.remove() },
      el('div', { className: 'ed-sheet ed-small' }, el('p', { className: 'ed-kicker' }, 'all posts, drafts included'), ul,
        el('div', { className: 'ed-actions' }, el('button', { type: 'button', textContent: 'close', onclick: () => modal.remove() }))));
    document.body.append(modal);
  }
})();
