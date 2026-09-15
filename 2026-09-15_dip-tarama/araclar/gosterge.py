# -*- coding: utf-8 -*-
"""CLAUDE.md'de ZEC 23.08.2026 referansiyla dogrulanmis formuller."""
import numpy as np

def _wilder(x, n):
    a = np.empty_like(x, dtype=float); a[:] = np.nan
    if len(x) < n: return a
    a[n-1] = x[:n].mean()
    for i in range(n, len(x)):
        a[i] = (a[i-1]*(n-1) + x[i]) / n
    return a

def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = _wilder(np.where(d > 0, d, 0.0), n)
    dn = _wilder(np.where(d < 0, -d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / dn
    r = 100 - 100/(1+rs)
    r[dn == 0] = 100.0
    return r

def _sma(x, n):
    o = np.full_like(x, np.nan, dtype=float)
    if len(x) < n: return o
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0))
    o[n-1:] = (cs[n:] - cs[:-n]) / n
    o[:n-1] = np.nan
    return o

def stochrsi(c, n=14, m=14, k=3, d=3):
    r = rsi(c, n)
    out = np.full_like(r, np.nan)
    for i in range(len(r)):
        w = r[max(0, i-m+1):i+1]
        w = w[~np.isnan(w)]
        if len(w) < m: continue
        lo, hi = w.min(), w.max()
        out[i] = 0.0 if hi == lo else (r[i]-lo)/(hi-lo)*100
    K = _sma(out, k); D = _sma(K, d)
    return K, D

def kdj(h, l, c, n=9):
    K = np.full(len(c), np.nan); D = np.full(len(c), np.nan)
    pk = pd_ = 50.0
    for i in range(len(c)):
        if i < n-1: continue
        hh = h[i-n+1:i+1].max(); ll = l[i-n+1:i+1].min()
        rsv = 50.0 if hh == ll else (c[i]-ll)/(hh-ll)*100
        pk = (2/3)*pk + (1/3)*rsv
        pd_ = (2/3)*pd_ + (1/3)*pk
        K[i], D[i] = pk, pd_
    return K, D, 3*K - 2*D

def wr(h, l, c, n=14):
    o = np.full(len(c), np.nan)
    for i in range(n-1, len(c)):
        hh = h[i-n+1:i+1].max(); ll = l[i-n+1:i+1].min()
        o[i] = 0.0 if hh == ll else (hh-c[i])/(hh-ll)*-100
    return o

def _ema(x, n):
    a = 2/(n+1); o = np.full(len(x), np.nan, dtype=float)
    o[0] = x[0]
    for i in range(1, len(x)): o[i] = x[i]*a + o[i-1]*(1-a)
    return o

def macd(c, f=12, s=26, sig=9):
    dif = _ema(c, f) - _ema(c, s)
    dea = _ema(dif, sig)
    return dif, dea, dif - dea
