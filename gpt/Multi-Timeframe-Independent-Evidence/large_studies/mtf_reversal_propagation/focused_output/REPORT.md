# Focused StochRSI Motion Transition Validation

Setup sabit StochRSI seviyesi kullanmaz. `-0++` ve `-00+`, StochRSI K hareketi + K/D spread hareketinin 15 dakikalık yön durumlarıdır: düşüş -> nötrleme -> yukarı dönüş.

## 2024
Setup n=112 | 3/6/12/24s ort 0.053/0.193/0.300/0.436% | 12s win 54.5% | MFE 1.59% | MAE -1.32%.
1H teyit <=1/2/4s: 29.5/45.5/70.5%. 4H teyit <=4/8/12s: 7.1/36.6/49.1%. Sıralı 15M->1H->4H: 32.1%.

15M girişten sonra 1H <=4s teyit GELİRSE: n=79, 12s=0.523%, win=60.8%. Teyit GELMEZSE: n=33, 12s=-0.236%, win=39.4%.

## 2025
Setup n=109 | 3/6/12/24s ort 0.064/0.063/0.297/0.172% | 12s win 57.8% | MFE 1.26% | MAE -1.07%.
1H teyit <=1/2/4s: 34.9/50.5/74.3%. 4H teyit <=4/8/12s: 16.5/38.5/58.7%. Sıralı 15M->1H->4H: 43.1%.

15M girişten sonra 1H <=4s teyit GELİRSE: n=81, 12s=0.491%, win=63.0%. Teyit GELMEZSE: n=28, 12s=-0.266%, win=42.9%.

## 2026
Setup n=73 | 3/6/12/24s ort 0.152/0.151/0.309/0.126% | 12s win 63.0% | MFE 1.30% | MAE -0.94%.
1H teyit <=1/2/4s: 32.4/41.9/68.9%. 4H teyit <=4/8/12s: 17.6/47.3/56.8%. Sıralı 15M->1H->4H: 37.8%.

15M girişten sonra 1H <=4s teyit GELİRSE: n=50, 12s=0.732%, win=74.0%. Teyit GELMEZSE: n=23, 12s=-0.613%, win=39.1%.

2026 setup - geniş olay 12s getiri farkı: 0.334% [%95 GA -0.031, 0.714].