# -*- coding: utf-8 -*-
"""HACIM FILTRESI — 2019-2020 DOGRULAMA. TEK KOSU. On kayda birebir uyar."""
import os, json, pickle, sys, time
import numpy as np
sys.path.insert(0,"."); sys.path.insert(0,"/home/user/botum_lab/claude/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem
from akis_olc import akis_seri
from akis_olc2 import sim_hizli, band
V="veri_2019"
BAS=int(time.mktime(time.strptime("2019-01-01","%Y-%m-%d"))*1000)
BIT=int(time.mktime(time.strptime("2021-01-01","%Y-%m-%d"))*1000)

def yukle(s):
    d={}
    for itv in ("15m","1h","4h"):
        a=pickle.load(open(os.path.join(V,f"{s}__{itv}.pkl"),"rb"))
        d[itv]=a
    return d

def main():
    syms=sorted({f.split("__")[0] for f in os.listdir(V)})
    syms=[s for s in syms if all(os.path.exists(os.path.join(V,f"{s}__{i}.pkl")) for i in ("15m","1h","4h"))]
    print(f"2019-2020 evren: {len(syms)} parite (delist dahil)",flush=True)
    _A={}
    DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
    tum=[]; n=0; t0=time.time()
    for s in syms:
        n+=1
        try:
            d=yukle(s)
            _A[s]={k:tuple(v[:4]) for k,v in d.items()}
            sg,_=DT.coin_tara(s,BAS,BIT)
            if sg:
                A1=akis_seri(d["1h"])
                t1,h1,l1,c1=d["1h"][:4]; a1h=atr14(h1,l1,c1)
                t15,h15,l15,c15=d["15m"][:4]
                for x in sg:
                    i=np.searchsorted(A1["t"],x["t"],side="right")-1
                    if i<30: continue
                    hv=A1["hacim"][i]
                    if not np.isfinite(hv): continue
                    r=islem(x,t15,h15,l15,c15,t1,a1h,3,0.6)
                    if r is None: continue
                    tum.append((int(x["t"]),float(r[0]),int(r[1]),float(hv)))
        except Exception: pass
        finally: _A.pop(s,None)
        if n%40==0: print(f"   {n}/{len(syms)}  {len(tum)} dolan islem  {time.time()-t0:.0f}sn",flush=True)
    print(f"\ndolan islem: {len(tum)}",flush=True)
    if False:
        print(">>> (bilgi) 40'tan az dolan islem (on kayda gore)"); return
    tum.sort(key=lambda z:z[0])
    ay=(tum[-1][0]-tum[0][0])/1000/86400/30.44
    rng=np.random.default_rng(42)
    f=lambda p:f"{p:,.0f}$ %{((p/10000)**(1/ay)-1)*100:+.2f}"
    med=float(np.median([z[3] for z in tum]))
    print(f"donem uzunlugu: {ay:.1f} ay   hacim orani medyani: {med:.3f}\n")
    tab=band([(a,b,c) for a,b,c,_ in tum],rng)
    print(f"  {'TABAN (filtresiz)':<24}{f(tab[1]):<22}[{f(tab[0])} .. {f(tab[2])}]  ort {tab[3]:.0f} isl")
    ust=[(a,b,c) for a,b,c,h in tum if h>=med]
    alt=[(a,b,c) for a,b,c,h in tum if h< med]
    ru=band(ust,rng); ra=band(alt,rng)
    print(f"  {'HACIM YUKSEK yari':<24}{f(ru[1]):<22}[{f(ru[0])} .. {f(ru[2])}]  ort {ru[3]:.0f} isl")
    print(f"  {'HACIM DUSUK yari':<24}{f(ra[1]):<22}[{f(ra[0])} .. {f(ra[2])}]  ort {ra[3]:.0f} isl")
    ayu=((ru[1]/10000)**(1/ay)-1)*100
    print()
    if ru[1]<=ra[1]: print(">>> KALDI — yon ters, dusuk hacim yarisi kazaniyor.")
    elif ayu>=1.0: print(f">>> GECTI — yuksek yari onde ve ayda %{ayu:+.2f} (esik +%1.00).")
    else: print(f">>> SONUCSUZ — yon dogru ama ayda %{ayu:+.2f}, +%1.00 esiginin altinda.")

if __name__=="__main__": main()
