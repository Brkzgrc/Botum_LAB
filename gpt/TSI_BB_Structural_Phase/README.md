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
