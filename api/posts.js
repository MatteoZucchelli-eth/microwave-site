// Owner-only content API. Saving commits the Markdown file to the repo; Vercel rebuilds and the page is live in ~1 min.
//   GET    /api/posts                 list coffee posts (incl. drafts): [{ path, name }]
//   GET    /api/posts?path=<file>     { text, sha }
//   PUT    /api/posts  { path, text, sha? }     create or update (sha required to update)
//   DELETE /api/posts  { path, sha }
// Only content/pages/coffee.md and content/coffee/YYYY-MM-DD-<slug>.md can be touched.
import { env, session, sameOrigin, gh } from './_lib.js';

const ALLOWED = /^content\/(pages\/coffee|coffee\/\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*)\.md$/;
const MAX = 200_000;

export default async function handler(req, res) {
  if (!session(req)) return res.status(401).json({ error: 'not signed in' });
  const repo = env('CONTENT_REPO'), branch = env('CONTENT_BRANCH', 'main');
  const at = (p) => `/repos/${repo}/contents/${p}`;

  if (req.method === 'GET') {
    const path = req.query.path;
    if (!path) {
      const r = await gh(`${at('content/coffee')}?ref=${branch}`);
      if (!r.ok) return res.status(502).json({ error: `GitHub ${r.status}` });
      return res.status(200).json(r.data.filter((f) => f.type === 'file' && ALLOWED.test(f.path))
        .map((f) => ({ path: f.path, name: f.name })).sort((a, b) => b.name.localeCompare(a.name)));
    }
    if (typeof path !== 'string' || !ALLOWED.test(path)) return res.status(400).json({ error: 'path not allowed' });
    const r = await gh(`${at(path)}?ref=${branch}`);
    if (r.status === 404) return res.status(404).json({ error: 'not found' });
    if (!r.ok) return res.status(502).json({ error: `GitHub ${r.status}` });
    return res.status(200).json({ text: Buffer.from(r.data.content, 'base64').toString('utf8'), sha: r.data.sha });
  }

  if (!sameOrigin(req)) return res.status(403).json({ error: 'cross-site request' });
  const { path, text, sha } = req.body || {};
  if (typeof path !== 'string' || !ALLOWED.test(path)) return res.status(400).json({ error: 'path not allowed' });

  if (req.method === 'PUT') {
    if (typeof text !== 'string' || !text.trim() || text.length > MAX) return res.status(400).json({ error: 'empty or too long' });
    const name = path.split('/').pop();
    const r = await gh(at(path), { method: 'PUT', body: {
      message: `${sha ? 'coffee: edit' : 'coffee: new'} ${name}`, content: Buffer.from(text, 'utf8').toString('base64'),
      branch, ...(sha && { sha }) } });
    if (r.status === 409 || r.status === 422) return res.status(409).json({ error: 'changed elsewhere (or already exists): reload and try again' });
    if (!r.ok) return res.status(502).json({ error: `GitHub ${r.status}` });
    return res.status(200).json({ sha: r.data.content.sha, commit: r.data.commit.html_url });
  }

  if (req.method === 'DELETE') {
    if (!sha || path === 'content/pages/coffee.md') return res.status(400).json({ error: 'cannot delete this' });
    const r = await gh(at(path), { method: 'DELETE', body: { message: `coffee: delete ${path.split('/').pop()}`, sha, branch } });
    if (!r.ok) return res.status(r.status === 409 ? 409 : 502).json({ error: `GitHub ${r.status}` });
    return res.status(200).json({ ok: true });
  }
  res.status(405).json({ error: 'method not allowed' });
}
