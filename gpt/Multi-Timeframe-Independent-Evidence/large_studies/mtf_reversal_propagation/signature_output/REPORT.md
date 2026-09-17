# Motion Signature Discovery — true/false separation

Bu ikinci aşama sabit RSI/W%R/KDJ/StochRSI seviyelerini özellik olarak bile kullanmaz. Yalnız değişim, eğim, spread, OBV akışı, geçmiş fiyat hareketi, mum/geometri ve zaman-dilimi dönüş gecikmeleri kullanılır.

Baz olay: 4H turn within 16h + 1H turn within 4h + structure-supported 15m movement turn. Keşif olayları=1782, kör 2026 olayları=620, hareket özelliği=98.
RF hata: train MAE=1.160, OOB MAE=1.222, holdout MAE=1.047.

## 2026 sonuç
- BROAD_HOLDOUT: n=620 | 3/6/12/24s ort getiri -0.011/0.030/0.059/0.149% | 12s win 51.5% | MFE 1.12% | MAE -1.09%
- MODEL_TOP20_HOLDOUT: n=103 | 3/6/12/24s ort getiri -0.049/0.039/0.064/0.309% | 12s win 50.5% | MFE 1.26% | MAE -1.35%
- MODEL_TOP10_HOLDOUT: n=53 | 3/6/12/24s ort getiri -0.123/-0.029/-0.026/0.103% | 12s win 52.8% | MFE 1.24% | MAE -1.32%
Top20 - broad 12s ort getiri farkı bootstrap: 0.005% [%95 GA -0.346, 0.340]
Top10 - broad 12s ort getiri farkı bootstrap: -0.081% [%95 GA -0.524, 0.405]

## En etkili hareket özellikleri
- h4_stoch_spread_d3: 0.1010
- price_ret_1h: 0.0683
- price_accel_1h: 0.0541
- h4_wpr_d3: 0.0401
- h1_rsi_d1: 0.0299
- h1_macd_hist_d3: 0.0268
- price_accel_4h: 0.0265
- price_ret_4h: 0.0250
- m15_stoch_k_d1: 0.0232
- price_ret_12h: 0.0224
- h4_rsi_d1: 0.0210
- h1_stoch_spread_d3: 0.0201
- h4_body_frac: 0.0199
- h4_wpr_d1: 0.0192
- m15_rsi_d3: 0.0178

## Sığ ağacın insan-okunur keşif kuralı
```
|--- h4_stoch_spread_d3 <= 33.3241
|   |--- price_ret_1h <= -0.3543
|   |   |--- value: [0.9258]
|   |--- price_ret_1h >  -0.3543
|   |   |--- h4_wpr_d3 <= 38.2308
|   |   |   |--- value: [0.1148]
|   |   |--- h4_wpr_d3 >  38.2308
|   |   |   |--- value: [-0.3790]
|--- h4_stoch_spread_d3 >  33.3241
|   |--- value: [-0.9143]

```
Bu ağaç yalnız açıklama içindir; seçim Random Forest'ın 2024-2025 OOB tahmin kesimlerinden yapılır ve 2026'ya değişmeden uygulanır.