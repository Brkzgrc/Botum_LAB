# TSI BB Structural Phase

Bu klasör bu araştırma hattının TEK aktif çalışma alanıdır.

## 1. Amaç

Binance Spot USDT evreninde long-only bir sistem için, güçlü TSI+BB / r2 çekirdeğinin kalitesini mümkün olduğunca korurken sinyal frekansını artırmak.

Operasyonel hedef:
- minimum yaklaşık 5 sinyal/hafta,
- tercih edilen 10–15 sinyal/hafta,
- win rate tek başına başarı ölçütü değildir,
- net 24H getiri, medyan, Profit Factor, kötü kuyruk ve dönemler arası dayanıklılık birlikte değerlendirilir,
- round-trip maliyet varsayımı: %0.20.

## 2. Sahiplik ve klasör sınırı

BU ARAŞTIRMA İÇİN:
- Yazılacak/değiştirilecek araştırma kodu, rapor ve sonuçların tamamı: `gpt/TSI_BB_Structural_Phase/`
- GitHub Actions zorunlu olarak `.github/workflows/` altında durabilir; sadece bu klasördeki kodu çalıştıran `gpt-tsi-bb-structural-project-*` workflow'ları kullanılmalıdır.
- `gpt/Multi-Timeframe-Independent-Evidence/` başka session'ın çalışma alanıdır. Buraya YAZMA.
- `gpt/btc-frozen-reversal-fingerprint-validation/` eski BTC fingerprint arşividir. Buraya YAZMA.
- Gerekirse bu iki alandan yalnızca referans/veri OKUNABİLİR; yeni araştırma mantığı burada tutulmalıdır.
- Yeni bağımlılık gerekirse mümkünse önce bu klasörün `lib/` altına snapshot/kopya alınmalı, sonra yerel kopya kullanılmalıdır.

## 3. Mevcut referans sistemler

2026 eşit dönem karşılaştırması (2026-01-01 – 2026-09-18, %0.20 maliyet):

| Sistem | Sinyal | Sinyal/hafta | Win24 | Ort. net24 | Medyan net24 | PF24 |
|---|---:|---:|---:|---:|---:|---:|
| Frozen TSI+BB | 150 | 4.04 | %84.00 | +%3.257 | +%3.200 | 6.13 |
| TSI+BB r2 | 110 | 2.96 | %92.73 | +%3.978 | +%3.489 | 12.07 |
| Reconstructed fingerprint | 3169 | 85.32 | %41.65 | -%0.428 | -%0.641 | 0.79 |

Kaynak snapshot:
- `results/equal_2026_comparison_summary.json`
- `results/equal_2026_comparison_REPORT.md`

Fingerprint hattı bu araştırmanın ana adayı değildir; eşit kıyas için tutulmuş referanstır.

## 4. Araştırma disiplini

Temel kural:
- Threshold / kural seçimi 2023–2025 discovery + calibration verisinden yapılır.
- 2026 seçim için kullanılmaz; aday seçildikten sonra evaluation/holdout olarak açılır.
- 2026 sonucuna bakıp eşik değiştirmek yasaktır.
- Win rate yükseldi diye aday başarılı sayılmaz.
- Frekansı öldüren filtre başarısız olabilir.
- Bir filtre/feature ancak marjinal katkısı ölçülüyorsa eklenir; göstergeleri körlemesine üst üste yığma.

Her aday için en az şu metrikleri raporla:
- n
- signals/week
- win24
- mean net24
- median net24
- PF24
- p10 net24 / downside
- up3-before-dn2 ve danger-dn2-first uygun olduğunda
- sembol yoğunlaşması
- mümkünse aylık dönem dayanıklılığı

## 5. Phase 1 — Frequency / quality search

Kod:
- `src/phase1_frequency_quality_search.py`

Test edilen aileler:
- PPO/MACD histogram değişimi ve ivmesi
- DI spread / bearish pressure proxy
- VWAP mesafesi
- Bollinger %B
- relative volume
- Efficiency Ratio
- gevşetilmiş BTC 1H TSI_d1 + BTC 4H BB width eşikleri

Sonuç:
- 6,801 aday test edildi.
- Pre-2026 şartlarını aynı anda geçen aday: 0.
- Bu basit tek-feature eşik yaklaşımı hedefe ulaşmadı.

Sonuç dosyaları:
- `results/phase1_summary.json`
- `results/phase1_REPORT.md`

