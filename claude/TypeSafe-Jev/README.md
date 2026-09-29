# TypeSafe Jev — golge modu yargic

Claude'un calisma alani (2026-09-29). Kural: sadece bu klasore yazilir, digerleri okunur.
**Public depo — API anahtari buraya ASLA girmez.** Anahtar Claude cloud ortaminin
"API credentials" bolumunde (host `api.typesafe.ai`), Render'da env degiskeni olarak durur.

## Jev nedir (dokumandan, 2026-09-29'da okundu)

TypeSafe AI'in "System One" modeli, 2026-09-15'te erken erisimle cikti. Metin uretmez;
bir `state` ve tipli sorular alir, olasilik doner. Tum sorular tek istekte, paralel.

| soru tipi | doner |
|---|---|
| Noul | P(evet), 0-1 |
| Choice | secilen secenek + her secenegin olasiligi + guven |
| Score | siralı olcekte puan + olasiliklar + guven |

- Fiyat: $0.042 / milyon GIRDI tokeni, cikti ucretsiz. Gecikme 70-500 ms.
- Baglam: 64k token (state + tum sorular); 32k (state + en uzun soru). Sadece metin.
- Surum: `jev-1.13.0`. `jev-latest` alias'i kayabilir -> OLCUMDE SURUM SABITLENIR.

### Dokumanin kendi soyledigi zayifliklar (jev-1.13 jaggedness)
- Sayi / aritmetik / sayma / sayisal yakinlik: guvenilmez -> **hesap kodda kalir**,
  Jev'e kova ve cumle gider ("RSI orta bolgede, yukseliyor"; `RSI=48.57` DEGIL).
- Tarih karsilastirma: guvenilmez -> kodda.
- Kelimesi kelimesine okur -> sorular kesin yazilir.
- Ingilizce birincil dil -> state ve sorular INGILIZCE.

### Kalibrasyon iddiasina dair uyari
Sirketin degerlendirmelerinde referans cevap = buyuk LLM'lerin (GPT-6 Astra, Fable 5.1)
ortalamasi; gorevler saglduyu tipi (siniflandirma, yonlendirme). Yani "kalibre" =
buyuk modellerle uyum, piyasa sonucu degil. "Bu coin 24 saatte +%3 gorur mu" saglduyu
sorusu degil; iyi kalibre model muhtemelen 0.5 civari der. Deger ancak OLCULEREK gorulur.
"Halusinasyon yapamaz" = tip hatasi yapamaz; cevap YANLIS olabilir.

## Baglanti testi (2026-09-29) — CALISIYOR

`GET /v1/models` ve `POST /v1/systemone` (jev-1.13.0) credential enjeksiyonuyla calisti.
Ornek: 3 soru, 473 token, ~$0.00002.

Gozlem: Jev SADECE state'teki kelimeleri okur. State'e "calm, slightly positive" yazinca
hava sorusuna guven 1.0 ile "sunny" dedi. **Jev gozlemcinin cumlelerinden fazlasini
bilemez.** Scanner ozelliklerinden uretilen cumlelerde Jev'in katkisi = bu ozellikleri
insan-sezgisi gibi tartmak. Bunun deger katip katmadigi ACIK SORUDUR.

## Plan — golge modu (onay bekliyor, kod YAZILMADI)

1. Scanner'in gonderdigi her sinyal (legacy v11 + TSI+BB) icin gozlemci katmani
   ozellikleri Ingilizce cumlelere cevirir (sayilar kodda kovalanir).
2. Jev 5-8 soruya olasilik verir: giris kalitesi, asiri uzama/kovalama, BTC havasi,
   stoptan once hedef gorur mu, vb.
3. Olasiliklar sinyal kaydina SADECE YAZILIR. Alimi engellemez, boyutu degistirmez.
4. 60-100 kapanmis islemden sonra, dokunulmamis veride: Jev olasiligi kazanani
   kaybedenden ayiriyor mu (AUC + kalibrasyon)? Esikler ONCEDEN yazilir.
5. Ayiriyorsa once boyutlandirmaya, sonra kapiya baglanir. Ayirmiyorsa birakilir.

### Neden geriye donuk backtest YOK
Jev'in egitim verisi kesim tarihi bilinmiyor; 2023-2025 fiyat/haberlerini biliyor
olabilir (ileriye bakma sizintisi). Tek gecerli test ileriye donuk golge modu.

## Iliskili bulgu (GITHUB_CONTROL_LEGACY)
TSI+BB arastirmasi net24'u "al, 24 saat sonra sat, STOPSUZ" olcuyor; canli sistem stop +
TP1 + ATR trailing kullaniyor. `danger_dn2_first` pre-2026 capraz holdout'ta %56.
Jev'in "stoptan once hedef gorur mu" sorusu tam bu boslugu hedefler.
