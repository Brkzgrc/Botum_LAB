# -*- coding: utf-8 -*-
import os, sys, pickle, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sistem
G="/tmp/claude-0/-home-user-Botum/3e092c90-6fa5-51e5-9584-2428d75342cd/scratchpad/gecmis"
VESKI=f"{G}/veri"; VD=f"{G}/veri_dogrulama"; V1=f"{G}/veri_1h"; VA=f"{G}/veri_akis"; V19=f"{G}/veri_2019"

def yukle(s, era):
    """(t,h,l,c,v) uclusu: 15m, 1h, 4h"""
    if era=="2019-2020":
        d={i:pickle.load(open(f"{V19}/{s}__{i}.pkl","rb")) for i in ("15m","1h","4h")}
        f=lambda a:(a[0],a[1],a[2],a[3],a[4])
        return f(d["15m"]), f(d["1h"]), f(d["4h"])
    if era=="2021-2022":
        d=pickle.load(open(f"{VESKI}/{s}.pkl","rb"))
        # 2021-2022 arsivinde hacim yok -> v=None, OBV sarti HIC kullanilmaz
        # (np.ones ile sahte OBV uretmek 6. sarti uydurmak olurdu)
        g=lambda k:(d[k][0],d[k][1],d[k][2],d[k][3],None)
        return g("15m"), g("1h"), g("4h")
    v=pickle.load(open(f"{VD}/{s}__{era}.pkl","rb")); h1=pickle.load(open(f"{V1}/{s}__{era}.pkl","rb"))
    a15=(v["15m"][0],v["15m"][1],v["15m"][2],v["15m"][3],v["15m"][4])
    a4 =(v["4h"][0], v["4h"][1], v["4h"][2], v["4h"][3], v["4h"][4])
    try:
        k=pickle.load(open(f"{VA}/{s}__{era}__1h.pkl","rb")); a1=(k[0],k[1],k[2],k[3],k[4])
    except Exception:
        a1=(h1[0],h1[1],h1[2],h1[3],None)
    return a15, a1, a4

def semboller(era):
    if era=="2019-2020":
        s={f.split("__")[0] for f in os.listdir(V19)}
        return sorted(x for x in s if all(os.path.exists(f"{V19}/{x}__{i}.pkl") for i in ("15m","1h","4h")))
    if era=="2021-2022":
        # kaldiracli token'lar (UP/DOWN/BULL/BEAR) canli evrende de yok
        kotu=("UPUSDT","DOWNUSDT","BULLUSDT","BEARUSDT")
        return sorted(f[:-4] for f in os.listdir(VESKI)
                      if f.endswith(".pkl") and not f[:-4].endswith(kotu))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{era}.pkl") and os.path.exists(f"{V1}/{f.split('__')[0]}__{era}.pkl"))

def ozet(B, hedefler=("10/5","20/10","30/15")):
    print(f"\n4h sinyal: {len(B):,}")
    n1=sum(1 for x in B if x['B']); n15=sum(1 for x in B if x['C'])
    print(f"  1h teyidi gelen : {n1:,}  (%{100*n1/max(1,len(B)):.0f})")
    print(f"  15m teyidi gelen: {n15:,}  (%{100*n15/max(1,len(B)):.0f})")
    print(f"\n{'kol':<28}{'islem':>8}" + "".join(f"{h:>22}" for h in hedefler))
    for ad, et in (("A","sadece 4h"),("B","4h + 1h teyidi"),("C","4h + 1h + 15m (tam)")):
        L=[x[ad] for x in B if x.get(ad)]
        if not L: continue
        sat=f"  {et:<26}{len(L):>8}"
        for hd in hedefler:
            r=[x["sonuc"][hd] for x in L]
            kar=[a for a,_ in r]; mae=[m for _,m in r]
            belli=[a for a in kar if a>=0]
            o=100*np.mean(belli) if belli else 0
            sat+=f"{f'%{o:.1f} (mae -%{abs(np.median(mae)):.1f})':>22}"
        print(sat)

if __name__=="__main__":
    era=sys.argv[1]; lim=int(sys.argv[2]) if len(sys.argv)>2 else 0
    syms=semboller(era)
    if lim: syms=syms[:lim]
    B=[]; t0=time.time(); n=0
    for s in syms:
        n+=1
        try:
            a15,a1,a4=yukle(s,era); sistem.coin_tara(a15,a1,a4,B)
        except Exception: pass
        if n%50==0: print(f"  {n}/{len(syms)}  {len(B):,} sinyal  {time.time()-t0:.0f}sn", flush=True)
    print(f"\n{'='*70}\n{era}  ({len(syms)} coin)  —  hedefe mi once ulasti, stopa mi\n{'='*70}")
    ozet(B)
