# -*- coding: utf-8 -*-
"""1. ADIM — "dogru ani yakaliyor muyuz?"  2021-2022, 399 parite (delist dahil)."""
import json, os, pickle, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import hareket as H

UFUKLAR = [(4,"1sa"), (12,"3sa"), (24,"6sa")]      # 15m bar sayisi
HEDEFLER= [1.0, 2.0, 3.0]
GOS     = ["RSI","MACD","SRSI","KDJ","OBV","WR"]

def hiza(t_hedef, t_kaynak):
    """t_hedef anlarinda KAPANMIS son kaynak barinin indeksi (nedensel)."""
    return np.searchsorted(t_kaynak, t_hedef, side="right") - 1

def sembol_oylari(v):
    """4 zaman dilimi icin oylar; hepsi 15m izgarasina nedensel hizalanir."""
    t15,h15,l15,c15,v15 = v["15m"]
    o = {}
    o["15m"] = H.tf_oylar(h15,l15,c15,v15)
    for tf in ("1h","4h"):
        t_,h_,l_,c_,v_ = v[tf]
        ot = H.tf_oylar(h_,l_,c_,v_)
        idx = hiza(t15, t_)
        gec = idx >= 0
        o[tf] = {g: np.where(gec, ot[g][np.clip(idx,0,None)], 0.0) for g in GOS}
    t1,h1,l1,c1,v1 = H.gunluk_turet(*v["4h"])
    if len(c1) > 60:
        ot = H.tf_oylar(h1,l1,c1,v1); idx = hiza(t15,t1); gec = idx>=0
        o["1d"] = {g: np.where(gec, ot[g][np.clip(idx,0,None)], 0.0) for g in GOS}
    else:
        o["1d"] = {g: np.zeros(len(c15)) for g in GOS}
    return o, (t15,h15,l15,c15)

