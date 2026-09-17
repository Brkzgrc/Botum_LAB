# Directional Sequence Mining — sabit değer yok

Bu aşama RSI=30, W%R=-80, StochRSI=20 gibi hiçbir sabit gösterge değerini kullanmaz. Her gösterge yalnız + / - / 0 yön dizisine çevrilir. Örnek: `H4_STOCH_P3=--+` son üç tamamlanmış 4H barda StochRSI hareketinin aşağı, aşağı, yukarı döndüğü anlamına gelir.

Geniş olay sayısı: 2024=841, 2025=807, kör 2026=590.
2024 ve 2025'in ikisinde de geniş tabandan iyi kalan tekil desen=24; ikili desen=2.
Keşif/ara-validasyonla seçilen setup: **H1_OBV_P4=++0- AND H1_RSI_P4=++0-**
- 2024: n=49 | 12s ort 0.150% | medyan 0.048% | win 53.1% | MFE 1.61% | MAE -1.48% | 24s ort 0.070%
- 2025: n=37 | 12s ort 0.525% | medyan 0.195% | win 56.8% | MFE 1.33% | MAE -0.90% | 24s ort 0.159%
- 2026: n=27 | 12s ort -0.231% | medyan -0.346% | win 37.0% | MFE 0.92% | MAE -1.26% | 24s ort 0.036%
2026 setup - geniş taban 12s getiri farkı bootstrap: -0.209% [%95 GA -0.632, 0.189]

## En güçlü tekil yön desenleri
- M15_STOCH_P4=-0++ | train konservatif lift 0.361% | 2026 n=29, 12s=0.395%
- H1_OBV_P4=0++0 | train konservatif lift 0.336% | 2026 n=20, 12s=0.007%
- H1_MACD_P4=++0- | train konservatif lift 0.254% | 2026 n=29, 12s=0.005%
- H4_WPR_P3=-0+ | train konservatif lift 0.204% | 2026 n=60, 12s=0.017%
- M15_STOCH_P4=-00+ | train konservatif lift 0.189% | 2026 n=44, 12s=0.251%
- H4_OBV_P3=-++ | train konservatif lift 0.181% | 2026 n=34, 12s=-0.247%
- H1_OBV_P4=++0- | train konservatif lift 0.148% | 2026 n=53, 12s=0.140%
- H1_OBV_P4=+0+- | train konservatif lift 0.138% | 2026 n=33, 12s=0.068%
- H1_STOCH_P4=++-- | train konservatif lift 0.135% | 2026 n=41, 12s=0.139%
- H4_RSI_P3=-0+ | train konservatif lift 0.125% | 2026 n=56, 12s=0.046%
- M15_RSI_P4=---+ | train konservatif lift 0.113% | 2026 n=45, 12s=-0.257%
- H1_RSI_P4=++0- | train konservatif lift 0.111% | 2026 n=42, 12s=-0.012%

## En güçlü ikili yön desenleri
- H1_OBV_P4=++0- AND H1_RSI_P4=++0- | train konservatif lift 0.119% | 2026 n=27, 12s=-0.231%
- H4_RSI_P3=0++ AND H4_WPR_P3=0++ | train konservatif lift 0.106% | 2026 n=30, 12s=-0.331%