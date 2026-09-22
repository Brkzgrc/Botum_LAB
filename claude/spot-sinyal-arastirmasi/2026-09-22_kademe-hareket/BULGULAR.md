# 4h→1h→15m Kademe Hipotezi — Ölçüm Kaydı (2026-09-22)

## Soru

Kullanıcının gözlemi: BTC 16.09.2026 ve başka örneklerde (DASH, QNT, RENDER
16.09.2026) 4 saatlik grafikte gösterge hareketliliği önce görünüyor, sonra
1 saatlikte, sonra 15 dakikalıkta — büyükten küçüğe sıralı bir "setup"
oluşumu. Soru: bu ölçülebilir bir sıralama mı, ve alım için kullanılabilir mi?

## 1. Dört örnek tek tek incelendi (kor değil, elle seçilmiş)

BTC 16-17.08.2026, DASH 16.09.2026, QNT 16.09.2026, RENDER 16.09.2026 —
4h/1h/15m mumları tek tek basılıp donus.py'nin 6 şartı (macd/rsi/kdj/wr/
stochrsi/obv) her mumda işaretlendi.

**Üç örnekte (BTC, DASH, RENDER):** gerçek dip 15m'de oluştu, 4h'nin kendi
dönüş şartı ancak dip mumu kapandıktan SAATLER SONRA (bir sonraki 4h mumunda)
ateşledi — yani 4h "geriden" geliyordu, önden değil.

**QNT'de:** 4h gerçekten erken ateşledi (14:59) ama fiyat ondan sonra %2.1
daha düştü; asıl dip yine 15m'de (17:29) oluştu. 4h'nin KENDİ dönüş teyidi
ancak ertesi gün geldi — hareket bitmişti.

**Sonuç: dört örnekte de dibi işaretleyen hep 15m. 4h'nin erken ateşlemesi
(QNT) dibi değil, dibe giden yolu işaretliyor.**

## 2. Sistemli ölçüm — sıralı teyit (4h sinyal → 1h teyit → 15m teyit)

`sistem.py` + `kos2.py`, 2021-2022, 150 coin, N≥2 şart, dip=bağlam(3 bar
içinde)+dönüş=tetik ayrımıyla: 44.907 ham 4h sinyali.

| kol | işlem | +10/-5 | +20/-10 | +30/-15 |
|---|---|---|---|---|
| sadece 4h | 44.907 | %37.7 | %38.3 | %37.9 |
| 4h+1h teyidi | 12.899 (%29) | %37.7 | %36.5 | %35.4 |
| 4h+1h+15m (tam) | 11.544 (%26) | %37.4 | %36.1 | %35.0 |

**Her teyit kademesi işlem sayısını kırpıyor, isabeti YÜKSELTMİYOR — düşürüyor.**
4h sinyallerinin sadece %29'u 1h teyidi alıyor; elenen %71 kalan %29'dan kötü
değil. "4h sinyal verir, küçük TF'ler teyit eder" modeli ÇALIŞMIYOR.

**Not — metodoloji düzeltmesi:** ilk koşu, her sinyalde 22.000 barlık
göstergeyi baştan hesaplıyordu (5 saat sürüp bitmedi). `_teyit()` artık
önceden hesaplanmış `say` dizisini kullanıyor. Ayrıca 2021-2022 arşivinde
hacim yok — `v=None` verilip OBV o dönemde hiç kullanılmadı (sahte hacim
uydurmak 6. şartı sahte üretirdi).

## 3. Kullanıcı itirazı: "dip işaretlemeden çok gösterge hareketi önemli"

Dip şartı (son N barın en dibi) tamamen kaldırıldı. Sadece "kaç gösterge
BİRDEN dönüyor" ölçüldü, taban (aynı dönemde rastgele bar) yanına kondu.

`hareket.py` + `kos3.py`, 2021-2022, 150 coin, +20/-10 hedefi:

| kaç şart | 15m | 1h | **4h** |
|---|---|---|---|
| taban | %38.5 | %38.5 | %38.7 |
| ≥2 | %38.7 | %38.1 | %38.6 |
| ≥3 | %38.6 | %38.3 | %39.1 |
| ≥4 | %38.5 | %38.5 | **%41.1** |
| **≥5** | %38.3 | %37.9 | **%44.2** |

**15m ve 1h'de gösterge şartı sayısının hiçbir değeri yok — taban neyse o.**
Değer SADECE 4h'de var ve monoton artıyor. Yani 4h dip/tetik olarak değil,
**bağlam/filtre** olarak işe yarıyor. 15m dibi iyi buluyor ama kendi
göstergeleri hiçbir şey söylemiyor.

