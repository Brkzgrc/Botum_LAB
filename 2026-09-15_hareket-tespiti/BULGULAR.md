# Hareket Tespiti — 15.09.2026

**Veri:** 2021-01 / 2023-01 · 399 USDT paritesi · **DELIST OLANLAR DAHIL**
(arsiv: s3-ap-northeast-1.amazonaws.com/data.binance.vision)

**Olcut:** +%2.5'e ULASTI **ve** bu -%2.5'e inmeden ONCE oldu, **1 saat icinde**.
Yol-farkinda. Cikis kurali varsaymaz (kullanici: "stop/TP sonraki mesele").
Kullanicinin "dogru an" vurgusu geregi ufuk KISA tutuldu (24 saat degil 1 saat).

**TABAN %51.0** (4.836.054 bar) · **BASABAS %54.0** (komisyon %0.20, +-%2.5)

---

## SONUC TABLOSU — en iyiden kotuye

| kurulum | isabet | n | net/islem | t |
|---|---|---|---|---|
| dalga2 + TUM KAPILAR | %58.6 | 1.007 | +%0.229 | +2.19 |
| **1G BTC + 1G coin + 4S coin** | **%58.0** | **100.604** | **+%0.201** | **+6.37** |
| dalga2 + BTC (1h yaklasma) | %57.6 | 16.215 | +%0.179 | +4.00 |
| HULL ikisi + yaklasma ucu | %57.6 | 21.850 | +%0.180 | +2.09 |
| dalga2 + SRSI 60-80 | %56.8 | 2.032 | +%0.142 | +2.65 |
| HL + SRSI + BTC | %56.1 | 9.978 | +%0.104 | +5.38 |
| HL + StochRSI donus | %55.2 | 39.917 | +%0.060 | +6.29 |
| dalga2 (EMA20>EMA50 kesisim) | %54.8 | 50.675 | +%0.038 | +4.09 |
| kapi zinciri (MACD tabanli) | %53.8 | 58.216 | -%0.010 | +1.30 |
| HL (yukselen dip) | %53.2 | 229.113 | -%0.040 | +4.30 |
| **taban** | %51.0 | 4.836.054 | -%0.152 | -0.05 |
| LL (dusen dip) | %50.1 | 224.996 | -%0.200 | +1.35 |

**EN SAGLAM: `1G BTC + 1G coin + 4S coin` — %58.0, n=100.604, t=+6.37**

---

## 1. EN ONEMLI BULGU — kapilar tek tek ISE YARAMIYOR, birlesince yariyor

Kullanicinin tanimi: **EMA20 ile EMA50 arasindaki mesafe 3 bar duzenli azaliyor.**
EMA20 ALTTAYSA "yukselis", USTTEYSE "dusus".

| kapi | tek basina | |
|---|---|---|
| 1G BTC yukselis | %53.3 | basabasin ALTINDA |
| 1G coin yukselis | %51.9 | tabanda |
| 4S coin yukselis | %52.7 | basabasin ALTINDA |
| **UCU BIRDEN** | **%58.0** | **+7.0 puan** |

Dogrusal DEGIL. Uc zayif kapi, ust uste binince guclu bir filtre veriyor.
Kullanicinin tarif ettigi "kapi zinciri" mantiginin olculmus hali.

Kontrol: 1G BTC **DUSUS** durumunda %50.8 — tabanin altinda. Yon dogru.

### Bu tanim kesisimi ONGORMUYOR (olculdu)

| | 12 bar icinde gercekten kesisti |
|---|---|
| BTC 1h yukselis durumu | %31.1 |
| BTC 4h yukselis durumu | %30.4 |

%70'inde EMA'lar yaklasip kesismeden geri aciliyor. Degeri kesisim tahmininde
DEGIL, o anki piyasa baskisini tarif etmesinde.

---

## 2. YAPI CALISIYOR, OSILATOR CALISMIYOR

| tur | sonuc |
|---|---|
| **yapi** (EMA kesisim, EMA yaklasma, LL/HL) | %53-58, t=+4..+6 |
| **osilator** (RSI/MACD/StochRSI/KDJ/OBV/W%R) | %48-53, hicbiri basabasi gecmiyor |

### LL/HL — kullanicinin hipotezi DOGRU
```
LL (dusen dip)     %50.1   t=+1.35   anlamsiz
HL (yukselen dip)  %53.2   t=+4.30   GERCEK
```
Tek basina basabasin altinda, ama StochRSI ile birlesince %55.2 (t=+6.29).

