// GET /api/auth/login (also /login): send the owner to GitHub to confirm who they are. No scopes: identity only.
import { env, cookie, nonce, origin } from '../_lib.js';

export default function handler(req, res) {
  const state = nonce();
  const url = new URL('https://github.com/login/oauth/authorize');
  url.searchParams.set('client_id', env('GITHUB_CLIENT_ID'));
  url.searchParams.set('redirect_uri', `${origin(req)}/api/auth/callback`);
  url.searchParams.set('state', state);
  url.searchParams.set('allow_signup', 'false');
  res.setHeader('Set-Cookie', cookie('mw_state', state, { maxAge: 600, path: '/api/auth' }));
  res.statusCode = 302; res.setHeader('Location', url.toString()); res.end();
}
