# 1 GÜNLÜK StochRSI Kesişim Kurulumu — Ölçüm Kaydı (01.10.2026)

**Proje:** `claude/spot-sinyal-arastirmasi/`
**Çalışma:** `2026-10-01_gunluk-stochrsi-kesisim/`
**Durum:** keşif + iki dönemde doğrulama tamamlandı

---

## 0. ÖZET — üç cümlede

1. **Kullanıcının kuralı, yazıldığı haliyle REDDEDİLDİ.** Üç dönemin üçünde de
   tabanın altında; aynı-gün kesit kontrolünde t = −2.4 / −4.2 / −0.4.
2. **Ama gözlem yanlış değildi** — yükselişlerin başlangıcında gerçekten
   StochRSI < 15 (2.6x), W%R −100..−75 (2.5x), MACD hist < 0 (1.8x) var.
   Sorun yönün tersi: bu değerler **dibi** bulur, dip olmak yükselişi getirmez.
3. **Kuralın iki parçası çıkarılınca çalışıyor.** `StochRSI kesişimi` şartı ve
   `RSI > 40` şartı atılıp RSI **ters** çevrilince (`RSI ≤ 40`), kurulum üç
   dönemin üçünde de tabanı geçiyor: 5 günlük net medyan getiri
   **+%1.24 / +%1.13 / −%0.57** (taban: −%0.95 / −%0.20 / −%2.35),
   kazanan oranı tabanın **+7 ile +9 puan** üstünde.

---

## 1. Araştırma sorusu

Kullanıcının 1 günlük grafikte elle bulduğu kurulum:

```
StochRSI KESİŞİM anında (kesişim öncesi / kesişim / kesişim sonrası = 3 alan)
    StochRSI < 15            (KESİN şart)
RSI    > 40
MACD   < 0.05
W%R    −100 ile −75 arası
```

Sorular:
1. Bu kurulum gerçekten yükseliş başlangıcını işaretliyor mu?
2. **Benzer ama farklı özellik/değer, ya da başka yükseliş formasyonları var mı?**

---

## 2. Açıkça belirtilen belirsizlikler (sessizce varsayılmadı)

| # | belirsizlik | nasıl çözüldü |
|---|---|---|
| B1 | "StochRSI < 15" hangi çizgi? | `max(K,D)`, `min(K,D)`, `K` — **üçü de ayrı ölçüldü**, sonuç değişmiyor |
| B2 | **"MACD < 0.05" MUTLAK bir sayı; MACD fiyat ölçeğine bağlıdır.** BTC'de (fiyat ~100.000) MACD yüzlerle ifade edilir, 0.05 eşiği orada anlamsızdır | 6 ayrı okuma test edildi: şart yok / hist<0 / dif<0 / dif<fiyatın %0.05'i / dif<fiyatın %1'i / dif<0.05 (birebir). **Hepsi aynı sonucu veriyor** — MACD şartı neredeyse hiç iş yapmıyor (çıkarılınca n 3989→4036) |
| B3 | "kesişim sonrası" barı kullanmak **geleceğe bakmaktır** | 3 pencere ayrı ölçüldü. Kesişim sonrası kullanılan varyantta sinyal barı **1 gün ileri atıldı** (gecikmeli giriş) — ileriye bakma yok |

---

## 3. Veri ve evren

| | |
|---|---|
| zaman dilimi | **1 GÜN** (bu projede ilk kez 1 günlük ızgarada doğrudan kurulum arandı) |
| kaynak | `data-api.binance.vision` (yaşayan pariteler) + `s3-ap-northeast-1.amazonaws.com/data.binance.vision` aylık arşiv (delist olanlar) |
| dönem | 2017-08-17 → 2026-09-30 (bugünün KAPANMAMIŞ mumu hariç) |
| parite | **593** USDT paritesi · **789.011 günlük bar** |
| delist dahil mi | **EVET** (hayatta kalma yanlılığı yok) |
| likit alt küme | 20 günlük ortalama quote hacim ≥ 1.000.000 USDT |

### Evren filtresi — metadata ile, substring körlemesi YOK

`araclar/evren.py`, çıktı `veri/evren_1g.json` (elenen her sembol sebebiyle kayıtlı).

