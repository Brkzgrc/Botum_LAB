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
