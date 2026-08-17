# FurkAI BIST V15.9.0 QA

## Passed
- Python compile: `server.py`, `api_fast.py`, `notification_service.py`, `backtest_engine.py`
- FastAPI `/` 200
- `/sw.js` 200
- `/manifest.webmanifest` 200
- `/icon-180.png` 200
- `/icon-512.png` 200
- `/api/health` 200, version 15.9.0
- `/api/config` 200, Gemini key masked only
- `/api/portfolio` 200, 11 persisted positions
- `/api/signals` 200
- `/api/universe` 200
- `/api/docs-info` 200
- `/api/notifications/status` 200
- WebSocket `/ws/signals` handshake + connected message passed
- BacktestEngine wrapper + Monte Carlo unit smoke test passed
- ZIP integrity check passed

## Environment limitation
Chromium in the isolated build environment blocks localhost navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`, so an actual Chromium click-through test cannot truthfully be marked passed here. HTTP/API and WebSocket tests were executed directly.