| elenen | sayı | kural |
|---|---|---|
| tokenize hisse/ETF | **87** | exchangeInfo `permissionSets` içinde **`TRD_GRP_261`** |
| leveraged token | 40 | exchangeInfo `LEVERAGED` izni |
| leveraged token (BULL/BEAR) | 8 | sonek + önek gerçek varlık + bugün SPOT'ta yok |
| stablecoin | 19 | açık liste |
| fiat | 3 | açık liste (AUD, EUR, GBP) |

**KORUNANLAR (false positive üretilmedi):** `SYRUP` (önek "SYR" varlık değil),
`JUP`, `PUMP`, `SUPER`, `PAXG`, `BULL`, `BEAR`, `PUNDIX`.

> **Yeni bulgu — tokenize hisse tuzağı.** Veri setine Binance'in tokenize
> hisseleri (AAPLB, NVDAB, SPYB, TSLAB, QQQB, SOXL/SOXS...) karışıyordu. Bunları
> "BUSDT ile bitiyor" diye elemek **ARB, BNB, SHIB, QNT, DGB, TRB, CKB, AMB,
> MOB, PHB, VIB** gibi gerçek coinleri de siler. Doğru işaret `TRD_GRP_261`
> izin grubudur; 87 ürünü tam yakalar, gerçek coinlerin hiçbirine dokunmaz.

---

## 4. Gösterge kodu doğrulaması + DÜZELTİLEN HATA

`araclar/gosterge1g.py`, bu depoda önceden doğrulanmış
`2026-09-15_dip-tarama/araclar/gosterge.py`'ye karşı sınandı
(`araclar/test_gosterge.py`, çıktı `sonuclar/test_gosterge_cikti.txt`):
**8/8 gösterge ısınma sonrası birebir aynı** (RSI, StochRSI K/D, MACD dif/dea/hist, W%R, KDJ J).

> ### DÜZELTİLEN HATA — sahte "StochRSI < 15"
> Eski `gosterge.py`'nin `_sma` fonksiyonu `np.nan_to_num` kullanıyor; penceresinde
> NaN olan barlarda NaN yerine **sayı** üretiyor. Sonuç: her sembolün geçmişinin
> **ilk ~26 barında StochRSI K = D = 0.0**. BTC'de ilk 40 barın **24'ünde**
> "StochRSI < 15" görünüyordu — tamamı sahte. 593 sembolde bu ~15.000 uydurma
> dip sinyali demekti. `gosterge1g.py` NaN-güvenli SMA + açık ısınma güvencesi
> kullanıyor; ilk geçerli StochRSI barı 31.
>
> **Bu hata eski çalışmaların sonuçlarını etkilemiş olabilir** (dip-tarama,
> hareket-tespiti, kademe-hareket hepsi `gosterge.py` kullanıyor). Bu çalışmada
> düzeltildi; eski sonuçlara DOKUNULMADI, ileride ayrı bir işte gözden geçirilmeli.

---

## 5. Metodoloji

### Çıkış kuralı VARSAYILMADI
Her barın sonraki **30 günlük yolunun tamamı** kaydedildi: hangi gün
+%2.5/5/10/15/20/30/50'ye ulaştı, hangi gün −%2.5/5/10/15/20'yi gördü,
5/10/20/30 günlük MFE / MAE / kapanış getirisi, zirveye kaç gün.
Hedef/stop/temiz-yükseliş ölçüleri **sonradan** bu tablodan türetildi.
(2026-09-22 kademe-hareket çalışmasından devralınan ilke.)

### Ölçü tanımları (bu çalışmanın sürümü)
- `temiz +X/−Y` = 30 gün içinde +%X'e **ulaştı ve bunu −%Y'yi görmeden ÖNCE yaptı**.
  Aynı gün hem +X hem −Y görülürse **temiz DEĞİL** sayılır (ihtiyatlı).
- `MFE30` = 30 gün içindeki en yüksek yükseliş (medyan raporlanır).
- Giriş = sinyal barının **kapanışı**. İleriye bakma yok.
- Ortalama getiriler **kullanılmadı** (mikro-cap uç değerleri +%945 gibi anlamsız
  ortalamalar üretiyor). **Medyan** raporlanır.

### Üç ayrı taban (hepsi raporlandı)
| | |
|---|---|
| **T1** | tüm evren barları (ham taban) |
| **T2** | **AYNI GÜN kesit eşlemesi** — "aynı gün, aynı piyasada, bu kuralın seçtiği coinler o günün diğerlerinden iyi mi?" Piyasa rejimi karıştırıcısını yok eder |
| **T3** | sadece StochRSI yukarı kesişimi olan barlar (ek şartların katkısı ne) |

