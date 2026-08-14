# FurkAI BIST v15.0

BIST analiz, tarama, portföy ve long-only backtest terminali.

## v15.0 güvenlik ve QA düzeltmeleri

- Gemini API anahtarı artık `config.json` içinde şifreli (Fernet) saklanır; deploy ortamında `FURKAI_SECRET_KEY` kullanılması önerilir.
- Ayarlar ekranına Gemini bağlantı testi ve veri sağlığı göstergeleri eklendi.
- Config dosyası ve yerel secret dosyası için kullanıcıya özel dosya izinleri uygulanır.
- Health/config sürüm bilgisi 15.0 ile tutarlı hale getirildi.

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


## V15.0 Mobile/PWA
- iPhone/Android responsive layout under 700px.
- Bottom navigation for Ana, Tarama, Grafik, Portföy, Ayarlar.
- Safe-area support for iPhone.
- PWA manifest and service worker included.
- API routes are never cached by the service worker.
