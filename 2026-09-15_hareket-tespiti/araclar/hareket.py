# -*- coding: utf-8 -*-
"""HAREKET TESPITI — 1. adim: "aldiklarimiz yukseliyor mu?"

Kullanicinin tarifi birebir:
  - Gosterge seti SADECE: RSI, MACD, StochRSI, KDJ, OBV, W%R
  - Her gosterge BAGIMSIZ oy verir, en sonda toplanir:  (RSI)+(MACD)+(KDJ)+...
  - Tek soru: "dususten yukselise geciyor mu" -> HAREKET. Sabit seviye YOK.
  - Coin: 15m/1h/4h/1d   ·   BTC ortami: 1h/4h/1d
  - 1d/4h kontrol cercevesi, 15m karar cercevesi

MUTLAK ESIK YOK: oy = (donus olustu) x (gostergenin kendi son 200 barindaki
goreli dipligi). Sonuc 0..1 arasi surekli sayi; ayarlanacak esik yok.

Cikis kurali YOK. Sadece hareket olculur (stop/TP sonraki mesele).
Basari (yol-farkinda): W saat icinde high +X%'e ULASTI **ve** bu, low -X%'e
inmeden ONCE oldu.
"""
import io, json, os, pickle, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests

KOK   = os.path.dirname(os.path.abspath(__file__))
VERI  = os.path.join(KOK, "veri_hacimli")
S3    = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
AYLAR = ["2020-11","2020-12"] + [f"{y}-{m:02d}" for y in (2021,2022) for m in range(1,13)] + ["2023-01"]
TFLER = ("15m","1h","4h")
PENCERE   = 200
IZGARA_4H = 1                      # her 4h barinda bir bak
HEDEFLER  = [2.0, 3.0, 5.0]
SURELER   = [24, 72]
os.makedirs(VERI, exist_ok=True)
oturum = requests.Session()

# ═══ 1) VERI (hacim DAHIL) ═══
def _indir(sym, tf, ay):
    for d in range(3):
        try:
            r = oturum.get(f"{S3}/{sym}/{tf}/{sym}-{tf}-{ay}.zip", timeout=45)
            if r.status_code == 404: return None
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    return z.read(z.namelist()[0]).decode("utf-8","ignore")
            time.sleep(1.5*(d+1))
        except Exception: time.sleep(1.5*(d+1))
    return None

def hazirla(sym):
    yol = os.path.join(VERI, f"{sym}.pkl")
    if os.path.exists(yol):
        try:
            with open(yol,"rb") as f: return pickle.load(f)
        except Exception: pass
    veri = {}
    for tf in TFLER:
        sat = []
        for ay in AYLAR:
            csv = _indir(sym, tf, ay)
            if not csv: continue
            for s in csv.splitlines():
                p = s.split(",")
                if len(p) < 7 or not p[0].strip() or p[0].startswith("open_time"): continue
                try: sat.append((int(p[6]), float(p[2]), float(p[3]), float(p[4]), float(p[5])))
                except ValueError: continue
        if len(sat) < 500: return None
        sat.sort()
        veri[tf] = tuple(np.array([r[i] for r in sat],
                         dtype=np.int64 if i==0 else np.float64) for i in range(5))
    with open(yol,"wb") as f: pickle.dump(veri, f, protocol=4)
    return veri

# ═══ 2) GOSTERGELER ═══
def _wilder(x, n):
    a = np.full(len(x), np.nan)
    if len(x) < n: return a
    a[n-1] = x[:n].mean()
    for i in range(n, len(x)): a[i] = (a[i-1]*(n-1)+x[i])/n
    return a

def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up=_wilder(np.where(d>0,d,0.0),n); dn=_wilder(np.where(d<0,-d,0.0),n)
    with np.errstate(divide="ignore", invalid="ignore"): rs=up/dn
    r=100-100/(1+rs); r[dn==0]=100.0
    return r

def _sma(x,n):
    o=np.full(len(x),np.nan)
    if len(x)<n: return o
    cs=np.cumsum(np.insert(np.nan_to_num(x),0,0.0)); o[n-1:]=(cs[n:]-cs[:-n])/n
    return o

def _ema(x,n):
    a=2/(n+1); o=np.empty(len(x)); o[0]=x[0]
    for i in range(1,len(x)): o[i]=x[i]*a+o[i-1]*(1-a)
    return o

def stochrsi_k(c,n=14,m=14,k=3):
    r=rsi(c,n); o=np.full(len(r),np.nan)
    for i in range(n+m-2,len(r)):
        w=r[i-m+1:i+1]
        if np.isnan(w).any(): continue
        lo,hi=w.min(),w.max(); o[i]=0.0 if hi==lo else (r[i]-lo)/(hi-lo)*100
    return _sma(o,k)

