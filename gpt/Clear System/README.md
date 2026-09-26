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
| 2026-09-22 | Taker Flow Absorption/Release run 35674885928 | ELENDİ | 15M taker dengesindeki emilim, akış dönüşü ve serbestleşme; kapanmış 1H/4H akış dizileriyle 26 özellik olarak test edildi. | `completed/success`; 28 dk 02 sn duvar süresi, 334,6 runner-dk; 64/64 shard + aggregate geçti; veri 2023-01-01–2026-09-17; maliyet %0,20; 912.836 olay, 466 sembol, 11 kısa geçmişli coin zararsız dışlandı. Discovery + Calibration kapısını geçen champion yok: `NO_STABLE_TAKER_FLOW_ABSORPTION_RELEASE`. Bu nedenle sinyal/gün, active-day, expectancy, PF, target/stop-first, MFE/MAE ve OOS champion metrikleri N/A; `Clear System.py` değiştirilmedi. |
| 2026-09-22 | Trade Intensity Participation run 35678448195 | ELENDİ | Taker-share kullanmadan; işlem sayısı, ortalama işlem büyüklüğü, fiyatın katılıma tepkisi ve kapanmış 15M→1H→4H dizileriyle 28 özellik test edildi. | `completed/success`; 27 dk 24 sn duvar süresi, 332,1 runner-dk; 64/64 shard + aggregate geçti; veri 2023-01-01–2026-09-17; maliyet %0,20; 1.365.143 olay, 466 sembol, 11 kısa geçmişli coin zararsız dışlandı. Discovery + Calibration kapısını geçen champion yok: `NO_STABLE_TRADE_INTENSITY_PARTICIPATION`. Bu nedenle sinyal/gün, active-day, expectancy, PF, target/stop-first, MFE/MAE ve OOS champion metrikleri N/A; `Clear System.py` değiştirilmedi. |
| 2026-09-26 | Market Breadth Data Preflight run 36234735002 | GEÇTİ | BTC/ETH/BNB/SOL/XRP/DOGE kapalı 15M→1H hareketlerinden daralma→genişleme breadth context veri/schema uygunluğu denetlendi. | `completed/success`; 6 dk 24 sn; veri 2025-01-01–2026-09-18; 360.000 mum; her referansta ve ortak timeline'da %100 kapsama; 59.996 geçerli özellik satırı; 3.077 ignition olayı, 618 aktif gün; +15 dk kapanmış-mum hizası doğrulandı. Veri preflight'ı olduğundan maliyet, sinyal/gün, expectancy, PF ve OOS N/A. Tam araştırmaya geçilebilir; `Clear System.py` değiştirilmedi. |
| 2026-09-26 | Market Breadth Ignition runs 36235398705 + 36237687553 | ELENDİ | Altı majörde breadth daralma→genişleme sonrası hedef coinin 15M/1H/4H yerel hareket geçişi; 25 kapalı-mum hareket özelliği. İlk run’da 64/64 shard geçti, aggregate tarihçesiz dört sembolü yanlış sınıflandırdı; kurtarma run’ı mevcut shard artifact’lerini yeniden kullandı. | Kurtarma `completed/success`; 14 dk 28 sn; veri 2023-01-01 09:45 UTC–2026-09-17 23:45 UTC; maliyet %0,20; 634.806 olay, 466 sembol; 64/64 shard, 15 sınırlı tarihçe dışlaması, hard error 0. Discovery + Calibration + pre-2026 cross-holdout kapısını geçen champion yok: `NO_STABLE_MARKET_BREADTH_IGNITION`. Bu nedenle champion sinyal/gün, active-day, expectancy, PF, target/stop-first, MFE/MAE ve 2026 OOS metrikleri N/A; 2026 seçim için açılmadı. `Clear System.py` değiştirilmedi. |
| 2026-09-26 | Phase 11–13 trajectory kanıt denetimi | AKTARILMADI | Başka çalışma alanındaki pre-2026 D+C+cross kilitli trajectory sonuçları, frozen r2 ile eşit 2026 döneminde karşılaştırıldı; yeni Action çalıştırılmadı. | r2: 110 sinyal, 2,96/hafta, WR24 %92,73, mean24 +%3,978, PF24 12,07, p10 +%0,759. Phase 11 OR: 139 sinyal, 3,74/hafta, WR24 %85,61, mean24 +%3,325, PF24 5,77, p10 -%2,700; frekans +%26 fakat PF -%52 ve kötü kuyruk bozuldu. Phase 12: 3,66/hafta, PF24 5,80. Phase 13: 205 sinyal, 5,52/hafta fakat WR24 %72,20, mean24 +%2,113, PF24 3,14, p10 -%3,662. Mevcut r2 kalitesini anlamlı bozdukları için `Clear System.py` içine alınmadı. |

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
- Trade-intensity gerçekleşen bütçe: 332,1 runner-dk ve 27 dk 24 sn duvar süresi; shard aralığı 2,35–7,85 dk. Sonraki benzer veri hacmi için güvenli üst tahmin 390 runner-dk / 35 dk olarak alınır.
- Market Breadth tam çalışma tahmini: tam referans context'i 14–18 runner-dk; 64 hedef shard + aggregate önceki gerçek hızla 332–390 runner-dk; toplam yaklaşık 350–430 runner-dk ve 45–55 dk duvar süresi. Context/preflight 25 dk, shard 55 dk, komut 46 dk ve aggregate 25 dk sınırı kullanılacak.
- Market Breadth aggregate-kurtarma bütçesi (run 36237687553): mevcut 64 shard yeniden kullanılacak; tam compile/self-test/context/iki-coin smoke + aggregate yaklaşık 25–35 runner-dk ve 20–30 dk duvar süresi. Preflight 25 dk, context komutu 18 dk, smoke 4 dk ve aggregate 25/14 dk job/step sınırları korunur; shard matrisi açılmaz.
- Peer Network Lead–Lag veri preflight bütçesi: 24–32 likit fakat stable/fiat olmayan Spot USDT sembolünde 2025–2026 kapalı 15M→1H veri; yaklaşık 25–40 runner-dk / 20–30 dk duvar süresi, workflow 35 dk ve veri komutu 27 dk sınırı. Yeterli tekrarlanan pair-event, kapsama ve zaman hizası yoksa tam araştırma açılmaz.

