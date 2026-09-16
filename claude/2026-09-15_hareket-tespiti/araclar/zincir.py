# -*- coding: utf-8 -*-
"""KAPI ZINCIRI — kullanicinin gercek akisi.

1G  BTC+coin genel durum: yukselisde VEYA donus sonrasi yukselis basi
 ->4S  alim firsati: yukselis/yatay (dusus DEGIL)
   ->1S  yukselis baslangici (donus)
     ->15D  1 saati teyit  -> ALIM YERI

Her kapi bir oncekinin ICINDEN gecer. Isabet her kapidan sonra ayri olculur.
"""
import json, os, pickle, sys, time
from collections import defaultdict
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import hareket as H, yontem as Y

HED=2.5
def hiza(a,b): return np.searchsorted(b,a,side="right")-1
def ema(x,n):
    a=2/(n+1); o=np.empty(len(x)); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o
def egim(x,n=3):
    o=np.full(len(x),np.nan); k=np.arange(n)-(n-1)/2.0; pd=(k**2).sum()
    for i in range(n-1,len(x)):
        w=x[i-n+1:i+1]
        if np.isnan(w).any(): continue
        o[i]=((w-w.mean())*k).sum()/pd
    return o

def gunluk_uygun(h,l,c):
    """yukselisde VEYA donus sonrasi yukselis basi."""
    e20=ema(c,20)
    yukselisde = (c>e20)&(egim(e20)>0)
    _,_,hist=Y.macd(c)
    kesis=(hist>0)&(np.roll(hist,1)<=0); kesis[0]=False
    ki=np.where(kesis)[0]
    taze=np.zeros(len(c),bool)
    for i in range(len(c)):
        o=ki[ki<=i]
        if len(o) and (i-o[-1])<=4: taze[i]=True      # donus sonrasi yukselis BASI
    return yukselisde|taze

def dort_saat_uygun(h,l,c):
    """dusus DEGIL: yukselis ya da yatay."""
    e20=ema(c,20); e50=ema(c,50)
    return (c>=e50)|(egim(e20)>=0)

def bir_saat_donus(h,l,c):
    """yukselis baslangici: MACD B/C VEYA StochRSI 30 ustunde yukari donus."""
    as_,_,_,_=Y.asama_15m(c)                 # ayni asama mantigi, 1h serisinde
    K=H.stochrsi_k(c); dK=np.diff(K,prepend=np.nan); oK=np.roll(dK,1); oK[0]=np.nan
    S=(dK>0)&(oK<=0)&(K>=30)&~np.isnan(K)    # kullanici: "30'dan sonra manasi var"
    return ((as_=="B")|(as_=="C"))|S

def main():
    ev=json.load(open(os.path.join(KOK,"evren_2021_2022.json")))
    with open(os.path.join(H.VERI,"BTCUSDT.pkl"),"rb") as f: bv=pickle.load(f)
    bt4,bh4,bl4,bc4,_=bv["4h"]
    bg=H.gunluk_turet(bt4,bh4,bl4,bc4,bv["4h"][4])
    btc_gun_ok=gunluk_uygun(bg[1],bg[2],bg[3]); btc_gun_t=bg[0]

    say=defaultdict(lambda:[0,0]); gun=defaultdict(lambda: defaultdict(list))
    t0=time.time()
    for k,s in enumerate(ev):
        try:
            with open(os.path.join(H.VERI,f"{s}.pkl"),"rb") as f: v=pickle.load(f)
            t15,h15,l15,c15,_=v["15m"]
            if len(c15)<3000: continue
            t4,h4,l4,c4,v4=v["4h"]; t1,h1,l1,c1,_=v["1h"]
            g=H.gunluk_turet(t4,h4,l4,c4,v4)
            if len(g[3])<60: continue
        except Exception: continue
        r=H.yol_sonuc(h15,l15,c15,4,HED); ok=r>=0

        G  = gunluk_uygun(g[1],g[2],g[3]);  ig=hiza(t15,g[0])
        G  = np.where(ig>=0, G[np.clip(ig,0,None)], False)
        ib = hiza(t15,btc_gun_t)
        GB = np.where(ib>=0, btc_gun_ok[np.clip(ib,0,None)], False)
        D4 = dort_saat_uygun(h4,l4,c4); i4=hiza(t15,t4)
        D4 = np.where(i4>=0, D4[np.clip(i4,0,None)], False)
        S1 = bir_saat_donus(h1,l1,c1); i1=hiza(t15,t1)
        S1 = np.where(i1>=0, S1[np.clip(i1,0,None)], False)
        as15,_,_,_=Y.asama_15m(c15)
        K=H.stochrsi_k(c15); dK=np.diff(K,prepend=np.nan); oK=np.roll(dK,1); oK[0]=np.nan
        T15=(((as15=="B")|(as15=="C")) | ((dK>0)&(oK<=0)&(K>=30)&~np.isnan(K)))

        kapilar=[
          ("0  taban (tum barlar)",        np.ones(len(c15),bool)),
          ("1  +1G coin uygun",            G),
          ("2  +1G BTC uygun",             G&GB),
          ("3  +4S uygun",                 G&GB&D4),
          ("4  +1S donus",                 G&GB&D4&S1),
          ("5  +15D teyit = ALIM",         G&GB&D4&S1&T15),
        ]
        for ad,msk in kapilar:
            gg=msk&ok
            if gg.any():
                say[ad][0]+=int(r[gg].sum()); say[ad][1]+=int(gg.sum())
                for tt,rr in zip(t15[gg],r[gg]): gun[ad][int(tt)//86_400_000].append(int(rr))
        if (k+1)%100==0: print(f"  {k+1}/{len(ev)} {time.time()-t0:.0f}sn",flush=True)

    print("\n"+"="*86)
    print(f"KAPI ZINCIRI — +%{HED} once mi geldi (1 saat). BASABAS %54.0")
    print("2021-2022 · 399 parite · delist DAHIL")
    print("="*86)
    print(f"{'kapi':<26}{'isabet':>9}{'n':>12}{'kalan %':>9}{'gun':>7}{'gun ort':>9}{'t':>7}")
    ilk=None
    for ad,_ in kapilar:
        a,b=say[ad]
        if b<200: print(f"{ad:<26}{'-':>9}{b:>12,}"); continue
        if ilk is None: ilk=b
        gd=np.array([np.mean(x) for x in gun[ad].values()])
        se=gd.std(ddof=1)/len(gd)**0.5 if len(gd)>2 else np.nan
        tv=(gd.mean()-0.54)/se if se and se>0 else np.nan
        print(f"{ad:<26}%{a/b*100:>7.1f}{b:>12,}{b/ilk*100:>8.2f}%{len(gd):>7,}%{gd.mean()*100:>7.1f}{tv:>+7.2f}")
    json.dump({k:list(v) for k,v in say.items()},open(os.path.join(KOK,"zincir_sonuc.json"),"w"))

if __name__=="__main__": main()
