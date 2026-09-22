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

GitHub Actions workflow dosyaları teknik zorunluluk nedeniyle yalnız `.github/workflows/` altında tutulur. Araştırma kodu, çıktı ve teslim dosyaları `gpt/Clear System/` sınırında kalır.

## Kanonik teslim dosyası

- `Clear System.py`: GUI hariç çalıştırılabilir güncel sistem.
- İlk sürüm kanıtlanmış `tsi_bb_frozen_candidate_spot_audited_r2` tarayıcısının birebir başlangıç kopyasıdır.
- Kanıtlanmamış fikirler bu dosyaya eklenmez.
- Yeni setup yalnız Discovery + Calibration + dokunulmamış OOS/holdout ve r2 ile OR birleşim testlerini geçerse bu dosya güncellenir.

## Değişmez araştırma kuralları

### Hareket-takibi zorunluluğu

Nihai sistem statik gösterge değerleriyle çalışan bir “tek kare değer okuyucu” olmayacaktır. Örneğin yalnız `RSI < 30`, `StochRSI < 20` veya `ADX > 20` koşulu sinyal üretmeye yetmez.

Sistem, kapanmış mumlar boyunca oluşan hareket dizilerini ölçmelidir:

- fiyatın dip/tepe sırası, eğimi, hızlanması ve yavaşlaması
- RSI/StochRSI/KDJ/Williams %R yön değişimi ve dönüş süreci
- MACD çizgi/histogramının küçülme, dönüş ve genişleme dizisi
- OBV/hacim akışının fiyat hareketine eşlik veya ayrışması
- 4H → 1H → 15M hareket aktarımı
- destek/dirence yaklaşım biçimi, sıkışma, kırılım ve retest
- BTC/ETH hareketi ile altcoinin gecikme veya liderlik ilişkisi

Araştırma sırasında statik seviyeler; olay havuzu oluşturma, rejim ayırma veya hareketin başladığı bağlamı tanımlama amacıyla denenebilir. Ancak üretim sinyali, en az bir nedensel hareket/transition dizisi ve kapanmış mum teyidi olmadan kabul edilmez.

Araştırma yöntemi serbesttir: ileri yönlü event study, yükselen sonuçlardan geriye doğru outcome-first inceleme, önce değer sonra hareket, doğrudan hareket keşfi, kümeleme, ablation ve OR-aile karşılaştırmaları kullanılabilir. Tek ölçüt, veri sızıntısız biçimde hedefe yaklaşmasıdır.


