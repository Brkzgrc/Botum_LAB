# -*- coding: utf-8 -*-
"""4h barinda olculebilen, KULLANICININ ALTI GOSTERGESINDE OLMAYAN olculer.
Hacim YOK (2021-2022 arsivinde hacim yok; kesif ve dogrulama ayni sette olsun diye
hacimli olculer hic kullanilmiyor)."""
import numpy as np

def _ema(x,n):
    a=2/(n+1); o=np.empty_like(x); o[0]=x[0]
    for i in range(1,len(x)): o[i]=a*x[i]+(1-a)*o[i-1]
    return o
def _sma(x,n):
    c=np.cumsum(np.insert(x,0,0.0)); o=np.full_like(x,np.nan)
    o[n-1:]=(c[n:]-c[:-n])/n; return o
def _rma(x,n):
    o=np.empty_like(x); o[0]=x[0]
    for i in range(1,len(x)): o[i]=(o[i-1]*(n-1)+x[i])/n
    return o
def _roll(x,n,fn):
    o=np.full_like(x,np.nan)
    for i in range(n-1,len(x)): o[i]=fn(x[i-n+1:i+1])
    return o

def ozellikler(t,h,l,c):
    n=len(c); F={}
    tr=np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1)))); tr[0]=h[0]-l[0]
    atr=_rma(tr,14); atrp=atr/c*100
    F["atr_yuzde"]=atrp
    F["atr_degisim"]=atrp/np.roll(_sma(atrp,50),0)
    # ADX / DMI
    up=h-np.roll(h,1); dn=np.roll(l,1)-l
    pdm=np.where((up>dn)&(up>0),up,0.0); ndm=np.where((dn>up)&(dn>0),dn,0.0)
    pdi=100*_rma(pdm,14)/np.where(atr==0,np.nan,atr); ndi=100*_rma(ndm,14)/np.where(atr==0,np.nan,atr)
    dx=100*np.abs(pdi-ndi)/np.where((pdi+ndi)==0,np.nan,pdi+ndi)
    F["adx"]=_rma(np.nan_to_num(dx),14); F["di_fark"]=pdi-ndi; F["di_arti"]=pdi; F["di_eksi"]=ndi
    # EMA yapisi
    for p in (20,50,100,200):
        e=_ema(c,p); F[f"ema{p}_uzaklik"]=(c/e-1)*100
    F["ema20_50_fark"]=(_ema(c,20)/_ema(c,50)-1)*100
    F["ema50_200_fark"]=(_ema(c,50)/_ema(c,200)-1)*100
    F["ema20_egim"]=(_ema(c,20)/np.roll(_ema(c,20),5)-1)*100
    # Bollinger
    m=_sma(c,20); sd=_roll(c,20,np.std)
    F["bb_genislik"]=(4*sd)/np.where(m==0,np.nan,m)*100
    F["bb_konum"]=(c-(m-2*sd))/np.where((4*sd)==0,np.nan,4*sd)
    # Donchian / kanal konumu
    for p in (20,50,100):
        hh=_roll(h,p,np.max); ll=_roll(l,p,np.min)
        F[f"kanal{p}_konum"]=(c-ll)/np.where((hh-ll)==0,np.nan,hh-ll)
        F[f"dip{p}_uzaklik"]=(c/np.where(ll==0,np.nan,ll)-1)*100
        F[f"zirve{p}_uzaklik"]=(c/np.where(hh==0,np.nan,hh)-1)*100
    # Momentum / hiz
    for p in (3,6,12,24,48):
        F[f"roc{p}"]=(c/np.roll(c,p)-1)*100
    F["ivme"]=F["roc6"]-np.roll(F["roc6"],6)
    F["hiz_norm"]=F["roc6"]/np.where(atrp==0,np.nan,atrp)
    # CCI
    tp=(h+l+c)/3; sm=_sma(tp,20); md=_roll(tp,20,lambda a:np.mean(np.abs(a-a.mean())))
    F["cci"]=(tp-sm)/np.where(md==0,np.nan,0.015*md)
    # Aroon
    F["aroon_fark"]=_roll(h,25,lambda a:100*(len(a)-1-np.argmax(a))/25*-1+100)-_roll(l,25,lambda a:100*(len(a)-1-np.argmin(a))/25*-1+100)
    # Vortex
    vp=np.abs(h-np.roll(l,1)); vm=np.abs(l-np.roll(h,1))
    F["vortex"]=(_sma(vp,14)-_sma(vm,14))/np.where(_sma(tr,14)==0,np.nan,_sma(tr,14))
    # mum geometrisi
    gv=np.abs(c-np.roll(c,1)); rng=np.where((h-l)==0,np.nan,h-l)
    F["govde_orani"]=np.abs(c-np.roll(c,1))/rng
    F["alt_fitil"]=(np.minimum(c,np.roll(c,1))-l)/rng
    F["ust_fitil"]=(h-np.maximum(c,np.roll(c,1)))/rng
    F["bar_genislik"]=(h-l)/c*100
    # ust ust yon
    yon=np.sign(c-np.roll(c,1)); ard=np.zeros(n)
    for i in range(1,n): ard[i]=ard[i-1]+yon[i] if yon[i]==yon[i-1] else yon[i]
    F["ardisik_yon"]=ard
    # trend duzgunlugu: |toplam yol| / yol uzunlugu
    for p in (12,24):
        net=np.abs(c-np.roll(c,p)); yol=_roll(np.abs(c-np.roll(c,1)),p,np.sum)
        F[f"duzgunluk{p}"]=net/np.where(yol==0,np.nan,yol)
    # oynaklik rejimi
    F["oynaklik_orani"]=atrp/np.where(_sma(atrp,100)==0,np.nan,_sma(atrp,100))
    F["bb_sikisma"]=F["bb_genislik"]/np.where(_sma(F["bb_genislik"],50)==0,np.nan,_sma(F["bb_genislik"],50))
    return F
