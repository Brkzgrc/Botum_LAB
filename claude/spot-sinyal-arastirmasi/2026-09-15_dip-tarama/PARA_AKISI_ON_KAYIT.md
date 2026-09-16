# Para Akisi Testi — ON KAYIT (16.09.2026, SONUC GORULMEDEN YAZILDI)

## Neden

Dip taramanin kullandigi alti gosterge de (RSI, StochRSI, KDJ, W%R, MACD)
**yalnizca fiyattan** hesaplaniyor — `gostergeler(h, l, c)`, hacim parametresi yok.
Yani sistem paranin coine girip girmedigini HIC olcmuyor. Bugune kadar denenen
her sey (ofset, ATR, esikler, yakinsama) tek bir bilgi kaynaginin farkli okumasiydi.

Para akisi **hic denenmemis, bagimsiz bir bilgi kaynagi.**

## Olculecek alti ozellik — SABIT, sonradan eklenmeyecek

Hepsi sinyal aninda, SADECE kapanmis barlardan (nedensel):

| # | ad | tanim |
|---|---|---|
| 1 | `1h_taker` | taker_quote / quote_volume, son 3 barin ortalamasi (canli sistemin tanimi) |
| 2 | `4h_taker` | ayni, 4 saatlik |
| 3 | `1h_obv` | (OBV[-1] - OBV[-6]) / son 20 barin ortalama hacmi |
| 4 | `1h_hacim` | bar hacmi / son 20 barin ortalamasi |
| 5 | `1h_mfi` | Money Flow Index (14) |
| 6 | `4h_para_trend` | son 6 barin quote_volume toplami / onceki 6 barin toplami |

## Yontem

- Sinyal uretimi DEGISMEZ — mevcut `dip_tarama.py` sinyalleri aynen kullanilir.
- Her ozellik icin sinyaller o donemin MEDYANINDAN ikiye bolunur.
- Her yari icin ayri para simulasyonu: 10.000$, tek islem, -%3 giris, ATRx0.6,
  komisyon %0.2. Filtresiz taban da ayni tabloda gosterilir.
- **Iki yari da raporlanir** — sadece iyi olan degil.

## Donemler

- **ARAMA:** 2021-2022
- **DOGRULAMA:** 2023-2024 ve 2025-2026 (aramadan sonra tek kosu, ayar yok)

## KARAR KURALI — degismez

Bir ozellik ancak su UC sart birden saglanirsa **KABUL**:

1. Arama doneminde uygun yari, filtresiz tabani geciyor.
2. **Iki dogrulama doneminde de AYNI YON** (ayni yari kazaniyor).
3. Iki dogrulama doneminde de uygun yari filtresiz tabani geciyor.

Aksi halde **RED**. Esik kaydirma, ucuncu bir donem arama, ozellik ekleme YOK.

## Onceden kabul edilen sinirlar

- Alti ozellik test ediliyor; sadece sansla birinin arama doneminde iyi gorunme
  ihtimali yuksek. Iki bagimsiz donemde ayni yonu tutturma sarti bunun icin var.
- Islem sayisi yariya inecek (medyan bolmesi). Az islemli sonuclar gurultulu olur;
  bu KABUL edilir, daha az islemli diye bir ozellik kayirilmaz.
- 15 dakikalik para akisi OLCULMUYOR — kullanicinin yonteminde 15m alim yeri
  belirleme timeframe'i, olcum timeframe'i degil.
