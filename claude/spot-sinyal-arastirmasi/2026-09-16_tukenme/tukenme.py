# -*- coding: utf-8 -*-
"""TUKENME MOTORU — yukselis bolumleri + hareket olcumleri + kontrollu analiz.
Hicbir sabit esik yok: her olcum serinin KENDI gecmisine gore."""
import numpy as np

# ---------------------------------------------------------------- temel
def ema(x, n):
    a = 2/(n+1); o = np.empty(len(x)); o[0] = x[0]
    for i in range(1, len(x)): o[i] = x[i]*a + o[i-1]*(1-a)
    return o

def _wilder(x, n):
    a = 1/n; o = np.full(len(x), np.nan)
    if len(x) < n: return o
    o[n-1] = x[:n].mean()
    for i in range(n, len(x)): o[i] = x[i]*a + o[i-1]*(1-a)
    return o

def rsi(c, n=14):
    d = np.diff(c, prepend=c[0]); g = np.clip(d, 0, None); l = np.clip(-d, 0, None)
    ag, al = _wilder(g, n), _wilder(l, n)
    rs = np.divide(ag, al, out=np.full(len(c), np.inf), where=al > 0)
    return np.where(np.isnan(ag), 50.0, 100 - 100/(1+rs))

def _roll(x, n, fn):
    o = np.full(len(x), np.nan)
    for i in range(n-1, len(x)): o[i] = fn(x[i-n+1:i+1])
    return o

def _sma(x, n):
    c = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0)); o = np.full(len(x), np.nan)
    o[n-1:] = (c[n:]-c[:-n])/n; return o

def stoch_rsi(c, n=14, k=3, d=3):
    r = rsi(c, n); lo = _roll(r, n, np.min); hi = _roll(r, n, np.max)
    rng = np.where((hi-lo) == 0, np.nan, hi-lo)
    raw = 100*(r-lo)/rng
    K = np.nan_to_num(_sma(raw, k), nan=50.0); D = np.nan_to_num(_sma(K, d), nan=50.0)
    return K, D

def kdj(h, l, c, n=9):
    ll = _roll(l, n, np.min); hh = _roll(h, n, np.max)
    rng = np.where((hh-ll) == 0, np.nan, hh-ll)
    rsv = np.nan_to_num(100*(c-ll)/rng, nan=50.0)
    K = np.empty(len(c)); D = np.empty(len(c)); K[0] = D[0] = 50.0
    for i in range(1, len(c)):
        K[i] = 2/3*K[i-1] + 1/3*rsv[i]
        D[i] = 2/3*D[i-1] + 1/3*K[i]
    return K, D, 3*K - 2*D

def wr(h, l, c, n=14):
    hh = _roll(h, n, np.max); ll = _roll(l, n, np.min)
    rng = np.where((hh-ll) == 0, np.nan, hh-ll)
    return np.nan_to_num((hh-c)/rng*-100, nan=-50.0)

def macd(c):
    dif = ema(c, 12) - ema(c, 26); dea = ema(dif, 9)
    return dif, dea, dif-dea

def atr(h, l, c, n=14):
    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    tr[0] = h[0]-l[0]; return _wilder(tr, n)

# ------------------------------------------------- HAREKET DONUSUMLERI
# Hepsi serinin KENDI gecmisine gore. Sabit esik yok.

def _oynaklik(x, n=20):
    d = np.abs(np.diff(x, prepend=x[0]))
    o = _sma(d, n)
    return np.where((o == 0) | ~np.isfinite(o), np.nan, o)

def hiz(x, n=20):
    """son degisim / kendi ortalama degisimi  (normalize hiz)"""
    return np.diff(x, prepend=x[0]) / _oynaklik(x, n)

def ivme(x, n=20):
    h = hiz(x, n); return h - np.roll(h, 1)

def ardisik(x):
    """kac bar ust uste ayni yonde (isaretli: +3 = 3 bar yukari)"""
    d = np.sign(np.diff(x, prepend=x[0])); o = np.zeros(len(x))
    for i in range(1, len(x)):
        o[i] = o[i-1]+d[i] if d[i] != 0 and np.sign(o[i-1]) == d[i] else d[i]
    return o

def egim(x, n=5, m=20):
    return (x - np.roll(x, n)) / (n * _oynaklik(x, m))

