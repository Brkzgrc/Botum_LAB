# -*- coding: utf-8 -*-
"""KULLANICININ TAM YONTEMI — MACD yapi + StochRSI an + EMA destekleyiciler."""
import json, os, pickle, sys, time
from collections import defaultdict
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import yontem as Y, hareket as H

HED=2.5; UFUK=[(4,"1sa"),(12,"3sa"),(24,"6sa")]
def hiza(a,b): return np.searchsorted(b,a,side="right")-1
def ema(x,n):
    a=2/(n+1); o=np.empty(len(x)); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o

def main():
    evren=json.load(open(os.path.join(KOK,"evren_2021_2022.json")))
    with open(os.path.join(H.VERI,"BTCUSDT.pkl"),"rb") as f: bv=pickle.load(f)
    bt1=bv["1h"][0]; btc_ok=Y.btc_yukari(bv["1h"][3])
    say=defaultdict(lambda: defaultdict(lambda:[0,0])); adet=defaultdict(int)
    m=0; t0=time.time()
    for sym in evren:
        m+=1
        try:
            with open(os.path.join(H.VERI,f"{sym}.pkl"),"rb") as f: v=pickle.load(f)
            t15,h15,l15,c15,_=v["15m"]
            if len(c15)<2000: continue
            asama,_,_,_=Y.asama_15m(c15)
            K=H.stochrsi_k(c15)
            dK=np.diff(K,prepend=np.nan); oK=np.roll(dK,1); oK[0]=np.nan
            S=(dK>0)&(oK<=0)&~np.isnan(K)                      # StochRSI yukari dondu
            e20=ema(c15,20); e50=ema(c15,50)
            P20=(c15>e20)&(np.roll(c15,1)<=np.roll(e20,1)); P20[0]=False   # fiyat EMA20'yi kirdi
            de20=np.diff(e20,prepend=np.nan)
            E=(e20<e50)&(de20>0)                               # ema20<ema50 ve yukari donuyor
            t1h=v["1h"][0]; T=Y.teyit_1h(v["1h"][3])
            t4h=v["4h"][0]; D,_=Y.risk_4h(v["4h"][3])
            i1=hiza(t15,t1h); i4=hiza(t15,t4h); ib=hiza(t15,bt1)
            T=np.where(i1>=0,T[np.clip(i1,0,None)],False)
            D=np.where(i4>=0,D[np.clip(i4,0,None)],False)
            B=np.where(ib>=0,btc_ok[np.clip(ib,0,None)],False)
        except Exception: continue
        BC=(asama=="B")|(asama=="C")
        kur={
          "0 taban (tum barlar)"      : np.ones(len(c15),bool),
          "MACD B+C"                  : BC,
          "StochRSI donus (tek basina)": S,
          "  SRSI donus  0-20"        : S&(K<20),
          "  SRSI donus 20-50"        : S&(K>=20)&(K<50),
          "  SRSI donus 50-80"        : S&(K>=50)&(K<80),
          "  SRSI donus   80+"        : S&(K>=80),
          "fiyat EMA20 kirdi"         : P20,
          "EMA20<50 & yukari"         : E,
          "MACD B+C & SRSI donus"     : BC&S,
          "MACD B+C & SRSI 0-20"      : BC&S&(K<20),
          "MACD B+C & SRSI & EMA20kir": BC&S&P20,
          "MACD B+C & SRSI & 1h teyit": BC&S&T,
          "TAM (BC+SRSI+1h+4h+BTC)"   : BC&S&T&~D&B,
          "TAM & EMA20 kirdi"         : BC&S&T&~D&B&P20,
        }
        for Kb,ad in UFUK:
            r=H.yol_sonuc(h15,l15,c15,Kb,HED)
            for kad,msk in kur.items():
                g=msk&(r>=0)
                if g.any(): say[kad][ad][0]+=int(r[g].sum()); say[kad][ad][1]+=int(g.sum())
                if Kb==24: adet[kad]+=int(msk.sum())
        if m%50==0: print(f"  {m}/{len(evren)} {time.time()-t0:.0f}sn",flush=True)

    print("\n"+"="*88)
    print(f"+%{HED} ONCE MI GELDI — 2021-2022, 399 parite (delist dahil).  BASABAS %54.0")
    print("="*88)
    print(f"{'kurulum':<30}{'1sa':>17}{'3sa':>17}{'sinyal/ay':>12}")
    for kad in kur:
        s=f"{kad:<30}"
        for _,ad in UFUK[:2]:
            y,t=say[kad][ad]
            s+=f"{(f'%{y/t*100:.1f} ({t:,})' if t>=300 else '-'):>17}"
        s+=f"{adet[kad]/24:>12,.0f}"
        print(s)
    json.dump({k:dict(v) for k,v in say.items()},open(os.path.join(KOK,"yontem2.json"),"w"))

if __name__=="__main__": main()
