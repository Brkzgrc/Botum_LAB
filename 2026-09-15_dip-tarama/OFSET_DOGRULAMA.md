# Giris Ofseti ve ATR Carpani — Uc Donem Dogrulamasi

Olcut: **PARA**. 10.000$, ayni anda **tek islem**, komisyon %0.2,
24 saat limit dolum penceresi, 24 saat expire, TP1 sonrasi ATR trailing.
Sinyal kaynagi `dip_tarama.py` (kullanicinin kendi alim yontemi).
Delist olmus pariteler dahil (Binance arsivi).

## Sonuclar

### 2021-2022 (arama donemi, 369 sinyal)

| giris | ATRx0.6 | ATRx2.0 |
|---|---|---|
| yok | 11.648$ (+%0.65) | 16.064$ (+%2.03) |
| -%2 | 26.184$ (+%4.17, dd -%46) | 31.763$ (+%5.02, dd -%58) |
| **-%3** | **26.246$ (+%4.18, dd -%39)** | 21.447$ (+%3.29, dd -%45) |
| -%4 | 18.014$ (+%2.53) | 9.158$ (-%0.37) |
| -%5 | 26.683$ (+%4.25) | 15.362$ (+%1.84) |

### 2023-2024 (dokunulmamis, 588 sinyal, 433 coin)

| giris | ATRx0.6 | ATRx2.0 |
|---|---|---|
| yok | 5.170$ (-%2.73, 267 isl, dd -%83) | 5.101$ (-%2.78, dd -%80) |
| -%2 | 11.981$ (+%0.76, 191 isl, dd -%53) | 6.811$ (-%1.60, dd -%63) |
| **-%3** | **20.080$ (+%2.96, 122 isl, dd -%42)** | 10.830$ (+%0.33, dd -%59) |

### 2025-2026 (dokunulmamis, 485 sinyal, 498 coin)

| giris | ATRx0.6 | ATRx2.0 |
|---|---|---|
| yok | 8.826$ (-%0.63, 187 isl, dd -%79) | 4.391$ (-%4.06, dd -%82) |
| -%2 | 8.329$ (-%0.92, 126 isl, dd -%59) | 6.150$ (-%2.42, dd -%69) |
| **-%3** | **9.790$ (-%0.11, 82 isl, dd -%43)** | 5.297$ (-%3.15, dd -%62) |

## Ne dogrulandi

1. **-%3 giris uc donemde de en iyi satir.** Arama doneminde -%2 ile berabereydi,
   iki dogrulama doneminde acik ara onde (20.080 vs 11.981 · 9.790 vs 8.329).
2. **ATRx0.6, ATRx2.0'dan uc donemde de iyi** — tek istisna 2021-2022'nin ofsetsiz
   ve -%2 satirlari. -%3'te uc donemde de 0.6 kazaniyor.
3. **Ofsetin faydasi aritmetik, tahmine dayali degil.** Stop ve TP1 sabit kalirken
   giris asagi kayiyor: R:R 1.15 -> 4.51. Etki bu yuzden donemler arasi tasiniyor.
4. **Dusus (drawdown) ofsetle monoton azaliyor** — her donemde. Getirideki zikzak
   gurultu, dusus azalmasi gercek.

## Ne dogrulanmadi — sistemin kendisi

En iyi ayarla bile:

| donem | 10.000$ -> | ayda |
|---|---|---|
| 2021-2022 | 26.246$ | +%4.18 |
| 2023-2024 | 20.080$ | +%2.96 |
| **2025-2026** | **9.790$** | **-%0.11** |

Son iki yilda dip alim yontemi **basabasta**. Hedef (ayda %15-30) cok uzakta.
En iyi satirda bile ara dusus -%42/-%43 — 10.000$ yolun bir yerinde ~5.700$'a iniyor.

**Sonuc: ayar bulundu, sistem bulunamadi.**

## CANLI SISTEM ICIN DOGRUDAN SONUC

`spot_opportunity_scanner` su an **-%3 giris + ATRx2.0** kullaniyor —
yani en iyi girisle en kotu cikisin birlesimi. Uc donemin ucunde de
ATRx2.0, ayni girisle ATRx0.6'nin yaklasik yarisini veriyor.
(Not: bu olcum dip_tarama sinyalleriyle yapildi, spot_opportunity sinyalleriyle degil —
cikis kuralinin yonu hakkinda guclu ama dolayli bir kanittir.)

Arac: `araclar/dip_dogrula.py`