Frozen TSI+BB dönem davranışı:
- Discovery 2023–24: n=155, win24=%69.68, mean24=+%1.94, PF=2.99
- Calibration 2025: n=115, win24=%57.39, mean24=+%0.89, PF=1.58
- Cross-holdout pre-2026: n=157, win24=%56.05, mean24=+%0.50, PF=1.29
- Holdout 2026: n=51, win24=%86.27, mean24=+%4.34, PF=12.49

Ana ders:
- Performans rejime güçlü biçimde bağlı.
- Sadece basit indikatör eşiği ekleyerek frekans + kalite hedefi bulunamadı.

## 6. Phase 2 — Structural extension

Kod:
- `src/phase2_structural_extension.py`

Yerel bağımlılık:
- `lib/coin_mtf_core_snapshot.py`
- Bu dependency shared Multi-Timeframe klasöründen kopyalanmıştır; Phase 2 artık shared kodu import etmez.

Test edilen yapılar:
- bullish engulfing / hammer / sweep sonrası mum tepe kırılımı
- 15M CHoCH + higher low
- HL+HH
- 1H bearish structure veto
- 1H bullish structure
- son 48 saatlik dirence kalan alan
- swing low'a göre risk
- R/R proxy
- bunların gevşetilmiş TSI+BB havuzlarıyla birleşimleri

Son tamamlanan run:
- Eski workflow run: `35623154315`
- conclusion: success
- rows: 1,848
- tested structural candidates: 462
- viable pre-2026: 0

Sonuç:
- Tek yapısal kural + gevşetilmiş TSI/BB kombinasyonları da pre-2026 dayanıklılık şartını geçmedi.
- 2026 seçimde kullanılmadı.

Sonuç dosyaları:
- `results/phase2_summary.json`
- `results/phase2_REPORT.md`

## 7. Sıradaki araştırma

Phase 1 ve Phase 2 aynı şekilde daha fazla eşik tarayarak tekrarlanmayacak.

Sıradaki ana soru:
"Tek bir filtre yerine, girişe kadar olan HAREKET YOLU / STRUCTURAL SEQUENCE r2 kalitesini koruyup daha geniş aday havuzunu ayırabiliyor mu?"

Öncelik sırası:
1. 15M / 1H hareket yolu: pullback -> satış momentumunun yavaşlaması -> HL -> reclaim/break
2. Yapısal koşulların tek tek değil, sıralı olay dizisi olarak test edilmesi
3. Bull / mixed / bear rejimlerini ayrı ele almak
4. Aynı sembolde kısa aralıkta tekrarlanan sinyalleri episode/cooldown ile bağımsızlaştırmak
5. Aday seçimini yalnız pre-2026 üzerinde yapmak
6. Yeterli aday bulunursa 2026'yı tek seferlik evaluation olarak açmak
7. İyi aday çıkarsa threshold'u 2026'ya göre düzeltmemek; prospectif dönem için dondurmak

Araştırma hedefi hâlâ:
- >=5 sinyal/hafta öncelikli,
- mümkünse 10–15/hafta,
- anlamlı net P&L,
- yüksek PF,
- dönemler arası tutarlılık.

## 8. Yeni session başlatma protokolü

Kullanıcı yeni bir ChatGPT session açıp:
"gpt/TSI_BB_Structural_Phase/README.md oku ve devam et"
dediğinde yeni session şunları yapmalıdır:

1. Önce bu README'nin TAMAMINI oku.
2. `results/` içindeki son summary/REPORT dosyalarını kontrol et.
3. GitHub Actions'ta bu projeye ait son workflow run'ının gerçek durumunu kontrol et.
4. Tamamlanmış sonucu yeniden çalıştırma.
5. README'deki "Sıradaki araştırma" bölümünden devam et.
6. `Multi-Timeframe-Independent-Evidence` veya BTC fingerprint klasöründe yeni dosya oluşturma/değiştirme.
7. Yeni araştırma dosyasını bu klasörün `src/` altına ekle.
8. Çıktıları bu klasörün `results/` veya faza özel alt klasörüne kaydet.
9. Workflow gerekiyorsa yalnız `.github/workflows/gpt-tsi-bb-structural-project-*.yml` adını kullan.
10. Bir run gerçekten başlatılmadan "başladı/çalışıyor" deme.
11. Run bitmeden sonuç uydurma veya ara sonucu final diye raporlama.

## 9. README güncelleme kuralı — ZORUNLU

Bu README yaşayan proje hafızasıdır ve HER anlamlı araştırma adımından sonra güncellenecektir.

