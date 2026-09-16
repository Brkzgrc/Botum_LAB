# -*- coding: utf-8 -*-
"""YIL YIL: 2021..2026, -%3 giris, ATRx0.6 vs ATRx2.0. Olcut: PARA."""
import os, pickle, sys, time, datetime as dt
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
sys.path.insert(0,"/home/user/botum_lab/claude/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem

KAYNAK={  # yil -> (klasor bicimi, etiket)
 2021:("eski",None), 2022:("eski",None),
 2023:("yeni","2023-2024"), 2024:("yeni","2023-2024"),
 2025:("yeni","2025-2026"), 2026:("yeni","2025-2026")}
VESKI=os.path.join(KOK,"veri"); VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h")

def yukle(sym,kind,et):
    if kind=="eski":
        d=pickle.load(open(os.path.join(VESKI,f"{sym}.pkl"),"rb"))
        return {"15m":tuple(d["15m"][:4]),"1h":tuple(d["1h"][:4]),"4h":tuple(d["4h"][:4])}
    v=pickle.load(open(os.path.join(VD,f"{sym}__{et}.pkl"),"rb"))
    h1=pickle.load(open(os.path.join(V1,f"{sym}__{et}.pkl"),"rb"))
    return {"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":tuple(h1[:4])}

def semboller(kind,et):
    if kind=="eski": return sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{et}.pkl") and os.path.exists(os.path.join(V1,f.split('__')[0]+f"__{et}.pkl")))

SINYAL={}   # (kind,et) -> tum sinyaller
def sinyal_uret(kind,et):
    if (kind,et) in SINYAL: return SINYAL[(kind,et)]
    syms=semboller(kind,et); _A={}
    DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
    if kind=="eski": b0,b1="2021-01-01","2023-01-01"
    elif et=="2023-2024": b0,b1="2023-01-01","2025-01-01"
    else: b0,b1="2025-01-01","2026-10-01"
    bas=int(time.mktime(time.strptime(b0,"%Y-%m-%d"))*1000)
    bit=int(time.mktime(time.strptime(b1,"%Y-%m-%d"))*1000)
    tum=[]; n=0; t0=time.time()
    for s in syms:
        n+=1
        try:
            _A[s]=yukle(s,kind,et); sg,_=DT.coin_tara(s,bas,bit); tum+=sg
        except Exception: pass
        finally: _A.pop(s,None)
        if n%150==0: print(f"    {n}/{len(syms)} {len(tum)} sinyal {time.time()-t0:.0f}sn",flush=True)
    tum.sort(key=lambda x:x["t"]); SINYAL[(kind,et)]=tum
    return tum

CACHE={}
def coin(s,kind,et):
    k=(s,kind,et)
    if k not in CACHE:
        if len(CACHE)>25: CACHE.clear()
        try:
            d=yukle(s,kind,et)
            t1,h1,l1,c1=d["1h"]
            CACHE[k]=(d["15m"],(t1,atr14(h1,l1,c1)))
        except Exception: CACHE[k]=None
    return CACHE[k]

def sim(sg,kind,et,of,mult):
    para=10000.0; acik=0; n=0; kz=0; tp=para; dd=0.0
    for x in sg:
        if x["t"]<=acik: continue
        c=coin(x["s"],kind,et)
        if c is None: continue
        (t15,h15,l15,c15),(t1h,a1h)=c
        r=islem(x,t15,h15,l15,c15,t1h,a1h,of,mult)
        if r is None: continue
        p,ct=r; para*=(1+p/100); acik=ct; n+=1; kz+=1 if p>0 else 0
        tp=max(tp,para); dd=min(dd,(para/tp-1)*100)
    return para,n,kz,dd

def main():
    print(f"{'yil':>5}{'sinyal':>8}{'ay':>6}{'ATRx0.6':>34}{'ATRx2.0':>34}")
    print("-"*87)
    for yil in (2021,2022,2023,2024,2025,2026):
        kind,et=KAYNAK[yil]
        tum=sinyal_uret(kind,et)
        a=int(time.mktime(time.strptime(f"{yil}-01-01","%Y-%m-%d"))*1000)
        b=int(time.mktime(time.strptime(f"{yil+1}-01-01","%Y-%m-%d"))*1000)
        sg=[x for x in tum if a<=x["t"]<b]
        if len(sg)<15: print(f"{yil:>5}{len(sg):>8}   yetersiz"); continue
        ay=(sg[-1]["t"]-sg[0]["t"])/1000/86400/30.44
        sat=f"{yil:>5}{len(sg):>8}{ay:>6.1f}"
        for mult in (0.6,2.0):
            para,n,kz,dd=sim(sg,kind,et,3,mult)
            aa=((para/10000)**(1/ay)-1)*100 if para>0 and ay>0 else -99
            wr=100*kz/n if n else 0
            sat+=f"{f'{para:>9,.0f}$ %{aa:+6.2f} {n:>3}isl WR%{wr:.0f} dd%{dd:.0f}':>34}"
        print(sat,flush=True)

if __name__=="__main__": main()