## 4. Kullanıcı itirazı: isabet oranı değil BÜYÜKLÜK ölçülmeli

"5 işlemin 4'ü -%30 olsa da 1'i +%78 ise bu başarısızlık değildir." Ayrıca:
stop varsayımı olan ölçüm, "önce düşüp sonra asıl yükselişe geçen" işlemleri
göstermeden eliyor.

Yeni ölçüm: STOP YOK, SABİT PENCERE YOK. Her 4h sinyalinin sonraki 28 günlük
YOLUNUN TAMAMI (tepe büyüklüğü, tepeye kaç bar sonra ulaşıldığı, tepeden önce
en kötü çekilme, en dip) kaydedildi — çıkış kuralı SONRADAN bu tablodan
seçilecek, tahminle değil.

`topla.py`/`topla2.py`, N≥4 şart, 2021-2022, 150→353 coin: **25.538 sinyal**.

**Taban (tüm sinyaller):**
- medyan tepe yükseliş %25.1 · +%20'ye ulaşan %57.4 · +%50 %26.6 · +%100 %10.1
- KAYIP: -%10 gören %71.3 · -%20 gören %48.8
- "temiz yükseliş" (+%20'ye, önce -%10 görmeden): %36.2
- tepeye ulaşma süresi: medyan 64 bar (256 saat)

**43 yeni ölçü** (kullanıcının 6 göstergesi DIŞINDA — ATR%, ADX/DMI, EMA
yapısı, Bollinger, Donchian/kanal konumu, ROC, CCI, Aroon, Vortex, mum
geometrisi, trend düzgünlüğü, oynaklık rejimi) her birinin kendi üst/alt
%20'lik diliminde test edildi:

En iyi ayıranlar (temiz yükseliş oranı, taban %36.2):
| ölçü | dilim | temiz | -%10 gören |
|---|---|---|---|
| ema50-200 farkı | alt %20 | %44.1 | %73.4 |
| ema200 uzaklık | alt %20 | %43.2 | %73.5 |
| 100-bar zirveden uzaklık | alt %20 | %42.6 | %74.4 |
| ADX | üst %20 | %38.8 | %66.5 |

**Oynaklık ekseni (ATR%, bb_genişlik, bar_genişlik, dip_uzaklık) hem kazancı
hem kaybı BİRLİKTE büyütüyor** — birini azaltmadan diğerini azaltmıyor.
**ADX ayrı bir eksen:** hem temizi artırıyor hem kaybı kesiyor.

**DİKKAT — bu ADAY listesi, henüz DOĞRULANMADI.** 43 ölçü × 2 uç = 86 test;
CLAUDE.md kuralı gereği hüküm dokunulmamış dönemde (2023-2024, 2025-2026)
tek koşuda verilecek.

## 5. Kullanıcı fikri: göstergeler arası AYRIŞMA

"Bazı göstergeler yükselirken biri düşüş başlatıyorsa kayba yol açıyor
olabilir." `ayrisma.py` — her göstergenin (rsi/stochrsi/macd/kdj/wr/obv)
kendi yönü (1 ve 3 bar) ayrı çıkarıldı.

| durum | n | medyan tepe | -%10 gören | temiz |
|---|---|---|---|---|
| taban | 25.538 | %25.1 | %71.3 | %36.2 |
| hepsi yukarı | 24.050 | %25.3 | %71.1 | %36.4 |
| **biri aşağı dönmüş** | 1.488 | %22.2 | %75.3 | %32.8 |
| **StochRSI aşağı dönmüşken** | 755 | **%19.1** | %75.6 | %31.5 |

**Yön doğru — ayrışma varken sonuç her ölçütte kötüleşiyor.** Ama seyrek
(sinyallerin %5.8'i), toplam etkisi küçük (taban %36.2→%36.4).

Ayrıca N≥5 şart, N≥4'ten belirgin iyi: medyan tepe %24.4→%27.7, temiz
%35.4→%38.6.

## 6. Piyasa bağlamı (GPT/Multi-Timeframe çalışmasından esinle)

`Botum_LAB/gpt/Multi-Timeframe-Independent-Evidence` incelendi — o sistemin
3 dondurulmuş kuralının (C02/C09/C12) ÜÇÜ DE coin'in kendi göstergesine değil
BTC durumuna ve piyasa genişliğine bakıyor. Kendi 43 ölçümün TAMAMI coin'in
kendi içindendi — bu eksiklik `piyasa.py` ile kapatıldı: BTC getiri/EMA
uzaklığı/RSI + piyasa genişliği (353 coinin kaçı yükseliyor) 4h ızgarasında
hesaplanıp sinyal tablosuna eklendi (77 ölçüye çıktı, `tablo2_2021-2022_N4.npz`).
Analiz henüz yapılmadı — sıradaki adım.

## Kullanılan disiplin (CLAUDE.md kural 1-7 ile uyumlu)

- Taban (rastgele bar / hepsi-yukarı durumu) HER ölçümde yanında duruyor.
- 2021-2022 KEŞİF dönemi; 2023-2024 ve 2025-2026 DOKUNULMADI, doğrulama
  oradan tek koşuda yapılacak.
- Stop/hedef varsayımı olmayan "yol profili" ölçümü, isabet yerine BÜYÜKLÜK
  ve zaman kullanıyor (kullanıcı talebi: kazanma oranı > önem sırası değil).
- 43+15 = 58 yeni ölçünün ~86 testten adayı çıktı — henüz KANIT değil.

## Sıradaki adım

1. Piyasa bağlamlı tabloyu (`tablo2_2021-2022_N4.npz`) analiz et.
2. Aday listesini (ayrı ayrı + kombinasyon) 2023-2024 ve 2025-2026'da TEK
   KOŞUDA doğrula — eşik/özellik DEĞİŞTİRİLMEDEN.
3. Ayrışma ölçüsünü (StochRSI ters yön) filtre olarak deneyip beklenen
   getiriye etkisini gör.

## 7. Piyasa bağlamlı tablo analizi — SONUÇ

`tablo2_2021-2022_N4.npz` (77 ölçü: 43 coin-içi + 6 ayrışma + 15 piyasa
bağlamı + sart_sayisi). En iyi tekil ölçüler taban %36.2 (temiz yükseliş):

| ölçü | dilim | temiz | -%10 gören |
|---|---|---|---|
| coin ema50-200 farkı | alt %20 | %44.1 | %73.4 |
| BTC ema200 uzaklığı | alt %20 | %41.3 | %68.3 |
| BTC 7g getiri | alt %20 | %39.8 | %67.3 |
| piyasa genişliği 7g | alt %20 | %39.7 | %67.1 |

**ON KAYIT — ADAY (henüz doğrulanmadı):**

    coin_ema50_200_fark <= [kendi 2021-2022 %20 yuzdeligi]
      VE
    btc_ret_7g          <= [kendi 2021-2022 %20 yuzdeligi]

Kesif verisinde: n=1.727 · medyan tepe %39.0 (taban %25.1) · +%50'ye ulasan
%37.3 (taban %26.6) · -%10 goren %62.1 (taban %71.3) · temiz yukselis %51.0
(taban %36.2).

Icerigi: **coin kendi uzun-donem ortalamasinin altinda VE BTC son 7 gunde
dusmus** — yani "piyasa genelinde geri cekilme sirasinda, kendi trendi de
geri cekilmis coin" ariyor. Sezgisel olarak "herkes korkarken al" fikrine
yakin.

**Esik degistirilmeyecek, ucuncu kosul eklenmeyecek** — 2023-2024 ve
2025-2026'da TEK KOSUDA doğrulanacak.

## 8. GPT/Multi-Timeframe capraz kontrol

`Botum_LAB/gpt/Multi-Timeframe-Independent-Evidence/reports/stage4/
FROZEN_RULES.json` incelendi. O sistemin 3 dondurulmus kuralinin (C02/C09/C12)
UCU DE coin'in kendi gostergesine degil, BTC durumuna ve piyasa genisligine
bakiyor (`btc_ret_24h`, `btc_d1_ema20_uzaklik`, `breadth_ret72_delta72` gibi
alanlar). Bu bagimsiz bulgu, bu calismanin 6. ve 7. bolumlerindeki "piyasa
baglami katki sagliyor" sonucuyla AYNI YONDE — farkli bir ekipten (GPT),
farkli bir metodolojiden (kural madenciligi + rejim modeli) gelen bir
yakinsama. Bagimsiz replikasyon degildir (farkli veri/donem kullanmis
olabilirler, kontrol edilmedi) ama yon tutarliligi kayda deger.

`SPOT_STRATEJI_KURALLARI.txt` (37 video, YouTube egitim ozeti) da incelendi.
Video 6'nin "birlesik islem zinciri" (4H trend baglam -> 1H pullback/momentum
zamanlamasi -> 15M fiyat tetikleyicisi) bu calismanin 3. bolumdeki sonucla
(4h SIRALI TETIKLEYICI olarak islemiyor, ama BAGLAM/FILTRE olarak isliyor)
AYNI AYRIMI yapiyor. Ayrica 6.D.9 uyarisi (RSI/StochRSI/Stochastic bagimsiz
kanit sayilmamali) bu calismanin 5. bolumdeki ayrisma olcumune dogrudan
ilgili — henuz test edilmedi, sonraki adim.

## Sıradaki adım (güncellendi)

1. Piyasa-bağlamlı aday kuralı (bölüm 7) 2023-2024 ve 2025-2026'da tek
   koşuda doğrula.
2. RSI/StochRSI/Stochastic'in ne kadar bağımsız bilgi taşıdığını ölç
   (korelasyon + tekini çıkarınca sonuç değişiyor mu).
3. Ayrışma ölçüsünü (StochRSI ters yön) piyasa-bağlamlı aday kuralla
   birlikte dene.

## 9. Kullanıcının 3 canlı sistemi incelendi

`kullanici_sistemleri/` altına eklendi: `donus_tarayici.pyw` (huni/funnel
sistemi, ölçülmüş), `crypto_scanner_pullback.pyw` ve
`crypto_app2_role_based_v2.pyw` (rol-dağılımlı 4h/1h/15m puanlama), artı
üç JSON anlık görüntü.

### donus_tarayici.pyw — huni tasarımı bu çalışmanın 3. bölümünü doğrudan
doğruluyor

Sistem 4h/1h/15m'yi SIRALI TETİKLEYİCİ değil, **huni/elemedir**: 1G ve 4S
uygun değilse alt zaman dilimlerine hiç bakılmaz (elenir), 1S'te dönüş
aranır, **15m hiçbir zaman sıralama skoruna girmez** (`TF_AGIRLIK["15m"]=0.0`)
— sadece "giriş penceresi açık mı" kapısı. Bu, bu çalışmanın 3. bölümünde
ölçülen "4h bağlam olarak işliyor, sıralı tetikleyici olarak işlemiyor"
sonucuyla BİREBİR aynı yapıyı, bağımsız bir tasarımda gösteriyor.

### İki yeni, ölçülmüş eksen (önceden hiç test edilmemiş)

**a) Hız kapısı (24s ROC, MONOTON DEĞİL):** kaçmış (>%50, 24s): tipik -%9.4,
kazanan %42, risk 5x. Geç kalınmış (%25-50): -%2.8, risk 3x. **%10-25 "en
verimli bölge"** (pozitif puan). <%10: nötr.

