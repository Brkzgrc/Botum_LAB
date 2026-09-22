# -*- coding: utf-8 -*-
"""Tablo + PIYASA BAGLAMI (BTC durumu + genislik)."""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donus, ozellik4h, ayrisma, piyasa, kos2, topla as T

if __name__=="__main__":
    era=sys.argv[1]; N=int(sys.argv[2]); lim=int(sys.argv[3]) if len(sys.argv)>3 else 0
    syms=kos2.semboller(era)
    if lim: syms=syms[:lim]
    t0=time.time()
    # 1) piyasa izgarasi
    ser={}
    for s in syms:
        try:
            t,h,l,c,v=T.dort_saat(s,era)
            if len(t)>=280: ser[s]=(t,c)
        except Exception: pass
    btc=ser.get("BTCUSDT")
    tum,M=piyasa.izgara(ser)
    PB=piyasa.baglam(tum,M,btc)
    PAD=sorted(PB)
    print(f"piyasa izgarasi: {len(ser)} coin · {len(tum)} zaman · {len(PAD)} baglam olcusu · {time.time()-t0:.0f}sn", flush=True)
    # 2) sinyaller
    AD=None; X=[]; P=[]; C=[]; TS=[]
    for n,s in enumerate(syms,1):
        try: t,h,l,c,v=T.dort_saat(s,era)
        except Exception: continue
        if len(t)<280: continue
        _,say,_=donus.sartlar(h,l,c,v)
        F=ozellik4h.ozellikler(t,h,l,c); F.update(ayrisma.ayrisma_ozellikleri(h,l,c,v))
        if AD is None: AD=sorted(F)+PAD
        Mx=np.column_stack([F[a] for a in sorted(F)])
        gi=np.searchsorted(tum,t)     # bu coinin barlarinin izgaradaki yeri
        sonr=-10**9
        for i in range(210,len(t)-8):
            if say[i]<N or i-sonr<T.SOGUMA: continue
            sonr=i; g=float(c[i])
            sh=h[i+1:i+1+T.UFUK]; sl=l[i+1:i+1+T.UFUK]; sc=c[i+1:i+1+T.UFUK]
            if len(sh)<12: continue
            rmax=np.maximum.accumulate(sh)/g-1.0; rmin=np.minimum.accumulate(sl)/g-1.0
            tepe_i=int(np.argmax(sh))
            sat=[float(np.max(sh)/g-1.0), float(tepe_i+1), float(np.min(sl[:tepe_i+1])/g-1.0),
                 float(np.min(sl)/g-1.0), float(len(sh))]
            sat+=[float(rmax[min(k,len(rmax))-1]) for k in T.KLER]
            sat+=[float(rmin[min(k,len(rmin))-1]) for k in T.KLER]
            sat+=[float(sc[min(k,len(sc))-1]/g-1.0) for k in T.KLER]
            X.append(np.concatenate([Mx[i], [PB[a][gi[i]] for a in PAD]]))
            P.append(sat); C.append(s); TS.append(int(t[i]))
        if n%100==0: print(f"  {n}/{len(syms)}  {len(X):,} sinyal  {time.time()-t0:.0f}sn", flush=True)
    sut=["tepe","tepe_bar","mae_tepeye_kadar","en_dip","bar_sayisi"]
    sut+=[f"tepe_k{k}" for k in T.KLER]+[f"dip_k{k}" for k in T.KLER]+[f"kap_k{k}" for k in T.KLER]
    np.savez_compressed(f"tablo2_{era}_N{N}.npz", ad=np.array(AD), sut=np.array(sut),
                        X=np.array(X,float), P=np.array(P,float), C=np.array(C), T=np.array(TS))
    print(f"{era} N>={N}: {len(X):,} sinyal · {len(AD)} olcu · {len(set(C))} coin · {time.time()-t0:.0f}sn")
