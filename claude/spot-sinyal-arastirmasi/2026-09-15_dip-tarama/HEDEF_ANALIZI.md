# Hedef Analizi — 15.09.2026

Kullanicinin hedefi: 10.000$ · **min ayda %15-20, asil hedef %30**
(gunde %1-2 / asil %3 · haftada %5-7 / asil %10)

## GERCEK KISIT: ayni anda TEK islem

Tum hesaplar buna gore. Her islem sermayenin TAMAMINI kullanir.

## Sistemin olculen tavani

Gunde 3 sinyal siniri + tek pozisyon, 10.000$, 20.1 ay:

| olcu | deger |
|---|---|
| alinan islem | 163 -> **8.1/ay** |
| ortalama | **+%0.852** (medyan +%0.158) |
| kazanc / kayip | +%5.04 / -%3.49 (R:R 1.44) |
| kazanma orani | %50.9 |
| aritmetik aylik | +%6.90 |
| **GERCEKLESEN aylik** | **+%5.60** |
| oynaklik suruklemesi | 1.30 puan/ay |
| maxDD | **-%50.2** |

**%5.60 RAKAMI YANILTICI — tek aydan geliyor:**

| donem | |
|---|---|
| 2026-08 | **+%110.7** <- tum sonuc bu |
| 2025-08 -> 2026-04 | **10 ay ust uste dusus: 14.589$ -> 9.526$ (-%35)** |
| pozitif ay | 12 / 21 |
| **%15 hedefini tutturan ay** | **4 / 21 (%19)** |

O tek ay olmasa 20 ay sonu ~14.200$ = **ayda %1.7**.

## GUNLUK SINYAL SINIRI GEREKSIZ (olculdu)

Tek pozisyon sartinda:

| gunluk sinir | islem | aylik | maxDD |
|---|---|---|---|
| 1 | 153 | %4.93 | -%51.5 |
| **2** | 163 | %5.60 | -%50.2 |
| **3** | **163** | **%5.60** | **-%50.2** (2 ile BIREBIR AYNI) |
| 5 | 166 | %5.39 | -%52.2 |
| 10 | 169 | %6.01 | -%52.2 |
| yok | 171 | %5.69 | -%55.0 |

Sinir kaldirilinca 20 ayda sadece 10 fazladan islem (ayda 0.5),
ortalamalari -%0.04, WR %50. Gurultu. **Sinir>=2 islevsiz.**

## HEDEF-DURDUR KURALI (kullanicinin onerisi) — ISE YARIYOR

"Gunluk/haftalik/aylik hedef dolduysa o periyotta islem acma"

| kural | islem | 20 ay sonu | aylik | **maxDD** |
|---|---|---|---|---|
| kural yok | 163 | 29.968$ | %5.60 | **-%50.2** |
| gun %1 / hafta %5 / ay %15 | 114 | 25.618$ | %4.78 | **-%32.9** |
| sadece ay %15 | 129 | 26.313$ | %4.92 | **-%32.2** |
| sadece gun %1 | 162 | 33.742$ | %6.23 | -%44.0 |
| gun %3 / hafta %10 / ay %30 | 142 | 21.370$ | %3.84 | -%46.3 |

**Getiri kucuk dusuyor, DUSUS YARIYA INIYOR (-%50 -> -%32).**
Islem sayisi 163 -> 114. "Az ve net islem" olcumde karsilik buluyor.

Mekanizma iki yonlu: hedefi tutturunca durmak, sonraki kotu seriden de koruyor.
2026-08 ornegi: kural yok +%110.7 · ay %15'te dur +%16.8 · ay %30'da dur +%30.8

**UYARI:** 8 varyant denendi. "sadece gun %1" (%6.23) muhtemelen gurultu.
Guvenilir kisim: hedef-durdur ailesinin TAMAMI dususu ciddi azaltiyor.

**ASIL HEDEF (%30/ay) EN KOTU SATIR** — esik yukseldikce koruma kayboluyor,
cunku %30'a neredeyse hic ulasilmiyor; kural devreye girmiyor ama risk devam ediyor.

## AYDA %15 ICIN NE GEREKIYOR

Tek pozisyon, mevcut kalite (+%0.852/islem, WR %50.9, R:R 1.44):

| islem/ay | gereken ortalama | gereken WR | |
|---|---|---|---|
| 8 (su an) | %2.16 | %66.2 | |
| 13 | %1.33 | %56.5 | |
| **20** | **%0.86** | **%51.0** | mevcut kalite YETER |
| 30 | %0.57 | %47.7 | yeter |

Mevcut kaliteyle: 8 islem -> %5.9 · **20 islem -> %14.8** · 30 -> %22.2 · 45 -> %33.3

## TIKANIKLIK ZINCIRI

    22 aday/ay uretiliyor
      -> gunde 3 siniri          -> 13
      -> tek pozisyon bloklamasi -> 8.1 alinabiliyor

Medyan tutma suresi 11.2 saat -> fiziksel tavan gunde ~2 islem = ayda 60.
**20 islem/ay FIZIKSEL OLARAK MUMKUN. Sinyal yok.**

Sinyaller KUMELENMIS geliyor: 613 gunun sadece %27'sinde sinyal var,
sinyal olan gunlerde medyan 1 tane, ama bazi gunlerde 44 tane.
Esit dagilmis 22 aday olsa 20'sini alirdin.

Somut ornek (12.07.2025): 44 sinyal -> sinir 3 -> tek pozisyon 2 alabildi.
+%17.04 yapan 1INCHUSDT, -%1.76 yapan ALTUSDT acik oldugu icin KACIRILDI.

## ARASTIRMA HEDEFI (artik olculebilir)

> Ayda **45-50 aday**, **zamana yayilmis** (kumelenmemis), ortalama **>= +%0.85**
>
> Su an: 22 aday, agir kumelenmis, +%0.852

**Kalite hedefi ZATEN TUTUYOR. Eksik olan SAYI ve DAGILIM.**
Filtre eklemek, esik sikilastirmak, cikis kuralini degistirmek YANLIS YON.

## HUKUM

Ayda %15 bu sistemle ulasilabilir degil. Olculen tavan **~%5-6/ay**,
o da -%50 dususle ve tek sansli aya dayanarak. Surdurulebilir seviye **%1.5-2/ay**.
Hedef, sistemin verebildiginin **3-10 kati**.

Hedef-durdur kurali dogru bir kural (riski yariya indiriyor) ama tavani yukseltmiyor.

## Simulasyon dogrulamalari (hepsi temiz)

- Alinan islemler birbiriyle cakismiyor: 0 cakisma
- 97 atlananin 97'si gercekten pozisyon aciktayken geldi, sebepsiz atlanan 0
- Sermaye tek islemde (para/1)
- Gunluk sinir SINYAL uzerinden uygulandi (kotu senaryo); ISLEM uzerinden
  olsaydi %5.60 yerine %5.69 — fark onemsiz
