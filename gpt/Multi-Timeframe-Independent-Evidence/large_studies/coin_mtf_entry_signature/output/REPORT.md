# Coin MTF Entry-Time Signature Discovery — Strictly Causal

Amaç: 15M sinyali çıktığı anda, gelecekteki 1H mumunu görmeden, 1H'ın 4 saat içinde teyit verip vermeyeceğini giriş anındaki hareket geometrisinden ayırmak.

## Look-ahead kilidi
- Sabit RSI/KDJ/W%R/StochRSI seviyesi feature değildir.
- 15M feature yalnızca kapanmış 15M mumdan gelir.
- 1H/4H/BTC4H feature yalnızca tamamen kapanmış üst-zaman mumu kapandıktan sonra kullanılabilir.
- Giriş karar anında değil; ek 15 dakika güvenlik gecikmesi sonrası bir sonraki açılıştadır.
- Gelecekteki 1H teyidi sadece hedef/etikettir, feature değildir.
- Model ve eşik yalnız TRAIN+CALIBRATION tarafında seçilir; FINAL double-holdout seçim sürecine hiç girmez.

Olay=10360 | feature=224 | hata=0
Seçilen model=LOGISTIC | train-prob quantile=0.50 | threshold=0.5464
Calibration seçili: n=1015 | H1 teyit=71.8% | net12=%-0.259

## FINAL double-holdout
BASE: n=976 | H1 teyit=64.7% | net12=%-0.266 | win=39.9%
SELECTED: n=510 | H1 teyit=71.0% | net12=%-0.219 | win=41.2% | selected=52.3%
Selected - base net12 cluster-bootstrap: %0.049 [%95 GA -0.173, 0.269]

## En etkili giriş-anı hareket feature'ları
- h1_motion_pos: 0.9950
- h4_rsi_d1n: 0.7887
- btc4_rsi_d1n: 0.7588
- h4_rsi_accn: 0.7406
- btc4_wpr_d1n: 0.7186
- btc4_kdj_spread_d3n: 0.6016
- btc4_macd_hist_accn: 0.5887
- btc4_stoch_k_d1n: 0.5519
- btc4_close_loc: 0.5248
- h1_body_signed_pct: 0.4904
- m15_kdj_spread_accn: 0.4821
- btc4_kdj_spread_accn: 0.4590
- btc4_upper_wick_frac: 0.4575
- h1_motion_neg: 0.4109
- btc4_kdj_j_d1n: 0.3946

## Confirm / no-confirm ayrımında üç bölümde de aynı yönü koruyan feature'lar
- h1_obv_accn: train=-0.311, calib=-0.286, final=-0.385
- h1_rsi_d1n: train=-0.259, calib=-0.440, final=-0.319
- h1_body_signed_pct: train=-0.255, calib=-0.379, final=-0.327
- h1_obv_sign4: train=-0.500, calib=-1.000, final=-0.250
- h1_motion_rise: train=-0.250, calib=-0.500, final=-0.500
- h1_price_ret_1: train=-0.244, calib=-0.383, final=-0.312
- h1_wpr_accn: train=-0.224, calib=-0.245, final=-0.332
- h1_wpr_d1n: train=-0.210, calib=-0.341, final=-0.353
- h1_kdj_j_accn: train=-0.210, calib=-0.302, final=-0.289
- h1_kdj_spread_accn: train=-0.206, calib=-0.276, final=-0.286
- h1_rsi_accn: train=-0.202, calib=-0.229, final=-0.357
- h1_close_loc: train=-0.198, calib=-0.399, final=-0.421
- h1_obv_d1n: train=-0.196, calib=-0.394, final=-0.183
- h1_macd_hist_accn: train=-0.176, calib=-0.222, final=-0.335
- h1_price_accel_1: train=-0.176, calib=-0.182, final=-0.344