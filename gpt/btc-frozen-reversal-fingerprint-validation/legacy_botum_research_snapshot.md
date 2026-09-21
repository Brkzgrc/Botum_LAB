# Legacy research snapshot from Botum

Source repository: `Brkzgrc/Botum`
Source commit: `aedb91d5a0be831d0c27ddc65aa2147813618493`
Source file: `CLAUDE.md`

> This is a research-only snapshot copied into Botum_LAB so future validation no longer needs access to the live Botum repository.

## 12 ISARET — ZOR NEGATIF PARMAK IZI CALISMASI (2026-09-12, TAMAMLANDI)

**Sebep:** Kullanici hakli olarak itiraz etti — arastirma onun sorusunu degil
kendi urettigi olay tanimlarini cozuyordu. Ayrica dogrulama her seferinde
problemi baska bir hedef/stop testine ceviriyordu. Bu bolumdeki calisma
kullanicinin tarif ettigi deneyin BIREBIR uygulanmis halidir.

### Ground truth: kullanicinin ISARETLEDIGI 12 bolge

BTC gunluk, **10.11.2021 - 10.11.2022 (AYI PIYASASI, 66.948 -> 15.923, -%76)**.
Grafikteki 12 daire piksel okumasiyla tarihe cevrildi:

18.12.21 · 08.01.22 · 25.01.22 · 22.02.22 · 14.03.22 · 28.05.22 ·
03.07.22 · 13.07.22 · 27.07.22 · 05.08.22 · 07.09.22 · 22.10.22

12'sinin 12'si de 10-30 gun icinde +%7..+%29 sicradi. 9'unda sonraki dusus
kucuk (-%0.6..-%8), 3'unde ciddi (-%18.7, -%20.8, -%29.8).

**REJIM AYRIMI KRITIK:** 2020-21 "yukselis/duzeltme/yukselis", 2021-22
"kesintisiz dusus". Bunlar FARKLI problemler, havuzlanmamali. Bu oturumda
2020-2026 tek havuzda toplandigi icin cikan tek tutarli sey hep "boga
yilinda al" oldu.

### Kontrol grubu: ZOR NEGATIF (onceki turlarin en buyuk hatasi duzeltildi)

Onceki kontroller "rastgele bar" veya "yerel dip olup yukselmeyen"di — KOLAY
negatifler. Cogu isaretli ana hic benzemiyordu, o yuzden ayrisan sey "bu an
iyi mi" degil "bu an dip mi" oluyordu.

Zor negatif = ayni rejimde, **baglam olarak en yakin**, sicramamis gunler.
Benzerlik SADECE GECMISE bakan olculerle: RSI14/50, 20-60 gunluk dususun
buyuklugu, EMA50/200 uzakligi, ATR%, dip20 uzakligi, 5-20 gun getirisi.

Eslesme kalitesi (medyan): RSI 39.99 vs 41.34 · ATR 5.97 vs 5.17 ·
ema200 -27.09 vs -25.17. Ornek: isaret 22.10.22 ile zor negatif 15.10.22
bir hafta arayla, baglam mesafesi 0.56 — biri sicradi biri sicramadi.
**Kalan fark:** isaretler 60 gunluk dususte 8.4 puan daha derin. Eslesme
mukemmel degil.

### Deney

- **4 zaman dilimi BIRLIKTE**: 15m + 1h + 4h + 1d (once sadece 4h+1d vardi;
  tetikleyici alt dilimlerde olabilir)
- **YORUNGE**: her ozellik icin 0/-6s/-24s/-72s degerleri VE aralarindaki degisim
- **DERIN BIRLESIM**: 6 kosula kadar acgozlu arama (once 3'tu)
- **4 AYRI CAPA**: bolge_basi · bolge_merkezi · lokal_dip · ilk_kirilim
  (daireler 2-3 gunluk bolge; tek gune sabitlemek yapay hassasiyet uretir)
- **26.824 ozellik-an** uretildi, 4.000'i kullanildi (secim ETIKETTEN BAGIMSIZ,
  sabit tohumlu — etikete bakan on eleme sans tabanini gecersiz kilardi)
- **30.258 tekil kosul**
- Olcut F1 (kesinlik x duyarlilik), islem sonucu DEGIL

### SONUC — dort capada da ayrim sansi asmadi

| capa | gercek F1 | sans %95 | sans en iyi |
|---|---|---|---|
| bolge_basi | 0.800 | 0.857 | 0.909 |
| bolge_merkezi | 0.800 | 0.857 | 0.957 |
| lokal_dip | 0.857 | 0.857 | 0.909 |
| ilk_kirilim | 0.857 | 0.800 | 0.957 |

**EN ONEMLI SAYI:** lokal_dip capasinda bulunan kural 12 isaretin 9'unu
%100 isabetle yakaladi (F1 0.857) — ve ayni arama RASTGELE etiketle 0.909
uretti. "9/12'yi sifir yanlis alarmla yakalayan kural" bu orneklem
buyuklugunde SIRADAN bir sans sonucudur.

### Bu bir GUC ifadesidir, kanit ifadesi degil

"Parmak izi yok" DENEMEZ. Denebilecek: **"bu 12 isaretle, kusursuza yakin
olmayan hicbir parmak izi GORULEMEZ."** Kismi/olasiliksal bir iz varsa bu
deney onu goremez.

### Kac isaret gerekiyor — OLCULDU

Ayni arama (30.000 kosul, 6 derinlik, 1:8 negatif orani), rastgele etiketle:

| isaret | sans F1 | ne gorunur |
|---|---|---|
| **12** | **0.957** | sadece MUKEMMELE yakin kural |
| 20 | 0.833 | sadece iyi kural (%85/%85) |
| 30 | 0.735 | sadece iyi kural |
| **50** | **0.622** | **gercekci kural (%70/%70) gorunur** |
| 80 | 0.496 | rahat |
| 120 | 0.421 | rahat |