### EMA dalgalari — kullanicinin sira hipotezi DOGRU
```
23.277 EMA20/EMA50 kesisiminin %100'unde fiyat EMA20'yi ONCE kesmis.
gecikme: medyan 5 bar (1.2 saat)
dalga1 (fiyat>EMA20)   %53.2
dalga2 (EMA20>EMA50)   %54.8   <- dalga2 daha degerli
```

---

## 3. OLEN HIPOTEZLER

| hipotez | sonuc |
|---|---|
| 6 gostergenin "donus oyu" toplami | skor YUKSELDIKCE isabet DUSUYOR (6+ kova %47.6) |
| StochRSI dipten donus (0-20) | **%50.3 — en kotu kova.** Iyi olan 60-80 (%53.4) |
| MACD huni (A/B/C/D) | D "gec kaldik" = %51.9, B "kesisim" = %51.4. D DAHA IYI |
| 4H RSI esigi gevsetme (60/55/50/45) | yil ici siralama tutarsiz, kararli optimum YOK |
| BTC verimlilik orani (efficiency ratio) | hic ayirmiyor |
| **Hull Suite (HMA55, 1G)** | **coin %50.8 · BTC %50.6 · ikisi %50.4 — hepsi TABANIN ALTINDA** |

Hull notu: HMA55 gunlerce suren swing icin tasarlanmis; 1 saatlik ufka karsi
test edildi. Uzun ufukta calisiyor olabilir, bu testte katki yok.

---

## 4. YONTEM NOTLARI (tekrar dusulmesin)

1. **15m OLCUM IZGARASI DEGIL.** Kullanici 15m'e ancak 1G ve 4S onay verdikten
   SONRA bakiyor. Ilk kosularda 4.8M bar tarandi — kullanicinin hic bakmayacagi
   barlar. Kapi zinciri kurulunca isabet 51.0 -> 53.8'e cikti.
2. **"Gun ortalamasi" para olcutu DEGIL.** Gun bazinda taban %54.0 (islem bazinda
   %51.0) — kucuk gunler esit agirlik aliyor. Para olcutu ISLEM bazindadir.
   Bir ara bu ikisi karistirildi, duzeltildi.
3. **Binance `endTime` ACILIS zamanina gore filtreler.** Sinyal 12:15'teyse
   12:00'de acilan 4h mum (16:00 kapanisli) listeye girer -> ILERIYE BAKMA.
   4h RSI'da medyan -4.71 puan sapma yaratmisti. Duzeltme: kapanisi sinyal
   anindan sonra olan mumlari at.
4. **Salinim dibi ancak W bar SONRA onaylanir.** Sinyal onay barinda uretilir.
5. **Delist yanliligi gercek:** 30 likit majorde dalga2 %57.7, tum evrende %54.8.
   Fark 2.9 puan, tamami hayatta kalmaktan. (yasayan %56.2 / delist %53.7)

---

## 5. KULLANICININ YONTEMI (kendi ifadesiyle)

```
1 GUNLUK   BTC + coin · genel piyasa: yukselisde mi, donus sonrasi yukselis basi mi
   v uygunsa
4 SAAT     alim firsati: yukselis / yatay / dusus?
   v uygunsa
1 SAAT     yukselis baslangici bekle (donus)
   v
15 DAKIKA  1 saati teyit -> ALIM YERI
```

MACD huni: A=arastir (negatif, yukari donuyor) · B=sifiri kesti (AL, BTC yukari
sinyal vermeli) · C=kesis+1-2 bar (AL, kar al cik) · D=gec kaldik (VETO, takip)

Gosterge rolleri: **MACD yavas = yapi · StochRSI hizli = AN**
StochRSI "30'dan sonra manasi var" (olcumle dogrulandi: 0-20 en kotu kova)

Destekleyici (sart degil): EMA20<EMA50 iken EMA20 yukari donuyor · fiyat EMA20'yi kiriyor

Cikis: +%2-3 cik · en gec 3 saatte +%5'i gecerse %1-2 trailing

---

## SONRAKI ADIM

1. **Dogrulama:** `1G BTC + 1G coin + 4S coin` kuralini 2023-2024'te TEK kosuda
   sina. 2025-2026 ikinci dogrulama. Arama YOK, esik ayari YOK.
2. Hedef/ufuk duyarliligi: +%2.5/1sa disinda da tutuyor mu
3. Cikis arastirmasi (kullanicinin sirasi: once giris kanitlansin)