Her tamamlanan faz/run sonrası:
- son workflow run ID ve sonucu,
- kullanılan tarih aralığı,
- kullanılan evren,
- test edilen hipotez/kurallar,
- kaç aday test edildiği,
- seçim kriteri,
- discovery/calibration/holdout sonuçları,
- neyin başarısız olduğu,
- neyin korunacağı,
- sıradaki tek somut adım
bu README'ye eklenmelidir.

Bir kural başarısız olduysa silinmez; "başarısız denemeler" olarak kayda geçer. Böylece yeni session aynı deneyi tekrar etmez.

## 10. Dosya düzeni

```
gpt/TSI_BB_Structural_Phase/
  README.md
  OBJECTIVE.md
  src/
    phase1_frequency_quality_search.py
    phase2_structural_extension.py
    equal_2026_comparison.py
  lib/
    coin_mtf_core_snapshot.py
  results/
    phase1_summary.json
    phase1_REPORT.md
    phase2_summary.json
    phase2_REPORT.md
    equal_2026_comparison_summary.json
    equal_2026_comparison_REPORT.md
```

Bu klasör aktif araştırma alanıdır. Eski klasörler yalnız provenance / arşiv amaçlıdır.


## 11. Phase 3 — Movement Path — 2026-09-21

Workflow:
- `GPT - TSI BB Structural Project Phase 3`
- Run: `35630137879`
- Conclusion: `success`

Amaç:
Tek filtre yerine girişe kadar olan hareket dizisini test etmek:
- pullback,
- momentum/satış baskısının yavaşlaması,
- momentum dönüşü,
- higher-low,
- reclaim / önceki tepe kırılımı,
- bunların gevşetilmiş TSI+BB havuzlarıyla birleşimi.

Seçim disiplini:
- 2026 seçimde kullanılmadı.
- Aday seçimi yalnız pre-2026 discovery/calibration üzerinden yapıldı.

Sonuç:
- enriched rows: 1,848
- tested candidates: 187
- viable pre-2026 candidates: 0
- top candidates: none

Karar:
- Phase 3 hedefe ulaşmadı.
- Aynı sequence şablonlarını daha fazla threshold tarayarak tekrar etme.
- Sıradaki çalışma daha yüksek seviyede rejim/relative-strength ayrımı veya candidate-ranking yaklaşımına geçmelidir; tek binary filtre zinciri tekrarlanmamalıdır.


## Phase 9 — Horizon-Adaptive Trajectory Families (2026-09-21)
- Workflow run: 35644195419 — SUCCESS.
- Method: 12h/24h/48h pre-entry paths; winner labels at 12/24/48/72/168h. Each family chooses its own outcome horizon using PRE-2026 only.
- Events: 1845, data errors: 0.
- Candidate families tested: 112.
- Viable on discovery+calibration: 49.
- Greedy union selected 4 families and reached 199 signals in 2026 (~5.36/week), but 2026 quality dropped materially (24h win 71.86%, mean +1.99%, PF 2.84) and several individual families failed badly in 2026.
- Decision: Phase 9 proves frequency can be expanded beyond 5/week, but discovery+calibration alone is not robust enough. Do NOT promote Phase 9 union.
- Next: require the SAME chosen horizon to survive DISCOVERY + CALIBRATION + CROSS_HOLDOUT_PRE2026 before 2026 is opened. No 2026 selection.


## 12. Phase 4–8 — Tersine mühendislik hattı

### Phase 4 — Winner Reverse Engineering
- Run: `35636346584` — SUCCESS.
- r2 kazanan/kaybeden hareket özellikleri karşılaştırıldı; 340 özellikten 111 kararlı fark, 24 fingerprint özelliği.
- Yeni viable genişleme: 0.
- Ders: r2 kazananlarında ölçülebilir yapı var fakat az sayıdaki kaybeden nedeniyle scalar fingerprint kırılgan.

### Phase 5 — Winner Prototype
- Run: `35639850594` — SUCCESS.
- 340 özellikten 40 özellikli kazanan-prototip benzerliği ile non-r2 R1 olayları arandı.
- Yeni viable genişleme: 0.
- Ders: scalar prototip benzerliği yeterli değil; doğrudan fiyat yolu/trajectory gerekli.

### Phase 6 — Direct Trajectory
- Run: `35640912701` — SUCCESS.
- 577 frozen TSI+BB olayı; giriş öncesi 48 saatlik 15M fiyat yolu, 13 trajectory noktası.
- Yeni viable genişleme: 0.
- Ders: yalnız 48 saatlik fiyat şekli r2 kalitesinde ek sinyal ayırmadı.