Kendi 25.538 sinyallik tabloda test edildi (`roc6` = gerçek 6x4h=24 saat —
İLK DENEMEDE `roc24` (96 saat) kullanılmıştı, YANLIŞ BİRİM, düzeltildi):

| bant | n | medyan tepe | +%10 gören | temiz |
|---|---|---|---|---|
| taban | 25.538 | %25.1 | %71.3 | %36.2 |
| <10 (yavaş) | 25.404 | %25.1 | %71.2 | %36.2 |
| 10-25 (iddia: verimli) | 120 | %26.5 | %89.2 | %25.0 |

**Kendi 4h ızgaramda doğrulanamadı** — n=120 çok küçük (orijinal sistem 1h
ızgarada ölçmüş, benimki 4h; 4h barında 24 saatlik hızlı hareket nadir
görülüyor). Yön belirsiz, örnek yetersiz. Doğru test 1h ızgarada yapılmalı.

**b) RS_ESIK — coin BTC'den ZAYIF olmalı (ters sezgi):** "coin 24s getirisi
− BTC 24s getirisi ≤ 0" filtresiyle filtresiz +%0.56/işlem'den +%3.20/işlem'e
çıkmış (78 coin/489 gün ölçümü, kayıtlı).

Kendi tabloda test edildi (roc6 - btc_ret_24s):