**ESIK 50.** Bunun altinda arastirma yapilabilir ama SONUC CIKARILAMAZ.

### SONRAKI ADIM (kullanicidan beklenen)

1. **Geriye donuk (hizli):** ayni ayi piyasasinda BASKA COINLERDE de isaretle
   (ETH, SOL, LINK, AVAX, DOT...). Coin basina 10-12 x 4-5 coin = 50+.
   Altyapi hazir: `_isaretli_olaylar.json` formatinda tarih listesi yeter.
   Riski: hindsight.
2. **Ileriye donuk (kesin):** bundan sonra firsat gorunce, SICRAMAYI GORMEDEN
   yaz. Hindsight'i tamamen kapatir. Yavas ama kesin.

Ikisi birlikte: 1 ile 50'ye cikip kismi iz var mi bak; 2 ile hindsight
kontrolu yap. Ikisinde de tutan sey gercektir.

### Araclar (scratchpad, repoya girmez)

`zor_negatif.py` (baglam eslestirme + 4 capa) · `parmak_izi.py` (4 TF,
yorunge, 6 derinlik, F1 + sans tabani) · `yapi_fabrikasi.py` (86 indikator
OLMAYAN ozellik: yol geometrisi, entropi/Hurst/fraktal, FFT/spektral,
degisim noktalari, motif/matrix-profile) · `etkilesim_avcisi.py` (elle
isaretli olaylari kabul eden birlesim madencisi) · `ozellik_fabrikasi.py`
(870 klasik gosterge turevi/zaman dilimi).

`yapi_fabrikasi` ve `parmak_izi` dogrulandi: ileriye bakma SIFIR, gostergeler
ZEC referansiyla birebir, ekilen ayrim bulunuyor, rastgelede sans asilmiyor.

## NIHAI TEST — (2026-09-12, SONUC: AYRIM YOK · PROTOKOL HENUZ DONMADI)

Kullanicinin ikinci ve ucuncu itirazi uzerine yedi metodolojik acik kapatildi.

**PROTOKOL DONDURULMADI.** Once "donduruldu" yazilmisti; kullanici hakli olarak
itiraz etti — dondurmadan SONRA iki hata daha bulundu (OBV olcek artifakti,
episode zincirlemesi). Bu hala KESIF/GELISTIRME setidir. Dogru sira:
hatalari bul -> episode tanimini duzelt -> coin normalizasyonunu duzelt ->
null'u dogrula -> **ANCAK O ZAMAN dondur** -> sonra yeni donemlere dokunma.

### Kapatilan bes acik

1. **Zaman bagimliligi** — once etiketler BAR bazinda karistiriliyordu.
   Birbirine yakin barlar ayni trendi/oynakligi/haber ortamini paylasir.
   Simdi EPISODE bazinda (14 gun icindekiler ayni olay), episode butun halinde.
2. **Coklu capa = coklu test** — dort capanin en iyisine bakmak ek serbestlik.
   Capa secimi KALDIRILDI; referans isaretli bolgenin BASLANGICI (veriden
   secilen nokta yok).
3. **15m'de yeniden hindsight** — gunluk daireyi veriye bakarak tek 15m barina
   indirgemek. Simdi olay PENCERE: bolge basindan onceki 5 zaman penceresinde
   (72-48s, 48-24s, 24-12s, 12-6s, 6-0s) ortalama/egim/fark.
4. **Zor negatif eslesmesi** — CALIPER: 8 baglam boyutunda mutlak fark siniri.
   Sinir asilirsa aday hic alinmaz. Sonuc: "isaretler daha derin dusmus"
   karistiricisi 60 gunluk dususte 8.4 puandan **2.4 puana** indi; 20 gunluk
   getiride yon TERSINE dondu (negatifler daha cok dusmus).
5. **Olcek artifakti (BU TURDA BULUNDU)** — ilk kosu F1=1.000 verdi ve sansi
   asti. Kural: `1d_OBV <= 3.458e6`. OBV kumulatif hacim; coinler arasi
   **8 BASAMAK** degisiyor (BTC 1.6e6 ... SHIB 3.4e14). 12 isaretin hepsi BTC
   oldugu icin bu kosul "bu satir BTC mi" diye soruyordu. Ayni sorun MACD dif'te
   de var (fiyat birimi).
   Cozum: VERIYE BAKAN olcek filtresi — bir ozelligin coin bazindaki medyanlari
   25 kattan fazla degisiyorsa elenir (etikete BAKMAZ, sans tabanini etkilemez).

### Kurulum

12 isaretli bolge (BTC, Kasim 2021-Kasim 2022) · 111 zor negatif (19 coin,
ayni ayi rejimi, caliper'li) · 44.068 ozellik (15m/1h/4h/1d x 5 pencere x
ort/egim/fark + 1d nokta) · olcek filtresi 2.772 ozelligi eledi ·
31.265 tekil kosul · 6 derinlikli acgozlu arama · 1000 tur episode permutasyonu.

### SONUC

| kurulum | F1 | sans %95 | sans en iyi | hukum |
|---|---|---|---|---|
| olcek filtresi YOK (7 ep) | 1.000 | 0.875 | 0.952 | asti (ARTIFAKT) |
| olcek filtresi VAR (7 ep) | 0.800 | 0.875 | 0.947 | asmadi |
| **+ episode duzeltmesi + coin ici yuzdelik (17 ep)** | **0.909** | 0.857 | **1.000** | ~~ASMADI~~ |

**BU TABLONUN "HUKUM" SUTUNU GECERSIZ — bkz. "UC AUDIT" bolumu.** Hukum
`f1 > null_max` kod satirindan geliyordu; dogru ampirik p = **0.0125**
(AUDIT 4 permutasyon duzeltmesinden sonra).

### UCUNCU NORMALIZASYON KATMANI eklendi

