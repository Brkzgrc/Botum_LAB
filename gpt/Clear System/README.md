# Clear System

## Amaç

Binance Spot USDT evreninde yalnız LONG çalışan, az fakat yüksek kaliteli sinyal üreten tek dosyalı sistem geliştirmek.

Kullanıcının önceliği:

1. Sinyal kalitesi ve net P&L
2. En az yaklaşık 1–2 gerçek sinyal/gün hedefine yaklaşmak
3. Mevcut yüksek kaliteli r2 setup'ını sulandırmamak
4. Ücretli API kullanmamak
5. Son ürünün GUI hariç tek dosyada çalışması: `Clear System.py`

> Gerçek piyasada “garanti işlem” yoktur. Araştırmanın hedefi garanti iddiası değil; maliyet, stop-first/target-first, OOS ve dönem dayanıklılığıyla ölçülmüş yüksek pozitif beklentidir.

## Klasör sınırı

Bu araştırmada oluşturulan veya güncellenen bütün araştırma ve teslim dosyaları yalnız `gpt/Clear System/` altında tutulur.

GitHub Actions'ın çalışabilmesi için workflow dosyasının teknik olarak `.github/workflows/` altında bulunması gerekir. Bu konum klasör sınırıyla çeliştiği için şu an repo köküne workflow yazılmadı. Araştırma tasarımı burada tutulacak; kullanıcı klasör dışı tek istisnaya izin verirse Actions workflow ayrıca eklenebilir.

## Kanonik teslim dosyası

- `Clear System.py`: GUI hariç çalıştırılabilir güncel sistem.
- İlk sürüm kanıtlanmış `tsi_bb_frozen_candidate_spot_audited_r2` tarayıcısının birebir başlangıç kopyasıdır.
- Kanıtlanmamış fikirler bu dosyaya eklenmez.
- Yeni setup yalnız Discovery + Calibration + dokunulmamış OOS/holdout ve r2 ile OR birleşim testlerini geçerse bu dosya güncellenir.

## Değişmez araştırma kuralları

- Binance Spot USDT, long-only.
- Stablecoin/fiat base varlıklar hariç.
- Round-trip maliyet: %0,20.
- Yalnız kapanmış mum verisi; look-ahead yasak.
- Kural seçimi 2023–2025 Discovery + Calibration üzerinde yapılır.
- 2026, seçimden sonra açılan dokunulmamış değerlendirme dönemidir.
- Aynı coin/zaman sinyalleri dedupe edilir.
- Başarı yalnız win rate değildir.

Her aday için en az şu metrikler tutulur:

- sinyal/gün ve sinyal/hafta
- aktif gün oranı
- net 24H mean/median
- Profit Factor
- +3 önce -2, +4 önce -2,5, +5 önce -3
- MFE / MAE
- yıl, ay ve coin dağılımı
- maksimum ardışık kayıp
- r2 ile çakışma ve OR birleşim sonucu
- OOS/holdout dayanıklılığı

## Başlangıç referansı — Frozen r2

2026 referansı:

| Metrik | Sonuç |
| --- | ---: |
| Sinyal | 110 |
| Sembol | 99 |
| Sinyal/hafta | yaklaşık 2,96 |
| Win24 | %92,73 |
| Ortalama net24 | +%3,98 |
| Medyan net24 | yaklaşık +%3,49 |
| PF24 | 12,07 |
| +3 önce -2 | yaklaşık %80 |

Bu sonuçlar mevcut repo raporlarından devralınmıştır. Yeniden üretim tamamlanmadan “bağımsız tekrar doğrulandı” denmez.

## İncelenen mevcut araştırmalar

### Korunan

- Frozen TSI+BB r2: kalite referansı ve v0.1 çekirdeği.
- Eski C09 Confirmed Reversal ve C12 Continuation bulguları: yeniden, güncel protokolle sınanması gereken adaylar.

### Elenen veya r2'ye eklenmeyen yollar

Aşağıdaki çalışmalar workflow olarak başarıyla tamamlanmış olsa da araştırma sonucu negatiftir:

- r2 movement expansion
- r2 nonlinear PCA/k-means movement clusters
- independent movement signatures
- 62 independent price-path variants
- causal impulse-origin retest
- recovery leadership
- sell-climax reclaim
- structural acceptance transition
- HTF mitigation reclaim

Bunlar yeni adlarla aynı eşik taramasına dönüştürülüp tekrar çalıştırılmayacaktır.

## Video özetlerinden çıkarılan test edilebilir adaylar