- Binance Spot USDT, long-only.
- Stablecoin ve fiat base varlıklar kesin olarak hariç; stable/fiat pariteleri araştırma ve canlı tarama evrenine alınmaz.
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
| 2026-09-21 | Tasarım kilidi | Güncellendi | Nihai sistem için statik değer okuma yasaklandı; hareket/transition dizisi zorunlu kılındı. Spot USDT evreninden stablecoin ve fiat base varlıkların kesin dışlanması tekrar kilitlendi. | Baseline yalnız referans; yeni aileler hareket-takibi olarak araştırılacak. |
| 2026-09-21 | Preflight run 35656755689 | GEÇTİ | Compile, hareket korumaları, kapanmış mum kodu ve gerçek Binance Spot evren smoke testi çalıştı. | `completed/success`; yaklaşık 29 saniye. USDC ve EUR dışlandı, BTC/ETH/SOL/XRP kabul edildi. |
| 2026-09-22 | Motion Leadership run 35662533375 | ELENDİ | Coinin BTC'ye göre birkaç mum boyunca kalıcı liderliği + değer alanı kabulü + taze 15M genişleme araştırıldı. | `completed/success`; 34 dakika 2 saniye; 18 kural, 162.960 event, 465 sembol; Discovery + Calibration'da stabil champion yok: `NO_STABLE_MOTION_LEADERSHIP_PERSISTENCE`. `Clear System.py` değiştirilmedi. |
| 2026-09-22 | Outcome-First Transition run 35666323044 | ELENDİ | 26 kapalı-mum hareket özelliğiyle geniş olay havuzu; model yalnız Discovery'de öğrendi, plan/eşik yalnız Calibration'da seçildi, 2026 seçim için kullanılmadı. | `completed/success`; 27 dk 32 sn; 1.433.251 event, 466 sembol, 11 yeni/eksik geçmişli coin zararsız dışlandı; Discovery + Calibration kabul kapısını geçen champion yok: `NO_STABLE_OUTCOME_FIRST_TRANSITION`. Bu nedenle sinyal/gün, active-day, expectancy, PF ve OOS champion metrikleri oluşmadı; `Clear System.py` değiştirilmedi. |
| 2026-09-22 | Taker Flow Data Preflight run 35670232639 | GEÇTİ | Binance 15M kline taker-buy alanlarının tarihsel kapsaması, oran geçerliliği ve emilim/serbestleşme olay yoğunluğu altı likit sembolde denetlendi. | `completed/success`; 4 dk 37 sn; veri 2025-01-01–2026-09-18; 360.000 mum; her sembolde %100 kapsama ve %100 geçerli pay; 49.946 olay. Bu bir veri denetimi olduğundan maliyet, sinyal/gün, active-day, expectancy, PF, target/stop-first, MFE/MAE ve OOS: N/A. Tam nedensel araştırmaya geçilebilir. |
| 2026-09-22 | Taker Flow Absorption/Release run 35674885928 | ÇALIŞIYOR | 15M taker dengesindeki emilim, akış dönüşü ve serbestleşme; kapanmış 1H/4H akış dizileriyle 26 özellik olarak test ediliyor. | Bütçe: yaklaşık 730–900 runner-dk / 50–65 dk duvar süresi; maliyet %0,20. Yerel compile, self-test, AST/nedensellik ve YAML kontrolleri geçti. Workflow compile/self-test/statik denetim ve 6 sembollük gerçek-veri smoke geçti; 64 shard kontrollü biçimde başladı. Sinyal/gün, active-day, expectancy, PF, target/stop-first, MFE/MAE ve OOS: sonuç bekleniyor. `Clear System.py` değiştirilmedi. |

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

## Action süre ve hata disiplini

- Her job açık `timeout-minutes` taşır.
- Komut düzeyinde mümkünse ayrıca `timeout` kullanılır.
- Uzun tarama başlamadan compile, self-test, şema ve gerçek-veri smoke zorunludur.
- Full scan shard'lara bölünür; eksik shard varsa aggregate başarısız olur.
- `if: always()` ile hata halinde de log/ara kanıt artifact olarak saklanır.
- Workflow yeşil olsa bile summary/metrik dosyası okunmadan araştırma başarılı sayılmaz.
- Her deneyden önce yaklaşık toplam runner dakikası hesaplanıp bu README'ye yazılır.
- İlk preflight sınırı 25 dakika, canlı smoke komut sınırı 12 dakikadır; gerçek çalışma yaklaşık 29 saniyede tamamlanmıştır.
- Taker-flow tam araştırma bütçesi (preflight hızından): yaklaşık 730–900 runner-dakikası; 16 paralel runner ile yaklaşık 50–65 dakika duvar süresi. Preflight 22 dk, her shard 55 dk, komut 46 dk, aggregate 25 dk ile ayrıca sınırlandırılır.

## Sonraki somut adım

Run `35674885928` şu anda tek pahalı araştırma olarak çalışıyor. Compile, deterministik self-test, statik nedensellik/evren denetimi ve altı sembollük gerçek-veri smoke geçti; 64 shard başladı. Sonraki turda önce bu run izlenecek; yeni araştırma başlatılmayacak. Başarılı olursa `summary.json` içindeki tüm dönem metrikleri okunacak. Aday ancak 2026 OOS'u geçip frozen r2 ile dedupe/OR kalite doğrulamasını da başarırsa `Clear System.py` içine alınacak.
