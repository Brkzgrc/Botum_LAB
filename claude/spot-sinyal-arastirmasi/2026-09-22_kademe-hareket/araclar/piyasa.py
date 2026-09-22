# -*- coding: utf-8 -*-
"""PIYASA BAGLAMI — coin'in kendi icinden DEGIL, disindan gelen olculer.
GPT/Multi-Timeframe calismasindaki eksen: BTC durumu + genislik (breadth).
Tum coinlerin 4h kapanislari ortak zaman izgarasina oturtulup hesaplanir.
"""
import numpy as np

def izgara(seriler):
    """seriler: {sym:(t,c)} -> ortak zaman izgarasi ve hizalanmis kapanis matrisi"""
    tum=np.unique(np.concatenate([t for t,_ in seriler.values()]))
    M=np.full((len(seriler), len(tum)), np.nan)
    for r,(t,c) in enumerate(seriler.values()):
        idx=np.searchsorted(tum,t)
        M[r,idx]=c
    return tum, M

def baglam(tum, M, btc=None):
    """M: (coin x zaman) kapanis. Doner: {ad: zaman dizisi}"""
    F={}
    def get(p):
        o=np.full_like(M,np.nan)
        o[:,p:]=M[:,p:]/M[:,:-p]-1.0
        return o
    for p,ad in ((6,"24s"),(18,"72s"),(42,"7g")):
        R=get(p)
        F[f"genislik_{ad}"]=100*np.nanmean(R>0,axis=0)        # kaci yukselmis
        F[f"piyasa_ort_{ad}"]=100*np.nanmedian(R,axis=0)      # medyan getiri
    g=F["genislik_72s"]
    d=np.full_like(g,np.nan); d[18:]=g[18:]-g[:-18]
    F["genislik_delta72"]=d
    if btc is not None:
        bt,bc=btc
        i=np.searchsorted(bt,tum,side="right")-1
        ok=i>=0
        b=np.full(len(tum),np.nan); b[ok]=bc[i[ok]]
        for p,ad in ((6,"24s"),(18,"72s"),(42,"7g")):
            o=np.full(len(tum),np.nan); o[p:]=b[p:]/b[:-p]-1.0
            F[f"btc_ret_{ad}"]=100*o
        def ema(x,n):
            a=2/(n+1); o=np.copy(x); 
            for k in range(1,len(x)):
                if np.isnan(o[k]): o[k]=o[k-1]
                else: o[k]=a*o[k]+(1-a)*o[k-1]
            return o
        for n in (20,50,200):
            e=ema(np.nan_to_num(b,nan=np.nanmean(b)),n)
            F[f"btc_ema{n}_uzaklik"]=100*(b/e-1.0)
        e50=ema(np.nan_to_num(b,nan=np.nanmean(b)),50)
        s=np.full(len(tum),np.nan); s[3:]=100*(e50[3:]/e50[:-3]-1.0)
        F["btc_ema50_egim"]=s
        # BTC RSI(14) 4h
        d1=np.diff(b,prepend=b[0]); up=np.where(d1>0,d1,0); dn=np.where(d1<0,-d1,0)
        def rma(x,n):
            o=np.copy(x)
            for k in range(1,len(x)): o[k]=(o[k-1]*(n-1)+x[k])/n
            return o
        ru=rma(np.nan_to_num(up),14); rd=rma(np.nan_to_num(dn),14)
        F["btc_rsi"]=100-100/(1+ru/np.where(rd==0,np.nan,rd))
    return F
