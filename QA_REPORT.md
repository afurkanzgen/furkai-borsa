# FurkAI BIST V15.0 — Final QA

## 10x QA loop
1. Re-check → found invalid JavaScript (`async async async async`). Fixed.
2. Re-check → WSGI lacked HEAD support. Fixed root/static/API public HEAD handling.
3. Re-check → regression tests expected old WSGI strings. Updated tests and added HEAD/JS regression coverage.
4. Re-check → live local HTTP smoke test: HEAD/GET root and health all 200.
5. Re-check → direct WSGI HEAD/GET smoke test: root, health, config, data-status and PWA assets all pass.
6. Re-check → PWA/mobile shell inspected: manifest, iPhone icon, service worker and safe-area/mobile rules present.
7. Re-check → duplicate JS functions and scanner model inventory checked; 27 models present.
8. Re-check → secret/key storage and unsafe dynamic HTML insertion checked; Gemini key is encrypted and no plaintext key is bundled.
9. Re-check → Render deployment config hardened: WSGI start command, `/api/health` health check, and `FURKAI_SECRET_KEY` environment variable.
10. Final re-check → clean release package, Python compile, JS syntax, full regression suite, ZIP integrity, and no bundled secret/runtime artifacts.

## Automated results
- Regression suite: **51/51 PASS**
- Python compile: **PASS**
- JavaScript syntax (`node --check`): **PASS**
- Local HTTP HEAD/GET smoke test: **PASS**
- WSGI HEAD/GET smoke test: **PASS**
- PWA manifest/icon/service worker checks: **PASS**
- 27 scanner models: **PASS**
- No duplicate critical JS functions: **PASS**
- No plaintext Gemini API key bundled: **PASS**
- No `.furkai_secret` bundled: **PASS**
- ZIP integrity: **PASS**

## Deployment note
Render should use `python server_wsgi.py`, health check `/api/health`, and a persistent `FURKAI_SECRET_KEY` environment secret. Never commit a Gemini API key or `.furkai_secret` to GitHub.