| | n | medyan tepe | −%10 gören | temiz |
|---|---|---|---|---|
| RS≤0 (zayıf, iddia) | 17.530 | %26.0 | %71.7 | **%37.1** |
| RS>0 (güçlü) | 8.008 | %23.0 | %70.4 | %34.2 |

**Yön doğrulandı** — küçük ama tutarlı, bağımsız ölçümle aynı taraf.

### Üçüncü kanıt: skor_hacim'deki hacim/hız birleşik bulgusu

87 coin / 183 bin saatlik veri: hacimsiz osilatör kurulumu RASTGELEDEN
KÖTÜ (+%20 olasılığı %1.2, taban %2.2); hacim ≥5× ile %11.2'ye çıkıyor.
AMA coin 7 günde %30+ yükselmişken hacim patlarsa bu "spike & fade"
(medyan -%1.2); coin düşüşten geliyorken hacim patlarsa %56 kazanan,
yarı risk. **Hacim tek başına değil, ÖNCEKİ HAREKETLE BİRLİKTE** anlamlı —
bu çalışmanın 5. bölümündeki "göstergeler tek başına değil birlikte"
bulgusuyla aynı disiplin, farklı bir örnekte.

### Gerçek ileriye dönük (forward) set — hindsight yok

`donus_tarayici_izleme_20260922.json`: 21.09.2026 14:31'de kaydedilmiş 25
sinyal, 22.09.2026 11:02 itibarıyla ~21 saatlik takip. ÇOK ERKEN, hüküm
verilemez. Anlık durum: 23/25 "C — 1S dönüş bekle", 2/25 "B — 15D teyit
bekle". En büyük hareket TAO +%10.8, tek belirgin kayıp ZAMA -%9.6.