Bunlar sisteme eklenmiş doğrulanmış kurallar değildir; yalnız hipotezdir.

### H1 — MTF pullback + candle break

- 4H: trend/yapı yukarı.
- 1H: EMA20/EMA50, destek veya eski breakout bölgesine geri çekilme.
- 15M: bullish engulfing, hammer veya bullish pin bar.
- Giriş: dönüş mumunun yüksek seviyesinin kapanmış mumla kırılması.
- Stop: geçerli swing low altında ATR tamponu; toplam stop mesafesi ayrıca sınırlandırılır.
- Veto: ilk gerçekçi dirence kadar yeterli R alanı yoksa sinyal yok.

### H2 — Resistance pressure breakout/retest

- 4H: ana direnç bölgesi.
- 1H: direnç altında yükselen dipler ve sığlaşan geri çekilmeler.
- 15M/1H: bölge üstünde kapanış; yalnız fitil kırılımı kabul edilmez.
- Tercihen retest ve bölgenin destek olarak korunması.
- Giriş: retest teyit mumunun yüksek seviye kırılımı.
- Veto: hacim/OBV teyidi zayıf, hedef alanı dar veya BTC rejimi risk-off ise sinyal yok.

### H3 — Gösterge hareket dizisi teyidi

Statik değer yerine göstergenin hareket dizisi ölçülür:

- RSI'ın yönü ve 50 eşiği
- Stoch RSI dipten dönüş/kesişim
- MACD histogram küçülme → sıfır çevresi → büyüme dizisi
- KDJ yönü
- Williams %R dönüşü
- OBV eğimi ve fiyatla uyumu

Bu aile, aynı momentum bilgisini tekrar tekrar saymamak için korelasyon/ablation testiyle sınanacaktır.

## Deney sırası

1. Baseline r2 yeniden üretim ve kod/veri uyum denetimi.
2. C09 Confirmed Reversal güncel protokolle tekrar test.
3. C12 Continuation güncel protokolle tekrar test.
4. H1 MTF pullback + candle break.
5. H2 breakout/retest.
6. H3 yalnız H1/H2 üzerinde ek filtre olarak ablation testi.
7. Adayların r2 ile OR birleşimi, dedupe ve portföy gerçekçiliği.
8. En iyi doğrulanmış birleşimi `Clear System.py` içine alma.
9. Son aşamada GUI ekleme; araştırma mantığı sabitlendikten sonra.

## Kabul kapısı

Bir aday ancak aşağıdakilerin tamamında olumluysa ana sisteme eklenebilir:

- Discovery ve Calibration'da aynı yönde sonuç
- dokunulmamış OOS'ta pozitif net expectancy
- maliyet sonrası PF kabul edilebilir
- tek coin veya kısa döneme yığılmama
- r2 ile birleşimde frekansı anlamlı artırma
- r2'nin toplam kalite/kötü kuyruk profilini belirgin bozmama
- look-ahead, açık mum ve survivorship hatası olmama

## Sürüm günlüğü

| Tarih | Sürüm | Durum | Değişiklik | Sonuç / karar |
| --- | --- | --- | --- | --- |
| 2026-09-21 | v0.1 | Başlangıç | Frozen r2 kanonik tarayıcı `Clear System.py` olarak taşındı. Mevcut araştırmalar ve video kuralları sınıflandırıldı. | Yeni kural eklenmedi; kalite korunuyor. Önce baseline yeniden üretim. |

## Yeni session'da devam protokolü

1. Bu README'nin tamamını oku.
2. `Clear System.py` sürümünü ve bu tablodaki son kaydı karşılaştır.
3. Mevcut GitHub Actions durumunu gerçek run/job çıktısından kontrol et; tahmin etme.
4. Son tamamlanan deneyin raporunu ve metriklerini oku.
5. Başarısız teknik run varsa aynı deneyi düzelt; yeni hipoteze atlama.
6. Araştırma sonucu negatifse buraya metrikleri ve “ELENDİ” kararını ekle.
7. Sonuç pozitifse önce OOS + OR birleşim doğrulamasını yap.
8. Kabul kapısını geçmeden `Clear System.py` sinyal mantığını değiştirme.
9. Her anlamlı değişiklikte tarih, run ID, veri dönemi, maliyet, metrikler ve sonraki adımı kaydet.

## Sonraki somut adım

Baseline r2'nin bağımsız yeniden üretimini çalıştırmak; ardından C09 ve C12'yi aynı veri evreni, aynı maliyet ve aynı first-touch hedef/stop planlarıyla karşılaştırmak.