Anlamlılık **gün bazında**: aynı günün sinyalleri **tek gözlem** sayılır
(CLAUDE.md: bar değil OLAY say). Ayrıca ay bloklu t.

### Dönem bölümü
| dönem | rol |
|---|---|
| 2017-08 → 2022-12 | **KEŞİF** — tüm arama burada |
| 2023-01 → 2024-12 | **DOĞRULAMA** — eşikler donduruldu, tek koşu |
| 2025-01 → 2026-09 | **DOĞRULAMA** — en güncel, tek koşu |

Eşikler keşif döneminde hesaplanıp `sonuclar/formasyon_kesif.json`'a **donduruldu**;
doğrulamada değiştirilmedi.

---

## 6. SONUÇ 1 — Kullanıcının kuralı, yazıldığı haliyle

### 6.1 Ham taban karşılaştırması (A1 = tam kural, likit evren)

| dönem | n | temiz+20/−10 | taban | MFE30 medyan | taban | 5g net medyan | taban | kazanan | taban |
|---|---|---|---|---|---|---|---|---|---|
| keşif 2017-2022 | 3.556 | %28.1 | %35.0 | %18.4 | %24.6 | **−%1.87** | −%0.95 | %41.0 | %46.3 |
| doğr. 2023-2024 | 3.939 | %32.4 | %34.4 | %17.6 | %19.5 | **−%0.57** | −%0.20 | %47.2 | %49.0 |
| doğr. 2025-2026 | 2.606 | %27.4 | %25.3 | %13.1 | %14.4 | **−%1.87** | −%2.35 | %41.4 | %39.1 |

(net = komisyon %0.2 düşülmüş, 5 gün sabit tutma)

### 6.2 Aynı-gün kesit kontrolü (karıştırıcı-arındırılmış)

| dönem | temiz+20/−10 fark | t | MFE30 t | RET20 t |
|---|---|---|---|---|
| keşif 2017-2022 | −2.61 puan | **−2.39** | −5.09 | −4.01 |
| doğr. 2023-2024 | −5.51 puan | **−4.60** | −0.75 | −2.61 |
| doğr. 2025-2026 | −0.62 puan | −0.45 | +0.76 | −1.16 |

### 6.3 Ablasyon — her şart ÇIKARILINCA sonuç İYİLEŞİYOR (keşif dönemi)

| | n | temiz+20/−10 |
|---|---|---|
| TAM KURAL (4 şart) | 3.989 | %30.0 |
| `StochRSI<15` çıkarıldı | 5.617 | %31.7 |
| `RSI>40` çıkarıldı | 9.331 | %31.3 |
| `W%R` çıkarıldı | 5.792 | %32.5 |
| `MACD hist<0` çıkarıldı | 4.036 | %29.9 (etkisi ~sıfır) |
| **taban** | 267.658 | **%36.2** |

**Dört şartın hiçbiri tek başına da tabanı geçmiyor.** Pencere varyantları:
pencere 0 → %26.3, pencere 1 → %30.0, pencere 2 → %29.1, kesişim şartı yok → %28.2.

### HÜKÜM 1: Kural, yazıldığı haliyle REDDEDİLDİ.
Üç dönem, iki evren, dört ölçüt, üç taban — hepsinde tabanın altında.

---

## 7. SONUÇ 2 — Gözlem neden doğru hissettiriyor? (taban-oran yanılgısı)

Kullanıcının bakışı **geriye dönük**: yükselen mum gruplarına bakıp başlangıç
anındaki değerleri okudu. Bu `P(değerler | yükseliş başladı)` ölçer.
Alım kararı için gereken ise **tersi**: `P(yükseliş başlayacak | değerler)`.