def kdj_j(h,l,c,n=9):
    K=np.full(len(c),np.nan); D=np.full(len(c),np.nan); pk=pd_=50.0
    for i in range(n-1,len(c)):
        hh=h[i-n+1:i+1].max(); ll=l[i-n+1:i+1].min()
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        pk=(2/3)*pk+(1/3)*rsv; pd_=(2/3)*pd_+(1/3)*pk; K[i],D[i]=pk,pd_
    return 3*K-2*D

def wr(h,l,c,n=14):
    o=np.full(len(c),np.nan)
    for i in range(n-1,len(c)):
        hh=h[i-n+1:i+1].max(); ll=l[i-n+1:i+1].min()
        o[i]=0.0 if hh==ll else (hh-c[i])/(hh-ll)*-100
    return o

def macd_hist(c):
    dif=_ema(c,12)-_ema(c,26); return dif-_ema(dif,9)

def obv(c,v):
    return np.cumsum(np.sign(np.diff(c,prepend=c[0]))*v)

# ═══ 3) HAREKET OYU — esik yok ═══
def _yuzdelik(x,n=PENCERE):
    """x[i]'nin kendi onceki n barindaki goreli konumu (0=dip, 1=tepe). Nedensel."""
    o=np.full(len(x),np.nan)
    for i in range(n,len(x)):
        if np.isnan(x[i]): continue
        w=x[i-n:i]; w=w[~np.isnan(w)]
        if len(w)<n//2: continue
        o[i]=(w<x[i]).mean()
    return o

def oy_yukari(x):
    """(dun dusuyordu, bugun yukari)  x  (kendi gecmisinde ne kadar dipte)."""
    d=np.diff(x,prepend=np.nan)
    onceki=np.roll(d,1); onceki[0]=np.nan
    donus=(d>0)&(onceki<=0)
    p=_yuzdelik(x)
    o=np.where(donus & ~np.isnan(p), 1.0-p, 0.0)
    o[np.isnan(x)]=0.0
    return o

def tf_oylar(h,l,c,v):
    """6 gosterge, her biri BAGIMSIZ. Her biri 0..1, toplam 0..6."""
    return {"RSI":oy_yukari(rsi(c)), "MACD":oy_yukari(macd_hist(c)),
            "SRSI":oy_yukari(stochrsi_k(c)), "KDJ":oy_yukari(kdj_j(h,l,c)),
            "OBV":oy_yukari(obv(c,v)), "WR":oy_yukari(wr(h,l,c))}

def gunluk_turet(t,h,l,c,v):
    gun=t//86_400_000
    kes=np.where(np.diff(gun,prepend=gun[0]-1)!=0)[0]
    T,H,L,C,V=[],[],[],[],[]
    for a,b in zip(kes,list(kes[1:])+[len(t)]):
        if b<=a: continue
        T.append(t[b-1]); H.append(h[a:b].max()); L.append(l[a:b].min())
        C.append(c[b-1]); V.append(v[a:b].sum())
    return (np.array(T,dtype=np.int64),np.array(H),np.array(L),np.array(C),np.array(V))

# ═══ 4) SONUC: DOGRU AN MI? ═══
from numpy.lib.stride_tricks import sliding_window_view

def yol_sonuc(h15, l15, c15, K, hedef):
    """Her 15m bari giris kabul et: K bar icinde +hedef%'e ULASTI ve bu
       -hedef%'e inmeden ONCE mi oldu?  1=evet 0=hayir -1=hicbiri."""
    n = len(c15)
    if n < K+2: return np.full(n, -1, dtype=np.int8)
    H = sliding_window_view(h15, K); L = sliding_window_view(l15, K)   # [n-K+1, K]
    m = len(H)
    giris = c15[:m-1]                       # i. barda gir, i+1'den itibaren bak
    ust = giris*(1+hedef/100); alt = giris*(1-hedef/100)
    Hp = H[1:m]; Lp = L[1:m]
    u = Hp >= ust[:,None]; d = Lp <= alt[:,None]
    iu = np.where(u.any(1), u.argmax(1), K+1)
    idn = np.where(d.any(1), d.argmax(1), K+1)
    r = np.full(n, -1, dtype=np.int8)
    var = (iu <= K) | (idn <= K)
    r[:m-1] = np.where(~var, -1, np.where(iu < idn, 1, 0))
    return r

def sure_dk(h15, c15, K, hedef):
    """Hedefe kac dakikada ulasti (ulasmadiysa -1)."""
    n=len(c15)
    if n < K+2: return np.full(n,-1.0)
    H=sliding_window_view(h15,K); m=len(H)
    ust=c15[:m-1]*(1+hedef/100); Hp=H[1:m]
    u=Hp>=ust[:,None]
    idx=np.where(u.any(1),u.argmax(1),-1)
    r=np.full(n,-1.0); r[:m-1]=np.where(idx>=0,(idx+1)*15.0,-1.0)
    return r
