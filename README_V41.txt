FurkAI V42 Unified – consolidated stability/data/UI pass

FurkAI V41 FIX
- BIST fiyat/geçmiş verisi için local Python market proxy.
- Derin analiz artık /api/history üzerinden veri alır.
- BIST taraması KAP evrenini kullanmaya çalışır ve yerleşik listeye düşer.
- Portföy ticker tıklaması detay modalı açar.
- Binance/altın botu BIST portföyünden ayrıldı; BTCUSDT/PAXGUSDT/XAUUSDT teknik sinyal + Paper/Testnet akışı.
- Sinyal geçmişi eklendi.
- Screenshot artık yalnızca PNG indirir.
- Temettü DRIP grafiğinde dripChartInstance tanımlı.
- KAP için geçersiz şirket URL'si yerine resmi KAP bildirim sorgusu kullanılır.
- Açık/koyu tema ve BIST/Trading menü ayrımı eklendi.
- Gerçek para emirleri bu sürümde otomatik olarak etkinleştirilmez.


V42 notes: portfolio startup no longer overwrites saved positions; TradingView null guard fixed; BIST quote batching/caching added; scanner now supports 9 technical conditions; BIST live/iDeal execution UI removed; backtest execution is next-bar to reduce look-ahead bias; Render health/HEAD support added.
