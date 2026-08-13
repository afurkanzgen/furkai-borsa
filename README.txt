FurkAI V41 Unified
==================

Bu paket V38 MASTER'in mevcut ekranlarini korur ve iki eksigi kapatir:

1. BIST Tarama Merkezi artik sunucuda calisir. Secili coklu teknik kosullari
   tek tek degerlendirir; veri alinamayan sembol icin sonuc uydurmaz. Mümkünse
   KAP Pazarlar listesinden guncel evreni alir, ulasamazsa ekranda bunu belli
   eden yerlesik baslangic listesine duser.

2. Binance Futures ayrica "Binance Testnet" ekranina tasindi. Paper varsayilan
   moddur. Taramalar otomatik emir acmaz. Testnet emri sadece API key + secret
   kaydedildikten sonra, kullanicinin ayri onayiyla gonderilir. Bu pakette
   Binance LIVE modu yoktur.

KORUNAN EKRANLAR
- Portfoy: hisse, kripto, altin; ekle/duzenle/sil, kar-zarar, fiyat yenileme
- Altin analizi
- AI asistan ve Gemini baglantisi
- Hisse analizi, haber/KAP baglantilari, temettu, risk, strateji/backtest
- BIST firsatlari ve BIST bot/paper/iDeal Bridge ekrani
- "Sorun Bildir / SS Al" sabit ekran goruntusu butonu

BASLATMA
1. ZIP'i yeni bir klasore cikar.
2. start.bat dosyasina cift tikla.
3. Tarayici acilmazsa http://127.0.0.1:8798/ adresini ac.

KONTROL LISTESI
- Sol menude Portfoy, Tarama Merkezi, Binance Testnet gorunur.
- Sag altta "Sorun Bildir / SS Al" butonu gorunur.
- Tarama Merkezi'nde kosul kutularini secip Taramayi Baslat'a bas.
- Binance Testnet'te anahtar girmeden emir denemesi basarisiz olur; bu kasitli
  guvenlik davranisidir.

VERI NOTU
BIST ucretsiz/gecikmeli Yahoo OHLCV ve KAP pazar listesini kullanir. Bunlar
lisansli canli veri veya emir defteri verisi degildir. Bir kaynak erisilemezse
uygulama bunu hata/veri eksigi olarak gosterir; fiyat ya da sinyal uydurmaz.


CLOUD / RENDER
Bu paket Render web service icin PORT ortam degiskenini kullanir ve FURKAI_PASSWORD ayarlandiginda Basic Auth ile korunur.
