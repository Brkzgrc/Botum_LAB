# 2026-09-15 — Dip Tarama

Kullanicinin kendi alim yonteminin mekanik kural haline getirilmis hali.
Kural 5 gercek ornekten cikarildi, uydurulmadi.

## Kural

|            | 4 SAAT | 1 SAAT | 15 DAKIKA |
|------------|--------|--------|-----------|
| rol        | trend gucu | **giris** | teyit |
| RSI        | >= 60  | <= 55  | <= 50 |
| StochRSI   | <= 15  | <= 10  | <= 20 |
| KDJ J      | —      | <= 15  | — |
| W%R        | —      | <= -75 | <= -70 |
| MACD hist  | —      | negatif | — |

Cikis: stop = destek x 0.975 · TP1 = en yakin direnc >= +%2.5 · %2.5 trailing · 24h
Komisyon %0.2. Tarama sikligi 15 dakika.

## Sonuc — tum evren (sonuclar/..._TUMEVREN_..._1310.json)

451 islem · 253 coin · 04.01.2025 - 10.09.2026

| olcu | deger |
|---|---|
| toplam | +539.28 puan |
| islem basina | +%1.196 |
| medyan islem | +%0.683 |
| kazanan | %57.4 |
| naif t | 4.60 |

Cikis kirilimi:

| cikis | islem | ortalama |
|---|---|---|
| trailing | 224 (%49.7) | +%5.18 |
| stop | 147 (%32.6) | -%3.95 |
| sure doldu | 80 (%17.7) | -%0.50 |

Kazanc kaybin 1.3 kati. Aranan "min kayip max kazanc" yapisi burada var.

Saglamlik: en iyi 20 islem cikarilinca hala +%0.48/islem. Kar birkac vurustan gelmiyor.

## UYARI — naif t = 4.60 SAHTE

Islemlerin cogu ayni anda aciliyor (orn. 16.04.2026 12:00'de APT, SUI, LINK,
AAVE, INJ birlikte). Bunlar bes ayri deney degil, TEK piyasa ani.

Episode bazinda (span-sinirli, zincirleme yok):

| bagimsiz gozlem tanimi | gozlem | t |
|---|---|---|
| her islem ayri (naif) | 451 | 4.60 |
| ayni gun = tek an | 138 | **1.32** |
| ayni 72 saat | 85 | 0.78 |
| ayni hafta | 54 | 0.65 |

Bu tam olarak daha once kayit altina alinan tuzak: bar saymak yaniltir,
OLAY saymak gerekir.

Haftalik blok bootstrap (68 hafta, 10000 tur): ort +1.196,
%95 GA [+0.018, +2.251], sifirin ustunde kalma %97.7.
Alt sinir sifira degiyor.

## Para olarak — sirali sermaye

2500$ · ayni anda sinirli pozisyon:

| max pozisyon | alinan islem | 2500$ -> | maxDD |
|---|---|---|---|
| 1 | 171 | 7.620$ | -%55.0 |
| 2 | 230 | 3.369$ | -%48.1 |
| 3 | 267 | 3.213$ | -%38.5 |
| 5 | 315 | 3.340$ | -%23.8 |

Yil kirilimi (max 3): 2025 -> 2.799$, 2026 -> 2.870$.

## Zayiflama

| | islem | ort | t |
|---|---|---|---|
| 2025 | 222 | +%1.81 | 4.80 |
| 2026 | 229 | +%0.60 | 1.69 |

## HUKUM

Kaybettirmiyor — mevcut spot_opportunity'den belirgin iyi, R:R yapisi dogru.

Ama KAZANDIRIYOR demek icin erken: bagimsiz gozlem 138, 20 ayda +%28,
dususu -%38. Dusus kardan buyuk. Bu haliyle canliya baglanmaz.

## SIRADAKI

Cikis kurali degil, ISLEM SECIMI. 451 islemin icinde +%5 ortalamayla
kapanan 224 tane var. Bunlari ayiran ozellik bulunabilirse islem sayisi
duser, ortalama yukselir.

Gerekli: sinyal anindaki 15m/1h/4h gostergeler (veri/ klasoru).
Metodoloji: olay bazinda puanlama + dokunulmamis donem + on kayit.
