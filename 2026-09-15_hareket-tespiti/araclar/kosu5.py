# -*- coding: utf-8 -*-
"""YAPI CALISMASI — LL/HL + dalga2 + StochRSI (5 kova). 2021-2022, delist dahil.

NEDENSELLIK: bir salinim dibi ancak W bar SONRA onaylanir. Sinyal onay barinda
uretilir, dibin kendi barinda DEGIL. Ileriye bakma yok.
"""
import json, os, pickle, sys, time
from collections import defaultdict
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import hareket as H

W=3; HED=2.5
def ema(x,n):
    a=2/(n+1); o=np.empty(len(x)); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o

def salinim_dipleri(low, w=W):
    """dip indeksleri + ONAY indeksleri (dip+w)."""
    n=len(low); dip=[]
    for i in range(w, n-w):
        if low[i]==low[i-w:i+w+1].min() and low[i]<low[i-w:i].min() and low[i]<=low[i+1:i+w+1].min():
            dip.append(i)
    return np.array(dip,dtype=int)

def main():
    ev=json.load(open(os.path.join(KOK,"evren_2021_2022.json")))
    say=defaultdict(lambda:[0,0]); gun=defaultdict(lambda: defaultdict(list))
    t0=time.time()
    for k,s in enumerate(ev):
        try:
            with open(os.path.join(H.VERI,f"{s}.pkl"),"rb") as f: v=pickle.load(f)
            t,h,l,c,_=v["15m"]
        except Exception: continue
        if len(c)<3000: continue
        r=H.yol_sonuc(h,l,c,4,HED); ok=r>=0
        e20=ema(c,20); e50=ema(c,50)
        X=(e20>e50)&(np.roll(e20,1)<=np.roll(e50,1)); X[0]=False
        K=H.stochrsi_k(c)
        dK=np.diff(K,prepend=np.nan); oK=np.roll(dK,1); oK[0]=np.nan
        S=(dK>0)&(oK<=0)&~np.isnan(K)

        dipler=salinim_dipleri(l)
        HL=np.zeros(len(c),bool); LL=np.zeros(len(c),bool)
        for j in range(1,len(dipler)):
            onay=dipler[j]+W
            if onay>=len(c): break
            if l[dipler[j]] > l[dipler[j-1]]: HL[onay]=True
            else:                             LL[onay]=True
        # HL sonrasi 12 bar icinde dalga2 oldu mu
        HL_X=np.zeros(len(c),bool)
        xi=np.where(X)[0]
        for i in np.where(HL)[0]:
            if ((xi>=i)&(xi<=i+12)).any(): HL_X[min(i+12,len(c)-1)]=True

        kur={
          "0 TABAN": np.ones(len(c),bool),
          "LL (dusen dip)": LL,
          "HL (yukselen dip)": HL,
          "dalga2 EMA20>EMA50": X,
          "HL & 12 bar icinde dalga2": HL_X,
          "HL & StochRSI donus": HL&S,
          "dalga2 & StochRSI donus": X&S,
          "SRSI  0-20": S&(K<20), "SRSI 20-40": S&(K>=20)&(K<40),
          "SRSI 40-60": S&(K>=40)&(K<60), "SRSI 60-80": S&(K>=60)&(K<80),
          "SRSI   80+": S&(K>=80),
          "dalga2 & SRSI  0-20": X&S&(K<20), "dalga2 & SRSI 20-40": X&S&(K>=20)&(K<40),
          "dalga2 & SRSI 40-60": X&S&(K>=40)&(K<60), "dalga2 & SRSI 60-80": X&S&(K>=60)&(K<80),
          "dalga2 & SRSI   80+": X&S&(K>=80),
        }
        for ad,msk in kur.items():
            g=msk&ok
            if g.any():
                say[ad][0]+=int(r[g].sum()); say[ad][1]+=int(g.sum())
                for tt,rr in zip(t[g],r[g]): gun[ad][int(tt)//86_400_000].append(int(rr))
        if (k+1)%100==0: print(f"  {k+1}/{len(ev)} {time.time()-t0:.0f}sn",flush=True)

    print("\n"+"="*80)
    print(f"YAPI CALISMASI — +%{HED} once mi geldi (1 saat). BASABAS %54.0")
    print("2021-2022 · 399 parite · delist DAHIL · nedensel (dip onay {}bar gecikmeli)".format(W))
    print("="*80)
    print(f"{'kurulum':<28}{'isabet':>9}{'n':>12}{'bagimsiz gun':>14}{'gun ort':>9}{'t':>7}")
    for ad in kur:
        a,b=say[ad]
        if b<200: print(f"{ad:<28}{'-':>9}{b:>12,}"); continue
        gd=np.array([np.mean(x) for x in gun[ad].values()])
        se=gd.std(ddof=1)/len(gd)**0.5 if len(gd)>2 else np.nan
        tv=(gd.mean()-0.54)/se if se and se>0 else np.nan
        print(f"{ad:<28}%{a/b*100:>7.1f}{b:>12,}{len(gd):>14,}%{gd.mean()*100:>7.1f}{tv:>+7.2f}")
    json.dump({k:list(v) for k,v in say.items()}, open(os.path.join(KOK,"yapi_sonuc.json"),"w"))

if __name__=="__main__": main()
