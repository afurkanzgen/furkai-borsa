# FurkAI BIST V15.9.2 — Navigation/Page Integrity Fix

## Root cause addressed
Page switching relied primarily on CSS `.section { display:none!important }`. In a stale/cached UI or after duplicated CSS rules, an old section could remain visually present while the selected page rendered farther down the document. This produced the observed symptom where Portföy/Temettü appeared below Tarama content instead of replacing it.

## Fix
`go(page)` now targets only `main.main > .section` and applies inline `display`/`visibility` with `!important` to every section. Exactly one section is visible after every navigation action. The main container and window scroll positions are reset to the top.

## Cache migration
Service-worker cache was bumped from `furkai-v15.9.0-shell` to `furkai-v15.9.2-shell`. A new worker is registered with a versioned URL so stale UI assets are not reused.

## Static checks
- Python compile: PASS
- 9 navigation sections: PASS
- Every sidebar page has matching `data-page`: PASS
- `go()` sets exactly one visible section: PASS
- SW cache version: PASS
- ZIP integrity: PASS

## Important
The previous screenshot showing `V15.9.0` is the older package. This fixed package must show `V15.9.2` in the sidebar.
