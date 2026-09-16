# Hacim Filtresi — SONUC (16.09.2026)

On kayitlar: `PARA_AKISI_ON_KAYIT.md`, `HACIM_ON_KAYIT_2019_2020.md`

## Hipotez

    1h hacim orani (bar hacmi / son 20 barin ortalamasi)
    medyanin USTUNDE olan dip sinyallerini al, altindakileri ELE.

## Dort donemin tamami

Hepsi: -%3 giris, ATRx0.6 cikis, tek islem, komisyon %0.2,
200 rastgele secim sirasinin ORTANCASI.

| donem | filtresiz | **hacim YUKSEK** | hacim DUSUK | isl (Y/D) |
|---|---|---|---|---|
| 2019-2020 | 12.280$ +%0.92 | **14.894$ +%1.79** | 9.028$ -%0.46 | 19 / 17 |
| 2021-2022 | 21.567$ +%3.31 | **18.850$ +%2.72** | 10.004$ +%0.00 | 59 / 80 |
| 2023-2024 | 16.581$ +%2.16 | **19.040$ +%2.76** | 9.883$ -%0.05 | 76 / 74 |
| 2025-2026 | 11.095$ +%0.53 | **16.691$ +%2.62** | 7.372$ -%1.53 | 51 / 48 |

**Dort donemin dordunde de yon ayni.** Dusuk hacim yarisi dort donemde de
sifir ya da altinda. Yuksek hacim yarisi dort donemde de pozitif.

## HUKUM: DOGRULANMADI

Iki ayri sebeple:

1. **Kesif kirli.** 2021-2026'daki tutarlilik, karsilastirma bicimi
   SONUC GORULDUKTEN SONRA degistirilerek bulundu (taban-vs-yari yerine
   yari-vs-yari). Kusur gercekti ve sonuca bakmadan gorulebilirdi,
   ama gorulmedi. Bu yuzden o uc donem KESIF setidir, dogrulama degil.
2. **Bagimsiz dogrulama yetersiz.** 2019-2020 tek dokunulmamis donemdi:
   **37 dolan islem**, on kayittaki 40 alt sinirinin altinda -> **SONUCSUZ**.
   (Esik dusurulmedi. Rakamlar bilgi amaciyla yukarida, hukmu degistirmez.)

## Dogrulanan tek sey: sonuk hacimde alim yapilmamali

Dort donemin dordunde de hacim DUSUK yarisi para kazanmiyor
(+%0.00 / -%0.05 / -%1.53 / -%0.46). Bu, "yuksek hacim kazandirir"dan
daha zayif ama daha tutarli bir ifade ve dort donemde de ayni.

## Neden daha fazla dogrulanamiyor

2017-2026 arasindaki butun Binance USDT spot verisi artik kullanildi.
Dokunulmamis GECMIS donem KALMADI. Bundan sonraki gercek dogrulama
ancak ILERIYE DONUK olabilir: bugunden itibaren uretilen sinyaller
kaydedilip sonuclari beklenmeli.

## Elenen bes olcu (ayni kosuda, ayni titizlikle)

| olcu | 2021-22 | 2023-24 | 2025-26 | |
|---|---|---|---|---|
| 1h_taker (alici orani) | UST | ALT | ALT | tutarsiz |
| 4h_taker | UST | UST | ALT | tutarsiz |
| 1h_obv | UST | ALT | ALT | tutarsiz |
| 1h_mfi | ALT | UST | UST | tutarsiz |
| 4h_para_trend | berabere | ALT | ALT | tutarsiz |

Alici/satici kirilimi (taker) — en umut vaat edeni sanilan olcu — hicbir
tutarlilik gostermedi.

## Araclar

`araclar/akis_indir.py` (hacim+taker verisi) · `araclar/akis_olc2.py`
(alti olcu, secim sirasi bandi) · `araclar/indir_2019.py` · `araclar/test_2019.py`
