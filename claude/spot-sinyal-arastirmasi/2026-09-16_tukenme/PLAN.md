# TUKENME ARASTIRMASI — yukselis ne zaman biter?

## Soru

Girisi bulmak yetmiyor. "5 islemin 4'u -%30, 1'i +%78" tablosunda kayip
CIKIS tarafinda. Soru: **bir yukselis suruyorken, bittigini onceden
haber veren bir HAREKET var mi?**

Bugune kadar bu projede yapilan her sey GIRISE bakiyordu. Cikis tarafi
sadece parametre taramasiydi (ATR carpani 0.6/1.0/2.0...) — yani sabit
deger. Yukselisin kendisi hic incelenmedi.

## Temel ilke: HAREKET, deger degil

Hicbir sabit esik kullanilmaz. "RSI 70'in ustunde" gibi bir sey YOK.
Her olcum, serinin KENDI gecmisine gore ifade edilir:

| olcum | tanim |
|---|---|
| hiz | degisim / son 20 barin ortalama mutlak degisimi |
| ivme | hizin degisimi |
| ardisiklik | kac bar ust uste ayni yonde |
| egim | n barlik egim / kendi oynakligi |
| makas | hizli-yavas farki, ve makas ACILIYOR mu DARALIYOR mu |
| zirveden dusus | bolum icindeki tepesinden % kac geri gelmis |

Esikler veriye sorulur (kendi ondalik dilimleri), disaridan verilmez.

## Bolum (episode) tanimi — mekanik, geriye bakis yok

1. 1 saatlik izgarada yerel dip bulunur
2. Dipten +%15'e ULASAN ve bunu -%7.5'e inmeden ONCE yapan hareketler
   "yukselis bolumu" sayilir (yol-farkinda)
3. Bolumun TEPESI = geri cekilme baslamadan onceki en yuksek nokta

## Kontrol — en kritik kisim

Ayni bolumun ICINDEN iki grup:

- **BITIYOR**: tepeye K bar veya daha az kalmis anlar
- **SURUYOR**: tepeye K bardan fazla olan anlar

Ayni coin, ayni bolum, ayni piyasa. Tek fark: zaman.
Bu, "farkli rejim" karistiricisini ortadan kaldirir — projede daha once
tam bu yuzden uc ayri sahte bulgu cikmisti.

## Olculecek seriler (hepsi 1h, baglam icin 4h)

fiyat · RSI14 · MACD dif/dea/hist · StochRSI K/D · KDJ K/D/J · W%R ·
EMA20/EMA50 · ATR · hacim · quote_volume · islem sayisi ·
taker_quote · **taker orani** · **net para = alici - satici**

Her seriye yukaridaki 6 hareket donusumu uygulanir.
Cift seriler (dif/dea, K/D, EMA20/50, net para/ortalamasi) icin ayrica
makas olcumleri. Toplam ~110 olcum.

## Cikti bicimi — istenen bu

Her olcum icin, kontrole karsi:

    "net para girisi bolum zirvesinden %X geri gelince,
     yukselislerin %A'si Y bar icinde tepe yapmis.
     Suren yukselislerde ayni durum %B oraninda gorulmus."

A ile B arasindaki fark anlamliysa o olcum ise yariyor.
Anlamlilik BOLUM bazinda permutasyonla olculur (bar bazinda DEGIL —
ayni bolumun barlari bagimsiz ornek degildir, bu tuzaga projede
daha once dusuldu).

## Yurutme

Tek oturumda bitmez. Bolum bolum kosar, sonucu kaydeder, kaldigi
yerden devam eder. GitHub Actions ile bilgisayar kapaliyken de surer.

## Onceden kabul edilen kural

Arama 2021-2022 + 2023-2024'te. **2025-2026 ve 2019-2020 DOKUNULMAZ**
— dogrulama icin saklanir. Arama doneminde bulunan her olcum,
dokunulmamis iki donemde tek kosuda sinanir.