"Yükseliş başlangıcı" mekanik tanım: 30 günde +%20'ye ulaştı, bunu −%10'u
görmeden önce yaptı, **ve** bar son 10 günün en düşük kapanışı (yerel dip).
Keşif döneminde 16.022 böyle bar (tüm barların %6.0'ı).

| şart | **başlangıçlarda** | tüm barlarda | oran | **ileriye: başlangıç olma oranı** |
|---|---|---|---|---|
| StochRSI(max K,D) < 15 | **%40.3** | %15.1 | **2.67x** | %16.0 |
| W%R −100..−75 | **%83.8** | %33.7 | **2.49x** | %14.9 |
| MACD hist < 0 | **%75.1** | %42.5 | **1.77x** | %10.6 |
| **RSI > 40** | **%32.3** | %71.5 | **0.45x** | %2.7 |
| **StochRSI yukarı kesişim** | **%2.1** | %11.6 | **0.18x** | %1.1 |
| **KULLANICININ TAM KURALI** | **%0.4** | %1.5 | **0.29x** | %1.7 |
| taban (rastgele bar) | — | — | — | **%6.0** |

Aynı tablo 2023-2024 ve 2025-2026'da **birebir aynı yönde** çıktı.

**Okunuşu:**
- **Kullanıcı StochRSI/W%R/MACD konusunda HAKLI.** Yükselişlerin başlangıcında
  bu değerler gerçekten taban-oranın 1.8–2.7 katı sıklıkta var.
- **`RSI > 40` şartı TERS.** Gerçek yükseliş başlangıçlarının sadece %32'si
  RSI>40; medyan RSI **36.6**, %75'lik dilim 41.9. Bu şart yükseliş
  başlangıçlarının **üçte ikisini siliyor**.
- **`Kesişim` şartı en zararlı parça.** Yükseliş başlangıçlarının yalnızca
  **%2.1'inde** o barda kesişim var (taban %11.6 — yani kesişim yükseliş
  başlangıçlarında **daha SEYREK**). Gerçek dip, kesişimden ÖNCE oluşuyor;
  kesişim onayı geldiğinde hareket çoktan başlamış ya da dip çoktan geçmiş.
- **Tam kural, gerçek yükseliş başlangıçlarının %99.6'sını kaçırıyor.**

### 7.1 Kritik kontrol: dip bulmak ≠ yükselecek dibi bulmak

Yerel dip barlarının içinde (keşif dönemi, 46.622 dip, taban temiz+20 = %34.4):

| şart | n | temiz+20/−10 | fark | aynı-gün t |
|---|---|---|---|---|
| StochRSI<15 | 18.443 | %35.0 | +0.6 | −1.13 |
| RSI>40 | 16.305 | %31.7 | **−2.6** | −1.02 |
| RSI≤40 (**ters**) | 29.899 | %35.9 | **+1.5** | −0.53 |
| W%R −100..−75 | 39.665 | %33.9 | −0.5 | −0.73 |
| MACD hist<0 | 34.053 | %35.3 | +1.0 | −1.38 |
| 4 şart birlikte | 5.189 | %29.7 | −4.6 | −1.24 |
| **TAM KURAL** | 324 | **%21.3** | **−13.1** | **−2.04** |

Ve en önemlisi: **yerel dip havuzunun kendi tabanı (%34.4), rastgele barın
tabanından (%36.2) FARKLI DEĞİL.** Yani 1 günlükte dip olmak, yükselme
olasılığını artırmıyor. Osilatörler dibi buluyor; dip bir avantaj değil.

---

## 8. SONUÇ 3 — Başka formasyonlar arandı (asıl soru)

15 formasyon × 4 ölçüt, keşif döneminde, aynı-gün kontrolüyle
(`sonuclar/05_formasyon_kesif.txt`). Ayrıca 35 özellik × 2 uç + 5 olay = **73 kesim**
yerel dip havuzunda tarandı (`sonuclar/04_kesif.txt`).

### 8.1 Aynı-gün kontrolünü geçen formasyon YOK
Keşif döneminde 15 formasyonun **hiçbiri** pozitif anlamlı t vermedi
(en iyi: B5 +0.64, A4 +0.16, B2 +0.11; gerisi negatif). Yani hiçbir formasyon
"aynı gün diğer coinler arasından iyisini seçmek" yapamıyor.

### 8.2 Özellik taramasında en güçlü eksen = OYNAKLIK/BÜYÜKLÜK (artefakt)
En yüksek t değerleri: düşük hacim (+5.12), 100-gün zirvesinden çok uzak (+2.80),
EMA200'ün çok altında (+2.14), 20-gün getirisi çok negatif (+2.00),
Bollinger genişliği yüksek (+1.42). Hepsi aynı şeyi söylüyor: **küçük, illikit,
derin düşmüş, oynak coin.** Bu eksende `MFE30` t değerleri çoğunlukla NEGATİF —
yani kazancı da kaybı da birlikte büyütüyor. **Bu, 2026-09-22 çalışmasının
"oynaklık ekseni hem kazancı hem kaybı birlikte büyütüyor" bulgusunun bağımsız
bir tekrarıdır.**

