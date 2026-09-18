# Frozen MTF Lead-Lag Rule — Broad Historical Validation

Frozen rule: M15_ENGULF & M15_HL_HH & LEAD_GAP4

Bu çalışma kuralı yeniden seçmez/değiştirmez. Sabit osilatör seviyesi setup şartı değildir.
15M karar yalnız kapanmış mumdan gelir; 1H/4H/BTC4H yalnız tamamen kapanmış mumdan gelir.
Giriş karar anında değil, ek 15 dakika güvenlik gecikmesi sonrası bir sonraki 15M açılışındadır.

Window: 2023-01-01..2026-09-18 | universe=400 | events=154097 | selected=8174 | selected symbols=390

## ALL
Base: n=154053 net12@0.20=-0.137% win=45.5%
Selected: n=8173 net12@0.20=-0.141% win=45.2% H1<=4h=71.5% MFE12=3.03% MAE12=-2.90%

## PRE2026
Base: n=117082 net12@0.20=-0.149% win=46.2%
Selected: n=6618 net12@0.20=-0.195% win=45.0% H1<=4h=71.8% MFE12=3.00% MAE12=-2.98%

## NEW_SYMBOLS
Base: n=111264 net12@0.20=-0.150% win=45.4%
Selected: n=5300 net12@0.20=-0.173% win=45.4% H1<=4h=71.6% MFE12=3.10% MAE12=-2.95%

## NEW_SYMBOLS_2026
Base: n=26083 net12@0.20=-0.096% win=43.0%
Selected: n=876 net12@0.20=-0.106% win=44.2% H1<=4h=68.9% MFE12=3.28% MAE12=-2.77%

## FRESH_EVIDENCE
Base: n=143165 net12@0.20=-0.139% win=45.6%
Selected: n=7494 net12@0.20=-0.184% win=44.9% H1<=4h=71.5% MFE12=3.04% MAE12=-2.95%

## Y2023
Base: n=29429 net12@0.20=0.047% win=45.8%
Selected: n=1433 net12@0.20=-0.001% win=45.3% H1<=4h=73.8% MFE12=2.97% MAE12=-2.36%

## Y2024
Base: n=38579 net12@0.20=-0.197% win=47.0%
Selected: n=2270 net12@0.20=-0.020% win=48.5% H1<=4h=73.1% MFE12=3.20% MAE12=-3.14%

## Y2025
Base: n=49074 net12@0.20=-0.228% win=45.7%
Selected: n=2915 net12@0.20=-0.426% win=42.1% H1<=4h=69.9% MFE12=2.87% MAE12=-3.16%

## Y2026
Base: n=36971 net12@0.20=-0.099% win=43.2%
Selected: n=1555 net12@0.20=0.088% win=46.0% H1<=4h=70.1% MFE12=3.14% MAE12=-2.54%

## Bootstrap
All selected-base: {'mean': -0.004051121597577639, 'ci_low': -0.08622248472037865, 'ci_high': 0.07818236466922102}
Fresh evidence selected-base: {'mean': -0.0450952614096896, 'ci_low': -0.1327865863663248, 'ci_high': 0.046432661906910457}

## Liquidity (descriptive; NOT a selection gate)
- <1M/day: n=1162 net12@0.20=-0.034% win=45.7%
- 1-5M/day: n=3108 net12@0.20=-0.206% win=45.2%
- 5-20M/day: n=2148 net12@0.20=-0.091% win=46.0%
- >=20M/day: n=1755 net12@0.20=-0.158% win=43.7%