"Olceksiz olmak" yetmiyor — RSI 0-100 arasi ama BTC'nin RSI dagilimiyla
SHIB'inki ayni olmak zorunda degil. Her ozellik serisi, KENDI COININ son 500
barindaki goreli konumuna cevrildi (`coin_ici_yuzdelik`, nedensel). Dogrulandi:
ayni seri 1e8 ile carpilinca yuzdelikler birebir ayni (fark 5.5e-13),
kaydirmadan etkilenmiyor, ileriye bakmiyor.

### YENI VE KRITIK BULGU: arama uzayi cok genis

Duzeltilmis (durust) null ile: **31.344 kosul + 6 derinlikle, 12 pozitifi 111
negatiften RASTGELE etiketle bile KUSURSUZ ayirmak mumkun** (sans max F1=1.000).
Bu kurulumda hicbir sonuc kanit olamaz.

**Sonuc: orneklem buyutmek kadar ARAMA UZAYINI DARALTMAK da gerekiyor.**
Dogrulayici test icin hem daha cok bagimsiz episode hem de onceden kayitli,
cok daha dar bir ozellik/derinlik seti sart.

### ~~ASIL SINIR: 7 EPISODE~~ — BU SAYI YANLISTI, DUZELTILDI

**DUZELTME (kullanici itirazi hakli cikti):** "7 episode" sayisi EPISODE
MOTORUNUN HATASIYDI. `episodeler()` TEK BAGLANTI (single-linkage) calisiyordu:
yalnizca BIR ONCEKI ornekle arasindaki bosluga bakiyordu. A-B 10 gun, B-C 10
gun, C-D 10 gun zinciriyle AYLARCA suren tek episode uretiyordu.

Denetim tablosu (eski motor): 7 episode'un **4'u** 14 gunluk siniri asiyordu —
en genisi **82 GUN** (39 ornek, 14 coin), digerleri 56, 48 ve 36 gun. Uc aylik
bir donemi "tek piyasa olayi" saymak tanimin kendisiyle celisiyor.

**Duzeltme:** yeni episode su iki durumda baslar — (a) onceki ornekle bosluk >
EPISODE_GUN, (b) episode'un ILK ornegine uzaklik > EPISODE_GUN. Yani hicbir
episode'un TOPLAM GENISLIGI siniri asamaz.

| | eski (zincirleme) | yeni (span sinirli) |
|---|---|---|
| toplam episode | 7 | **17** |
| isaretli episode | 6 | **10** |
| sinir asan | 4 (en genisi 82 gun) | **0** |

Permutasyon cesitliligi: 7'den 6 secmek = 7 yol; **17'den 10 secmek = 19.448
yol**. Minimum p-degeri 0.14'ten ~0.00005'e indi.

**KRITIK: bu duzeltme testi ZAYIFLATMADI, DURUSTLESTIRDI.** Eski null
dagilimi neredeyse sabit oldugu icin sans tabanini OLDUGUNDAN DUSUK
gosteriyordu (max F1 0.947). Duzeltilmis motorla ayni arama, rastgele
etiketlerle **F1 = 1.000'e ulasiyor**. Yani onceki "0.947" sahte bir
guvenceydi.

**OLCULDU — ayni tarihlerde baska coin eklemek ISE YARAMIYOR:** 19 coinden
111 negatif toplandi, bagimsiz olay sayisi 7'de kaldi. Ayni piyasa sokunun
yansimalari bagimsiz ornek degildir.

### GEREKEN: FARKLI ZAMANLARDAN isaret

Hedef ~50 bagimsiz EPISODE. 12 isaret 6 episode veriyorsa kabaca **100 isaret
ve en az 4-5 AYRI DONEM** gerekiyor:

