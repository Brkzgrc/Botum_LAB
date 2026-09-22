# -*- coding: utf-8 -*-
"""4h sinyal tablosu — SONUC OLARAK ISABET DEGIL BUYUKLUK kaydedilir.

Her sinyal icin ileriye donuk yolun ozeti saklanir; cikis kurali SONRADAN
bu tablodan secilir. Boylece 'kac bar bekle' gibi sayilar tahminle degil
olcumle belirlenir.
"""
import os, sys, pickle, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donus, ozellik4h, ayrisma, kos2

UFUK=168          # 28 gun (4h bar)
SOGUMA=6          # 24 saat
KLER=[1,2,3,6,12,24,42,84,168]   # 4sa,8sa,12sa,1g,2g,4g,1hf,2hf,4hf

def dort_saat(s, era):
    if era=="2021-2022":
        d=pickle.load(open(f"{kos2.VESKI}/{s}.pkl","rb")); k=d["4h"]
        return k[0],k[1],k[2],k[3],None
    a15,a1,a4=kos2.yukle(s,era); return a4

def topla(era, syms, N):
    AD=None; X=[]; P=[]; C=[]; T=[]
    for s in syms:
        try: t,h,l,c,v=dort_saat(s,era)
        except Exception: continue
        if len(t)<280: continue
        _,say,_=donus.sartlar(h,l,c,v)
        F=ozellik4h.ozellikler(t,h,l,c)
        F.update(ayrisma.ayrisma_ozellikleri(h,l,c,v))
        if AD is None: AD=sorted(F)
        M=np.column_stack([F[a] for a in AD])
        sonr=-10**9
        for i in range(210,len(t)-8):
            if say[i]<N or i-sonr<SOGUMA: continue
            sonr=i; g=float(c[i])
            sh=h[i+1:i+1+UFUK]; sl=l[i+1:i+1+UFUK]; sc=c[i+1:i+1+UFUK]
            if len(sh)<12: continue
            rmax=np.maximum.accumulate(sh)/g-1.0
            rmin=np.minimum.accumulate(sl)/g-1.0
            tepe_i=int(np.argmax(sh))                    # tepenin kacinci bar oldugu
            mae_once=float(np.min(sl[:tepe_i+1])/g-1.0)  # tepeye kadarki en kotu cekilme
            sat=[float(np.max(sh)/g-1.0), float(tepe_i+1), mae_once,
                 float(np.min(sl)/g-1.0), float(len(sh))]
            sat+=[float(rmax[min(k,len(rmax))-1]) for k in KLER]   # k bar sonra tepe
            sat+=[float(rmin[min(k,len(rmin))-1]) for k in KLER]   # k bar sonra dip
            sat+=[float(sc[min(k,len(sc))-1]/g-1.0)    for k in KLER]   # k bar sonra kapanis
            X.append(M[i]); P.append(sat); C.append(s); T.append(int(t[i]))
    sut=["tepe","tepe_bar","mae_tepeye_kadar","en_dip","bar_sayisi"]
    sut+= [f"tepe_k{k}" for k in KLER]+[f"dip_k{k}" for k in KLER]+[f"kap_k{k}" for k in KLER]
    return AD, sut, np.array(X,float), np.array(P,float), np.array(C), np.array(T)

if __name__=="__main__":
    era=sys.argv[1]; N=int(sys.argv[2]); lim=int(sys.argv[3]) if len(sys.argv)>3 else 0
    syms=kos2.semboller(era)
    if lim: syms=syms[:lim]
    t0=time.time()
    AD,SUT,X,P,C,T=topla(era,syms,N)
    np.savez_compressed(f"tablo_{era}_N{N}.npz", ad=np.array(AD), sut=np.array(SUT),
                        X=X, P=P, C=C, T=T)
    print(f"{era} N>={N}: {len(X):,} sinyal · {len(AD)} olcu · {len(set(C))} coin · {time.time()-t0:.0f}sn")
