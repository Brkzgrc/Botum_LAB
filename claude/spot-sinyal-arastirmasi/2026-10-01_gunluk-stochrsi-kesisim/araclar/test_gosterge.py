# -*- coding: utf-8 -*-
"""
gosterge1g.py'yi bu depoda ONCEDEN DOGRULANMIS gosterge.py'ye karsi sinar.
Referans: 2026-09-15_dip-tarama/araclar/gosterge.py (ZEC 23.08.2026 ile dogrulandi)
Iki bagimsiz uygulama ayni sayiyi vermeli.
"""
import os, sys, pickle
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(BURASI))))  # Botum_LAB
REF = os.path.join(KOK, "claude", "spot-sinyal-arastirmasi",
                   "2026-09-15_dip-tarama", "araclar")
sys.path.insert(0, BURASI)
sys.path.insert(0, REF)

import gosterge1g as yeni
import gosterge as ref          # dogrulanmis referans



def yukle():
    """BTC 1 gunluk mumlari (API). pandas bagimliligi olmasin diye dogrudan cekiliyor."""
    import json, urllib.request
    url = ("https://data-api.binance.vision/api/v3/klines"
           "?symbol=BTCUSDT&interval=1d&limit=1000")
    istek = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
    with urllib.request.urlopen(istek, timeout=60) as r:
        kl = json.loads(r.read().decode())
    return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in kl]


ISINMA = 40   # ilk 40 bar karsilastirma DISI: referans gosterge.py bu bolgede
              # NaN yerine sayi uretiyor (nan_to_num hatasi), bkz gosterge1g._sma


def kars(ad, a, b, tol=1e-7):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = ~np.isnan(a) & ~np.isnan(b)
    m[:ISINMA] = False
    sadece_a = int((~np.isnan(a) & np.isnan(b)).sum())
    sadece_b = int((np.isnan(a) & ~np.isnan(b)).sum())
    if m.sum() == 0:
        print(f"  {ad:14s} KARSILASTIRILAMADI (ortak gecerli bar 0)")
        return False
    fark = np.abs(a[m] - b[m])
    tamam = fark.max() <= tol
    print(f"  {ad:14s} ortak={m.sum():5d}  maxfark={fark.max():.3e}  "
          f"{'AYNI' if tamam else '>>> FARKLI <<<'}"
          f"   (isinma farki: yeni-sadece {sadece_a}, ref-sadece {sadece_b})")
    return tamam


def main():
    ham = yukle()
    print(f"BTC 1g bar: {len(ham)}  ornek satir uzunlugu: {len(ham[0])}")
    # satir bicimini bul
    r0 = ham[0]
    if len(r0) >= 6 and isinstance(r0[0], (int, float)) and r0[0] > 1e11:
        o = np.array([float(r[1]) for r in ham]); h = np.array([float(r[2]) for r in ham])
        l = np.array([float(r[3]) for r in ham]); c = np.array([float(r[4]) for r in ham])
    else:
        o = np.array([float(r[0]) for r in ham]); h = np.array([float(r[1]) for r in ham])
        l = np.array([float(r[2]) for r in ham]); c = np.array([float(r[3]) for r in ham])
    print(f"kapanis araligi: {c.min():.2f} - {c.max():.2f}\n")

    tum = []
    tum.append(kars("RSI14", yeni.rsi(c, 14), ref.rsi(c, 14)))

    yK, yD = yeni.stochrsi(c); rK, rD = ref.stochrsi(c)
    tum.append(kars("StochRSI K", yK, rK, 1e-9))
    tum.append(kars("StochRSI D", yD, rD, 1e-9))

    ydif, ydea, yh = yeni.macd(c); rdif, rdea, rh = ref.macd(c)
    tum.append(kars("MACD dif", ydif, rdif, 1e-6))
    tum.append(kars("MACD dea", ydea, rdea, 1e-6))
    tum.append(kars("MACD hist", yh, rh, 1e-6))

    tum.append(kars("W%R 14", yeni.wr(h, l, c, 14), ref.wr(h, l, c, 14), 1e-6))

    yKk, yDk, yJ = yeni.kdj(h, l, c); rKk, rDk, rJ = ref.kdj(h, l, c)
    tum.append(kars("KDJ J", yJ, rJ, 1e-5))

    print(f"\nSONUC: {sum(tum)}/{len(tum)} gosterge isinma SONRASI BIREBIR AYNI")
    print(f"(ilk {ISINMA} bar haric tutuldu: referans gosterge.py o bolgede"
          f" StochRSI icin NaN yerine 0.0 uretiyor -> sahte 'StochRSI<15'."
          f" gosterge1g.py bunu duzeltti, ilk gecerli StochRSI barı 31.)")
    sys.exit(0 if all(tum) else 1)


if __name__ == "__main__":
    main()
