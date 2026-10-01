# -*- coding: utf-8 -*-
"""
1 GUNLUK gosterge kutuphanesi.

RSI / StochRSI / MACD / W%R formulleri, bu depoda ZEC 23.08.2026 referansiyla
dogrulanmis `2026-09-15_dip-tarama/araclar/gosterge.py` ile BIREBIR AYNI
tanimlardir (kopyalanmadi, ayni formul yeniden yazildi + vektorlestirildi).
Dogrulama testi: araclar/test_gosterge.py
"""
import numpy as np


# ---------- yardimcilar ----------------------------------------------------
def _wilder(x, n):
    a = np.full(len(x), np.nan)
    if len(x) < n:
        return a
    a[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        a[i] = (a[i - 1] * (n - 1) + x[i]) / n
    return a


def _sma(x, n):
    """NaN-GUVENLI SMA.

    DIKKAT — duzeltilmis hata: bu deponun onceki `gosterge.py` surumu
    `np.nan_to_num(x)` kullaniyordu; penceresinde NaN olan barlarda NaN yerine
    SAYI uretiyordu. StochRSI'da bu, her sembolun gecmisinin ilk ~26 barinda
    K=D=0.0 (yani "StochRSI < 15") gibi SAHTE dip uretiyor. Burada pencerede
    NaN varsa cikti NaN'dir.
    """
    o = np.full(len(x), np.nan)
    if len(x) < n:
        return o
    x = np.asarray(x, dtype=float)
    nanmi = np.isnan(x)
    cs = np.cumsum(np.insert(np.where(nanmi, 0.0, x), 0, 0.0))
    cn = np.cumsum(np.insert(nanmi.astype(np.int64), 0, 0))
    toplam = cs[n:] - cs[:-n]
    nan_say = cn[n:] - cn[:-n]
    o[n - 1:] = np.where(nan_say == 0, toplam / n, np.nan)
    return o


def _ema(x, n):
    a = 2.0 / (n + 1)
    o = np.empty(len(x))
    o[0] = x[0]
    for i in range(1, len(x)):
        o[i] = x[i] * a + o[i - 1] * (1 - a)
    return o


def _pencere(x, n):
    """(len(x), n) kayan pencere gorunumu; ilk n-1 satir gecersiz."""
    if len(x) < n:
        return None
    return np.lib.stride_tricks.sliding_window_view(x, n)


def kayan_max(x, n):
    o = np.full(len(x), np.nan)
    p = _pencere(x, n)
    if p is not None:
        o[n - 1:] = p.max(axis=1)
    return o


def kayan_min(x, n):
    o = np.full(len(x), np.nan)
    p = _pencere(x, n)
    if p is not None:
        o[n - 1:] = p.min(axis=1)
    return o


def kayan_ort(x, n):
    return _sma(x, n)


# ---------- gostergeler ----------------------------------------------------
def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = _wilder(np.where(d > 0, d, 0.0), n)
    dn = _wilder(np.where(d < 0, -d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / dn
    r = 100 - 100 / (1 + rs)
    r[dn == 0] = 100.0
    r[:n] = np.nan
    return r


def stochrsi(c, n=14, m=14, k=3, d=3):
    """TradingView varsayilani: RSI(14) uzerinde Stoch(14), K=3, D=3."""
    r = rsi(c, n)
    ham = np.full(len(r), np.nan)
    p = _pencere(r, m)
    if p is not None:
        lo = p.min(axis=1)
        hi = p.max(axis=1)
        gecerli = ~np.isnan(lo) & ~np.isnan(hi)
        pay = r[m - 1:] - lo
        bol = hi - lo
        deg = np.where(bol == 0, 0.0, np.divide(pay, bol,
                                                out=np.zeros_like(pay),
                                                where=bol != 0) * 100)
        ham[m - 1:] = np.where(gecerli, deg, np.nan)
    K = _sma(ham, k)
    D = _sma(K, d)
    # acik isinma guvencesi: RSI(n) + Stoch(m) + K(k) + D(d) zinciri
    gerekli = n + m - 1 + (k - 1) + (d - 1)
    K[:gerekli] = np.nan
    D[:gerekli] = np.nan
    return K, D


def macd(c, f=12, s=26, sig=9):
    dif = _ema(c, f) - _ema(c, s)
    dea = _ema(dif, sig)
    out = dif - dea
    dif = dif.copy(); dea = dea.copy(); out = out.copy()
    dif[:s] = np.nan; dea[:s + sig] = np.nan; out[:s + sig] = np.nan
    return dif, dea, out


def wr(h, l, c, n=14):
    hh = kayan_max(h, n)
    ll = kayan_min(l, n)
    bol = hh - ll
    o = np.where(bol == 0, 0.0,
                 np.divide(hh - c, bol, out=np.zeros_like(c), where=bol != 0) * -100)
    o = np.asarray(o, dtype=float)
    o[np.isnan(hh) | np.isnan(ll)] = np.nan
    return o


def kdj(h, l, c, n=9):
    hh = kayan_max(h, n)
    ll = kayan_min(l, n)
    bol = hh - ll
    rsv = np.where(bol == 0, 50.0,
                   np.divide(c - ll, bol, out=np.zeros_like(c), where=bol != 0) * 100)
    K = np.full(len(c), np.nan); D = np.full(len(c), np.nan)
    pk = pd_ = 50.0
    for i in range(len(c)):
        if np.isnan(hh[i]):
            continue
        pk = (2 / 3) * pk + (1 / 3) * rsv[i]
        pd_ = (2 / 3) * pd_ + (1 / 3) * pk
        K[i], D[i] = pk, pd_
    return K, D, 3 * K - 2 * D


def atr(h, l, c, n=14):
    onc = np.roll(c, 1); onc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - onc), np.abs(l - onc)))
    return _wilder(tr, n)


