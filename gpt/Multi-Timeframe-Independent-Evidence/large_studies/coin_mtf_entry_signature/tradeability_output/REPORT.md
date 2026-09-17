# Tradeability Signature — Strictly Causal

Bu aşamada hedef artık gelecekteki 1H teyidini tahmin etmek değil; giriş anındaki hareket geometrisinden gerçekten işlem yapılabilir alt kümeyi ayırmaktır.

- Sabit osilatör seviyesi yok.
- Gelecek 1H/4H verisi feature değil.
- Aynı katı giriş modeli korunur: sinyal kapanışı + ek 15M gecikme + sonraki açılış.
- Model/eşik yalnız calibration'da seçilir; final double-holdout dokunulmadan kalır.

Champion=WIN_LOGISTIC q=0.60 threshold=0.5327
Calibration: n=823 net12=-0.208% win=45.2% H1conf=62.6% excursion_edge=0.007%

## FINAL double-holdout
BASE n=976 net12=-0.266% win=39.9% MFE=2.43% MAE=-2.28%
SELECTED n=406 (41.5%) net12=-0.365% win=36.7% MFE=2.13% MAE=-2.23% H1conf=62.1%
Selected-base net12 cluster bootstrap: -0.101% [%95 -0.346, 0.134]

## Top movement features
### WIN_LOGISTIC
- btc4_rsi_d1n: 1.4134
- btc4_kdj_j_d1n: 1.0013
- btc4_macd_hist_accn: 0.9198
- btc4_range_pct: 0.8707
- btc4_kdj_spread_d3n: 0.7138
- m15_price_ret_4: 0.6241
- btc4_stoch_spread_d1n: 0.6049
- h4_kdj_j_d1n: 0.5731
- btc4_range_log_ratio: 0.4725
- btc4_kdj_spread_d1n: 0.4453
- h1_range_pct: 0.4314
- btc4_upper_wick_frac: 0.4257
- m15_stoch_k_accn: 0.4195
- btc4_close_loc: 0.4118
- m15_macd_hist_d1n: 0.4063