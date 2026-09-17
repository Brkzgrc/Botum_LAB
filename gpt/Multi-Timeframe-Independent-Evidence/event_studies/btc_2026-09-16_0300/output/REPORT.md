# BTC 16-09-2026 03:00 TR — 4H → 1H → 15M Hareket Yayılımı Olay Çalışması

Bu çalışma sabit RSI/KDJ/W%R/StochRSI eşiklerini **setup kuralı olarak kullanmaz**. Seviyeler yalnızca bağlamdır; tespit yön değişimi, eğim, spread değişimi, OBV akışı ve fiyat yapısına dayanır.

## En önemli metodoloji notu

TradingView'da `03:00` etiketli 4H mum 03:00 TR'de açılır ve 07:00 TR'de kapanır. Bu yüzden iki şeyi ayırdık: **kapanmış-mum analizi** ve 15 dakikalık veriden yeniden oluşturulan **canlı/intrabar 4H durumu**. Böylece geleceği görme (look-ahead) yok.

## İlk hareket dönüşleri

- 15M: hareket ailesinden en az 4/6'sının 3 ardışık snapshot iyileşmesi: **2026-09-16 01:45 TR**
- 1H (canlı/intrabar): aynı tanım: **2026-09-16 02:30 TR**
- 4H (canlı/intrabar): aynı tanım: **2026-09-16 03:30 TR**

## Hareket + fiyat yapısı birlikte ilk belirme

- 15M: **2026-09-15 23:45 TR**
- 1H: **2026-09-16 02:00 TR**
- 4H intrabar: **2026-09-16 12:00 TR**

### 15M ilk yapı destekli dönüş — 2026-09-15 23:45 TR
Giriş referansı 75935.24. Sonraki 24 saatte MFE **+0.82%**, MAE **-1.15%**. 4s/8s/12s/24s getiriler: -0.21% / -0.09% / -0.26% / +0.32%.

### 1H ilk yapı destekli dönüş — 2026-09-16 02:00 TR
Giriş referansı 75896.99. Sonraki 24 saatte MFE **+0.87%**, MAE **-1.10%**. 4s/8s/12s/24s getiriler: +0.08% / -0.02% / +0.03% / -0.07%.

### 4H intrabar ilk yapı destekli dönüş — 2026-09-16 12:00 TR
Giriş referansı 75796.23. Sonraki 24 saatte MFE **+1.29%**, MAE **-0.96%**. 4s/8s/12s/24s getiriler: +0.00% / -0.09% / +0.42% / +1.18%.

## Mum ve grafik yapısı araştırması

Otomatik olarak hammer-benzeri mum, bullish engulfing, önceki tepe reclaim, 8-mum dip süpürme/reclaim, higher-low/higher-high ve yerel swing dizileri tarandı. Bunlar tek başına şart değildir; göstergelerin hareket yönüyle birlikte zamanlanır.

### 15M swing yapısı
Son yerel dipler: 2026-09-16 02:30=75562, 2026-09-16 04:45=75458, 2026-09-16 06:45=75768, 2026-09-16 08:00=75678, 2026-09-16 11:15=75350, 2026-09-16 14:15=75874, 2026-09-16 17:00=75423, 2026-09-16 17:45=75476
Son yerel tepeler: 2026-09-16 07:30=76023, 2026-09-16 09:00=76029, 2026-09-16 10:00=76098, 2026-09-16 12:00=75950, 2026-09-16 13:00=76046, 2026-09-16 14:45=76304, 2026-09-16 16:45=75941, 2026-09-16 17:30=75830

### 1H swing yapısı
Son yerel dipler: 2026-09-16 04:00=75458, 2026-09-16 08:00=75678, 2026-09-16 11:00=75350, 2026-09-16 17:00=75423, 2026-09-16 21:00=75065, 2026-09-17 01:00=75633, 2026-09-17 05:00=76055, 2026-09-17 16:00=76000
Son yerel tepeler: 2026-09-16 05:00=76111, 2026-09-16 10:00=76098, 2026-09-16 14:00=76304, 2026-09-16 21:00=76561, 2026-09-17 04:00=76774, 2026-09-17 12:00=76770, 2026-09-17 15:00=77179, 2026-09-17 20:00=76970

### 4H swing yapısı
Son yerel dipler: 2026-09-15 19:00=74968, 2026-09-16 19:00=75065
Son yerel tepeler: 2026-09-15 19:00=77343, 2026-09-17 03:00=76774

## Çalışmanın sınadığı asıl hipotez

Tek bir zaman diliminde 'RSI kaç?' sorusu yerine şu zincir test edilir: **4H'ta satış baskısının zayıflaması / dönüşe izin veren zemin → 1H'ta yön değişiminin oluşması → 15M'de fiyat-yapısı ile giriş tetiği**. Ters yönden bakıldığında ise gerçek dönüş çoğu kez **15M → 1H → 4H** şeklinde teyit yayılımı gösterebilir. İki sıra birbirine zıt değildir: biri üstten-aşağı bağlam/karar akışı, diğeri alttan-yukarı gerçekleşen teyit yayılımıdır.

## Sonraki araştırma önerisi

Bu tek olaydan kural çıkarılmamalı. Aynı hareket-imzasını BTC'nin yüzlerce yükseliş/dönüş episode'unda tarayıp zaman gecikmesi dağılımı çıkarılmalı: 4H baskı-zayıflama anı, 1H dönüş anı, 15M tetik anı; ayrıca yanlış tetiklerde aynı dizinin ne kadar görüldüğü ölçülmeli. Sabit seviyeler sadece açıklayıcı bağlam olarak raporlanmalı, seçim filtresi yapılmamalı.
