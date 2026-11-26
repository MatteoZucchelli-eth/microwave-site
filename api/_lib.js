// Shared helpers for the owner-only editor. Files starting with "_" are not routes on Vercel.
//
// Environment (Vercel project settings):
//   GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET  OAuth app used only to confirm who you are (no scopes requested)
//   OWNER_GITHUB_LOGIN                      the only GitHub username allowed to edit
//   SESSION_SECRET                          random string, >= 32 chars; signs the session cookie
//   CONTENT_REPO                            "owner/repo" of this site
//   CONTENT_BRANCH                          branch Vercel deploys (default "main")
//   GITHUB_CONTENT_TOKEN                    fine-grained token: this repo only, Contents read & write
import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

export const env = (k, d) => {
  const v = process.env[k] ?? d;
  if (v === undefined || v === '') throw new Error(`missing env ${k}`);
  return v;
};

const b64u = (b) => Buffer.from(b).toString('base64url');
const sign = (data) => createHmac('sha256', env('SESSION_SECRET')).update(data).digest('base64url');
const same = (a, b) => a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));

export function cookies(req) {
  return Object.fromEntries((req.headers.cookie || '').split(';').map((c) => c.trim().split('=')).filter((p) => p[0])
    .map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
}
export function cookie(name, value, { maxAge, httpOnly = true, path = '/' } = {}) {
  return [`${name}=${encodeURIComponent(value)}`, `Path=${path}`, 'Secure', 'SameSite=Lax',
    httpOnly && 'HttpOnly', maxAge !== undefined && `Max-Age=${maxAge}`].filter(Boolean).join('; ');
}

const DAY = 86400;
export const SESSION_DAYS = 30;
export function sessionCookies(login) {
  const body = b64u(JSON.stringify({ login, exp: Math.floor(Date.now() / 1000) + SESSION_DAYS * DAY }));
  return [cookie('mw_session', `${body}.${sign(body)}`, { maxAge: SESSION_DAYS * DAY }),
    // readable hint so the editor script only asks the server when it might be you; not a credential
    cookie('mw_owner', '1', { maxAge: SESSION_DAYS * DAY, httpOnly: false })];
}
export const clearCookies = () => [cookie('mw_session', '', { maxAge: 0 }), cookie('mw_owner', '', { maxAge: 0, httpOnly: false })];

export function session(req) {   // -> login or null
  const v = cookies(req).mw_session; if (!v) return null;
  const [body, sig] = v.split('.'); if (!body || !sig || !same(sig, sign(body))) return null;
  try {
    const { login, exp } = JSON.parse(Buffer.from(body, 'base64url').toString());
    if (exp < Date.now() / 1000) return null;
    return login.toLowerCase() === env('OWNER_GITHUB_LOGIN').toLowerCase() ? login : null;
  } catch { return null; }
}

export const nonce = () => randomBytes(18).toString('base64url');
export { same };

export function origin(req) {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  const proto = req.headers['x-forwarded-proto'] || 'https';
  return `${proto}://${host}`;
}
// mutating requests must come from this site (the cookie is SameSite=Lax; this closes the rest)
export const sameOrigin = (req) => req.headers.origin === origin(req);

export async function gh(path, { method = 'GET', body } = {}) {
  const r = await fetch(`https://api.github.com${path}`, {
    method, body: body && JSON.stringify(body),
    headers: { Authorization: `Bearer ${env('GITHUB_CONTENT_TOKEN')}`, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'microwave-site-editor', ...(body && { 'Content-Type': 'application/json' }) },
  });
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  return { ok: r.ok, status: r.status, data };
}