### 8.3 Dondurulmuş eşiklerle doğrulama (likit evren, tek koşu)

| formasyon | keşif temiz20/taban | 2023-24 temiz20/taban | 2025-26 temiz20/taban | hüküm |
|---|---|---|---|---|
| **B2 dip + derin değer** | 45.2/35.0 | **45.4/34.4** | **32.2/25.3** | **yön 3/3 tutuyor** |
| B5 dip + ADX↑ + PDI↑ | 36.1/35.0 | 34.2/34.4 | 31.3/25.3 | tutarsız |
| B3 dip + KDJ kesişimi | 47.1/35.0 | 43.8/34.4 | 30.5/25.3 | n küçük (314-433) |
| C2 EMA20 kırılımı + StochRSI dipten çıkmış | 38.5/35.0 | 36.0/34.4 | **22.4/25.3** | 2025-26'da TERS |
| C4 yükselen dip + EMA20 üstü + hacim | 37.0/35.0 | 38.8/34.4 | 26.0/25.3 | zayıf |
| C1 trend içi geri çekilme | 34.1/36.2 | — | — | keşifte bile taban altı |
| A1 kullanıcı tam kural | 28.1/35.0 | 32.4/34.4 | 27.4/25.3 | **red** |

**B2 = yerel dip + EMA200'ün ≥%46.5 altında + 100-gün zirvesinin ≥%65.1 altında.**
Üç dönemin üçünde de tabanın üstünde (temiz+20, MFE30 medyan, RET20 medyan).
AMA: aynı-gün t'si üç dönemde de ~0 veya negatif (+0.11 / −1.04 / −1.36) →
avantaj **coin seçiminden değil, zamanlamadan + beta'dan** geliyor.
Ve 2025-2026'da RET20 medyanı hâlâ **negatif** (−%2.91) — yani "ortalamadan az
kaybediyor", "kazanıyor" değil. Ayrıca güçlü piyasada neredeyse hiç ateşlemiyor
(2023-2024'te n=555, 2025-2026'da n=5.049).

> **ÖNEMLİ ÇELİŞKİ UYARISI:** B2'nin içeriği ("coin kendi uzun dönem
> ortalamasının çok altında"), 2026-09-22 çalışmasında **REDDEDİLEN**
> piyasa-bağlamlı adayla aynı eksendir. O aday 2025-2026'da **ters dönmüştü**.
> B2 ters dönmüyor (yön 3/3 tutuyor) — fark, B2'nin BTC bağlamı içermemesi ve
> ölçütün farklı olması olabilir. İki bulgu da korunmalı; B2 "kanıt" değil,
> **yönü üç dönemde tutan tek aday**.

### HÜKÜM 3: Aynı-gün kontrolünü geçen yeni formasyon BULUNAMADI.
Tek dayanıklı aday (B2) bir oynaklık/beta etkisidir, seçim becerisi değil.

---

## 9. SONUÇ 4 — ASIL BULGU: kullanıcının fikri iki değişiklikle çalışıyor

Bölüm 7'deki imza tablosu iki parçanın ters olduğunu gösterdi. **İki karar**
alındı (eşik taraması YOK, optimizasyon YOK):
1. `StochRSI kesişim` şartı **kaldırıldı** (başlangıçlarda 0.18x)
2. `RSI > 40` → **`RSI ≤ 40`** (başlangıçlarda 0.45x, tersi 2.2x)

**A3 kurulumu (nihai hali):**

```
1 GÜNLÜK, kapanışta:
    max(StochRSI K, StochRSI D) < 15
    Williams %R  −100 ile −75 arası
    MACD histogram < 0
    RSI ≤ 40
(kesişim şartı YOK)
```

### Likit evren, komisyon %0.2 düşülmüş, 5 gün SABİT tutma (stop/hedef yok)

| dönem | rol | n | net medyan | kazanan | taban net medyan | taban kazanan | ay bloklu t |
|---|---|---|---|---|---|---|---|
| 2017-2022 | keşif | 15.671 | **+%1.24** | **%55.3** | −%0.95 | %46.3 | +1.02 |
| 2023-2024 | **doğrulama** | 13.982 | **+%1.13** | **%56.2** | −%0.20 | %49.0 | **+3.39** |
| 2025-2026 | **doğrulama** | 14.890 | **−%0.57** | **%47.7** | −%2.35 | %39.1 | +1.41 |

