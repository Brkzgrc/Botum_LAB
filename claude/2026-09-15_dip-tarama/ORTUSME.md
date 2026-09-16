# Dip Tarama ile Canli Sistem ayni sinyalleri mi yakaliyor?

Donem 2025-2026 (21 ay). Canli `spot_opportunity_scanner`'in giris kosullari
ayni gecmis veride birebir yeniden kuruldu ve dip taramayla yan yana kosuldu.

## Canli tarafin kurulumu (v2 — duzeltilmis)

- `universe()` filtresi uygulandi (stablecoin / sarilmis token / kaldiracli elendi) -> 477 coin
- her tarama saatinde ucuz 1H on-eleme puaniyla **en iyi 96** secildi (CORE_N=72 + seed)
- `FINAL_MIN_QUALITY = 72`
- gunde en fazla **3** sinyal, ayni coinde 24 saat tekrar yok

## Sonuc

| | sinyal | coin |
|---|---|---|
| dip tarama | 458 | 258 |
| canli sistem | 1.346 | 347 |
| ikisinde de sinyal olan coin | 218 | |

| pencere | gercek ortak | sans tabani |
|---|---|---|
| **+-4 saat** | **0 (%0.0)** | %1.4 |
| +-12 saat | 12 (%2.6) | %4.2 |
| +-24 saat | 34 (%7.4) | %7.3 |

Sans tabani: dip sinyalleri ayni coinde rastgele bir zamana tasinip ayni hesap
50 kez tekrarlandi.

**458 dip sinyalinin HICBIRINDE canli sistem +-4 saat icinde ayni coinde
sinyal vermiyor. Ters yon de ayni: %0.0.**

+-12 saatte gercek ortusme sans tabaninin ALTINDA — iki sistem bagimsiz degil,
**birbirini itiyor**. Beklenen davranis: ayni coin ayni anda hem "4H'de EMA50'nin
%6 ustunde, hareket baslamis" (canli) hem "4H StochRSI 15 altinda, geri cekilme
dibinde" (dip) olamaz.

+-24 saatte tam sans seviyesine donuyor — bir gun icinde ayni coinde iki sistemin
de bir sey gormesi, sadece ikisinin de o coine bakmasindan ibaret.

## Pratik sonuc

Dip tarama, canli sistemin bir **iyilestirmesi degil**; tamamen ayri bir sistem,
ayri firsat kumesi. Ayni anda tek islem kurali nedeniyle ikisi birlikte
kosarsa birbirinin yerini isgal eder. Birini secmek gerekiyor.

## Olcumun sinirlari

1. Elimdeki veride acilis fiyati yok — acilis = onceki kapanis alindi
   (spotta pratikte ayni). `upper_wick` bundan etkilenir, kucuk bir terim.
2. Alici/satici hacim kirilimi yok — `taker_buy_ratio` notr 0.5 sayildi.
3. Canli `evaluate()`'teki "onceki tarama izlemedeydi + yeni 15M mumu kapandi"
   durum makinesi ve `chased` kontrolu uygulanmadi. Bunlar sinyal SAYISINI
   azaltir, hangi kurulumlarin uygun oldugunu degistirmez.

## Onceki (HATALI) olcum — kayit icin

Ilk kosuda canli taraf 498 coinin tamaminda derin analize sokulmustu ve
evren filtresi uygulanmamisti: 13.256 sinyal, +-4 saat ortusme %9.3.
**Ikisi de gecersiz.** Duzeltilince 1.346 sinyal ve %0.0.

## Yan bulgu — CANLI KODDA HATA

`spot_opportunity_scanner.py` `universe()`, kaldiracli token adlarini
`UP`/`DOWN` sonekiyle eliyor. **JUP** ve **SYRUP** de "UP" ile bittigi icin
eleniyor — ikisi de normal spot coin, canli sistem bunlara hic bakmiyor.
`CRYPTO_BASES_ENDING_B` benzeri bir muafiyet listesi gerekiyor.
(Duzeltilmedi — canli dosya, kullanici onayi bekliyor.)

Araclar: `araclar/ortusme.py` (gosterge serileri + v1), `araclar/ortusme2.py`
(evren filtresi + top96 + gunluk sinir)
