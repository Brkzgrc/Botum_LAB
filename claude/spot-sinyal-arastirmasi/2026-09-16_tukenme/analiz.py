# -*- coding: utf-8 -*-
"""TUKENME ANALIZI — biriktirmeli.
Her cikis kurali icin "yukselisin yuzde kacini cebe koydu" dagilimi toplanir.
Esikler COIN-ICI ondaliklar (serinin kendi gecmisine gore) — sabit deger yok."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tukenme import olcumler, yukselis_bolumleri, atr

KOM = 0.2
ONDALIK = (5,10,20,30,40,50,60,70,80,90,95)
# histogram: -100..+200 arasi %2 adim
KENAR = np.arange(-100, 300.25, 0.25)   # ince kutu: %0.25
NBIN = len(KENAR)-1

def _bos():
    return {"n":0, "toplam":0.0, "hist":[0]*NBIN}

def _ekle(d, deger):
    d["n"] += 1; d["toplam"] += float(deger)
    i = int(np.clip(np.searchsorted(KENAR, deger, side="right")-1, 0, NBIN-1))
    d["hist"][i] += 1

def medyan(d):
    if not d["n"]: return None
    h = np.array(d["hist"]); k = np.cumsum(h); yari = d["n"]/2.0
    i = int(np.searchsorted(k, yari))
    return float(KENAR[min(i, NBIN-1)] + 0.125)

def atr_trail(c, h, a, b, mult):
    """Giris DIPTEN; trailing +%15 tetiginden sonra silahlanir."""
    g = c[b["dip"]]; zir = max(g, float(np.max(h[b["dip"]:b["tetik"]+1])))
    for j in range(b["tetik"]+1, b["son"]+1):
        zir = max(zir, h[j])
        aa = a[j] if np.isfinite(a[j]) else g*0.02
        if c[j] <= max(g, zir - aa*mult): return j
    return b["son"]

def coin_isle(t,h,l,c,v,qv,tq, birik):
    """Bir coin icin tum bolumleri isler, sonucu birik sozlugune EKLER."""
    O = olcumler(t,h,l,c,v,qv,tq)
    A = atr(h,l,c)
    bol = yukselis_bolumleri(t,h,l,c)
    if not bol: return 0
    # coin-ici esikler: tum serinin kendi dagilimindan
    ESIK = {}
    for ad, x in O.items():
        f = x[np.isfinite(x)]
        if len(f) < 500: continue
        ESIK[ad] = np.percentile(f, ONDALIK)
    for b in bol:
        g = c[b["dip"]]
        if g <= 0 or b["son"] <= b["tetik"]: continue
        # getiri DIPTEN olculur; kural taramasi TETIKTEN baslar
        getiri = (c[b["tetik"]:b["son"]+1]/g - 1)*100 - KOM
        mukemmel = (h[b["tepe"]]/g - 1)*100 - KOM
        if mukemmel <= 0: continue
        # --- kontroller
        birik.setdefault("_taban", {})
        for ad, val in (("mukemmel", mukemmel),
                        ("tutmaya_devam", getiri[-1])):
            birik["_taban"].setdefault(ad, _bos()); _ekle(birik["_taban"][ad], val)
        for m in (0.6,1.0,2.0,3.0):
            j = atr_trail(c,h,A,b,m)
            val = (c[j]/g-1)*100 - KOM
            for k,vv in ((f"atr{m}", val), (f"atr{m}#oran", 100.0*val/mukemmel)):
                birik["_taban"].setdefault(k, _bos()); _ekle(birik["_taban"][k], vv)
        birik["_taban"].setdefault("tutmaya_devam#oran", _bos())
        _ekle(birik["_taban"]["tutmaya_devam#oran"], 100.0*getiri[-1]/mukemmel)
        # --- kurallar
        for ad, esikler in ESIK.items():
            x = O[ad][b["tetik"]:b["son"]+1]
            for qi, q in enumerate(ONDALIK):
                e = esikler[qi]
                for yon in (1,-1):
                    m = (x >= e) if yon > 0 else (x <= e)
                    m = m & np.isfinite(x); m[0] = False
                    idx = np.argmax(m) if m.any() else None
                    val = getiri[idx] if idx is not None else getiri[-1]
                    k = f"{ad}|{q}|{yon}"
                    birik.setdefault(k, _bos()); _ekle(birik[k], val)
                    ko = k + "#oran"
                    birik.setdefault(ko, _bos()); _ekle(birik[ko], 100.0*val/mukemmel)
    return len(bol)

def birlestir(a, b):
    for k, v in b.items():
        if k == "_taban":
            a.setdefault("_taban", {})
            for kk, vv in v.items():
                d = a["_taban"].setdefault(kk, _bos())
                d["n"] += vv["n"]; d["toplam"] += vv["toplam"]
                d["hist"] = [x+y for x,y in zip(d["hist"], vv["hist"])]
        else:
            d = a.setdefault(k, _bos())
            d["n"] += v["n"]; d["toplam"] += v["toplam"]
            d["hist"] = [x+y for x,y in zip(d["hist"], v["hist"])]
    return a

def rapor(birik, en_az=150, ust=40):
    tab = birik.get("_taban", {})
    print("\n=== KONTROLLER ===")
    print(f"  {'':<16}{'getiri medyan':>15}{'getiri ort':>13}{'YAKALANAN ORAN medyan':>24}{'n':>8}")
    for k in ("mukemmel","atr0.6","atr1.0","atr2.0","atr3.0","tutmaya_devam"):
        d = tab.get(k); o = tab.get(k+"#oran")
        if d and d["n"]:
            om = f"%{medyan(o):.1f}" if o and o["n"] else ("%100.0" if k=="mukemmel" else "-")
            print(f"  {k:<16}{medyan(d):>+14.2f}{d['toplam']/d['n']:>+13.2f}{om:>24}{d['n']:>8}")
    en_iyi_taban = max((medyan(tab[k]) for k in tab if k.startswith("atr")), default=0)
    sat = []
    for k, d in birik.items():
        if k == "_taban" or k.endswith("#oran") or d["n"] < en_az: continue
        o = birik.get(k+"#oran")
        sat.append((medyan(d), d["toplam"]/d["n"], medyan(o) if o and o["n"] else None, d["n"], k))
    sat.sort(key=lambda z: (-(z[2] if z[2] is not None else -999), -z[1]))
    print(f"\n=== EN IYI {ust} CIKIS KURALI (en iyi ATR tabani: %{en_iyi_taban:+.2f}) ===")
    print(f"  {'getiri med':>11}{'getiri ort':>12}{'ORAN med':>10}{'n':>7}  kural")
    for m,o,orn,n,k in sat[:ust]:
        print(f"  {m:>+11.2f}{o:>+12.2f}{(f'%{orn:.1f}' if orn is not None else '-'):>10}{n:>7}  {k}")
    return sat
