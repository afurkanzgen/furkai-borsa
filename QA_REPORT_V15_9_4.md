# FurkAI BIST V15.9.4 QA

## Changes
- Removed Backtest from the user-facing sidebar and page section.
- Reworked Temettü into: portfolio dividend holdings, FurkAI dividend candidates, and single-stock dividend history.
- Added `/api/dividends-dashboard` with background refresh so external dividend data cannot block page navigation.
- Candidate score uses historical dividend regularity, last-12-month dividend yield and recency; it is explicitly not a balance-sheet sustainability score.
- Kept Backtest backend/module intact for compatibility; it is no longer exposed in navigation.

## Static checks
- `python -m py_compile server.py api_fast.py` PASS
- `node --check app.js` PASS
- Backtest navigation/section in index.html: 0 occurrences PASS
- 8 user-facing sidebar pages remain PASS
- Theme buttons: dark/light/system present PASS

## Production HTTP smoke test
- GET / -> 200 PASS
- GET /app.js?v=15.9.4 -> 200 PASS
- GET /manifest.webmanifest -> 200 PASS
- GET /sw.js -> 200 PASS
- GET /api/health -> 200 PASS
- GET /api/portfolio -> 200 PASS
- GET /api/dividends-dashboard -> 200 in ~0.01s with background refresh PASS

## Data note
The sandbox cannot reach Yahoo Finance reliably. The dividend dashboard therefore returns a non-blocking `loading` state and refreshes in the background; no fake dividend values are generated.