10 gün tutmada da aynı yön: +%0.40 / +%1.29 / −%1.53 (taban −%1.86 / −%0.70 / −%4.17).

### Kısa ufuk isabet oranları (likit)

| | +%2.5 / 3 gün | +%5 / 5 gün | RET5 medyan | RET10 medyan |
|---|---|---|---|---|
| **2017-2022** A3 / taban | %85.0 / %79.0 | %76.9 / %69.3 | +%1.44 / −%0.75 | +%0.60 / −%1.66 |
| **2023-2024** A3 / taban | %75.2 / %72.9 | %64.4 / %61.7 | +%1.33 / +%0.00 | +%1.49 / −%0.50 |
| **2025-2026** A3 / taban | %75.1 / %71.3 | %63.5 / %58.1 | −%0.37 / −%2.15 | −%1.33 / −%3.97 |

A1 (kullanıcının kuralı) aynı tabloda üç dönemde de tabanın **altında**.

### A3 hakkında dürüst sınırlar
- **Avantaj kısa ufukta (3–10 gün).** 20–30 günlük ufukta kayboluyor ya da
  tersine dönüyor. Bu bir **dip SIÇRAMASI**, "yükseliş başlangıcı" değil.
- **Aynı-gün kesit t'si ~0 veya negatif** (−1.19 / −1.58 / −0.84). Avantaj
  **hangi GÜN ateşlediğinden** geliyor, hangi coini seçtiğinden değil.
  Spot'ta nakitte beklemek bir seçenek olduğu için bu pratikte hâlâ işe yarar,
  ama "coin seçme becerisi" diye sunulamaz.
- **2025-2026'da net medyan NEGATİF** (−%0.57). Tabanın (−%2.35) belirgin
  üstünde ama kâr değil. Rejim baskın.
- **A3 keşif döneminin imza tablosundan türetildi** → keşif dönemi sayıları
  teknik olarak in-sample. 2023-2024 ve 2025-2026 bu varyant için
  dokunulmamıştı; o iki dönem **gerçek out-of-sample**.
- Sadece **iki karar** alındı, ikisi de sonuç optimizasyonundan değil imza
  tablosundan çıktı → aşırı uyum riski düşük, ama sıfır değil.
- Ortalama getiriler **kullanılamaz** (mikro-cap uç değerleri +%945 gibi
  anlamsız ortalamalar üretiyor). Sadece medyan ve isabet oranı güvenilir.

---

## 10. Önceki araştırmayla ilişki

