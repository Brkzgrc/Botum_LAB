# -*- coding: utf-8 -*-
"""Donus sartlari — donus_tarayici'daki _vek_donus_sayisi ile ayni tanim."""
import numpy as np

def _w(x,n):
    a=1/n; o=np.full(len(x),np.nan)
    if len(x)<n: return o
    o[n-1]=x[:n].mean()
    for i in range(n,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o
def rsi(c,n=14):
    d=np.diff(c,prepend=c[0]); g=np.clip(d,0,None); l=np.clip(-d,0,None)
    ag,al=_w(g,n),_w(l,n)
    rs=np.divide(ag,al,out=np.full(len(c),np.inf),where=al>0)
    return np.where(np.isnan(ag),50.0,100-100/(1+rs))
def _roll(x,n,fn):
    o=np.full(len(x),np.nan)
    for i in range(n-1,len(x)): o[i]=fn(x[i-n+1:i+1])
    return o
def _sma(x,n):
    c=np.cumsum(np.insert(np.nan_to_num(x),0,0.0)); o=np.full(len(x),np.nan)
    o[n-1:]=(c[n:]-c[:-n])/n; return o
def ema(x,n):
    a=2/(n+1); o=np.empty(len(x)); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o
def stoch_rsi(c,n=14,k=3,d=3):
    r=rsi(c,n); lo=_roll(r,n,np.min); hi=_roll(r,n,np.max)
    rng=np.where((hi-lo)==0,np.nan,hi-lo)
    raw=100*(r-lo)/rng
    K=np.nan_to_num(_sma(raw,k),nan=50.0); D=np.nan_to_num(_sma(K,d),nan=50.0)
    return K,D
def macd(c):
    dif=ema(c,12)-ema(c,26); dea=ema(dif,9); return dif,dea,dif-dea
def kdj(h,l,c,n=9):
    ll=_roll(l,n,np.min); hh=_roll(h,n,np.max)
    rng=np.where((hh-ll)==0,np.nan,hh-ll)
    rsv=np.nan_to_num(100*(c-ll)/rng,nan=50.0)
    K=np.empty(len(c)); D=np.empty(len(c)); K[0]=D[0]=50.0
    for i in range(1,len(c)):
        K[i]=2/3*K[i-1]+1/3*rsv[i]; D[i]=2/3*D[i-1]+1/3*K[i]
    return K,D
def wr(h,l,c,n=14):
    hh=_roll(h,n,np.max); ll=_roll(l,n,np.min)
    rng=np.where((hh-ll)==0,np.nan,hh-ll)
    return np.nan_to_num((hh-c)/rng*-100,nan=-50.0)

def obv(c,v):
    return np.cumsum(np.sign(np.diff(c,prepend=c[0]))*v)

def sartlar(h,l,c,v=None):
    """donus_tarayici'nin 5 bagimsiz donus sarti, bar bar"""
    sh=lambda x,k: np.concatenate([np.full(k,np.nan),x[:-k]])
    r=rsi(c); K,D=stoch_rsi(c); dif,dea,hist=macd(c); kk,dd=kdj(h,l,c); w=wr(h,l,c)
    s={}
    s["stochrsi"]=(K>D)&(sh(K,1)<=sh(D,1))&(K>sh(K,1))&(K<70)
    s["rsi"]     =(r>sh(r,1))&(sh(r,1)<=sh(r,2))&(r<60)
    s["macd"]    =((hist>sh(hist,1))&(sh(hist,1)<=sh(hist,2))&(hist<0))|((dif>dea)&(sh(dif,1)<=sh(dea,1)))
    s["kdj"]     =(kk>dd)&(sh(kk,1)<=sh(dd,1))
    s["wr"]      =(w>-80)&(sh(w,1)<=-80)
    if v is not None:
        o=obv(c,v); oe=ema(o,21)
        # OBV kendi EMA21'ini yukari kesti VE OBV yukseliyor (sahte kesisim elenir)
        s["obv"]=(o>oe)&(sh(o,1)<=sh(oe,1))&(o>sh(o,1))
    say=sum(np.nan_to_num(v).astype(int) for v in s.values())
    ek={"rsi":r,"K":K,"D":D,"hist":hist,"kdjK":kk,"kdjD":dd,"wr":w}
    if v is not None:
        o=obv(c,v); ek["obv"]=o; ek["obv_ema"]=ema(o,21)
    return s, say, ek
