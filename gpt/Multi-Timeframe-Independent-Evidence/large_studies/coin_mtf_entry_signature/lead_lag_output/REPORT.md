# Lead-Lag Movement Rule Discovery — Strictly Causal

Arama sabit RSI/KDJ/W%R/StochRSI değerleri kullanmaz. Yalnız hareket yönleri, 15M→1H lead/lag ilişkisi, kapanmış H4/BTC4 hareketi ve mum/fiyat yapısı kullanılır.

Token=35 | test edilen kural=6494 | train+calibration'da ikisi de pozitif kural=74
Seçilen: `M15_ENGULF & M15_HL_HH & LEAD_GAP4`
Train: n=199 net12=0.794% win=51.8%
Calibration: n=127 net12=0.225% win=48.8%

## Final double-holdout
Base: n=976 net12=-0.266% win=39.9%
Selected: n=60 net12=0.177% win=35.0%
Bootstrap selected-base: {'mean': 0.44196419976553086, 'ci_low': -0.6055918120035333, 'ci_high': 2.1003159163789693}

## Ultra holdout (yeni rezerv)
Base: n=95 net12=0.463%
Selected: n=7 net12=6.448% win=42.9%
Bootstrap selected-base: {'mean': 5.392296575764124, 'ci_low': -1.529119112577985, 'ci_high': 16.522414691615836}