# -*- coding: utf-8 -*-
"""Ofset uygulanirken stop ve TP1 de kaymali mi? Dort tasarim, dort donem. Olcut: PARA."""
import os, json, pickle, sys, time
import numpy as np
sys.path.insert(0,"."); sys.path.insert(0,"/home/user/botum_lab/claude/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14
from akis_olc2 import band
KOM=0.2; DOLUM=24; EXP=24
V19="veri_2019"; VESKI="veri"; VD="veri_dogrulama"; V1="veri_1h"

def islem2(s,t15,h15,l15,c15,t1h,a1h,of,sof,tof,mult=0.6):
    """of=giris ofseti, sof=stop ofseti, tof=tp1 ofseti (hepsi % asagi)"""
    i0=np.searchsorted(t15,s["t"],side="left")
    if i0>=len(c15)-4: return None
    g=s["giris"]*(1-of/100); stop=s["stop"]*(1-sof/100); tp1=s["tp1"]*(1-tof/100)
    if g<=stop or tp1<=g: return None
    dol=None; son=s["t"]+DOLUM*3600_000
    for i in range(i0,len(c15)):
        if t15[i]>son: break
        if l15[i]<=g: dol=i; break
    if dol is None: return None
    lim=t15[dol]+EXP*3600_000; zir=g; tp=False
    for j in range(dol+1,len(c15)):
        if not tp:
            if l15[j]<=stop: return (stop/g-1)*100-KOM,int(t15[j])
            if h15[j]>=tp1: tp=True; zir=max(zir,h15[j])
            elif t15[j]>=lim: return (c15[j]/g-1)*100-KOM,int(t15[j])
        if tp:
            zir=max(zir,h15[j])
            k=np.searchsorted(t1h,t15[j],side="right")-1
            a=a1h[k] if 0<=k<len(a1h) and not np.isnan(a1h[k]) else g*0.02
            tr=max(g,zir-a*mult)
            if c15[j]<=tr: return (tr/g-1)*100-KOM,int(t15[j])
    return (c15[-1]/g-1)*100-KOM,int(t15[-1])

def yukle(s,era):
    if era=="2019-2020":
        return {i:tuple(pickle.load(open(os.path.join(V19,f"{s}__{i}.pkl"),"rb"))[:4]) for i in ("15m","1h","4h")}
    if era=="2021-2022":
        d=pickle.load(open(os.path.join(VESKI,f"{s}.pkl"),"rb"))
        return {k:tuple(d[k][:4]) for k in ("15m","1h","4h")}
    v=pickle.load(open(os.path.join(VD,f"{s}__{era}.pkl"),"rb"))
    h1=pickle.load(open(os.path.join(V1,f"{s}__{era}.pkl"),"rb"))
    return {"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":tuple(h1[:4])}

def semboller(era):
    if era=="2019-2020":
        s={f.split("__")[0] for f in os.listdir(V19)}
        return sorted(x for x in s if all(os.path.exists(os.path.join(V19,f"{x}__{i}.pkl")) for i in ("15m","1h","4h")))
    if era=="2021-2022": return sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{era}.pkl") and os.path.exists(os.path.join(V1,f.split('__')[0]+f"__{era}.pkl")))

TASARIM=[("ofsetsiz",       0,0,0),
         ("MEVCUT: giris-3, stop sabit, tp1 sabit", 3,0,0),
         ("stop da kayar (tp1 sabit)",              3,3,0),
         ("HEPSI kayar (giris+stop+tp1 -3)",        3,3,3)]

def main():
    for era,b0,b1 in (("2019-2020","2019-01-01","2021-01-01"),
                      ("2021-2022","2021-01-01","2023-01-01"),
                      ("2023-2024","2023-01-01","2025-01-01"),
                      ("2025-2026","2025-01-01","2026-10-01")):
        syms=semboller(era); _A={}
        DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
        bas=int(time.mktime(time.strptime(b0,"%Y-%m-%d"))*1000)
        bit=int(time.mktime(time.strptime(b1,"%Y-%m-%d"))*1000)
        sonuc={ad:[] for ad,*_ in TASARIM}; n=0; t0=time.time()
        for s in syms:
            n+=1
            try:
                d=yukle(s,era); _A[s]=d
                sg,_=DT.coin_tara(s,bas,bit)
                if sg:
                    t1,h1,l1,c1=d["1h"]; a1h=atr14(h1,l1,c1)
                    t15,h15,l15,c15=d["15m"]
                    for x in sg:
                        for ad,of,sof,tof in TASARIM:
                            r=islem2(x,t15,h15,l15,c15,t1,a1h,of,sof,tof)
                            if r: sonuc[ad].append((int(x["t"]),float(r[0]),int(r[1])))
            except Exception: pass
            finally: _A.pop(s,None)
            if n%150==0: print(f"    {era} {n}/{len(syms)}  {time.time()-t0:.0f}sn",flush=True)
        print(f"\n{'='*92}\n{era}\n{'='*92}",flush=True)
        rng=np.random.default_rng(42)
        for ad,*_ in TASARIM:
            L=sorted(sonuc[ad])
            if len(L)<20: print(f"  {ad:<42} yetersiz ({len(L)})"); continue
            ay=(L[-1][0]-L[0][0])/1000/86400/30.44
            r=band(L,rng)
            wr=100*np.mean([1 if p>0 else 0 for _,p,_ in L])
            print(f"  {ad:<42}{r[1]:>10,.0f}$ %{((r[1]/10000)**(1/ay)-1)*100:+6.2f}/ay  ort {r[3]:>3.0f} isl  dolan {len(L):>3}  WR %{wr:.0f}",flush=True)

if __name__=="__main__": main()
