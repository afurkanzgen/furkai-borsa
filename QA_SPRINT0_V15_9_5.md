# FurkAI BIST V15.9.5 — Sprint 0 QA

## Scope
Dead/duplicate code cleanup only. No new features and no intentional UI/business-logic changes.

## Changes
- Removed unused `.mobile-bottom-nav` CSS blocks; actual mobile navigation remains `.mobile-bar#mobileBar`.
- Removed unused frontend `drawBacktestCurves()` and `runBacktest()` functions left over from the removed Backtest UI.
- Kept `BacktestEngine` backend module because `api_fast.py` still imports/uses it.
- Verified `/api/docs-info` has a single route definition.
- Updated stale test assertions that still expected the removed Backtest UI functions.

## Static checks
- Python syntax: PASS
- JavaScript syntax (`node --check app.js`): PASS
- Duplicate docs-info route: PASS (1 definition)
- Unused mobile-bottom-nav references in application code: PASS (none)
- Backtest UI functions in application code: PASS (none)
- BacktestEngine backend reference: preserved

## HTTP smoke test (uvicorn api_fast:app)
- `/` 200 PASS
- `/app.js` 200 PASS
- `/sw.js` 200 PASS
- `/manifest.webmanifest` 200 PASS
- `/icon-180.png` 200 PASS
- `/api/health` 200 PASS
- `/api/config` 200 PASS
- `/api/portfolio` 200 PASS
- `/api/signals` 200 PASS
- `/api/dividends-dashboard` 200 PASS
- `/api/scan` reached 200 in the running server, but the external data path can be slow in the sandbox
- `/api/market-regime` not completed within the smoke-test timeout due external data dependency

## Existing test suite
`pytest -q test_engine.py` does NOT currently provide a clean baseline. The first failure is an older assertion expecting `<th>Sinyal Fiyatı</th>` in `index.html`; this is unrelated to Sprint 0 cleanup. The suite also contains other legacy expectations. We did not fabricate a PASS.

## Browser test
Not claimed. Chromium/Playwright is unavailable/blocked in this environment, so real click/visual/theme testing must be performed in a real browser environment.