## Canlı takip dosyası denetimi — 2026-09-26

Kullanıcı, `tsi_bb_frozen_candidate(1)(2).py` kodu ile 2026-09-26 15:20:30 yerel zamanlı `portfolio_snapshot(2).json` dosyalarını doğrudan sağladı. Bu, gerçek alım değil, portföye yansıyan takip kaydıdır; yalnız 2026-09-22–26 arasındaki beş günün 23 kapanmış işlemi vardır. Gönderilen Python dosyası sadece `TSI_BB_FROZEN_CANDIDATE` taramasını tanımlar: kapanmış 15M/1H/4H mumlarda RSI/MACD/KDJ/WPR/OBV/StochRSI yön değişimleri, BTC TSI+BB rejimi, 15M–1H lead gap, engulf/HL/HH ve 15 dakika gecikmeli yayın. Diğer stratejilerin giriş/tarama kodları bu dosyada yoktur.

| Takip alt türü | Kapanış | Pozitif | Kapanış yüzdelerinin toplamı | Ortalama / sinyal | Gözlem |
| --- | ---: | ---: | ---: | ---: | --- |
| PRESSURE | 7 | 7 | +%24,57 | +%3,51 | Yedi işlemin tamamında TP1 görülmüş; stop uzaklığı örneklerde %3,36–14,86. Bağımsız mekanizma ve seçim kuralı henüz incelenmedi. |
| RETRIGGER | 8 | 6 | +%3,87 | +%0,48 | Dört 24 saatlik expiry, bir stop, üç trailing. |
| TSI_BB_FROZEN | 8 | 5 | -%0,09 | -%0,01 | Dört trailing, iki stop, iki expiry; yalnız 22–23 Eylül günlerinde sinyal. |
| Toplam | 23 | 18 | +%28,35 | +%1,23 | Kaydın `win_rate` alanı %78,3, `avg_peak` %3,76; açık işlem yok. |

`close_pct` toplamı eşit ağırlıklı sinyal yüzdelerinin aritmetik toplamıdır; sermaye getirisi veya eşzamanlı işlemlerle uygulanabilir portföy P&L olarak sunulamaz. Kayıtlarda `fee_pct=0.2` görülür. `PRESSURE` ve `RETRIGGER` giriş kodu, günlük üç adayın seçilme biçimi, fill/slippage ve ortak risk bütçesi doğrulanmadı. Beş günlük gözlem kalıcı avantaj kanıtı değildir. Bu nedenle ne `PRESSURE` ne `RETRIGGER` OR olarak `Clear System.py` içine eklenmiştir. Bu veri, sonraki araştırma önceliğini günceller.