def main():
    evren = json.load(open(os.path.join(KOK,"evren_2021_2022.json")))
    print(f"[1/3] hacimli veri indiriliyor ({len(evren)} parite)", flush=True)
    t0=time.time(); n=0; hazir=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for sym, v in ex.map(lambda s:(s,H.hazirla(s)), evren):
            n+=1
            if v: hazir.append(sym)
            if n%50==0: print(f"  {n}/{len(evren)}  ok:{len(hazir)}  {time.time()-t0:.0f}sn", flush=True)
    print(f"hazir: {len(hazir)}\n", flush=True)

    print("[2/3] BTC ortam oylari", flush=True)
    with open(os.path.join(H.VERI,"BTCUSDT.pkl"),"rb") as f: bv=pickle.load(f)
    bt15 = bv["15m"][0]
    btc={}
    for tf in ("1h","4h"):
        t_,h_,l_,c_,v_=bv[tf]; ot=H.tf_oylar(h_,l_,c_,v_); idx=hiza(bt15,t_)
        btc[tf]=np.where(idx>=0,sum(ot[g] for g in GOS)[np.clip(idx,0,None)],0.0)
    t1,h1,l1,c1,v1=H.gunluk_turet(*bv["4h"]); ot=H.tf_oylar(h1,l1,c1,v1); idx=hiza(bt15,t1)
    btc["1d"]=np.where(idx>=0,sum(ot[g] for g in GOS)[np.clip(idx,0,None)],0.0)
    btc_top = btc["1h"]+btc["4h"]+btc["1d"]
    print(f"  BTC toplam oy: medyan {np.median(btc_top):.2f} max {btc_top.max():.2f}\n", flush=True)

    print("[3/3] taraniyor", flush=True)
    # kova -> {hedef_ufuk: [yukari, toplam]}
    kova=defaultdict(lambda: defaultdict(lambda:[0,0]))
    tfkova=defaultdict(lambda: defaultdict(lambda:[0,0]))
    goskova=defaultdict(lambda: defaultdict(lambda:[0,0]))
    btckova=defaultdict(lambda: defaultdict(lambda:[0,0]))
    sureler=defaultdict(list)
    m=0; t1_=time.time()
    for sym in hazir:
        m+=1
        try:
            with open(os.path.join(H.VERI,f"{sym}.pkl"),"rb") as f: v=pickle.load(f)
            o,(t15,h15,l15,c15)=sembol_oylari(v)
        except Exception:
            continue
        # sadece saat basi (1h kapanisiyla ayni an) noktalarda bak
        izg=np.zeros(len(t15),dtype=bool); izg[::4]=True
        izg[:H.PENCERE*4]=False
        skor_tf={tf:sum(o[tf][g] for g in GOS) for tf in ("15m","1h","4h","1d")}
        toplam=sum(skor_tf.values())
        bidx=hiza(t15, bt15); bgec=bidx>=0
        b_top=np.where(bgec, btc_top[np.clip(bidx,0,None)], 0.0)
        for K,ad in UFUKLAR:
            for hed in HEDEFLER:
                r=H.yol_sonuc(h15,l15,c15,K,hed)
                gec=izg & (r>=0)
                if not gec.any(): continue
                anahtar=f"{hed:.0f}%/{ad}"
                s=toplam[gec]; y=r[gec]
                for lo,hi,ad2 in ((0,1,"0-1"),(1,2,"1-2"),(2,3,"2-3"),(3,4,"3-4"),(4,6,"4-6"),(6,99,"6+")):
                    msk=(s>=lo)&(s<hi)
                    if msk.any(): kova[ad2][anahtar][0]+=int(y[msk].sum()); kova[ad2][anahtar][1]+=int(msk.sum())
                kova["TUMU"][anahtar][0]+=int(y.sum()); kova["TUMU"][anahtar][1]+=int(gec.sum())
                for tf in ("15m","1h","4h","1d"):
                    st=skor_tf[tf][gec]; msk=st>=1.0
                    if msk.any(): tfkova[tf][anahtar][0]+=int(y[msk].sum()); tfkova[tf][anahtar][1]+=int(msk.sum())
                for g in GOS:
                    gs=sum(o[tf][g] for tf in ("15m","1h","4h","1d"))[gec]; msk=gs>=1.0
                    if msk.any(): goskova[g][anahtar][0]+=int(y[msk].sum()); goskova[g][anahtar][1]+=int(msk.sum())
                bb=b_top[gec]
                for lo,hi,ad2 in ((0,1,"BTC 0-1"),(1,3,"BTC 1-3"),(3,99,"BTC 3+")):
                    msk=(bb>=lo)&(bb<hi)
                    if msk.any(): btckova[ad2][anahtar][0]+=int(y[msk].sum()); btckova[ad2][anahtar][1]+=int(msk.sum())
                if hed==2.0 and K==12:
                    sd=H.sure_dk(h15,c15,K,hed)[gec]
                    sureler["yuksek_skor" if True else ""] .extend(sd[(s>=4)&(sd>0)].tolist()[:500])
        if m%50==0: print(f"  {m}/{len(hazir)}  {time.time()-t1_:.0f}sn", flush=True)

    def yaz(baslik, d):
        print(f"\n{baslik}"); 
        anah=sorted({a for v in d.values() for a in v})
        print(f"  {'':<10}"+"".join(f"{a:>12}" for a in anah))
        for k in d:
            sat=f"  {k:<10}"
            for a in anah:
                y,t=d[k].get(a,[0,0])
                sat += f"{(f'%{y/t*100:.1f}' if t>=200 else '-'):>12}"
            print(sat)
        print(f"  {'(n)':<10}"+"".join(f"{d.get('TUMU',{}).get(a,[0,0])[1]:>12,}" for a in anah))

    print("\n"+"="*80); print("SONUC — yukari hareket ONCE gelme orani"); print("="*80)
    yaz("TOPLAM SKORA GORE (4 zaman dilimi, 24 oy uzerinden)", kova)
    yaz("ZAMAN DILIMINE GORE (o dilimde skor>=1)", tfkova)
    yaz("GOSTERGEYE GORE (o gosterge 4 dilimde toplam>=1)", goskova)
    yaz("BTC ORTAMINA GORE", btckova)
    json.dump({"kova":{k:dict(v) for k,v in kova.items()},
               "tf":{k:dict(v) for k,v in tfkova.items()},
               "gos":{k:dict(v) for k,v in goskova.items()},
               "btc":{k:dict(v) for k,v in btckova.items()}},
              open(os.path.join(KOK,"hareket_sonuc.json"),"w"))
    print("\nkaydedildi: hareket_sonuc.json")

if __name__=="__main__": main()