def adx(h, l, c, n=14):
    onc = np.roll(c, 1); onc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - onc), np.abs(l - onc)))
    up = h - np.roll(h, 1); up[0] = 0.0
    dn = np.roll(l, 1) - l;  dn[0] = 0.0
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr_ = _wilder(tr, n)
    pdi = 100 * _wilder(pdm, n) / np.where(atr_ == 0, np.nan, atr_)
    ndi = 100 * _wilder(ndm, n) / np.where(atr_ == 0, np.nan, atr_)
    tp = pdi + ndi
    dx = 100 * np.abs(pdi - ndi) / np.where(tp == 0, np.nan, tp)
    return _wilder(np.nan_to_num(dx), n), pdi, ndi


def cci(h, l, c, n=20):
    tp = (h + l + c) / 3.0
    sma = _sma(tp, n)
    o = np.full(len(c), np.nan)
    p = _pencere(tp, n)
    if p is not None:
        md = np.abs(p - sma[n - 1:, None]).mean(axis=1)
        o[n - 1:] = np.where(md == 0, 0.0, (tp[n - 1:] - sma[n - 1:]) / (0.015 * np.where(md == 0, np.nan, md)))
    return o


def mfi(h, l, c, v, n=14):
    tp = (h + l + c) / 3.0
    akis = tp * v
    d = np.diff(tp, prepend=tp[0])
    poz = np.where(d > 0, akis, 0.0)
    neg = np.where(d < 0, akis, 0.0)
    sp = _sma(poz, n) * n
    sn = _sma(neg, n) * n
    with np.errstate(divide="ignore", invalid="ignore"):
        o = 100 - 100 / (1 + sp / np.where(sn == 0, np.nan, sn))
    o = np.asarray(o, dtype=float)
    o[(sn == 0) & ~np.isnan(sp)] = 100.0
    return o


def bollinger(c, n=20, k=2.0):
    orta = _sma(c, n)
    o = np.full(len(c), np.nan)
    p = _pencere(c, n)
    if p is not None:
        o[n - 1:] = p.std(axis=1)
    ust, alt = orta + k * o, orta - k * o
    genislik = (ust - alt) / np.where(orta == 0, np.nan, orta)
    bol = ust - alt
    yuzde_b = np.where(bol == 0, 0.5, (c - alt) / np.where(bol == 0, np.nan, bol))
    return orta, ust, alt, genislik, np.asarray(yuzde_b, dtype=float)


def ema(c, n):
    o = _ema(c, n).copy()
    o[:n] = np.nan
    return o


def roc(c, n):
    o = np.full(len(c), np.nan)
    if len(c) > n:
        o[n:] = (c[n:] / np.where(c[:-n] == 0, np.nan, c[:-n]) - 1) * 100
    return o


def kesisim_yukari(hizli, yavas):
    """hizli, yavas'i ASAGIDAN YUKARI kesti mi (bool dizi)."""
    o = np.zeros(len(hizli), dtype=bool)
    gecerli = ~np.isnan(hizli) & ~np.isnan(yavas)
    onc_h = np.roll(hizli, 1); onc_y = np.roll(yavas, 1)
    onc_gecerli = np.roll(gecerli, 1); onc_gecerli[0] = False
    o[1:] = (gecerli[1:] & onc_gecerli[1:] &
             (onc_h[1:] <= onc_y[1:]) & (hizli[1:] > yavas[1:]))
    return o
