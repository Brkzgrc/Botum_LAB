# Hacim Filtresi — DOGRULAMA ON KAYDI (16.09.2026)

**Bu belge 2019-2020 verisine DOKUNMADAN once yazildi ve push edildi.**

## Nereden geldi

2021-2026 uzerinde alti para akisi olcusu test edildi (bkz. `PARA_AKISI_ON_KAYIT.md`).
Ilk karar kuralina gore **altisi da RED** oldu.

Ancak o kuralda YAPISAL BIR HATA vardi: yariyi "filtresiz taban" ile karsilastiriyordu.
Taban ~119 islem yapiyor, yarilar ~70 — az islem daha az bilesik buyume demek,
olcunun kalitesinden BAGIMSIZ olarak. Yani kural filtrelerin aleyhine egikti.

Dogru karsilastirma UST YARI vs ALT YARI (ikisi de ayni sayida islem). Buna gore:

| olcu | 2021-22 | 2023-24 | 2025-26 | tutarli mi |
|---|---|---|---|---|
| 1h_taker | UST | ALT | ALT | hayir |
| 4h_taker | UST | UST | ALT | hayir |
| 1h_obv | UST | ALT | ALT | hayir |
| **1h_hacim** | **UST** | **UST** | **UST** | **EVET** |
| 1h_mfi | ALT | UST | UST | hayir |
| 4h_para_trend | berabere | ALT | ALT | hayir |

`1h_hacim` (bar hacmi / son 20 barin ortalamasi) uc donemde de ayni yon, buyuk farkla:

| donem | hacim YUKSEK yari | hacim DUSUK yari |
|---|---|---|
| 2021-2022 | 18.850$ (+%2.72, 59 isl) | 10.004$ (+%0.00, 80 isl) |
| 2023-2024 | 19.040$ (+%2.76, 76 isl) | 9.883$ (-%0.05, 74 isl) |
| 2025-2026 | 16.691$ (+%2.62, 51 isl) | 7.372$ (-%1.53, 48 isl) |

2021-2022'de ustun yari DAHA AZ islemle (59 vs 80) daha cok kazaniyor —
"cok islem yapti o yuzden kazandi" yanilsamasi degil.

## KAYIT ALTINA ALINAN KUSUR

Karsilastirma **sonuc gorulduKTEN SONRA** degistirildi. Kusur gercekti ve sonuca
bakmadan da gorulebilirdi, ama gorulmedi. Bu yuzden yukaridaki tablo bir
**KESIF**tir, kanit degil. Bu belge o kesfi bagimsiz veride sinamak icin var.

## HIPOTEZ — tek hipotez, dondurulmus

    1h hacim orani (bar hacmi / son 20 barin ortalamasi)
    o donemin MEDYANININ USTUNDE olan dip sinyallerini al,
    altinda olanlari ELE.

Medyan, test doneminin KENDI sinyallerinden hesaplanir (disaridan esik tasinmaz).

## DONEM

**2019-01-01 – 2021-01-01.** Bu veriye bu projede hic bakilmadi.
Evren: o donemde islem goren tum USDT pariteleri, delist olanlar dahil.

## SABIT AYARLAR — degismez

- Sinyal uretimi: mevcut `dip_tarama.py`, hicbir esigi degismez
- Giris: -%3 ofset · Cikis: TP1 sonrasi ATRx0.6 trailing
- Komisyon %0.2 · ayni anda TEK islem · 24 saat dolum · 24 saat expire
- Secim sirasi belirsizligi: 200 rastgele sira, ORTANCA raporlanir

## KARAR KURALI — degismez

- **GECTI:** hacim YUKSEK yari, hacim DUSUK yariyi geciyor
  **VE** yuksek yari ayda en az +%1.0 getiriyor (ortanca).
- **KALDI:** yon ters (dusuk yari kazaniyor).
- **SONUCSUZ:** yon dogru ama yuksek yari +%1.0'in altinda,
  ya da donemde 40'tan az dolan islem var.

Tek kosu. Esik oynatilmaz. Ikinci olcu eklenmez. Alt donem aranmaz.
Sonuc ne cikarsa aynen raporlanir.