### Phase 7 — Broad Trajectory
- Run: `35641902696` — SUCCESS.
- Evren 1,847 olaya genişletildi.
- İlk viable ikinci aile bulundu: `NON_R2_TRAJECTORY_Q925`.
- r2 + ikinci aile 2026: 133 sinyal, 3.58/hafta; win24 %86.47, mean24 +%3.45, PF24 6.39.
- Başarılı ilerleme fakat >=5/hafta hedefi karşılanmadı.

### Phase 8 — Multiwindow Trajectory
- Run: `35643848911` — SUCCESS.
- 12/24/48 saat giriş-öncesi yollar ve 24/72/168 saat sonuç ufukları; 67 aile.
- Viable: 0.
- Metodolojik hata: bütün sonuç ufuklarını aynı anda pozitif tutma şartı gereğinden sertti. Kullanıcı sabit 24/48 saat çıkış şartı koymamıştır.
- Bundan sonra her aile kendi uygun sonuç ufkunu pre-2026 veriden seçebilir; 12/24/48/72/168 saat ayrı incelenir.

## 13. Phase 9 — Horizon-Adaptive Trajectory
- Run: `35644195419` — SUCCESS.
- 112 aile; Discovery+Calibration'da 49 viable.
- 4 aile birleşimi 2026'da 199 sinyal = 5.36/hafta.
- Ancak 24s kalite %71.86 WR, +%1.99 mean, PF 2.84'e düştü.
- Frekans hedefi ilk kez aşıldı fakat kalite kaybı kabul edilmedi.
- Ders: D+C tek başına overfit'i engellemiyor; cross-holdout zorunlu.

## 14. Phase 10 — Cross-Holdout Gate
- Run: `35645359556` — SUCCESS.
- 112 aile; aynı sonuç ufkunda Discovery + Calibration + CROSS_HOLDOUT_PRE2026 şartı.
- Cross-gated viable: 31.
- Birleşim 2026: 199 sinyal = 5.36/hafta; win24 %71.86, mean24 +%1.99, median24 +%2.50, PF24 2.84.
- Sonuç: frekans yeterli fakat kalite r2'ye göre fazla düştüğü için kabul edilmedi.
- Ders: yalnız trajectory benzerliği, rejim değişimini yeterince açıklamıyor.

## 15. Phase 11 — Regime-Conditioned Trajectory
- Run: `35647958921` — SUCCESS.
- Evren: 1,845 olay; veri hatası 0.
- BTC/alt volatilite ve TSI rejimleri içinde causal trajectory tersine mühendisliği.
- Pre-2026 Discovery + Calibration + Cross üzerinde 57 robust aday; 5 aile birleşime seçildi.
- 2026 birleşim: 139 sinyal = 3.74/hafta, 120 sembol.
- 24s: WR %85.61, mean +%3.33, median +%3.21, PF 5.77.
- 48s: WR %84.89, mean +%4.97, median +%4.61, PF 8.02.
- Sonuç: Phase 9/10'a göre kalite belirgin toparlandı; fakat >=5 sinyal/hafta hedefi karşılanmadı. Araştırma devam edecek.
- 2026 seçimde kullanılmadı.

## 16. Canonical sinyal sistemi dosyası

- `latest_signal_system.py` bu projenin TEK güncel sinyal sistemi tanımıdır.
- Araştırmada daha iyi ve kabul edilebilir bir sistem bulunduğunda bu dosya güncellenecek; eski başarısız deneyler README'den silinmeyecek.
- Şu an PROMOTED çekirdek: frozen TSI+BB r2. Phase 11 genişlemesi araştırma adayıdır; frekans hedefini karşılamadığı için promoted çekirdeğin yerine geçirilmemiştir.
- WR tek başına karar ölçütü değildir. WR düşüşü ancak mean/median P&L ve PF'deki yeterli artışla kabul edilebilir.

## 17. Sıradaki araştırma

Phase 11 kaliteyi koruyarak 3.74/haftaya ulaştı. Sıradaki çalışma aynı threshold taramasını tekrar etmeyecek.

Öncelik:
1. Phase 11'in iyi çalışan rejim/trajectory ailelerini koru.
2. Eksik frekansı farklı ve bağımsız hareket ailesinden tamamla; mevcut aileleri gevşetip kaliteyi ezme.
3. Discovery + Calibration + CROSS_HOLDOUT_PRE2026 zorunlu.
4. 2026 yalnız final evaluation.
5. >=5/hafta yakalanırsa aylık/haftalık kümelenme, sembol yoğunlaşması, overlap ve maliyet stres testi yap.
6. Kabul edilen sistem değiştiğinde `latest_signal_system.py` aynı committe güncellenecek.