| önceki bulgu | bu çalışma |
|---|---|
| `2026-09-15_hareket-tespiti`: "StochRSI dipten dönüş (0-20) = %50.3, **en kötü kova**" (1h ızgara, 1 saat ufuk) | **BAĞIMSIZ TEKRAR.** Farklı ızgara (1 gün), farklı ufuk (30 gün), farklı ölçüt (yol profili) — aynı sonuç: StochRSI dip dönüşü tek başına değer taşımıyor |
| `2026-09-15_hareket-tespiti`: "YAPI çalışıyor, OSİLATÖR çalışmıyor" | 1 günlükte **yapı da çalışmıyor** (C1 trend içi geri çekilme keşifte bile taban altı, t=−3.68; C2 2025-26'da ters döndü). Bu bulgu 1 günlüğe taşınamıyor |
| `2026-09-22_kademe-hareket`: "oynaklık ekseni kazancı ve kaybı BİRLİKTE büyütüyor" | **TEKRARLANDI.** 73 kesimde en yüksek t'ler oynaklık/büyüklük ekseninde, MFE30 t'leri negatif |
| `2026-09-22_kademe-hareket`: piyasa-bağlamlı aday (coin uzun dönem ort. altında) 2025-26'da **ters döndü, reddedildi** | B2 aynı eksende ama 3/3 yön tutuyor. **Çelişki kayda geçti**, ikisi de korunuyor |
| `2026-09-22_kademe-hareket`: 4h'de şart sayısı arttıkça isabet artıyor (N≥5 en iyi) | 1 günlükte **tersi**: şart eklemek sonucu bozuyor (ablasyon bölüm 6.3) |
| `donus_tarayici.pyw`: MACD hunisi "D = geç kaldık" VETO | Bu çalışma aynı şeyi başka yoldan buluyor: StochRSI **kesişimi** bir "geç kaldık" işareti (başlangıçlarda 0.18x) |

---

## 11. Üretilen dosyalar

```
2026-10-01_gunluk-stochrsi-kesisim/
  BULGULAR.md                      bu dosya
  araclar/
    evren.py                       evren kurucu (metadata filtreleri)
    indir.py                       1 günlük kline indirici (API + S3 arşiv)
    gosterge1g.py                  gösterge kütüphanesi (NaN-güvenli SMA DÜZELTMESİ)
    test_gosterge.py               referansa karşı doğrulama (8/8)
    tablo.py                       ana tablo + 30 günlük yol profili
    olc.py                         ölçüm motoru, tabanlar, gün bazlı t
    kural_kullanici.py             kullanıcının kuralı + belirsizlik varyantları
    kontrol.py                     aynı-gün kontrol + ablasyon + yıl yıl
    geriye.py                      ters yön (taban-oran yanılgısı) + imza
    kesif.py                       dip havuzunda 73 kesimlik özellik taraması
    formasyon.py                   15 formasyon, eşikleri dondurur
    dogrula.py                     dondurulmuş eşiklerle tek koşu doğrulama
    kisa_ufuk.py                   1-3-5-10 gün ufuk kontrolü
    net.py                         komisyon sonrası işlem başı dağılım
    guncel.py                      güncel izleme listesi üretici
  veri/
    evren_1g.json                  evren + elenen her sembol sebebiyle
    gunluk_1d.pkl                  593 parite × günlük bar (59 MB)
    tablo_1g.npz                   789.011 bar × 45 özellik + yol profili (140 MB)
  sonuclar/
    test_gosterge_cikti.txt        gösterge doğrulaması
    01_kesif_varyantlar.txt        18 belirsizlik varyantı
    02_kontrol.txt                 aynı-gün kontrol, ablasyon, yıl yıl
    03_geriye.txt                  taban-oran yanılgısı + imza tabloları
    04_kesif.txt                   73 kesimlik özellik taraması
    05_formasyon_kesif.txt         15 formasyon, keşif
    06_dogrulama.txt               dondurulmuş eşiklerle doğrulama
    08_kisa_ufuk.txt               kısa ufuk kontrolü
    09_net.txt                     komisyon sonrası
    guncel_izleme_20261001.json    İLERİYE DÖNÜK izleme listesi
    *.json                         makine okunur çıktılar
```

---

## 12. İleriye dönük izleme listesi (hindsight YOK)

`sonuclar/guncel_izleme_20261001.json` — 30.09.2026 kapanışına göre, likit evren.
**Sonuç YOK** (30 günlük ufuk dolmadı). **Tavsiye değil.**

| kurulum | son gün sinyali |
|---|---|
| A1 kullanıcı tam kural | 2 (COTI, SOPH) |
| **A3 (düzeltilmiş)** | **0** |
| B2 dip + derin değer | 0 (son 7 günde 7) |
| B5 dip + ADX↑ + PDI↑ | 5 (XRP, LSK, ONE, SAGA, G) |

A3'ün bugün sinyal vermemesi beklenen davranış: `RSI≤40 + StochRSI<15 + W%R
oversold` birlikteliği seyrek. Keşif döneminde ayda ~250 sinyal (593 parite
üzerinden), yani parite başına yılda ~5.

---

## 13. Sınırlar ve açık sorular

1. **Aynı-gün kontrolü hiçbir kurulumda pozitif değil.** 1 günlük ızgarada
   "aynı gün hangi coin" sorusuna cevap bulunamadı. Bu, bu projede üçüncü kez
   aynı duvara çarpmak demek.
2. **A3'ün avantajı zamanlamada.** Gerçek bir sistem için "hangi gün alınır"
   kısmı var, "hangi coin" kısmı YOK. Tek pozisyon kuralıyla (kullanıcının
   kısıtı) bu ciddi bir eksik — 2026-09-15 dip-tarama çalışmasının aynı tıkanıklığı.
3. **Çıkış kuralı test edilmedi.** Tüm sayılar sabit süre tutma (5/10/20/30 gün),
   stop yok. Stop/trailing/hedef eklenmesi ölçülmedi.
4. **2025-2026 rejimi her şeyi negatife çekiyor** (taban 5 günlük net medyan
   −%2.35). A3 bu rejimde tabanı 1.8 puan geçiyor ama hâlâ kaybediyor.
5. **Eski `gosterge.py` ısınma hatası** bu depodaki üç önceki çalışmayı
   etkilemiş olabilir — gözden geçirilmeli (ayrı iş).
6. **Hacim verisi 2021-2022 arşivinde eksik** olabilir (önceki çalışmanın notu);
   `hacim_oran`/`taker_oran` o dönemde zayıf olabilir. 1d API verisinde hacim var.
7. **73 + 60 = 133 test yapıldı.** B2 ve A3 dışındaki her şey aday bile değil.
   A3 iki dönemde doğrulandı; B2 üç dönemde yön tutuyor. Gerisi gürültü kabul edilmeli.

---

## 14. Hipotez hükmü

| hipotez | hüküm |
|---|---|
| Kullanıcının kuralı (yazıldığı haliyle) yükseliş başlangıcını işaretler | **REDDEDİLDİ** (3 dönem, 2 evren, 3 taban, 4 ölçüt) |
| Yükselişlerin başında StochRSI<15 / W%R oversold / MACD<0 vardır | **DESTEKLENDİ** (1.8–2.7x, 3 dönemde aynı) |
| `RSI > 40` şartı doğrudur | **REDDEDİLDİ** — tersi (`RSI ≤ 40`) doğru |
| `StochRSI kesişimi` şartı değer katar | **REDDEDİLDİ** — zararlı (başlangıçlarda 0.18x) |
| `MACD < 0.05` şartı değer katar | **REDDEDİLDİ** — etkisi ~sıfır, ayrıca ölçek-bağımlı |
| Düzeltilmiş kurulum (A3) kısa ufukta tabanı geçer | **DESTEKLENDİ** (2 bağımsız doğrulama dönemi) |
| 1 günlükte aynı-gün coin seçimi yapan bir formasyon vardır | **BULUNAMADI** (15 formasyon, 73 kesim) |
| Dip olmak yükselme olasılığını artırır (1 günlük) | **REDDEDİLDİ** (dip %34.4 vs rastgele %36.2) |

---

## 15. LLM Wiki

**Wiki bu ortamda ERİŞİLEBİLİR DEĞİL** (GitHub/cloud konteyneri; `D:\EĞİTİM
SETİ\KRİPTO\_0_0_Kripto-Wiki` yerel bir Windows yolu). Wiki güncellenmedi.

Wiki'ye taşınmaya değer, kalıcı bulgular:
1. **`gosterge.py` ısınma hatası** — `nan_to_num`'lu SMA, StochRSI'de her
   sembolün ilk ~26 barında sahte "<15" üretiyor. Metodoloji bulgusu, yeniden
   kullanılabilir düzeltme (`gosterge1g._sma`).
2. **Tokenize hisse tespiti** — `TRD_GRP_261` izin grubu. "BUSDT ile bitiyor"
   substring testi ARB/BNB/SHIB/QNT/DGB/TRB'yi siler. Evren kuralı bulgusu.
3. **StochRSI kesişimi bir "geç kaldık" işaretidir** — yükseliş başlangıçlarında
   taban-orandan DAHA SEYREK (0.18x). 1h ızgaradaki eski bulgunun 1 günlükte
   bağımsız tekrarı.
4. **1 günlükte dip olmak avantaj değil** (%34.4 vs %36.2).
5. **A3 kurulumu** — kullanıcının fikrinin düzeltilmiş hali, 2 dönemde doğrulandı.
6. **Taban-oran yanılgısı şablonu** — `P(şart|sonuç)` ile `P(sonuç|şart)` ayrımı;
   grafik üzerinden elle bulunan her kurulum için uygulanacak standart kontrol.
7. 2026-09-22'de reddedilen "derin değer" ekseniyle B2 arasındaki **çelişki**.

---

## 16. Üretim / Anton

- **Üretime hazır değil.** Hiçbir sonuç canlı sisteme bağlanabilir seviyede değil.
- **Anton için not:** "grafikten elle okunan kurulumu ters yönde doğrulama"
  (bölüm 7) yeniden kullanılabilir bir denetim yöntemidir — Anton'a eklenmesi
  ayrı bir iş olarak değerlendirilebilir. Bu çalışmadan otomatik aktarım YAPILMADI.
- Otomatik emir, borsa anahtarı, Render/portfolio_tracker değişikliği **yok**.
- Workflow/otomasyon **oluşturulmadı**.
- Başka ajanın (`gpt/`) ve kullanıcının dosyalarına **dokunulmadı**.
