# -*- coding: utf-8 -*-
"""KULLANICININ YONTEMI — MACD tabanli, kendi tarifiyle kodlanmis.

HUNI (15 dakika):
    A  histogram NEGATIF, yukari donuyor        -> ARASTIR (izlemeye al)
    B  histogram sifiri YUKARI kestigi bar      -> AL, ama BTC yukari sinyal vermeli
    C  kesisten sonraki 1-2 bar                 -> AL (kar al cik)
    D  pozitif, 3+ bardir yukselisde            -> VETO (gec kalindi)

TEYIT (1 saat):
    donus baslangici : histogram negatif AMA egim yukari (barlar kisaliyor)
    VEYA kesisime yaklasiyor : DIF<DEA ve |DIF-DEA| daraliyor

RISK (4 saat) — alim sarti DEGIL, uyari:
    asagi egim  -> dikkat
    yukari donmusse en fazla 4 mum once olmali

TREND (gunluk): kontrol

Esik yok; "barlar kisaliyor" egimle olculur (sabit bar sayisi degil).
"""
import numpy as np

def _ema(x, n):
    a = 2/(n+1); o = np.empty(len(x)); o[0] = x[0]
    for i in range(1, len(x)): o[i] = x[i]*a + o[i-1]*(1-a)
    return o

def macd(c, f=12, s=26, sig=9):
    dif = _ema(c, f) - _ema(c, s)
    dea = _ema(dif, sig)
    return dif, dea, dif - dea

def _egim(x, n=3):
    """son n barin dogrusal egimi (nedensel)."""
    o = np.full(len(x), np.nan)
    k = np.arange(n) - (n-1)/2.0
    payda = (k**2).sum()
    for i in range(n-1, len(x)):
        w = x[i-n+1:i+1]
        if np.isnan(w).any(): continue
        o[i] = ((w - w.mean())*k).sum()/payda
    return o

def asama_15m(c):
    """Her bar icin huni asamasi: 'A' | 'B' | 'C' | 'D' | ''  """
    dif, dea, hist = macd(c)
    eg = _egim(hist, 3)
    n = len(c); out = np.full(n, "", dtype="<U1")
    # sifiri yukari kesis
    kesis = (hist > 0) & (np.roll(hist, 1) <= 0); kesis[0] = False
    kesis_idx = np.where(kesis)[0]
    for i in range(3, n):
        if hist[i] > 0:
            # kesisten kac bar gecti
            onceki = kesis_idx[kesis_idx <= i]
            gecen = i - onceki[-1] if len(onceki) else 999
            if gecen == 0:   out[i] = "B"
            elif gecen <= 2: out[i] = "C"
            else:            out[i] = "D"
        else:
            if not np.isnan(eg[i]) and eg[i] > 0: out[i] = "A"
    return out, dif, dea, hist

def teyit_1h(c):
    """1 saat: donus baslangici VEYA kesisime yaklasma -> True"""
    dif, dea, hist = macd(c)
    eg = _egim(hist, 3)
    donus_basi = (hist < 0) & (eg > 0)
    fark = np.abs(dif - dea)
    daraliyor = (dif < dea) & (fark < np.roll(fark, 1)) & (np.roll(fark,1) < np.roll(fark,2))
    daraliyor[:2] = False
    return donus_basi | daraliyor

def risk_4h(c):
    """4 saat: (dikkat_mi, taze_donus_mu)"""
    dif, dea, hist = macd(c)
    eg = _egim(hist, 3)
    asagi_egim = eg < 0
    kesis = (hist > 0) & (np.roll(hist,1) <= 0); kesis[0] = False
    ki = np.where(kesis)[0]
    taze = np.zeros(len(c), dtype=bool)
    for i in range(len(c)):
        o = ki[ki <= i]
        if len(o) and (i - o[-1]) <= 4 and hist[i] > 0: taze[i] = True
    return asagi_egim, taze

def btc_yukari(c):
    """BTC 1h histogram egimi yukari mi (kirilgan degil mi)."""
    _,_,hist = macd(c)
    return _egim(hist, 3) > 0
