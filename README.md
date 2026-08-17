# FurkAI BIST v15.8

BIST analiz, tarama, portföy ve long-only backtest terminali.

## v15.8 güvenlik ve QA düzeltmeleri

- Gemini API anahtarı artık `config.json` içinde şifreli (Fernet) saklanır; deploy ortamında `FURKAI_SECRET_KEY` kullanılması önerilir.
- Ayarlar ekranına Gemini bağlantı testi ve veri sağlığı göstergeleri eklendi.
- Config dosyası ve yerel secret dosyası için kullanıcıya özel dosya izinleri uygulanır.
- Health/config sürüm bilgisi 15.8 ile tutarlı hale getirildi.

## v14 düzeltmeleri

- AND/OR multi-model scanner semantics corrected: OR defaults to at least one selected model; optional `min_models` can tighten the threshold.
- Added regression tests for OR/AND behavior and explicit OR thresholds.
- Tamamlanmamış günlük BIST mumu piyasa kapanışından önce analiz/taramadan çıkarılır.
- RSI ve ADX Wilder smoothing ile hesaplanır; ATR de Wilder/RMA kullanır.
- Backtest tamamlanmış günlük kapanıştan karar verir, sonraki seans açılışında execute eder.
- Son kararın emri test penceresinin dışına taşmaz; açık pozisyon son kapanışta mark-to-market edilir.
- Backtest 5 yıllık veri içinden 200 bar warm-up + tam N karar günü + 1 execution bar kullanır.
- Sinyal performansı ile backtest performansı ayrı kavramlardır.
- Score dağılım çubukları gerçek bileşen ağırlıklarına göre ölçeklenir.
- Test suite bütün testleri gerçekten çalıştırır; dosyanın ortasında erken çıkış yoktur.

## Modlar
- BIST spot odaklı, backtest LONG-only.
- KAP otomatik bildirimleri uydurulmaz; resmi KAP aramasına yönlendirilir.
- Gemini anahtarı backend'de şifreli tutulur. `gemini-3.6-flash` GA/production-ready bir modeldir.

## Çalıştırma
`python server.py`

Production deploy için Render environment variables: `FURKAI_USER`, `FURKAI_PASSWORD`, `FURKAI_REQUIRE_AUTH=1`.

- BIST Pay Piyasası tam gün kapanışı 18:10, 2024-2026 resmi yarım günleri 13:00 olarak modellenir.
- Sinyal geçmişi 1G/5G/20G değerlerini takvim günü değil, tamamlanmış işlem barı üzerinden hesaplar.
- Render deployment Waitress ile gerçek WSGI sunucusuna geçirilmiştir; yerel `python server.py` geliştirme sunucusu olarak kalır.
- Login ekranı yanlış kimlik bilgilerinde açık hata mesajı verir.

## Hardened QA sonrası ek düzeltmeler
- Score-only taramalar sinyal geçmişinde `FurkAI Score` provenance'ı ile saklanır.
- Yahoo split olayları geçmiş OHLCV serisine uygulanır; nakit temettüler fiyat serisine yapıştırılmaz.
- Sinyal duplicate kontrolü BIST yerel gününe göre yapılır ve model kümesi canonical sıralanır.
- Portföy kayıtları backend'de sembol/adet/maliyet/ID doğrulamasından geçer.
- Render'da auth zorunlu; yerel çıplak `python server.py` çalıştırması parola olmadan kilitlenmez.
- Dinamik frontend hata çıktıları HTML-escape edilir.
- Final regression suite: **47/47 PASS**.

## Başlangıç Portföyü
Uygulama ilk kez boş SQLite veritabanıyla başlatıldığında, kullanıcının 13 Ağustos 2026 tarihli son portföy ekranından girilen 11 pozisyon otomatik olarak başlangıç portföyüne alınır. Sonraki çalıştırmalarda mevcut veritabanı korunur.


## V15.8.7.2 Mobile/PWA
- iPhone/Android responsive layout under 700px.
- Bottom navigation for Ana, Tarama, Grafik, Portföy, Ayarlar.
- Safe-area support for iPhone.
- PWA manifest and service worker included.
- API routes are never cached by the service worker.


## V15.8.7.2 startup fix
`start.bat` uses a single CMD window, installs missing cryptography dependency, starts the server in the same console, waits for `/api/health`, then opens the browser.

## V15.9.4 architecture upgrade
- FastAPI is now the primary ASGI server (`api_fast.py`).
- `/ws/signals` provides a WebSocket signal stream with periodic scan updates.
- In-memory API rate limiting is enabled via `FURKAI_RATE_LIMIT` (default 120/min/IP).
- `notification_service.py` supports optional Telegram alerts through environment variables.
- `backtest_engine.py` provides a modular `BacktestEngine` facade and Monte Carlo trade-PnL simulation.
- Backtest execution now applies configurable commission and slippage (`FURKAI_COMMISSION_RATE`, `FURKAI_SLIPPAGE_BPS`).
- Yahoo Finance remains primary; Stooq is used as a secondary daily-data fallback when Yahoo is unavailable.
- `.env.example` documents local development secrets; production secrets should be configured as Render environment variables.


## V15.9.6 multi-user transition
- Open registration via `/api/auth/register` and session login via `/api/auth/login`.
- Portfolio rows are isolated by `user_id`.
- Existing single-user local portfolio is claimed by the first local account; Render production uses `FURKAI_USER`/`FURKAI_PASSWORD` as the bootstrap admin and claims the legacy portfolio on first database access.
- Gemini is a shared application key; only the admin can change it. Other users can see only masked status.
- Sessions are stored as SHA-256 token hashes with a 7-day expiry; passwords use PBKDF2-HMAC-SHA256 with per-user salts.