## Sonraki somut adım

İlk somut adım, kullanıcının sağladığı beş günlük takipte olumlu görünen `PRESSURE` ailesinin gerçek sinyal üretim ve üç aday seçimi kodunu bulup nedensellik, fill, maliyet, stop ve expiry kurallarını çıkarmaktır. Ardından bu kurallar 2023–2025 Discovery + Calibration + pre-2026 cross ve dokunulmamış 2026 OOS ile r2 OR birleşiminde test edilecek. Kuralın kodu ve seçilen tüm adayların eksiksiz kaydı olmadan canlı takip yüzdeleri genellenmeyecek. `Peer Network Lead–Lag Propagation` bağımsız sonraki hipotez olarak bekler. Yeni pahalı Action başlatılmadı; `Clear System.py` değişmedi.

## PRESSURE kaynak arşivi ve giriş/çıkış araştırması — 2026-09-26

Kullanıcının izniyle özel `Brkzgrc/Botum` deposundan kaynaklar **yalnız okunarak** `gpt/Clear System/sources/botum_2026-09-26/` altına birebir kopyalandı: `spot_opportunity_scanner.py`, `tsi_bb_frozen_candidate.py`, `portfolio_tracker.py`, `position_monitor.py`, `portfolio_snapshot.json`. Beş kaynak blob SHA'sı yeniden okunup doğrulandı; kaynak deposuna yazılmadı. Çalışma planı ve sürümlü kanıt `gpt/Clear System/research/pressure_confirmation/` altında; canlı tarayıcı kopyası çalıştırılmıyor.

Bu alt klasördeki `paper_cohort_audit.py` derlendi, self-test geçti ve 2026-09-26 16:50:40 anlık görüntüsündeki 23 kapanmış kâğıt işlem üzerinde maliyet/gross/net/tekil kimlik kontrolünü geçti. **Yeni Action run ID: yok; veri dönemi 2026-09-22–26; maliyet %0,20.** Gözlemsel özet: tümü 23 işlem, 18 pozitif/5 negatif, yüzde toplamı +28,35 puan; PRESSURE 7/7, +24,57 puan, 1,4 sinyal/takvim günü, %80 aktif gün; PRESSURE + yalnız GREEN RETRIGGER 10/10, +29,78 puan, 2,0/gün, %80 aktif gün. Bu alt kümeler sonuca bakılarak tanımlandığından PF'de gözlenen kayıp yok diye `sonsuz` sayılmadı; `null`/tanımsız tutuldu. TP1, stop, MFE/MAE ve günlük döküm `paper_cohort_summary.json` içindedir. OOS: **yok**; bu beş gün hipotezi seçtirdiği için temiz holdout sayılamaz.

Beş negatiften dördü toplam −18,26 puan kaybetti; aynı dördü BTC `YELLOW` sınıfındaydı, ancak kazanan `YELLOW` işlemler de var. Tüm büyük kayıpların skoru 95–100 olduğu için salt skor kapısı ayıramıyor. Kullanıcının çıkış fikri de sayısallaştırıldı: işlem sonrası tepeye bakarak brüt %0,25 TP'nin beş kaybın hepsine erişmiş olması, %0,20 ücret sonrası 23 işlemde yalnız **iyimser +1,15 puan** verir; brüt %0,80 TP üç kaybın tepesine erişir, iyimser toplam +8,87 puandır. Bunlar **hedef/stop sırası olmayan iyimser üst sınır**; çalıştırılabilir politika getirisi değildir.

Karar: PRESSURE temel aile olarak tarihsel yeniden oynatmaya değer. RETRIGGER/TSI-BB hareket onayı, rejim, tepeye yaklaşma, geri çekilme/reclaim, sabit ve kademeli TP, hareket sönmesi, süreli çıkış birlikte sistematik sınanacak. Önceki r2 loss-veto/dip çalışmaları başka aday havuzlarına ait, eşikleri kopyalanmayacak. Sonraki somut adım küçük gerçek-veri, kapanmış mumlu, zaman sıralı kaynak parity smoke; ilk tarama, kota ve aday sıralama ile 5M hedef/stop sırasını doğrulamak. Smoke sonrası tam Action maliyeti hesaplanmadan pahalı run açılmayacak. `Clear System.py` değişmedi.

