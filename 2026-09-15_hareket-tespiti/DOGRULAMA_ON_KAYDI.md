# DOGRULAMA ON KAYDI — 15.09.2026, VERI GORULMEDEN YAZILDI

2023-2026 verisine HIC bakilmadan yazildi. Sonuc gorulduktan sonra
bu dosya DEGISTIRILMEZ.

## DONDURULMUS KURAL — tek hipotez

    KAPI = 1G_BTC_yukselis  VE  1G_coin_yukselis  VE  4S_coin_yukselis

    "yukselis" tanimi (her uc yerde AYNI):
        EMA20 < EMA50
        VE |EMA20 - EMA50| mesafesi son 3 barda DUZENLI azaliyor
           (her bar bir oncekinden kucuk)

    Giris  : kapi acikken herhangi bir 15dk bari
    Olcut  : 1 saat (4 x 15dk bar) icinde +%2.5'e ULASTI
             VE bu -%2.5'e inmeden ONCE oldu   (yol-farkinda)
    Komisyon: %0.20  ->  BASABAS %54.0

## DEGISTIRILMEYECEKLER

- 3 bar -> 2 veya 4 YAPILMAZ
- EMA20/50 -> baska periyot YAPILMAZ
- +%2.5 -> baska hedef YAPILMAZ (bilgi amacli raporlanabilir, HUKMU DEGISTIRMEZ)
- 1 saat -> baska ufuk YAPILMAZ (ayni sekilde bilgi amacli)
- dorduncu kapi EKLENMEZ, kapi CIKARILMAZ
- Tek kosu. Sonuca gore ayar YOK.

## KESIF SONUCU (2021-2022) — kiyas noktasi

| | |
|---|---|
| taban | %51.0 |
| KAPI | **%58.0** |
| fark | **+7.0 puan** |
| n | 100.604 |
| gun bazinda t | +6.37 |

## GECME OLCUTU — simdi sabitleniyor

Donem basina UC hukum:

- **PASS**  : (a) isabet >= o donemin KENDI tabani + **3.0 puan**
              VE (b) isabet >= **%54.0** (basabas)
              VE (c) gun bazinda t >= **+2.0**
- **FAIL**  : (a) saglanmiyor VE n >= 20.000  (yani olcmeye gucumuz vardi, tutmadi)
- **SONUCSUZ**: n < 20.000  (guc yetersiz, hukum verilmez)

Gerekce (+3.0 puan): kesifte +7.0 cikti. Kesif skoru daima iyimserdir
(kazananin laneti). Yariya yakin bir kirilma payi birakiliyor.

## GENEL HUKUM

**DOGRULANDI** = 2023-2024 PASS **VE** 2025-2026 PASS
**KISMEN**     = biri PASS, digeri SONUCSUZ
**DOGRULANMADI** = herhangi biri FAIL

## DONEM SIRASI

1. **2023-2024** — bugun HIC dokunulmadi, en temiz
2. **2025-2026** — bugun BTC ve sikisma testleri icin bakildi;
   tam temiz degil, ikincil dogrulama sayilir

## AYRICA RAPORLANACAK (hukmu DEGISTIRMEZ)

- delist olan / hayatta kalan kirilimi
- yil bazinda ayrim
- +%2 ve +%3 hedefleri, 3 saat ufku
- kapilarin tek tek katkisi (kesifte %51.9 / %52.7 / %53.3 idi)
