# FurkAI BIST V15.9.3 — Production Static + Runtime Smoke QA

## Fixed
- Production FastAPI entrypoint (`api_fast.py`) now explicitly serves `/app.js`.
- Removed the duplicate `/api/docs-info` route.
- Did NOT mount the whole project directory as `/` static content; sensitive files such as `config.json`, `server.py`, and `furkai_bist.db` remain inaccessible over HTTP.
- Runtime version unified to V15.9.3 in application/config/UI assets.
- Service-worker cache version bumped to V15.9.3.

## Real HTTP tests
- `/` -> 200
- `/app.js` -> 200
- `/app.js?v=15.9.3` -> 200
- `/sw.js` -> 200
- `/manifest.webmanifest` -> 200
- `/icon-180.png` -> 200
- `/icon-512.png` -> 200
- `/api/health` -> 200
- `/api/config` -> 200
- `/api/portfolio` -> 200
- `/api/signals` -> 200
- `/api/universe` -> 200
- `/api/kap` -> 200
- `/api/docs-info` -> 200
- `/config.json` -> 404 (not publicly exposed)
- `/server.py` -> 404 (not publicly exposed)
- `/furkai_bist.db` -> 404 (not publicly exposed)

## WebSocket
- `/ws/signals` connection -> PASS
- Initial connection message returned version `15.9.3`.

## Static/DOM checks
- 9 main sections found and mapped to 9 sidebar navigation buttons.
- Theme controls: Dark / Light / System -> all present.
- Duplicate HTML IDs -> 0.
- `/app.js?v=15.9.3` referenced by index.html.

## Browser limitation
The execution environment blocks Chromium navigation to local HTTP/file URLs with `ERR_BLOCKED_BY_ADMINISTRATOR`, so real visual click testing could not be honestly marked as passed here. HTTP and DOM checks above were run independently.

## Important note
The older `test_engine.py` suite contains historical assertions tied to previous versions and to JavaScript that has since been moved from `index.html` into `app.js`; it is not a valid V15.9.3 regression suite. It was not silently counted as passing.
