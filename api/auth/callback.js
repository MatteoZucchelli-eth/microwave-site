// GET /api/auth/callback: GitHub sends the owner back here. Check state, learn the username, and only for the
// owner set a signed session cookie. The GitHub token is used once to read the username and then dropped.
import { env, cookies, cookie, same, sessionCookies, origin } from '../_lib.js';

const page = (res, status, msg) => {
  res.statusCode = status; res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(`<!doctype html><meta name="viewport" content="width=device-width"><title>${msg}</title>
<body style="font:18px system-ui;padding:3rem;background:#e1e3df;color:#1d1d1b"><p>${msg}</p><p><a href="/">← back to the microwave</a></p>`);
};

export default async function handler(req, res) {
  const { code, state } = req.query;
  const expected = cookies(req).mw_state;
  if (!code || !state || !expected || !same(String(state), expected)) return page(res, 400, 'That login link expired. Try again.');
  const t = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: env('GITHUB_CLIENT_ID'), client_secret: env('GITHUB_CLIENT_SECRET'), code,
      redirect_uri: `${origin(req)}/api/auth/callback` }),
  }).then((r) => r.json()).catch(() => ({}));
  if (!t.access_token) return page(res, 401, 'GitHub did not confirm the login.');
  const u = await fetch('https://api.github.com/user', {
    headers: { Authorization: `Bearer ${t.access_token}`, Accept: 'application/vnd.github+json', 'User-Agent': 'microwave-site-editor' },
  }).then((r) => r.json()).catch(() => ({}));
  const clearState = cookie('mw_state', '', { maxAge: 0, path: '/api/auth' });
  if (!u.login || u.login.toLowerCase() !== env('OWNER_GITHUB_LOGIN').toLowerCase()) {
    res.setHeader('Set-Cookie', clearState);
    return page(res, 403, 'Nice try. This microwave only opens for its owner.');
  }
  res.setHeader('Set-Cookie', [clearState, ...sessionCookies(u.login)]);
  res.statusCode = 302; res.setHeader('Location', '/coffee/'); res.end();
}
