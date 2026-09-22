# -*- coding: utf-8 -*-
"""GOSTERGELER ARASI AYRISMA — kullanicinin fikri.
'Bazi gostergeler yukselirken su gosterge dusus baslatiyorsa bu sinyal kayba
yol aciyor olabilir.' Her gostergenin KENDI yonu ayri cikarilir."""
import numpy as np
import donus

def _yon(x, n):
    o=np.zeros(len(x))
    o[n:]=np.sign(x[n:]-x[:-n])
    return o

def ayrisma_ozellikleri(h,l,c,v=None):
    s,say,ek = donus.sartlar(h,l,c,v)
    seri = {"rsi":ek["rsi"], "stochrsi":ek["K"], "macd":ek["hist"],
            "kdj":ek["kdjK"], "wr":ek["wr"]}
    if "obv" in ek: seri["obv"]=ek["obv"]
    F={}
    y1=[]; y3=[]
    for ad,x in seri.items():
        a=_yon(np.nan_to_num(x),1); b=_yon(np.nan_to_num(x),3)
        F[f"yon1_{ad}"]=a; F[f"yon3_{ad}"]=b
        y1.append(a); y3.append(b)
    Y1=np.array(y1); Y3=np.array(y3); k=len(y1)
    F["yukari_sayisi_1"]=(Y1>0).sum(axis=0)          # kaci yukari
    F["yukari_sayisi_3"]=(Y3>0).sum(axis=0)
    F["asagi_sayisi_1"] =(Y1<0).sum(axis=0)          # kaci ASAGI (ayrisan)
    F["asagi_sayisi_3"] =(Y3<0).sum(axis=0)
    F["uyum_1"]=np.abs(Y1.sum(axis=0))/k             # 1 = hepsi ayni yonde
    F["uyum_3"]=np.abs(Y3.sum(axis=0))/k
    # TAM UYUM: hepsi yukari mi
    F["hepsi_yukari_1"]=((Y1>0).sum(axis=0)==k).astype(float)
    F["hepsi_yukari_3"]=((Y3>0).sum(axis=0)==k).astype(float)
    # donus sarti sayisi da ozellik olsun (esigin ustundeki kademe)
    F["sart_sayisi"]=say.astype(float)
    return F
