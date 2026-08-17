# FurkAI BIST V15.9.6 — Multi-user Sprint QA

## Scope
- Open user registration
- Session-based login/logout
- User/portfolio isolation
- Shared Gemini key (admin-only write)
- Legacy single-portfolio migration safety
- Production FastAPI auth path

## Verified
- `python -m py_compile server.py api_fast.py server_wsgi.py` — PASS
- `node --check app.js` — PASS
- `GET /api/health` — 200
- Unauthenticated `GET /api/portfolio` — 401
- Admin bootstrap login from `FURKAI_USER/FURKAI_PASSWORD` — PASS
- Existing legacy portfolio preserved: 11 rows assigned to bootstrap admin
- Open registration — PASS
- Second user initially receives empty portfolio — PASS
- Second user can save its own portfolio — PASS
- First user's 11-position portfolio remains unchanged after second user's save — PASS
- User passwords stored as salted PBKDF2-HMAC-SHA256 hashes; no plaintext password column — PASS
- Session token login/me/logout — PASS
- Shared Gemini key visible only as masked status — PASS
- Non-admin Gemini/config write — HTTP 403 — PASS
- Admin shared-config write — PASS
- `/app.js` and PWA static files served by production `api_fast.py` — PASS
- Legacy `server.py`/WSGI portfolio paths updated to require the authenticated user and filter by `user_id`.

## Migration safety
- `portfolio.user_id` is added as a nullable column for existing databases.
- In production (`FURKAI_REQUIRE_AUTH=1`), the pre-existing portfolio is claimed only by the configured bootstrap admin (`FURKAI_USER` + `FURKAI_PASSWORD`).
- In local development (`FURKAI_REQUIRE_AUTH!=1`), the first registered account can claim the pre-existing local portfolio.
- New registrations never receive another user's portfolio.

## Not in this sprint
- Render persistent disk
- Portfolio history/equity curve
- API error contract standardization
- CORS tightening
- Price alerts
- CSV/Excel export
- WebSocket broadcast optimization
- Static cache headers
