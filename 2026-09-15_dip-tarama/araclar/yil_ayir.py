# -*- coding: utf-8 -*-
"""2025 ve 2026 AYRI AYRI — ATRx0.6 vs ATRx2.0, giris ofseti. Olcut: PARA."""
import os, pickle, sys, time
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
sys.path.insert(0,"/home/user/botum_lab/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem
VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h"); ET="2025-2026"

def main():
    syms=[f.split("__")[0] for f in os.listdir(VD) if f.endswith(f"__{ET}.pkl")]
    syms=[s for s in syms if os.path.exists(os.path.join(V1,f"{s}__{ET}.pkl"))]
    _A={}; DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
    bas=int(time.mktime(time.strptime("2025-01-01","%Y-%m-%d"))*1000)
    bit=int(time.mktime(time.strptime("2026-10-01","%Y-%m-%d"))*1000)
    tum=[]; n=0; t0=time.time()
    for s in syms:
        n+=1
        try:
            v=pickle.load(open(os.path.join(VD,f"{s}__{ET}.pkl"),"rb"))
            h1=pickle.load(open(os.path.join(V1,f"{s}__{ET}.pkl"),"rb"))
            _A[s]={"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":h1}
            sg,_=DT.coin_tara(s,bas,bit); tum+=sg
        except Exception: pass
        finally: _A.pop(s,None)
        if n%150==0: print(f"  {n}/{len(syms)} {len(tum)} sinyal {time.time()-t0:.0f}sn",flush=True)
    tum.sort(key=lambda x:x["t"])
    print(f"toplam sinyal: {len(tum)}",flush=True)
    SINIR=int(time.mktime(time.strptime("2026-01-01","%Y-%m-%d"))*1000)
    cache={}
    for etiket,sg in (("2025", [x for x in tum if x["t"]<SINIR]),
                      ("2026", [x for x in tum if x["t"]>=SINIR])):
        if len(sg)<20: print(f"\n{etiket}: yetersiz"); continue
        ay=(sg[-1]["t"]-sg[0]["t"])/1000/86400/30.44
        print(f"\n=== {etiket} — {len(sg)} sinyal, {ay:.1f} ay ===")
        print(f"{'giris':>7}{'ATRx0.6':>30}{'ATRx2.0':>30}")
        for of in (0,2,3):
            sat=f"{('-%'+str(of) if of else 'yok'):>7}"
            for mult in (0.6,2.0):
                para=10000.0; acik=0; n2=0; kz=0; tp=para; dd=0.0
                for x in sg:
                    if x["t"]<=acik: continue
                    s=x["s"]
                    if s not in cache:
                        if len(cache)>25: cache.clear()
                        try:
                            v=pickle.load(open(os.path.join(VD,f"{s}__{ET}.pkl"),"rb"))
                            h1=pickle.load(open(os.path.join(V1,f"{s}__{ET}.pkl"),"rb"))
                            cache[s]=(v["15m"],(h1[0],atr14(h1[1],h1[2],h1[3])))
                        except Exception: cache[s]=None
                    if cache[s] is None: continue
                    (t15,h15,l15,c15,_),(t1h,a1h)=cache[s]
                    r=islem(x,t15,h15,l15,c15,t1h,a1h,of,mult)
                    if r is None: continue
                    p,ct=r; para*=(1+p/100); acik=ct; n2+=1; kz+=1 if p>0 else 0
                    tp=max(tp,para); dd=min(dd,(para/tp-1)*100)
                aa=((para/10000)**(1/ay)-1)*100 if para>0 else -99
                wr=100*kz/n2 if n2 else 0
                sat+=f"{f'{para:>9,.0f}$ %{aa:+5.2f} {n2:>3}isl WR%{wr:.0f} dd%{dd:.0f}':>30}"
            print(sat,flush=True)

if __name__=="__main__": main()
