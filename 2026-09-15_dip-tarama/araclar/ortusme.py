# -*- coding: utf-8 -*-
"""CANLI scanner ile DIP TARAMA ayni sinyalleri mi yakaliyor? Olcum."""
import os, pickle, sys, time
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
sys.path.insert(0,"/home/user/botum_lab/2026-09-15_dip-tarama")
import dip_tarama as DT
VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h")
ET=sys.argv[1] if len(sys.argv)>1 else "2025-2026"
MIN_Q=72.0

def ema(x,n):
    a=2/(n+1); o=np.empty_like(x); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o
def rma(x,n):
    a=1/n; o=np.full(len(x),np.nan)
    if len(x)<n: return o
    o[n-1]=x[:n].mean()
    for i in range(n,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o
def rsi(c,n=14):
    d=np.diff(c,prepend=c[0]); g=np.clip(d,0,None); l=np.clip(-d,0,None)
    ag=ema_w(g,n); al=ema_w(l,n)
    rs=np.divide(ag,al,out=np.full(len(c),np.inf),where=al>0)
    return np.where(np.isnan(ag),50.0,100-100/(1+rs))
def ema_w(x,n):   # pandas ewm(alpha=1/n, min_periods=n)
    a=1/n; o=np.full(len(x),np.nan); s=0.0
    for i in range(len(x)):
        s=x[i]*a+s*(1-a) if i else x[i]
        if i>=n-1: o[i]=s
    return o
def roll(x,n,fn):
    o=np.full(len(x),np.nan)
    for i in range(n-1,len(x)): o[i]=fn(x[i-n+1:i+1])
    return o
def sma(x,n):
    c=np.cumsum(np.insert(np.nan_to_num(x),0,0.0)); o=np.full(len(x),np.nan)
    o[n-1:]=(c[n:]-c[:-n])/n; return o
def rollmax(x,n): return roll(x,n,np.max)
def rollmin(x,n): return roll(x,n,np.min)

def olcum(t,h,l,c,v):
    """canli scanner'in snap() ciktisinin seri hali"""
    n=len(c); o=np.empty(n); o[0]=c[0]; o[1:]=c[:-1]      # open ~ onceki kapanis
    r=rsi(c); lo=rollmin(r,14); hi=rollmax(r,14)
    rng=np.where((hi-lo)==0,np.nan,hi-lo)
    raw=100*(r-lo)/rng
    k=np.nan_to_num(sma(raw,3),nan=50.0); d=np.nan_to_num(sma(k,3),nan=50.0)
    e12=ema(c,12); e26=ema(c,26); macd=e12-e26; sig=ema(macd,9); hist=macd-sig
    obv=np.cumsum(np.sign(np.diff(c,prepend=c[0]))*v)
    e20=ema(c,20); e50=ema(c,50)
    rg=np.maximum(h-l,0); mx=np.maximum(o,c)
    upw=np.where(rg>0,(h-mx)/rg,0.0)
    def pc(a,b): return np.where(b!=0,(a/b-1)*100,0.0)
    sh=lambda a,k_: np.concatenate([np.full(k_,np.nan),a[:-k_]])
    hc6=np.zeros(n); hl6=np.zeros(n)
    for i in range(1,6):
        hc6[i:]+= (c[i:]>c[:-i] if i==1 else 0)
    # higher_closes6 = son 6 kapanisin ardisik artis sayisi
    up=np.zeros(n); up[1:]=(c[1:]>c[:-1]).astype(float)
    upl=np.zeros(n); upl[1:]=(l[1:]>=l[:-1]).astype(float)
    hc6=roll(up,5,np.sum); hl6=roll(upl,5,np.sum)
    return {"t":t,"p":c,"h":h,"l":l,"e20":e20,"e50":e50,"rsi":r,"k":k,"d":d,
      "kprev":sh(k,1),"kmin3":rollmin(k,3),"hist":hist,"histprev":sh(hist,1),
      "obv3":np.concatenate([np.full(2,np.nan),obv[:-2]]),"obv":obv,
      "e20s":pc(e20,sh(e20,3)),"e50s":pc(e50,sh(e50,3)),
      "de20":pc(c,e20),"de50":pc(c,e50),"ret3":pc(c,sh(c,3)),
      "hc6":hc6,"hl6":hl6,"nh20":np.maximum(0,-pc(c,rollmax(h,20))),
      "ph6":sh(rollmax(h,6),1),"upw":upw}

def gunluk(t4,h4,l4,c4,v4):
    """4h -> 1d (UTC 00:00 kapanisli)"""
    gun=(t4+1)//86400000
    idx=np.where(np.diff(gun,append=gun[-1]+1)!=0)[0]
    t=[];h=[];l=[];c=[];v=[]; s=0
    for e in idx:
        t.append(t4[e]); h.append(h4[s:e+1].max()); l.append(l4[s:e+1].min())
        c.append(c4[e]); v.append(v4[s:e+1].sum()); s=e+1
    return (np.array(t),np.array(h),np.array(l),np.array(c),np.array(v))

def at(m,i):
    return {kk:(m[kk][i] if i<len(m[kk]) else np.nan) for kk in m}

def canli_sinyaller(sym):
    try:
        vv=pickle.load(open(os.path.join(VD,f"{sym}__{ET}.pkl"),"rb"))
        h1=pickle.load(open(os.path.join(V1,f"{sym}__{ET}.pkl"),"rb"))
    except Exception: return []
    t15,h15,l15,c15,v15=vv["15m"]; t4,h4,l4,c4,v4=vv["4h"]
    if len(t15)<400 or len(t4)<300: return []
    m15=olcum(t15,h15,l15,c15,v15); m4=olcum(t4,h4,l4,c4,v4)
    if len(h1)==4: t1,h1a,l1a,c1a=h1; v1a=np.ones(len(t1))
    else: t1,h1a,l1a,c1a,v1a=h1
    if len(t1)<300: return []
    m1=olcum(t1,h1a,l1a,c1a,v1a)
    td,hd,ld,cd,vd=gunluk(t4,h4,l4,c4,v4)
    if len(td)<220: return []
    md=olcum(td,hd,ld,cd,vd)
    out=[]
    for i in range(400,len(t15)):
        ts=t15[i]
        j1=np.searchsorted(t1,ts,side="right")-1
        j4=np.searchsorted(t4,ts,side="right")-1
        jd=np.searchsorted(td,ts,side="right")-1
        if j1<60 or j4<60 or jd<220: continue
        F=at(m15,i); O=at(m1,j1); Q=at(m4,j4); D=at(md,jd)
        if np.isnan(Q["k"]) or np.isnan(O["k"]) or np.isnan(D["rsi"]): continue
        day_trend = D["p"]>=D["e20"] and D["e20s"]>=-.8 and D["rsi"]>=50
        four_trend= Q["p"]>=Q["e50"] and Q["e50s"]>=-.2 and Q["rsi"]>=45
        if not (day_trend and four_trend): continue
        one_struct= O["p"]>=O["e50"] and O["rsi"]>=38
        one_reset = O["k"]<=75 or O["kmin3"]<=30
        one_turn  = O["k"]>O["d"] and O["k"]>O["kprev"]
        one_mom   = O["hist"]>O["histprev"] or O["obv"]>=O["obv3"] or one_turn
        a=int(Q["de50"]>=6.0)+int(Q["e20s"]>=1.0)+int(O["de50"]>=2.0)+ \
          int(O["upw"]>=0.22)+int(O["k"]<=75.0)+int(D["rsi"]>=62.0)
        bal=day_trend and four_trend and one_struct and a>=5
        strict=day_trend and four_trend and Q["de50"]>=6.0 and O["de50"]>=2.0 and O["upw"]>=0.22 and O["k"]<=75.0
        ft=F["k"]>F["d"] and F["k"]>F["kprev"] and F["rsi"]>=40
        fc=ft and (F["hist"]>F["histprev"] or F["obv"]>=F["obv3"]) and F["p"]>=F["e20"]*.995
        press=day_trend and four_trend and a>=4 and O["p"]>=O["e20"] and O["e20s"]>0 and \
              O["rsi"]>=50 and O["hc6"]>=3 and O["hl6"]>=3 and O["nh20"]<=4.5
        fb=F["p"]>=F["ph6"]*.998 and F["rsi"]>=48 and (F["hist"]>F["histprev"] or F["obv"]>=F["obv3"])
        retr=bal and one_reset
        sb=(D["p"]<D["e50"] and Q["p"]<Q["e50"]) or (Q["p"]<Q["e50"] and O["p"]<O["e50"] and Q["e50s"]<0)
        bo=O["ret3"]>14 and O["k"]>85 and O["de20"]>15
        if sb or bo: continue
        q =32+a*8+(8 if one_turn else 0)+(7 if one_mom else 0)+(8 if fc else 0)+(8 if strict else 0)
        pq=24+a*8+(20 if press else 0)+(16 if fb else 0)
        qual=max(q if retr else 0, pq if press else 0); qual=max(0,min(100,qual))
        if qual>=MIN_Q and ((retr and one_mom and fc) or (press and fb)):
            out.append((int(ts),float(F["p"])))
    # ayni coinde 24 saat tekrar yok (dip taramayla ayni kural)
    ded=[]; son=-1
    for ts,p in out:
        if ts-son>=24*3600_000: ded.append((ts,p)); son=ts
    return ded

def main():
    syms=[f.split("__")[0] for f in os.listdir(VD) if f.endswith(f"__{ET}.pkl")]
    syms=[s for s in syms if os.path.exists(os.path.join(V1,f"{s}__{ET}.pkl"))]
    print(f"{ET} — {len(syms)} coin",flush=True)
    # 1) DIP sinyalleri
    _A={}
    DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
    y0=int(ET[:4]); y1=int(ET[5:])
    bas=int(time.mktime(time.strptime(f"{y0}-01-01","%Y-%m-%d"))*1000)
    bit=int(time.mktime(time.strptime(f"{min(y1+1,2026)}-{'10' if y1==2026 else '01'}-01","%Y-%m-%d"))*1000)
    dip={}; canli={}; n=0; t0=time.time()
    for s in syms:
        n+=1
        try:
            v=pickle.load(open(os.path.join(VD,f"{s}__{ET}.pkl"),"rb"))
            h1=pickle.load(open(os.path.join(V1,f"{s}__{ET}.pkl"),"rb"))
            _A[s]={"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":h1}
            sg,_=DT.coin_tara(s,bas,bit)
            if sg: dip[s]=[int(x["t"]) for x in sg]
        except Exception: pass
        finally: _A.pop(s,None)
        try:
            cs=canli_sinyaller(s)
            if cs: canli[s]=[ts for ts,_ in cs]
        except Exception: pass
        if n%100==0: print(f"  {n}/{len(syms)}  dip:{sum(len(x) for x in dip.values())} canli:{sum(len(x) for x in canli.values())}  {time.time()-t0:.0f}sn",flush=True)
    nd=sum(len(x) for x in dip.values()); nc=sum(len(x) for x in canli.values())
    print(f"\nDIP  sinyal: {nd}  ({len(dip)} coin)")
    print(f"CANLI sinyal: {nc}  ({len(canli)} coin)")
    ortak_coin=set(dip)&set(canli)
    print(f"Ikisinde de sinyal veren coin: {len(ortak_coin)}")
    for pen in (4,12,24,48):
        es=0; W=pen*3600_000
        for s in ortak_coin:
            ca=np.array(sorted(canli[s]))
            for ts in dip[s]:
                if len(ca) and np.min(np.abs(ca-ts))<=W: es+=1
        print(f"  +-{pen:>2} saat icinde ayni coinde her ikisi de: {es}  (dip sinyallerinin %{100*es/nd:.1f}'i)")
    import json
    json.dump({"dip":dip,"canli":canli},open(os.path.join(KOK,f"ortusme_{ET}.json"),"w"))

if __name__=="__main__": main()
