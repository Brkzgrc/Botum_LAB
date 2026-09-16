# -*- coding: utf-8 -*-
"""KULLANICININ YONTEMI — 1. adim: aldiklarimiz yukseliyor mu? (2021-2022)"""
import json, os, pickle, sys, time
from collections import defaultdict
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import yontem as Y, hareket as H

HED=2.5           # kullanicinin "%2-3 alir cikarim"
UFUK=[(4,"1sa"),(12,"3sa"),(24,"6sa")]

def hiza(t_hedef,t_kaynak): return np.searchsorted(t_kaynak,t_hedef,side="right")-1

def main():
    evren=json.load(open(os.path.join(KOK,"evren_2021_2022.json")))
    print(f"evren: {len(evren)}\n",flush=True)
    with open(os.path.join(H.VERI,"BTCUSDT.pkl"),"rb") as f: bv=pickle.load(f)
    bt1,_,_,bc1,_=bv["1h"]; btc_ok=Y.btc_yukari(bc1)

    say=defaultdict(lambda: defaultdict(lambda:[0,0]))   # kurulum -> ufuk -> [yukari, toplam]
    sure=defaultdict(list); adet=defaultdict(int)
    m=0; t0=time.time()
    for sym in evren:
        m+=1
        try:
            with open(os.path.join(H.VERI,f"{sym}.pkl"),"rb") as f: v=pickle.load(f)
            t15,h15,l15,c15,_=v["15m"]
            if len(c15)<2000: continue
            asama,_,_,_=Y.asama_15m(c15)
            t1h,_,_,c1h,_=v["1h"]; teyit=Y.teyit_1h(c1h)
            t4h,_,_,c4h,_=v["4h"]; dikkat,taze=Y.risk_4h(c4h)
            i1=hiza(t15,t1h); i4=hiza(t15,t4h); ib=hiza(t15,bt1)
            T=np.where(i1>=0, teyit[np.clip(i1,0,None)], False)
            D=np.where(i4>=0, dikkat[np.clip(i4,0,None)], False)
            TZ=np.where(i4>=0, taze[np.clip(i4,0,None)], False)
            B=np.where(ib>=0, btc_ok[np.clip(ib,0,None)], False)
        except Exception:
            continue
        kurulumlar={
            "A (arastir)"          : asama=="A",
            "B (kesis)"            : asama=="B",
            "C (kesis+1-2)"        : asama=="C",
            "D (gec) [kontrol]"    : asama=="D",
            "B veya C"             : (asama=="B")|(asama=="C"),
            "B+C & 1h teyit"       : ((asama=="B")|(asama=="C")) & T,
            "B+C & 1h & 4h dikkat yok": ((asama=="B")|(asama=="C")) & T & ~D,
            "B & BTC yukari"       : (asama=="B") & B,
            "B+C & 1h & BTC yukari": ((asama=="B")|(asama=="C")) & T & B,
            "TAM KURAL"            : ((asama=="B")|(asama=="C")) & T & ~D & B,
            "TAM + 4h taze donus"  : ((asama=="B")|(asama=="C")) & T & ~D & B & TZ,
        }
        for K,ad in UFUK:
            r=H.yol_sonuc(h15,l15,c15,K,HED)
            sd=H.sure_dk(h15,c15,K,HED)
            for kad,msk in kurulumlar.items():
                g=msk & (r>=0)
                if g.any():
                    say[kad][ad][0]+=int(r[g].sum()); say[kad][ad][1]+=int(g.sum())
                if K==24:
                    adet[kad]+=int((msk & (r>=-1)).sum())
                    ok=msk & (sd>0)
                    if ok.any(): sure[kad].extend(sd[ok].tolist()[:200])
        if m%50==0: print(f"  {m}/{len(evren)}  {time.time()-t0:.0f}sn",flush=True)

    print("\n"+"="*94)
    print(f"+%{HED} ONCE MI GELDI (yol-farkinda, +-%{HED} simetrik) — 2021-2022, delist dahil")
    print("="*94)
    print(f"{'kurulum':<26}{'1sa':>16}{'3sa':>16}{'6sa':>16}{'sinyal/ay':>12}{'medyan dk':>11}")
    for kad in kurulumlar:
        sat=f"{kad:<26}"
        for _,ad in UFUK:
            y,t=say[kad][ad]
            sat+=f"{(f'%{y/t*100:.1f} ({t:,})' if t>=100 else '-'):>16}"
        sat+=f"{adet[kad]/24:>12.0f}"
        sat+=f"{(np.median(sure[kad]) if sure[kad] else 0):>11.0f}"
        print(sat)
    print(f"\nbasabas (komisyon %0.2, +-%{HED}): %{((HED+0.2)/(2*HED))*100:.1f}")
    json.dump({k:dict(v) for k,v in say.items()}, open(os.path.join(KOK,"yontem_sonuc.json"),"w"))

if __name__=="__main__": main()