def zirveden_dusus(x, n=24):
    """son n barin tepesinden yuzde kac geri gelmis (pozitif = geri gelmis)"""
    hi = _roll(x, n, np.max)
    return np.where(np.abs(hi) > 1e-12, (hi - x)/np.abs(hi)*100, np.nan)

def yuzdelik(x, n=200):
    """su anki degerin son n bardaki yuzdelik konumu (0-100)"""
    o = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        w = x[i-n:i]; o[i] = 100.0*np.mean(w <= x[i])
    return o

DONUSUM = {"hiz": hiz, "ivme": ivme, "ardisik": ardisik, "egim": egim,
           "zirveden_dusus": zirveden_dusus, "yuzdelik": yuzdelik}

def makas_olcumleri(hizli, yavas, ad):
    """iki cizgi arasi: acikliyor mu daraliyor mu, kac bar ust uste"""
    m = hizli - yavas
    return {f"{ad}_makas_hiz": hiz(m), f"{ad}_makas_ivme": ivme(m),
            f"{ad}_makas_ardisik": ardisik(m), f"{ad}_makas_egim": egim(m)}

# ------------------------------------------------------- OLCUM FABRIKASI
def olcumler(t, h, l, c, v, qv, tq, trades=None):
    """~110 hareket olcumu uretir. Hepsi nedensel (sadece kapanmis barlar)."""
    S = {}
    S["fiyat"] = c
    S["rsi"] = rsi(c)
    dif, dea, hist = macd(c); S["macd_dif"], S["macd_dea"], S["macd_hist"] = dif, dea, hist
    sk, sd = stoch_rsi(c); S["srsi_k"], S["srsi_d"] = sk, sd
    kk, dd, jj = kdj(h, l, c); S["kdj_k"], S["kdj_d"], S["kdj_j"] = kk, dd, jj
    S["wr"] = wr(h, l, c)
    S["ema20"], S["ema50"] = ema(c, 20), ema(c, 50)
    S["atr"] = atr(h, l, c)
    S["hacim"] = v
    S["quote_hacim"] = qv
    tr = np.divide(tq, qv, out=np.full(len(qv), .5), where=qv > 0).clip(0, 1)
    S["taker_orani"] = tr
    S["giren_para"] = tq
    S["cikan_para"] = qv - tq
    S["net_para"] = tq - (qv - tq)
    S["obv"] = np.cumsum(np.sign(np.diff(c, prepend=c[0])) * v)
    if trades is not None: S["islem_sayisi"] = trades

    O = {}
    for ad, ser in S.items():
        ser = np.asarray(ser, dtype=float)
        for dad, fn in DONUSUM.items():
            try: O[f"{ad}_{dad}"] = fn(ser)
            except Exception: pass
    for ad, a, b in (("macd", dif, dea), ("srsi", sk, sd), ("kdj", kk, dd),
                     ("ema", S["ema20"], S["ema50"]),
                     ("netpara", S["net_para"], _sma(S["net_para"], 20))):
        O.update(makas_olcumleri(np.asarray(a, float), np.asarray(b, float), ad))
    return O

# ------------------------------------------------------ BOLUM (EPISODE)
def yukselis_bolumleri(t, h, l, c, artis=15.0, stop=7.5, geri=None):
    """Yerel dipten +artis%'e, -stop%'e inmeden ULASAN hareketler.
    Bolum tepede biter (tepeden geri% cekilince kapanir)."""
    if geri is None: geri = stop
    n = len(c); out = []; i = 30
    while i < n-5:
        # yerel dip mi (son 12 barin en dibi)
        if i < 12 or l[i] > np.min(l[i-12:i+1]): i += 1; continue
        giris = c[i]; ust = giris*(1+artis/100); alt = giris*(1-stop/100)
        j = i+1; ulasti = False
        while j < n:
            if l[j] <= alt: break
            if h[j] >= ust: ulasti = True; break
            j += 1
        if not ulasti: i += 1; continue
        # tepeyi bul: zirveden geri% cekilene kadar
        zirve = h[j]; zirve_i = j; k = j+1
        while k < n:
            if h[k] > zirve: zirve = h[k]; zirve_i = k
            elif c[k] <= zirve*(1-geri/100): break
            k += 1
        out.append({"dip": i, "tetik": j, "tepe": zirve_i, "son": min(k, n-1),
                    "giris": float(giris), "zirve": float(zirve),
                    "kazanc": float(zirve/giris-1)*100})
        i = max(k, zirve_i+1)
    return out
