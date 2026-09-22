# -*- coding: utf-8 -*-
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hareket, kos2

ESIK=[2,3,4,5,6]
if __name__=="__main__":
    era=sys.argv[1]; lim=int(sys.argv[2]) if len(sys.argv)>2 else 0
    syms=kos2.semboller(era)
    if lim: syms=syms[:lim]
    rng=np.random.default_rng(7)
    R={itv:{N:[] for N in ESIK} for itv in ("15m","1h","4h")}
    T={itv:[] for itv in ("15m","1h","4h")}
    t0=time.time()
    for n,s in enumerate(syms,1):
        try:
            a15,a1,a4=kos2.yukle(s,era)
            for itv,d in (("15m",a15),("1h",a1),("4h",a4)):
                hareket.tara(d,itv,ESIK,R[itv],T[itv],rng)
        except Exception: pass
        if n%25==0: print(f"  {n}/{len(syms)}  {time.time()-t0:.0f}sn", flush=True)
    print(f"\n{'='*94}\n{era}  ({len(syms)} coin)  —  SADECE GOSTERGE HAREKETI, dip sarti YOK")
    print(f"ufuk 28 gun · yol-farkindali (hedefe mi once degdi stopa mi) · basabas %33.3\n{'='*94}")
    for itv in ("15m","1h","4h"):
        print(f"\n--- {itv} ---")
        print(f"  {'kac sart birden':<20}{'sinyal':>9}" + "".join(f"{f'+{hd}/-{st}':>22}" for hd,st in hareket.HEDEFLER))
        hareket.ozet("TABAN (rastgele)", T[itv])
        for N in ESIK: hareket.ozet(f">= {N} sart", R[itv][N])
