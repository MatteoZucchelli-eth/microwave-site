// POST /api/auth/logout
import { clearCookies, sameOrigin } from '../_lib.js';

export default function handler(req, res) {
  if (req.method !== 'POST' || !sameOrigin(req)) return res.status(405).json({ error: 'POST from this site only' });
  res.setHeader('Set-Cookie', clearCookies()); res.status(200).json({ ok: true });
}
