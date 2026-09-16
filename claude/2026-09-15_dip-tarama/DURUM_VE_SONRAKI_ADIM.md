# Durum — 15.09.2026 sonu

## Bugun kesinlesenler

1. **451 islemlik sonuc gercekci degildi.** Gunluk 3 sinyal siniri uygulaninca
   +%1.196 -> +%0.174, medyan +%0.683 -> **-%0.525**, WR %57.4 -> %46.9.
   Kar 4 gunden geliyordu; o gunlerde tarama 44 islem aciyor, canli 3 alabiliyor.

2. **Naif t degeri sahte.** Islem bazinda t=4.60, olay bazinda (24sa = tek an)
   t=1.32; 2025 icin olay bazinda t=0.39. Islemler kumeleniyor.

3. **Panel iki kural surumunu karistiriyor** (snapshot 15.09 12:46, 44 kayit):
   - v1 (%2.5 trail, ofset yok): 35 islem, +%0.40, WR %60
   - v3 (-%3 giris + ATRx2.0): 9 islem, **-%2.14, WR %11**
   Panelin tek rakami (WR %50, net -5.22) bu ikisinin ortalamasi.
   Kullanici panel koduna DOKUNULMAMASINI istedi. Veri kayitlarda duruyor,
   ileride snapshot uzerinden offline ayristirilabilir (bugun oyle yapildi).

## Denenip OLENLER (tekrar deneme)

| hipotez | sonuc |
|---|---|
| BTC durumu (verimlilik orani, 15m/1h/4h/1d) | kural elemesi gerekeni tutuyor; olay bazinda taban +0.276, kural -0.054 |
| Coin sikismasi, sinyal aninda | OLCUM BOZUK: dusus araligi genisletiyor, hicbir coin SIKISIK cikmiyor |
| Coin sikismasi, 24/48/96 saat oncesi | hucreler 10-11 islem, kendi icinde celiskili, desen yok |
| Binance "Sinirli Aralik" urunu | detektor calisiyor ama odeme yapisi yeniyor: %5 risk / ~%3.3 odul -> %60 tutturma gerekiyor; sadece +-%7.5/7gun hucresi (%70.4) geciyor, orada da APR dusuk |

## CALISAN ARAC — sikisma detektoru (araclar/sikisma.py)

BTC'de dogrulandi. Dar aralik + SURE + dusuk hacim ucunu birden yakaliyor:

| durum | hacim orani | 7 gun +-%3.5 bantta kalma |
|---|---|---|
| SIKISIK | 0.66-0.81 | **%21.1** |
| GENIS | 1.24-1.37 | %9.3 |

21 ayin 20'sinde goz karariyla uyusuyor (tek sapma 2026-07).
Esikler BTC'nin KENDI dagiliminin %33 dilimi — islem sonucuna bakmaz.

## Boru hatti dogrulandi

`araclar/sinyal_ani_mumlari.pkl` (447 islem x 15m/1h/4h, sinyal anina kadar
KAPANMIS mumlar). Bagimsiz iki kod ayni sayiyi veriyor:
447 islemin 444'unde gostergeler orijinal taramayla BIREBIR ayni.
Nedensellik ihlali 0.

**Bulunan ve duzeltilen hata:** Binance `endTime` mumun ACILIS zamanina gore
filtreler. Sinyal 12:15'te ise 12:00'de acilan 4h mum (16:00'da kapanacak)
listeye giriyordu -> ileriye bakma. 4h RSI'da medyan -4.71 puan sapma.
Duzeltme: kapanisi sinyal aninda/sonrasinda olan mumlari at.

## SONRAKI ADIM — kullanicinin onerisi, kabul edildi

Arama 2021-2022'de, dogrulama 2023-2024 ve 2025-2026'da.
Gerekce: 2025'e bugun bakildi (BTC + sikisma testleri), artik temiz holdout degil.
2023-2024 hic dokunulmadi.

**Hayatta kalan yanliligi COZULDU:**
`s3-ap-northeast-1.amazonaws.com/data.binance.vision` erisilebilir
(`data.binance.vision` dogrudan 403 veriyor, S3 adresi calisiyor).
Arsivde HIC var olmus 734 USDT paritesi var; **253'u delist olmus**
ve verileri duruyor. Dogrulandi: AKROUSDT, AIONUSDT 2021-06 ve 2022-06
verisi iniyor (720 satir/ay, format dogru).
Liste: `veri/binance_evren_delist_dahil.json`

Aylik dosya boyutlari (parite basina): 15m 168KB · 1h 44KB · 4h 12KB

**Onerilen iki asamali indirme** (hepsini indirmek ~3.2 GB / 43.000 dosya):
1. Once 1h indir (~600 parite x 24 ay x 44KB = ~630 MB), 4h'i 1h'den turet.
   4H+1H kosullariyla aday anlari bul.
2. Sadece aday anlar icin 15m cek (API ile, bugunku `indir.py` gibi).

**Disiplin karari (bozulmayacak):** arama bitip kural YAZILIP KILITLENENE kadar
2023 sonrasina bakilmayacak.