`portfolio_role_based_20260922.json` (17 kayıt) ve
`portfolio_pullback_20260922.json` (3 kayıt): sadece giriş fiyatı var,
çıkış/sonuç henüz yok — ileride bu dosyalar büyüdükçe gerçek forward-test
verisi olarak kullanılabilir.

## Sıradaki adım (güncellendi)

1. Hız kapısını (24s ROC, monoton olmayan bant) 1h ızgarada, kullanıcının
   `_vek_donus_sayisi` (5 şartlı, OBV'siz) tanımıyla yeniden test et — 4h
   ızgara bu ekseni ölçmek için yanlış çözünürlük.
2. Piyasa-bağlamlı aday kuralı (bölüm 7) + RS_ESIK yönünü BİRLEŞTİRİP
   2023-2024/2025-2026'da tek koşuda doğrula.
3. `donus_tarayici_izleme.json`'ı birkaç gün arayla tekrar iste, forward
   setin büyümesini bekle.

## 10. İki adayın doğrulaması — İKİSİ DE REDDEDİLDİ

Dondurulmuş eşiklerle (değiştirilmedi) 2023-2024 ve 2025-2026'da tek koşu:

### Piyasa-bağlamlı aday (bölüm 7)

| dönem | taban -%10gör | aday -%10gör | yön |
|---|---|---|---|
| 2021-2022 (keşif) | %71.3 | %62.1 | kayıp azalıyor |
| 2023-2024 | %63.6 | %45.3 | kayıp azalıyor (güçlü) |
| **2025-2026** | %70.3 | **%79.7** | **kayıp ARTIYOR — ters yön** |

### Ayrışma adayı (bölüm 5)

| dönem | kabul (ayrışma yok) -%10gör | red (ayrışma var) -%10gör | fark |
|---|---|---|---|
| 2021-2022 (keşif) | %71.1 | %75.4 | gerçek (4.3 puan) |
| 2023-2024 | %63.7 | %62.5 | ters yön, anlamsız |
| 2025-2026 | %70.3 | %71.0 | gürültü (0.7 puan) |

**HÜKÜM: İKİ ADAY DA REDDEDİLDİ.** Piyasa-bağlamlı kural 3 dönemin 2'sinde
kayıp azaltıyor ama en güncel dönemde (2025-2026) TAM TERSİ yapıyor —
CLAUDE.md kural 6 kalıbının bir örneği daha (rejim ayardan baskın). Ayrışma
adayı sadece keşif döneminde gerçekmiş, ikisi de doğrulamada eriyor.

**Bu oturumun kayıp-azaltma sorusuna cevabı: BULUNAMADI.** Mevcut 58 yeni
ölçünün (43 coin-içi + 6 ayrışma + 15 piyasa bağlamı — hepsi 2021-2022
üzerinde arandı) üzerinde daha fazla dönmek sahte-pozitif riski taşıyor
(CLAUDE.md uyarısı: aynı veride tekrar arama artık keşiftir, kanıt değil).

Elde kalan tek GERÇEKTEN kanıtlı kayıp-kontrolü, bu oturumun ürünü değil —
`donus_tarayici.pyw`'nin kendi 78 coin/489 günlük ölçümündeki RS_ESIK ve
hız kapısı. Kayıp azaltma sorusu AÇIK; yeni bir hipotezle, YENİ bir veri
kaynağından (emir defteri, farklı zaman dilimi etkileşimi, ya da doğrudan
donus_tarayici'nin kendi büyüyen forward-set'i) başlanmalı.