- 2018-2019 ayi piyasasi (BTC 20.000 -> 3.200)
- 2021 Mayis-Temmuz duzeltmesi (64.000 -> 29.000)
- Kasim 2021 - Kasim 2022 (mevcut 12 isaret)
- 2024-2025 ayi/yatay donemler
- CANLI isaretleme (hindsight'i kapatir)

Rejimler AYRI tutulmali (yukselen trend geri cekilmesi ile dusen trend
sicramasi farkli problemler).

### Araclar (scratchpad)

`nihai_test.py` (dondurulmus protokol) · `zor_negatif.py` (caliper eslestirme)
· `yapi_fabrikasi.py` (86 indikator-disi ozellik) · `ozellik_fabrikasi.py`
(870 gosterge turevi) · `parmak_izi.py` · `etkilesim_avcisi.py` ·
`iz_avcisi.py` · `kural_madenci.py` · `cikis_lab.py`

Hepsi dogrulandi: ileriye bakma sifir · gostergeler ZEC referansiyla birebir ·
ekilen ayrim bulunuyor · rastgelede sans asilmiyor · olcek filtresi dogru
ayiriyor · episode karistirma toplam isareti koruyor.

## ADAY SECIM — on kayit (2026-09-12, TAMAMLANDI)

Episode motoru duzeltildikten (17 episode, 10 isaretli) ve coin-ici yuzdelik
normalizasyonu acildiktan sonra protokolun eksik son parcasi tamamlandi.

### Neden ayri bir adim gerekiyordu

Olculdu (12 poz / 111 neg sabit, rastgele etiket, 400 tur):

| kosul | derinlik | sans F1 |
|---|---|---|
| 200 | 2 | 0.636 <- gercekci kural (0.700) GORUNUR |
| 200 | 3 | 0.667 <- gorunur |
| 1.000 | 3 | 0.818 <- gorunmez |
| 31.000 | 6 | 0.957 <- hicbir sey gorunmez |

Yani genis arama bu orneklem buyuklugunde KANIT uretemez. Dogru kullanimi
**ADAY URETMEK**: genis aramayla hipotez cikar, dogrulamayi dar ve dondurulmus
bir testle yeni veride yap.

### Yontem ve bulunan metodoloji hatasi

Gercek etiketle en iyi 200 kural toplanip TEMEL ozelliklerin kac kez gectigi
sayildi; ayni sayim 300 tur episode-permutasyonuyla tekrarlandi.

**HATA (olculup duzeltildi):** ilk surum her ozelligi KENDI null dagiliminin
%95'iyle karsilastiriyordu. 300 ozellikte bu, tanim geregi ~15 sahte aday
uretir. Sentetik saf rastgele veride sinandi: **12 "aday" cikti, hepsi sahte.**
Duzeltme — **AILE DUZEYINDE esik**: her turda TUM ozelliklerin EN YUKSEK sayimi
alinir, bir ozellik ancak o dagilimin %95'ini asarsa aday olur. Duzeltilmis
surum saf rastgelede 0 aday veriyor, ekili ayrimda ekileni buluyor.

### SONUC — tek aday

| ozellik | gercek sayim | aile esigi %95 |
|---|---|---|
| **4h_dip100_uzaklik_d3** | **65** | 27.1 |

Sayim siralamasinda ikinci sirada 19 var (`1d_ema100_uzaklik_d6`) — yani tek
aday acik ara one cikiyor, gerisi sans bandinin icinde.

**Yakinsama (DIKKAT: bagimsiz replikasyon DEGIL):** bu ozellik, duzeltilmis
`nihai_test` kosusunda bulunan kuralin da BIRINCI kosuluydu
(`4h_dip100_uzaklik_d3|24-12s|ort <= 36.6`).

**DUZELTME — buraya once "iki bagimsiz olcut ayni yere isaret etti" yazilmisti;
bu yanlis.** Iki yontem farkli (derin acgozlu F1 / sig arama sayim yogunlugu)
ama AYNI 12 isaret ve AYNI kesif verisi uzerinde kosuyorlar. Dogru ifade:
*ayni kesif verisinde iki farkli analiz yontemi ayni ozelligi one cikardi.*
Degerli bir yakinsamadir, bagimsiz replikasyon degildir. Bagimsiz replikasyon
ancak YENI donem verisinden gelir.

### KISMI DOLASIKLIK — olculdu, gizlenmiyor

Isaretler zaten dip; caliper GUNLUK dip baglamini dengeliyor ama 4h 100-barlik
dibe uzakligi dengelemiyor. Aday bunun artigi olabilir mi diye olculdu:

| olcu | deger |
|---|---|
| isaret medyan / negatif medyan | 33.12 / 49.44 (yuzdelik) |
| 8 caliper boyutunun acikladigi varyans | **%26.6** |
| ham AUC | 0.125 |
| caliper artigi uzerinde AUC | **0.340** |

**DUZELTME — buraya once "ayrimin kabaca yarisi diplikten geliyor" yazilmisti;
bu cikarim gecersiz.** %26.6 aciklanan varyans ile AUC 0.125 -> 0.340 AYNI
OLCU DEGILDIR; birinden digerine "yarisi artifakt" sonucu matematiksel olarak
cikmaz. Yon duzeltilirse (aday dusukken isaret oldugu icin AUC < 0.5):

| | duzeltilmis yon |
|---|---|
| ham ayrim | 0.875 |
| caliper artigi uzerinde | **0.660** |

Dogru ifade: kontrol degiskenleri cikarildiktan **sonra bile 0.66 seviyesinde
artik ayrim var**. Mukemmel degil, ama sifir da degil. Aday kayit altinda
tutulmalidir.

### ON KAYIT (aday_ozellikler.json, scratchpad) — DEGISTIRILMEZ

    KURAL:  4h_dip100_uzaklik_d3|24-12s|ort <= 36.6
      VE    4h_RSI2_ivme|48-24s|ort    >= 48.4

Kesif verisindeki sonucu: F1 0.800 · 13 atesleme · 10 isaret · 3 yanlis alarm
(BCH, JST, XLM) · 9 isaretli episode kapsandi.

**Bu bir KANIT DEGIL.** F1 0.800, ayni genislikteki sans tabanina
(31k kosul / derinlik 2 -> 0.783) neredeyse esit. Degeri kesif verisindeki
skorunda degil, **ONCEDEN YAZILMIS olmasinda**.

### Dogrulama protokolu (bundan sonra degistirilemez)

- **Veri:** YENI donemler — 2018-19 ayi · 2021 May-Tem duzeltme · 2024-25 ·
  canli isaretleme (hindsight'i kapatir). Hedef ~50 bagimsiz episode.
- **Test:** TEK kosu, yukaridaki kural AYNEN bu esiklerle.
- **Arama YOK:** dogrulamada kural arama, esik ayari, ozellik secimi yapilmaz.
- Rejimler AYRI tutulur (yukselen trend geri cekilmesi ile dusen trend
  sicramasi farkli problemlerdir).

### Durum

Protokolun uc acigi da kapandi (episode motoru · coin-ici normalizasyon ·
on kayit). Kullanicidan yeni donem isaretleri artik istenebilir.

Arac: `aday_secim.py` (scratchpad, repoya girmez) — saf rastgelede 0 aday,
ekili ayrimda ekileni buluyor diye dogrulandi.

## UC AUDIT — "ayrim yok" HUKMU GERI ALINDI (2026-09-13)

Kullanicinin itirazi hakli cikti. **Onceki bolumlerdeki "ayrim sansi asmadi"
sonucu bir KOD HATASINDAN geliyordu, veriden degil.**

### AUDIT 1 — karar kriteri yanlisti (SONUCU DEGISTIRDI)

`nihai_test.py` satir 461:

```python
print(">>> AYRIM SANSI ASTI." if f1 > tmax else ">>> AYRIM SANSI ASMADI.")
```

Karar, null dagiliminin **MAKSIMUMUYLA** karsilastiriliyordu. 2000 turda
maksimumu gecmek `p < 1/2001` talep etmektir — standart bir test degildir.
Gercek 0.909, null %95 esigi 0.857 iken "asmadi" yazdiran sey buydu.

Dogrusu ampirik p: `k` = kac sahte >= gercek, `p = (k+1)/(N+1)`.

| olcut | gercek | null %95 | null max | k / 2000 | **p** |
|---|---|---|---|---|---|
| **SATIR-F1** (satir aramasi) | **0.909** | 0.857 | 1.000 | 21 | **0.0110** |
| ayni kuralin EPISODE-F1'i | 0.947 | 0.889 | 1.000 | 22 | **0.0115** |
| EPISODE-F1 (episode aramasi) | 0.947 | 1.000 | 1.000 | 1803 | 0.9015 |

Bu p **aile duzeyinde duzeltilmistir**: her permutasyonda 31.344 kosul
uzerindeki 6 derinlikli aramanin TAMAMI yeniden kosar ve MAKSIMUMU kaydedilir.
Yani arama genisligi zaten hesaba katilmistir.

Kod duzeltildi: artik ampirik p basiliyor ve null tavana yapissa uyari veriyor.

### AUDIT 2 — episode-level skor (iki ayri istatistik, biri ise yaramiyor)

Episode-F1 tanimi: `TP_ep` = kural o episode'da **en az bir isaret satirinda**
atesledi · `PP_ep` = herhangi bir satirda atesledi · kesinlik `TP/PP`,
duyarlilik `TP / isaretli episode sayisi`.

Satir aramasinin buldugu kural episode duzeyinde de **0.947 (9/10 isaretli
episode, 9 ateslemede 9 dogru), p = 0.0115**. Yani bulgu satir agirliginin
yan urunu degil — kullanicinin "buyuk episode'lar fazla agirlik aliyor olabilir"
endisesi olculdu ve gecerli cikmadi.

**Ama aramanin KENDISI episode-F1'i hedeflerse test cozunurlugunu kaybediyor:**

| episode-aramasi null dagilimi (2000 tur) | |
|---|---|
| %50 yuzdelik | 1.000 |
| %95 yuzdelik | 1.000 |
| F1 = 1.000 olan tur | **1337 / 2000 (%66.8)** |

**KUSURSUZ bir kural bu testte p = 0.669 alirdi.** Yani `p=0.90` sonucu bir RET
degil, "bu aletle olculemez"dir. Sebep: sadece 10 isaretli episode'u kapsamak
31.344 kosul ve 6 derinlikle rastgele etiketle bile kolay; 111 negatif SATIR
ise satir-F1'i kisitliyor ve testi zorlastiriyor.

**Kaydedilmesi gereken istatistik ayrimi:** permutasyon testinin GECERLILIGI
karistirma semasindan gelir (episode butun halinde tasiniyor — bagimlilik
boyle kontrol edilir), skor fonksiyonundan degil. GUCU ise skor fonksiyonundan
gelir. Ikisi de gecerli; biri guclu, digeri gucsuz. "Bagimsiz birim episode
ise skor da episode olmali" sezgisi burada yanlis yone goturuyor.

### AUDIT 3 — coin kimligi sizintisi YOK

Coin-ici yuzdelikten sonra "bu satir BTC mi" tahmin edilebiliyor mu?
Null: **episode ICI** permutasyon (ayni piyasa aninda coin kimligi okunabiliyor
mu — sorulmasi gereken soru budur; satirlari serbest karistirmak zamansal
baglantiyi bozup anlamliligi sisirirdi).

| olcut | gercek | null %95 | p |
|---|---|---|---|
| en yuksek tekil \|AUC-0.5\| (3.963 ozellik) | 0.300 | 0.317 | 0.156 |
| acgozlu arama F1 (etiket = BTC) | 0.786 | 0.828 | 0.232 |

Ikisi de sansin icinde. **Uc katmanli normalizasyon (olcek filtresi + boyutsuz
ozellikler + coin ici yuzdelik) coin kimligini temizlemis.**

*Not — dual ridge DENENDI VE BIRAKILDI:* tek basina AUC=1.000 olan ekili bir
ozellik, 500 gurultu ozelligi arasinda ridge CV ile ancak 0.76 veriyor
(p >> n oldugu icin agirlik dagiliyor). O dedektorle cikacak "AUC dusuk"
sonucu YANLIS GUVENCE olurdu.

### DEGISEN HUKUM

Onceki bolumlerdeki **"ayrim sansi asmadi" ifadeleri gecersizdir.** Kesif
verisinde, arama genisligi icin duzeltilmis, episode bazinda permute edilmis
sonuc: **p = 0.011**. Ve bu coin kimligi artifakti degil.

**GUNCELLEME (AUDIT 4):** permutasyonda bir hata daha bulundu; duzeltilmis
deger **p = 0.0125**. Ayrica dogru terim DISCOVERY p-degeri.

**Ama bu hala KANIT DEGIL.** Kapanmayan iki sey:

1. **Permutasyonun yakalayamadigi serbestlik.** p, arama genisligini duzeltir
   ama PROTOKOLUN KENDISININ veri gorulerek revize edilmis olmasini duzeltmez
   (olcek filtresi, episode motoru, coin ici yuzdelik — ucu de skor gorunurken
   eklendi). Her biri gercek bir metodolojik hatayi kapatti, skoru kovalamadi;
   ama permutasyon bunu bilemez.
2. **10 isaretli episode, tek ayi piyasasi, tek coin (BTC), geriye donuk
   isaretleme.**

Dogru sonuc: bu, **dogrulayici testi hak eden bir bulgudur** — kapatilacak bir
negatif degil. On kayitli kural ve esikleri AYNEN duruyor.

Arac: `audit.py` (scratchpad). Dogrulandi: episode-F1 elle hesapla birebir ·
satir-F1'den farkli agirlik veriyor · acgozlu_ep ekileni buluyor · ampirik p
`(k+1)/(N+1)` · null altinda p ~uniform · vektorel AUC tekil AUC ile ayni ·
episode ici karistirma coin sayilarini koruyor.

## AUDIT 4 — PERMUTASYON KARISIK BLOKLARDA BOZUKTU (2026-09-13, DUZELTILDI)

Kullanicinin son sorusu: episode'lar karisik (hem pozitif hem negatif satir
iceriyor); permutasyon episode'a TEK etiket mi veriyor, blok ici yapiyi ve
buyuklugu gercekten koruyor mu? Denetlendi.

### Gercek episode yapisi (17 episode, 123 satir)

Tek satirlik episode'lar VAR (5 ve 9), 2 pozitifli episode'lar da VAR (10, 11).
`k_e` coklu kumesi: `[0×7, 1×8, 2×2]` · hem poz hem neg iceren episode: **8**.

### Bulunan hata

```python
k = min(sayi[kaynak], boy[hedef])      # ESKI
```

Kaynak episode'un pozitif sayisi hedef episode'un SATIR sayisindan buyukse
fazlasi **sessizce siliniyordu**. 2 pozitifli bir kaynak, tek satirlik
episode 5 veya 9'a dusunce bir isaret kayboluyor.

| 5000 tur, gercek episode yapisi | eski |
|---|---|
| toplam isaret 12 yerine 10-11 olan tur | **1121 / 5000 (%22.4)** |
| `k_e` coklu kumesi korunan tur | %77.6 |
| episode BUYUKLUGU bozulan tur | 0 |
| isaretli episode sayisi (gercek 10) | hep 10 |
| karisik bloklar korunuyor mu | evet (medyan 8/10 — gercekle ayni) |

Yani **iki endise yersizdi** (tek-etikete cokme yok, buyukluk bozulmuyor) ama
**ucuncusu gercek bir hataydi**: null'un pozitif sayisi gercekten farkli olunca
F1 karsilastirilabilir olmaktan cikar.

### Duzeltme ve etkisi

`k_e` coklu kumesi AYNEN korunuyor; yerlestirme olanaksizsa permutasyon
yeniden cekiliyor (reddetme ornekleme, ~1.3 deneme). Dogrulandi: 5000/5000
turda toplam isaret ve `k_e` korunuyor, buyukluk bozulmuyor, karisik bloklar
duruyor, dar kurulumda bile kayip yok.

| olcut | eski (bozuk null) | **duzeltilmis** |
|---|---|---|
| SATIR-F1 0.909 | p = 0.0110 | **p = 0.0125** (k=24/2000) |
| ayni kuralin EPISODE-F1'i 0.947 | p = 0.0115 | **p = 0.0160** (k=31) |
| EPISODE-F1 (episode aramasi) | p = 0.9015 | p = 0.9070 (yine cozunurluk yok) |

Hata gercekti, etkisi kucuktu, **hukum degismedi.**

Coin kimligi sonuclari (p = 0.156 / 0.232) ETKILENMEDI — `episode_ici_karistir`
ayri bir fonksiyon, bu hataya hic dokunmuyor.

### Bilinen kalan kusur (duzeltilmeyecek, bilincli)

Aday secimindeki aile esigi (27.1) bu BOZUK null ile hesaplandi. Yeniden
kosulmuyor: aday secim bir HIPOTEZ URETME adimidir, cikarim degil; ve sonucu
gorduktan sonra ayni veride yeniden turetmek on kaydin tek degerini — yeni
veriye dokunmadan once yazilmis olmasini — yok eder.

### TERMINOLOJI DUZELTMESI

`p = 0.0125` bir **DISCOVERY p-degeridir**, bagimsiz dogrulama p-degeri degil.
Permutasyon arama genisligini duzeltir ama protokolun ayni veriye bakilirken
birkac kez revize edilmis olmasini duzeltemez.

## PROTOKOL DONDURULDU (2026-09-13)

Dort audit de kapandi. Bu veri uzerinde arastirma **BITTI**. Ayni veri setinde
kurali iyilestirmeye calismak onu oldurur.

### ON KAYIT — DEGISMEZ

    4h_dip100_uzaklik_d3|24-12s|ort <= 36.6
      VE
    4h_RSI2_ivme|48-24s|ort        >= 48.4

Yeni veride: esik degismez · ucuncu kosul eklenmez · ozellik degismez ·
genis arama ACILMAZ.

### Iki katmanli dogrulama

1. **Geriye donuk bagimsiz:** 2021 May-Tem duzeltmesi · 2018-19 ayi · diger net
   ayi/duzeltme donemleri. **Once daireleri bitir, tarihleri kilitle, SONRA
   kurali kostur.** Yeni donemlerde kurala bakarak isaret koyma.
2. **Ileriye donuk:** canli grafikte firsat gorunce SICRAMA OLMADAN once
   tarih/saat kaydet. Hindsight'i tamamen kapatir.

### Raporlama bicimi (her donem AYRI — havuzlama YOK)

Havuzlarsan "tek donem tum sonucu tasiyor" problemine geri donulur.

| donem | episode | yakalanan | yanlis alarm | kesinlik | duyarlilik | F1 | episode-blok p | hukum |
|---|---|---|---|---|---|---|---|---|
| 2018-19 | | | | | | | | PASS/FAIL |
| 2021 May-Tem | | | | | | | | PASS/FAIL |
| diger | | | | | | | | PASS/FAIL |
| canli set | | | | | | | | PASS/FAIL |

Rejimler ayri tutulur (yukselen trend geri cekilmesi ile dusen trend sicramasi
farkli problemlerdir).

### Siradaki adim KULLANICIDA

Yeni donem isaretleri bekleniyor — `_isaretli_olaylar.json` formatinda tarih
listesi yeterli. Isaretleme bitmeden kural kosturulmayacak.

## DOGRULAMA ON KAYDI — PASS/FAIL ESIGI (2026-09-13, VERI GORULMEDEN YAZILDI)

Sonuc geldikten sonra "p biraz yuksek ama F1 iyi" diye kriter kaydirmak tum on
kaydi gecersiz kilar. Esik **simdi** yazildi ve bir daha degismeyecek.

### HIPOTEZ A — tek hipotez, dondurulmus

    4h_dip100_uzaklik_d3|24-12s|ort <= 36.6
      VE
    4h_RSI2_ivme|48-24s|ort        >= 48.4

Icerigi: **4H'de uzun donem dip konumu + daha erken baslayan kisa RSI ivmesi.**

Esik 36.6 -> 40 YAPILMAZ · 48.4 -> 45 YAPILMAZ · ucuncu kosul EKLENMEZ ·
ozellik DEGISMEZ · genis arama ACILMAZ.

**Ayrica kaydedilmeli:** aday secim YONTEMININ kendisi dogrulanmis sayilmiyor
(aile esigi bozuk null ile hesaplanmisti, bkz. AUDIT 4). Dogrulanan sey
yontemin dogrulugu degil, SADECE Hipotez A.

### Testin gucu — OLCULDU (veriye bakmadan, simulasyonla)

Kesif ile dogrulamanin farki: **dogrulamada ARAMA YOK**, kural sabit. Null
cok daraliyor, dolayisiyla gereken performans makullesiyor.

Sabit kural · episode-blok permutasyonu · guc = p<=0.05 verme olasiligi:

| isaretli episode | yakala %50 / yanlis %10 | %60 / %10 | %60 / %20 | %70 / %20 |
|---|---|---|---|---|
| 10 | 0.90 | 0.96 | 0.80 | 0.92 |
| 15 | 0.97 | 0.99 | 0.93 | 0.99 |
| 20 | 0.98 | 1.00 | 0.95 | 1.00 |

**DUZELTME (kullanici itirazi hakli) — buraya once "10 isaretli episode zaten
yeterli" yazilmisti. Bu ifade YANLIS, cunku KOSULLU:** yukaridaki tablo sadece
GUCLU bir etki varsayiyor. Etki zayifladikca 10 episode coker:

| etki | yakala/yanlis | 10 ep | 15 ep | 20 ep | 30 ep |
|---|---|---|---|---|---|
| GUCLU | 70/10% | 1.00 | 1.00 | 1.00 | 1.00 |
| ORTA | 60/15% | 0.88 | 0.98 | 1.00 | 1.00 |
| **ZAYIF** | 50/20% | **0.53** | 0.75 | 0.83 | 0.95 |
| COK ZAYIF | 40/20% | 0.35 | 0.44 | 0.58 | 0.72 |
| MARJINAL | 40/30% | 0.10 | 0.13 | 0.20 | 0.24 |
| SILIK | 30/25% | 0.04 | 0.10 | 0.09 | 0.10 |

Zayif ama GERCEK bir etkide 10 episode yazi-tura (0.53). O hucrede bir FAIL
"kural oldu" demek DEGILDIR.

**Bu yuzden hukum ikili degil UCLU** (asagida): PASS · FAIL(gucul) · SONUCSUZ.

### Null kalibrasyonu — test OLDUGUNDAN KATI

Kural isaretle tamamen ILGISIZ iken (yakalama = yanlis alarm) gercek yanlis
PASS orani:

| isaretli episode | nominal %5 esikte | nominal %1.25 esikte |
|---|---|---|
| 10 | **%0.8** | %0.0 |
| 15 | **%2.5** | %0.5 |
| 20 | **%2.8** | %0.2 |

Yani a=0.05 pratikte %1-3 gibi davraniyor. **Bu yuzden ustune Bonferroni
KONULMUYOR** — konulsa 10 episode'da guc 0.80'den 0.58'e duserdi, cift kat
muhafazakarlik olurdu. Coklu donem sorunu bunun yerine BIRLESIK esikle
cozuluyor (asagida).

### KARAR KURALI — degismez

**HEDEF ETKI (simdi sabitleniyor):** guc kapisi **ORTA etki = %60 yakalama /
%15 yanlis alarm** icin hesaplanir. Gerekce: kesif setinde episode duyarlilik
9/10, kesinlik 9/9 cikti — ama kesif skoru daima iyimserdir (kazananin
laneti), o yuzden hedef bir kademe asagi alindi.

**Donem basina — UC hukum:**
- **KOSULMAZ:** donemde **< 10 bagimsiz isaretli episode** varsa test hic
  kosulmaz, **"NOT RUN"**.
- **PASS:** episode-blok ampirik p <= **0.05** (satir-F1, sabit kural,
  2000 tur, `(k+1)/(N+1)`).
- **FAIL:** p > 0.05 **VE** o donemin episode sayisinda ORTA etkiye karsi
  guc >= 0.80. Ancak bu durumda "kural bu donemde oldu" denebilir.
- **SONUCSUZ:** p > 0.05 ama guc < 0.80. **Kanit degildir, kural olmedi.**

Raporda her donem icin gercek episode sayisindaki guc de yazilir.

**Genel hukum (multiplicity buradan kontrol ediliyor):**
- **DOGRULANDI** = geriye donuk donemlerin **en az 2'si PASS**
  **VE** kosulan tum donemlerin Fisher-birlesik p'si <= **0.01**
  **VE** hicbir donemde yon TERS degil (episode kesinligi taban oranin
  altinda degil).
- Aksi halde **DOGRULANMADI**.

**ZINCIRIN TAMAMI NULL ALTINDA KALIBRE EDILDI** (kullanici talebi — Fisher'i
tek basina degil, butun zinciri olc). Kural isaretle TAMAMEN ilgisizken,
3000 deneme, donem basina 400 permutasyon:

| kurulum | >=2 PASS | Fisher<=.01 | **TUM ZINCIR** |
|---|---|---|---|
| 4 donem (10,10,15,20 ep) | %0.667 | %0.033 | **%0.000** |
| 3 donem (10,15,20 ep) | %0.200 | %0.100 | **%0.000** |
| 4 donem (hepsi 10 ep) | %0.533 | %0.133 | **%0.000** |

3000/3000 temiz — gercek yanlis-DOGRULANDI orani **%0.12'nin altinda**.
**Bonferroni kesinlikle gereksiz; zincir zaten fazlasiyla katidir.**

**Bunun bedeli kaydedilmeli:** bu kadar muhafazakar bir zincir GUC kaybettirir.
Genel "DOGRULANMADI" sonucu, donemlerin tek tek basarisiz oldugu anlamina
gelmez — donem tablosu ayrica okunmalidir.

**Ayri ve DIK bir etiket (PASS/FAIL'i degistirmez):**
- **KULLANISLI** = episode duyarlilik >= 0.40 **ve** episode kesinlik >= 0.50.
- Istatistiksel PASS ama KULLANISSIZ olabilir; bu durumda "gercek ama
  islem icin yetersiz" denir. Bu etiket bir FAIL'i kurtarmak veya bir PASS'i
  veto etmek icin KULLANILAMAZ.

**Canli (ileriye donuk) set** ayri raporlanir ve hindsight kontrolu olarak
tek basina belirleyicidir — geriye donuk sonuclarla havuzlanmaz.

### Rapor bicimi — her donem AYRI

| donem | rejim | bagimsiz ep | kor isaret | sicrayan | sicramayan | ateslenen ep | dogru | yanlis alarm | kesinlik | duyarlilik | F1 | p | ORTA etkide guc | HUKUM | KULLANISLI? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

HUKUM = PASS · FAIL(gucul) · SONUCSUZ · NOT RUN

### DONEM SIRASI (kurala BAKMADAN secilir)

1. **2021 May-Tem BTC duzeltmesi** — kesife yakin ama ayri episode'lar
2. **2018-19 BTC ayi piyasasi** — yapisal olarak cok farkli, en guclu bagimsiz test
3. Diger net dusus/duzeltme rejimleri — **once donemi tanimla, sonra isaretle**
4. **Canli isaretleme** — paralel yurur, en degerli set

### ISARETLEME — KOR (REPLAY) YONTEM ZORUNLU

**"Basarisiz firsatlari da isaretle" YETMEZ.** Gecmis grafigin TAMAMINI
gorerek isaretlersen hindsight kapanmaz: hangi bolgenin sonrasinda ne oldugunu
zaten biliyorsun, "firsat gibi gorunuyordu" yargisi bundan bagimsiz olamaz.

**Zorunlu yontem — TradingView bar replay:**

    gelecegi KAPAT -> o ana kadarki grafige bak -> firsat goruyorsan isaretle
    -> bir sonraki bara gec -> ... -> is bitince gelecegi ac

Ancak bu, "o anda gorur muydum?" sorusunun gercek testidir.

**Sonucun ne oldugunu YAZMA.** Tarihleri ver, sicrayip sicramadigini
mekanik olarak ben hesaplarim.

### HEDEF KAYMASI — bu yuzden IKI ayri test var

Kritik ayrim: kesif setindeki 12 isaretin **12'si de sicradi**. Yani
Hipotez A, "sicramadan ONCE ne var" sorusuna cevap olarak bulundu.

Kor isaretlemede sicramayanlar da pozitif sayilirsa soru DEGISIR:
artik "yukselisin parmak izi" degil **"kullanicinin firsat olarak gordugu
yapinin parmak izi"** dogrulanir. Ikisi de mesru ama AYNI SEY DEGIL.

Cozum — kor isaretleme + sonucu AYRI etiket olarak tutmak:

| test | pozitif | negatif | rol |
|---|---|---|---|
| **BIRINCIL** | kor isaret **VE** sicradi | kor isaret **AMA sicramadi** + caliper'li gunler | kesifle AYNI soru |
| IKINCIL (bilgi) | TUM kor isaretler | caliper'li gunler | "firsat gorusunun" izi |

**Sicramayan kor isaretler EN IYI ZOR NEGATIFTIR** — baglam eslestirmesiyle
uretilmis degil, gercekten "firsat gibi gorunup tutmamis" anlar. Caliper'in
yapay olarak yaklasmaya calistigi seyin ta kendisi.

**Bu ancak isaretleme KOR yapildiysa mesrudur.** Sonucu bilerek isaretlenirse
"sicramayan isaret" sinifi kirlenir ve bu tasarim cover.

Hukum BIRINCIL testten cikar. Ikincil rapor edilir, karari degistirmez.

### SICRAMA TANIMI — simdi sabitleniyor, degismez

    isaret gununun kapanisindan itibaren 30 gun icinde
    high +%10'a ULASIR   ve bu, close'un -%10 DUSMESINDEN ONCE olur

Yol-farkindadir (hedef-mi-once-stop-mu), tek yonlu "hic +%10 gordu mu" DEGIL.
Kesif isaretleri 10-30 gunde +%7..+%29 sicramisti; +%10 bu araligin altindan
secildi ama en dusuk isareti (+%7) disarida birakir — bilincli, cunku esik
sonuc gorulmeden sabitlenmeli.

`+%7` ve `+%15` icin sonuclar da raporlanir ama **SADECE BILGI AMACLI** —
hukmu degistiremez (KULLANISLI etiketiyle ayni disiplin).

### Kayit bicimi

    DONEM: 2021-05-01 / 2021-07-31
    REJIM: sert duzeltme
    YONTEM: bar replay (gelecek kapali)

    2021-05-19  firsat
    2021-05-23  firsat
    2021-06-08  firsat
    2021-06-22  firsat
    ...

Araclar (scratchpad): `guc_analizi.py` (guc + null kalibrasyonu) ·
`_zayif_etki.py` (etki buyuklugune gore guc) · `_zincir_kalibre.py`
(karar zincirinin tamami null altinda).
