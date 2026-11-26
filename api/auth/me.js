// GET /api/auth/me: is this browser the owner? The editor UI appears only when this says yes.
import { session, clearCookies } from '../_lib.js';

export default function handler(req, res) {
  const login = session(req);
  if (!login) { res.setHeader('Set-Cookie', clearCookies()); return res.status(401).json({ owner: false }); }
  res.status(200).json({ owner: true, login });
}