### PRESSURE tarihsel kaynak denetimi — run 36247391259

[GitHub Actions run 36247391259](https://github.com/Brkzgrc/Botum_LAB/actions/runs/36247391259) 2025-01-01–2025-08-29 kapalı 15M verisinde BTC/ETH/SOL/XRP/LINK/AVAX için kaynak SHA, ön eleme, ilk taramada sinyal vermeme ve sonraki kapanmış 15M barı sınamak üzere başlatıldı. Başlatmadan önce yerel Python derleme, SHA/self-test, AST nedensellik/evren güvenliği, YAML/job/komut süresi ve artifact tamlık kontrolleri geçti. Tahmini 8–12 runner-dk, job 20 dk, gerçek veri komutu 10 dk. Tek shard ve altı sembol zorunlu. Bu bir kaynak/veri smoke olduğundan sinyal sıklığı, PF, expectancy, target/stop-first, MFE/MAE ve OOS: N/A. **Run `completed/failure`:** job `108419005426` gerçek-veri adımında 18 saniyede durdu. Kesin neden `--start 2025-01-01` değerinin saat dilimsiz olması (`start/decision must be timezone-aware`); veri çekilmedi, `summary.json` üretilmedi. Bu nedenle dönem/kapsam yalnız plan, gerçekleşen maliyet ~0,3 runner-dk; sinyal/gün, active-day, expectancy, PF, target-first/stop-first, MFE/MAE ve OOS: N/A. Derleme/self-test/statik denetimler geçti. UTC `Z` damgası ve hata halinde `run.log` artifact kaydı düzeltildi; yerel derleme+self-test, AST/YAML/UTC denetimi ve her workflow komutu için `bash -n` ayrı ayrı geçti. Sonraki adım yalnız aynı sınırlı smoke testini doğrulayıp çalıştırmak; `summary.json` görülmeden tarihsel tam araştırma açılmayacak.** Tam tarama veya `Clear System.py` değişikliği yok.


### PRESSURE tarihsel kaynak denetimi düzeltme sonucu — run 36250743664

[GitHub Actions run 36250743664](https://github.com/Brkzgrc/Botum_LAB/actions/runs/36250743664) `completed/success`; 2026-09-26 15:05:54–15:08:11 UTC, yaklaşık 2 dk 17 sn duvar süresi. Önceki saat dilimi hatası UTC `Z` ile giderildi. Compile, kaynak blob SHA self-test, nedensellik/evren statik denetimi, gerçek Binance Spot verisi ve eksik shard/sembol kapısı geçti; `summary.json` artifact'ten okunup `research/pressure_confirmation/output/historical_parity_smoke/summary.json` altına arşivlendi.

Veri dönemi 2025-01-01–2025-08-29 UTC; BTC/ETH/SOL/XRP/LINK/AVAX Spot USDT, her birinde 23.042 adet 15M mum ve %100 kapsama; 6/6 sembol, 1/1 shard. İlk karar anında sinyal verilmedi; sonraki kapanmış 15M barı ilerledi. SOL örneğinde kaynak `ARMED → ENTRY` ve sonraki setup `PRESSURE` görüldü; bu tek olayın kârlılığı veya emir gerçekleşmesi ölçülmedi. Round-trip araştırma maliyeti sonraki sonuç çalışması için %0,20; bu smoke'da gerçek trade olmadığından sinyal/gün, active-day, expectancy, PF, target-first/stop-first, MFE/MAE ve OOS: **N/A**. Tam portföy kota/sıralama, tarihsel canlı ticker, emir fiyatı ve çıkışlar bu smoke kapsamında değil. Karar: **veri/kaynak uygunluğu geçti, strateji doğrulanmadı**; `Clear System.py` değişmedi.

Sonraki somut adım: kaynak tarayıcıyı tam zaman akışı ve günlük kota/sıralama ile tarihsel yeniden oynatacak, 5M ile hedef/stop sırasını ve alternatif sabit/kademeli/hareket temelli çıkışları karşılaştıracak kodu hazırlamak. Önce 2023–2025 örneğinde küçük preflight + gerçek veri smoke; sonra ancak süre/runner bütçesi uygunsa parçalı tam araştırma. 2026-09-22–26 kâğıt kohortu hipotez seçimini etkilediği için temiz OOS sayılmayacak. Yeni pahalı run başlatılmadı.
