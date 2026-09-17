# BTC Multi-Timeframe Reversal Propagation — Large Historical Study

Setup seçiminde sabit RSI/KDJ/W%R/StochRSI seviyeleri kullanılmadı. Tüm adaylar göstergelerin yönü, eğim değişimi, spread değişimi, OBV hareketi ve göreli fiyat/mum yapısından üretildi. Sabit yüzde eşikleri yalnızca SONUCU ölçmek için kullanılır.

Dönem: 2024-01-01 → 2026-09-18 | keşif: 2024-2025 | kör holdout: 2026 | aday kural: 42

## Keşif verisinde seçilen aday

**CTX4+trig5s+H1recent2h**

Keşif n=640; 12s ort. getiri 0.08%; win 51.41%; MFE 1.33%; MAE -1.25%.

2026 holdout n=220; 3s/6s/12s/24s ort. getiriler -0.03 / -0.06 / 0.01 / 0.04%. 12s win 46.36%; MFE>=1% 38.18%; ort. MFE 1.03%; ort. MAE -1.06%.

12s ortalama getiri bootstrap %95 GA: [-0.17, 0.21].

## 2026 baseline

Her 4 saatte bir kör snapshot: n=1557; 12s ort. getiri -0.01%; win 50.10%; MFE 1.12%; MAE -1.20%.

## Dönüş bilgisinin zaman dilimleri arasında yayılma sırası

- mixed: 5723 olay (35.8%)
- 15m->1h->4h: 4682 olay (29.3%)
- 4h/1h before 15m: 2837 olay (17.7%)
- 1h->15m->4h: 2763 olay (17.3%)

Bu sıra analizi bağımsız hareket-dönüş event'lerinin en yakın 1H/4H event'leriyle zaman farkına bakar; setup kuralı değildir.

## Güçlü yükseliş kapsaması

2026'daki 12 saatlik ileri getirinin üst %10'luk dilimi güçlü-yükseliş anchor'ı olarak tanımlandı (eşik sonuç dağılımından gelir: 1.57%). Bir setup'ın anchor'dan önceki 6 saatte görünme oranı ölçüldü.

- H4turn16h+H1turn4h+trig4: kapsama 55.7% | medyan öncülük 2.50s
- CTX2+trig4: kapsama 55.7% | medyan öncülük 2.62s
- CTX2+trig4s: kapsama 55.7% | medyan öncülük 2.75s
- H4turn16h+H1turn4h+trig4s: kapsama 54.2% | medyan öncülük 2.50s
- CTX2+trig5: kapsama 53.7% | medyan öncülük 2.75s

## Yorumlama kuralı

Bu test tek bir tarih örneğini ezberlemiyor. Aday, yalnız 2024-2025 verisinde seçildi ve 2026'ya değişmeden taşındı. Holdout sonucu baseline'dan anlamlı biçimde iyi değilse setup doğrulanmış sayılmayacak. İyiyse sıradaki adım BTC dışı coinlerde aynı hareket mantığını, sembol kimliğini özellik yapmadan sınamaktır.
