# Veriyi yeniden üretme

İki büyük dosya depoya **girmiyor** (`veri/.gitignore`):

| dosya | boyut | ne |
|---|---|---|
| `veri/gunluk_1d.pkl` | ~60 MB | 593 parite × 1 günlük kline (ham) |
| `veri/tablo_1g.npz` | ~141 MB | 789.011 bar × 45 özellik + 30 günlük yol profili |

Sebep: depo **public** ve GitHub tek dosya sınırı 100 MB. İkisi de aşağıdaki
üç komutla, kamuya açık Binance kaynaklarından **birebir** yeniden üretilir.

## Sıra (PowerShell / bash aynı)

```
python araclar/evren.py      # veri/evren_1g.json  (depoda VAR, ~36 KB)
python araclar/indir.py      # veri/gunluk_1d.pkl   ~15 dk
python araclar/tablo.py      # veri/tablo_1g.npz    ~2 dk
```

Gereken: `numpy` (başka bağımlılık yok; `pandas`/`scipy` gerekmez).

## Kaynaklar

| ne | adres |
|---|---|
| yaşayan pariteler, exchangeInfo | `https://data-api.binance.vision` |
| delist olmuş pariteler (aylık 1d zip) | `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision` |

Not: `data.binance.vision` doğrudan 403 veriyor, S3 adresi çalışıyor
(önceki çalışmanın notu, bu oturumda da doğrulandı).
`api.binance.com` bu ortamdan 451 döndü; `data-api.binance.vision` çalışıyor.

## Donmuş sınırlar

`araclar/indir.py` içinde:
- `BASLA = 1483228800000` (2017-01-01)
- `BITIR = 1790812800000` (2026-10-01 00:00 UTC) — **bugünün kapanmamış mumu hariç**

`BITIR` değiştirilirse sonuçlar bu rapordaki sayılarla karşılaştırılamaz.

## Bilinen veri tuzakları (ikisi de kodda çözülü)

1. **Mikrosaniye zaman damgası.** Binance arşivinde 2025'ten itibaren zaman
   damgaları mikrosaniye, öncesinde milisaniye; aynı sembolde ikisi birden
   bulunabilir. `indir.py::_ms()` satır bazında düzeltir (`t > 1e14 -> t //= 1000`).
2. **2025+ aylık CSV'lerde başlık satırı var.** `arsiv_indir()` sayı olmayan
   ilk alanı atar.
