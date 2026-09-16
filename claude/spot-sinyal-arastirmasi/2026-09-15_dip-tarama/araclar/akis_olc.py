# -*- coding: utf-8 -*-
"""PARA AKISI olcumu — on kayda birebir uyar. Olcut: PARA."""
import os, pickle, sys, time
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
sys.path.insert(0,"/home/user/botum_lab/claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem
VA=os.path.join(KOK,"veri_akis"); VESKI=os.path.join(KOK,"veri")
VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h")
OZ=["1h_taker","4h_taker","1h_obv","1h_hacim","1h_mfi","4h_para_trend"]

def sma(x,n):
    c=np.cumsum(np.insert(x,0,0.0)); o=np.full(len(x),np.nan)
    o[n-1:]=(c[n:]-c[:-n])/n; return o

def akis_seri(a):
    """a=(t,h,l,c,vol,qvol,takerq) -> ozellik serileri"""
    t,h,l,c,v,q,tq=a
    taker=np.divide(tq,q,out=np.full(len(q),.5),where=q>0).clip(0,1)
    taker3=np.convolve(taker,np.ones(3)/3,mode="full")[:len(taker)]
    taker3[:2]=np.nan
    vol20=sma(v,20)
    obv=np.cumsum(np.sign(np.diff(c,prepend=c[0]))*v)
    obv6=np.full(len(c),np.nan)
    obv6[6:]=(obv[6:]-obv[:-6])
    obv_n=np.divide(obv6,vol20,out=np.full(len(c),np.nan),where=(vol20>0))
    hac=np.divide(v,vol20,out=np.full(len(c),np.nan),where=(vol20>0))
    tp=(h+l+c)/3; rmf=tp*v
    pos=np.where(np.diff(tp,prepend=tp[0])>0,rmf,0.0)
    neg=np.where(np.diff(tp,prepend=tp[0])<0,rmf,0.0)
    ps=np.convolve(pos,np.ones(14),mode="full")[:len(pos)]; ps[:13]=np.nan
    ns=np.convolve(neg,np.ones(14),mode="full")[:len(neg)]; ns[:13]=np.nan
    mfi=100-100/(1+np.divide(ps,ns,out=np.full(len(c),np.inf),where=ns>0))
    q6=np.convolve(q,np.ones(6),mode="full")[:len(q)]; q6[:5]=np.nan
    q6p=np.concatenate([np.full(6,np.nan),q6[:-6]])
    ptr=np.divide(q6,q6p,out=np.full(len(c),np.nan),where=(q6p>0))
    return {"t":t,"taker":taker3,"obv":obv_n,"hacim":hac,"mfi":mfi,"ptr":ptr}

AK={}
def akis(sym,era,itv):
    k=(sym,era,itv)
    if k not in AK:
        if len(AK)>60: AK.clear()
        try: AK[k]=akis_seri(pickle.load(open(os.path.join(VA,f"{sym}__{era}__{itv}.pkl"),"rb")))
        except Exception: AK[k]=None
    return AK[k]

def ozellikler(sym,era,ts):
    o={}
    for itv,pre in (("1h","1h"),("4h","4h")):
        A=akis(sym,era,itv)
        if A is None: return None
        i=np.searchsorted(A["t"],ts,side="right")-1
        if i<30: return None
        g=lambda k: float(A[k][i]) if i<len(A[k]) and np.isfinite(A[k][i]) else np.nan
        if pre=="1h":
            o["1h_taker"]=g("taker"); o["1h_obv"]=g("obv"); o["1h_hacim"]=g("hacim"); o["1h_mfi"]=g("mfi")
        else:
            o["4h_taker"]=g("taker"); o["4h_para_trend"]=g("ptr")
    return o if all(np.isfinite(v) for v in o.values()) else None

def yukle(sym,era):
    if era=="2021-2022":
        d=pickle.load(open(os.path.join(VESKI,f"{sym}.pkl"),"rb"))
        return {"15m":tuple(d["15m"][:4]),"1h":tuple(d["1h"][:4]),"4h":tuple(d["4h"][:4])}
    v=pickle.load(open(os.path.join(VD,f"{sym}__{era}.pkl"),"rb"))
    h1=pickle.load(open(os.path.join(V1,f"{sym}__{era}.pkl"),"rb"))
    return {"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":tuple(h1[:4])}

def semboller(era):
    if era=="2021-2022": return sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{era}.pkl") and os.path.exists(os.path.join(V1,f.split('__')[0]+f"__{era}.pkl")))

C={}
def coin(s,era):
    k=(s,era)
    if k not in C:
        if len(C)>25: C.clear()
        try:
            d=yukle(s,era); t1,h1,l1,c1=d["1h"]
            C[k]=(d["15m"],(t1,atr14(h1,l1,c1)))
        except Exception: C[k]=None
    return C[k]

def sim(sg,era):
    para=10000.0; acik=0; n=0; kz=0; tp=para; dd=0.0
    for x in sg:
        if x["t"]<=acik: continue
        c=coin(x["s"],era)
        if c is None: continue
        (t15,h15,l15,c15),(t1h,a1h)=c
        r=islem(x,t15,h15,l15,c15,t1h,a1h,3,0.6)
        if r is None: continue
        p,ct=r; para*=(1+p/100); acik=ct; n+=1; kz+=1 if p>0 else 0
        tp=max(tp,para); dd=min(dd,(para/tp-1)*100)
    return para,n,kz,dd

def donem(era,b0,b1):
    syms=semboller(era); _A={}
    DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
    bas=int(time.mktime(time.strptime(b0,"%Y-%m-%d"))*1000)
    bit=int(time.mktime(time.strptime(b1,"%Y-%m-%d"))*1000)
    tum=[]; n=0; t0=time.time()
    for s in syms:
        n+=1
        try:
            _A[s]=yukle(s,era); sg,_=DT.coin_tara(s,bas,bit); tum+=sg
        except Exception: pass
        finally: _A.pop(s,None)
        if n%150==0: print(f"    {n}/{len(syms)} {len(tum)} sinyal {time.time()-t0:.0f}sn",flush=True)
    tum.sort(key=lambda x:x["t"])
    # ozellikleri ekle
    iyi=[]
    for x in tum:
        o=ozellikler(x["s"],era,x["t"])
        if o: x["oz"]=o; iyi.append(x)
    print(f"  {era}: {len(tum)} sinyal, akis verisi olan {len(iyi)}",flush=True)
    if len(iyi)<40: return
    ay=(iyi[-1]["t"]-iyi[0]["t"])/1000/86400/30.44
    p,n2,kz,dd=sim(iyi,era)
    aa=((p/10000)**(1/ay)-1)*100 if p>0 else -99
    print(f"\n  TABAN (filtresiz): {p:>9,.0f}$  %{aa:+.2f}/ay  {n2} isl  WR%{100*kz/n2 if n2 else 0:.0f}  dd%{dd:.0f}")
    print(f"  {'ozellik':<15}{'medyan':>9}{'UST YARI':>32}{'ALT YARI':>32}")
    for k in OZ:
        vals=np.array([x["oz"][k] for x in iyi]); med=np.median(vals)
        sat=f"  {k:<15}{med:>9.3f}"
        for ust in (True,False):
            sub=[x for x in iyi if (x["oz"][k]>=med if ust else x["oz"][k]<med)]
            if len(sub)<10: sat+=f"{'-':>32}"; continue
            a2=(sub[-1]["t"]-sub[0]["t"])/1000/86400/30.44
            p2,m,kz2,dd2=sim(sub,era)
            r2=((p2/10000)**(1/a2)-1)*100 if p2>0 and a2>0 else -99
            sat+=f"{f'{p2:>9,.0f}$ %{r2:+6.2f} {m:>3}isl WR%{100*kz2/m if m else 0:.0f}':>32}"
        print(sat,flush=True)

if __name__=="__main__":
    for era,b0,b1 in (("2021-2022","2021-01-01","2023-01-01"),
                      ("2023-2024","2023-01-01","2025-01-01"),
                      ("2025-2026","2025-01-01","2026-10-01")):
        print(f"\n{'='*95}\n{era}\n{'='*95}",flush=True)
        donem(era,b0,b1)
