# ON KAYIT — Jev golge modu, 6 coin (2026-09-29, VERI GORULMEDEN YAZILDI)

Bu dosya ilk canli cagridan ONCE yazildi. Asagidaki hicbir sey sonuc gorulduktan
sonra degistirilmez. Degistirilirse olcum sayaci SIFIRLANIR ve yeni pencere acilir.

## Evren

Kural: her sektorde piyasa degerine gore ilk coin; Binance 24s hacmi >= 40M$;
bir coin tek sektorde. Kaynak: Binance urun etiketleri, 2026-09-29.

| sektor | coin | not |
|---|---|---|
| layer 1 | ETH | |
| privacy | ZEC | Binance'te "privacy" etiketi yok; sektor lideri XMR Binance'te listeli degil |
| AI | TAO | AI #1 LINK, DeFi'ye gitti (bir coin tek sektor) |
| meme | DOGE | |
| DeFi / oracle | LINK | DeFi #1 HYPE hacim sartini gecemedi (25M$) |
| real world assets | AVAX | RWA #1 LINK zaten kullanildi |

Referans (soru degil, piyasa havasi icin): BTC.

## Ritim

- Her **15 dakikalik mum kapanisinda** 1 tur (sadece kapanmis mumlar).
- **Olay tetikleyici:** bir coin son 5 dakikada >= %2 oynarsa ara tur.
- Stop / trailing: kodda, her dakika, Jev'siz (portfolio_tracker zaten yapiyor).

## Model ve maliyet

- Model `jev-1.13.0` (sabit; alias kullanilmaz).
- Tur: 87 soru (6 x 14 coin sorusu + 3 piyasa sorusu), kuru kosu tahmini ~9.500 token.
- Tahmini maliyet: ~0,0004$/tur, ~0,04$/gun, **~1,15$/ay**.
- Tavan: tur basina 0,01$ ve 2 cagri. Tahmin > 0,10$ ise onaysiz GONDERILMEZ.
- `billing_error` / 401 / 402 / 403: tekrar deneme YOK. Sadece 429/5xx'te en fazla 3 deneme.

## Sorular

Birebir `jev_golge.py` icindeki metinler gecerlidir (kriter cumleleri dahil).

**ANA SORULAR (hukum yalniz bunlarla verilir):**
1. `entry_quality` — Is this a good moment to open a long position in X for the next 24 hours?
2. `target_before_stop` — Is X more likely to rise about 3% before it falls about 2%?

**KESIF SORULARI (hukum vermez):** chasing, pullback_buy, late_in_move,
trend_aligned, momentum_fading, volume_confirms, support_close,
reward_worth_risk, volatility_hostile, btc_drag, opportunity (score 0-3),
setup_type (choice), market__best_of_six, market__weather, market__risk_off.
Bir kesif sorusu iyi gorunurse "aday" olur; ancak YENI bir 30 gunluk pencerede
tekrar sinanirsa kullanilir.

**Bilincli olarak konmayan kriter:** videodaki "yukseliste araligin tepesinde olmak
tek basina bekleme sebebi degil" cumlesi. Botum'un 2026-09-11 teshisi tersini
olcmustu (scanner'in zarari gerilmis, tepeye yakin girislerden geliyordu).

## Sonuc etiketi

Her tur ve her coin icin, turun kapanis fiyatindan itibaren 24 saat icinde:
**+%3'e -%2'den ONCE degdi mi** (yol farkinda). 1 dakikalik mumla hesaplanir;
ayni 1 dakikalik mumda ikisine de degen durumlar "once stop" sayilir ve sayisi raporlanir.

## Olcum

- **Ornek birimi:** coin-gun. Her coin icin her gun 00:00 UTC sonrasi ILK tur
  (15 dakikalik ardisik turlar birbirine cok benzer; bagimsiz sayilmaz).
- **Ilk degerlendirme:** 30 gun sonra (~180 coin-gun), TEK kosu.
- **Olcut:** ana iki sorunun olasiligi ile sonuc etiketi arasinda AUC.
- **Esik:** AUC >= 0,60 **ve** gun-blok permutasyonu (gunler butun halinde
  karistirilir; coinler BTC ile birlikte hareket ettigi icin) p <= 0,05.
- **Teyit:** sonraki 30 gunde ayni test, esikler ayni.
- Iki ana sorudan biri iki pencerede de gecerse: "Jev bu evrende bilgi tasiyor".
  Gecmezse golge modu kapatilir, canliya BAGLANMAZ.

## KONTROL GRUBU — bedava kod kurali (2026-09-29, Jev'den ONCE donduruldu)

Soru "Jev bilgi tasiyor mu" degil, **"Jev, AYNI bilgiyle basit bir kod kuralindan
daha iyi mi"**. Jev gozlemcinin cumlelerinden fazlasini bilemez; kural ayni olculeri
(ayni kova esiklerini) gorur. Kod: `jev_golge.py -> kontrol_skoru()`.

Kural VERIYE BAKILMADAN kuruldu. Bes bilesen, her biri 0 / 0.5 / 1, esit agirlik:

| bilesen | 1 | 0.5 | 0 | dayanak |
|---|---|---|---|---|
| trend | gunluk ve 4s yukari (ortalama) | | asagi | trend uyumu |
| not_stretched | 4s EMA20'ye uzaklik <= 1.5 ATR | <= 3 ATR | > 3 ATR | 2026-09-11: gerilmis girisler zararli |
| not_overheated | RSI1s < 70 ve StochRSI4s < 80 | biri | ikisi de | 2026-09-11: StochRSI 73-85'ten giris |
| support_close | destek < %2 | < %5 | >= %5 | dip_tarama: yakin destek kaybi kucultur |
| momentum_turning | RSI1s son 3 saatte > +2 | arada | < -2 | |

`skor` = bes bilesenin ortalamasi (0-1). `buy` = skor >= 0.70.

### Karsilastirma testi (ana hukum)

Ayni coin-gun orneklerinde, ayni sonuc etiketiyle:
- **Jev katki saglar** = AUC(Jev `entry_quality`) - AUC(kontrol `skor`) > 0 ve bu farkin
  gun-blok bootstrap %95 guven araligi 0'i DISLAR — **iki pencerede de**.
- Aynisi `target_before_stop` icin ayrica raporlanir.
- Uc sonuc mumkun: (a) Jev kurali gecer -> Jev degerli; (b) ikisi de ayni -> bedava
  kural yeter, Jev'e para odenmez; (c) ikisi de AUC 0.5 civari -> bu olculer bu evrende
  bilgi tasimiyor.

Kontrol kurali Jev acilmadan da calisir ve kaydedilir; kredi gelene kadar biriken
kontrol verisi SADECE kontrol icin kullanilir, Jev'li donemle havuzlanmaz.

## Yasaklar

- Jev ile gecmis veri uzerinde backtest yok (egitim verisi sizintisi).
- Sonuca bakip soru, kriter cumlesi, kova esigi veya evren degistirmek yok.
- Canli sisteme (scanner / portfolio_tracker kararlari) baglanti yok — sadece kayit.
