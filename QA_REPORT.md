# FurkAI V15.0 — 10x Furkan Loop QA

Her turda: hata kontrolü → eksik tespiti → geliştirme/düzeltme → tekrar kontrol.

1. **Sürüm/konfigürasyon:** 15.0 tek sürüm haline getirildi; 14.8 artıkları temizlendi. PASS
2. **Frontend kaynakları:** Eski `app.js` kaldırıldı; tüm gerekli fonksiyonlar tek `index.html` kaynağına taşındı. PASS
3. **QA/test altyapısı:** Eski app.js referansları ve yanlış markup beklentileri düzeltildi. PASS
4. **Grafik çizim araçları:** Yatay çizgi, trend çizgisi, Fibonacci ve çizimleri temizleme eklendi; JS sözdizimi kontrol edildi. PASS
5. **Grafik yenileme:** Otomatik yenileme ayarlara bağlandı; refresh süresi ve aç/kapat durumu işlendi. PASS
6. **AI UX:** Tarama AI sonucu aynı panelde açılıyor; kayan/üst üste eklenen AI kartı davranışı kaldırıldı. PASS
7. **Hisse Tarama:** AND/OR, min model, hazır stratejiler, model filtreleme, temizleme ve sonuç sıralama akışı kontrol edildi. PASS
8. **Tema/Ayarlar:** Koyu, açık ve sistem teması; tema ayarının sunucu config'ine kaydı; Gemini ayarları kontrol edildi. PASS
9. **Veri sağlığı/portföy:** Veri tazeliği, son veri zamanı ve portföy çeşitlendirme/korelasyon özeti geliştirildi. PASS
10. **Final regression:** Python compile, JavaScript syntax, WSGI, güvenlik/config kontrolleri ve uygulama testleri yeniden çalıştırıldı. **49/49 PASS.** PASS

## Son güvenlik kontrolleri
- Paket içinde plaintext Gemini API key bulunmuyor.
- `.furkai_secret` paketlenmedi; deployment için `FURKAI_SECRET_KEY` kullanılabilir.
- Eski `app.js` bulunmuyor.
- 14.8 sürüm artığı bulunmuyor.
- `aiStock`, `runBacktest`, `loadDashboard`, `setTheme` fonksiyonları tekil.
