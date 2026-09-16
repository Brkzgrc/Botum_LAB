# -*- coding: utf-8 -*-
"""DIP TARAMA — giris ofseti x ATR trailing izgarasi.  Olcut: PARA.

Giris : sinyal fiyatinin %0 / %1 / %2 / %3 altina limit (24 saat icinde dolmazsa iptal)
Cikis : stop = destek x 0.975  ·  TP1 sonrasi ATR(14,1h) x {0.6, 1.0, 1.5, 2.0} trailing
        trail giris altina inmez  ·  TP1 gorulmezse 24 saat expire
Sermaye: 10.000$, ayni anda TEK islem, sirayla. Komisyon %0.2
"""
import json, os, pickle, sys
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
KOM=0.2; DOLUM_SAAT=24; EXPIRE_SAAT=24

def atr14(h,l,c):
    tr=np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
    a=np.full(len(c),np.nan)
    if len(tr)<14: return a
    a[14]=tr[:14].mean()
    for i in range(15,len(c)): a[i]=(a[i-1]*13+tr[i-1])/14
    return a

def islem(sig, t15,h15,l15,c15, t1h,atr1h, ofset, mult):
    """Donus: (yuzde, kapanis_ms) veya None (dolmadi)."""
    i0=np.searchsorted(t15, sig["t"], side="left")
    if i0>=len(c15)-4: return None
    giris=sig["giris"]*(1-ofset/100)
    stop=sig["stop"]; tp1=sig["tp1"]
    if giris<=stop: return None                      # giris stopun altinda -> elenir
    # 1) limit dolumu
    dolum=None
    son=sig["t"]+DOLUM_SAAT*3600_000
    for i in range(i0,len(c15)):
        if t15[i]>son: break
        if l15[i]<=giris: dolum=i; break
    if dolum is None: return None
    # 2) pozisyon
    limit=t15[dolum]+EXPIRE_SAAT*3600_000
    zirve=giris; tp1_gordu=False
    for j in range(dolum+1,len(c15)):
        if not tp1_gordu:
            if l15[j]<=stop: return (stop/giris-1)*100-KOM, int(t15[j])
            if h15[j]>=tp1: tp1_gordu=True; zirve=max(zirve,h15[j])
            elif t15[j]>=limit: return (c15[j]/giris-1)*100-KOM, int(t15[j])
        if tp1_gordu:
            zirve=max(zirve,h15[j])
            k=np.searchsorted(t1h,t15[j],side="right")-1
            a=atr1h[k] if 0<=k<len(atr1h) and not np.isnan(atr1h[k]) else giris*0.02
            tr=max(giris, zirve-a*mult)
            if c15[j]<=tr: return (tr/giris-1)*100-KOM, int(t15[j])
    return (c15[-1]/giris-1)*100-KOM, int(t15[-1])

def main():
    sig=json.load(open(os.path.join(KOK,"esik_60.json")))["islemler"]
    sig.sort(key=lambda x:x["t"])
    print(f"dip_tarama sinyalleri (2021-2022, orijinal kural): {len(sig)}\n")
    veri={}
    for s in {x["s"] for x in sig}:
        try:
            v=pickle.load(open(os.path.join(KOK,"veri_hacimli",f"{s}.pkl"),"rb"))
            t1,h1,l1,c1,_=v["1h"]
            veri[s]=(v["15m"], (t1, atr14(h1,l1,c1)))
        except Exception: pass
    print(f"verisi olan coin: {len(veri)}\n")
    print(f"{'giris':>7} " + "".join(f"{'ATRx'+str(m):>22}" for m in (0.6,1.0,1.5,2.0)))
    print(f"{'':>7} " + "".join(f"{'10.000$ -> / aylik':>22}" for _ in range(4)))
    print("-"*95)
    ay=(sig[-1]["t"]-sig[0]["t"])/1000/86400/30.44
    tablo={}
    for ofset in (0,1,2,3):
        sat=f"{('-%'+str(ofset) if ofset else 'yok'):>7} "
        for mult in (0.6,1.0,1.5,2.0):
            para=10000.0; acik=0; n=0; kaz=0; tepe=para; dd=0.0
            for x in sig:
                if x["t"]<=acik: continue
                if x["s"] not in veri: continue
                (t15,h15,l15,c15,_),(t1h,a1h)=veri[x["s"]]
                r=islem(x,t15,h15,l15,c15,t1h,a1h,ofset,mult)
                if r is None: continue
                p,ct=r; para*=(1+p/100); acik=ct; n+=1; kaz+= 1 if p>0 else 0
                tepe=max(tepe,para); dd=min(dd,(para/tepe-1)*100)
            aylik=((para/10000)**(1/ay)-1)*100 if para>0 else -99
            tablo[(ofset,mult)]=(para,n,kaz,dd,aylik)
            sat+=f"{f'{para:>9,.0f}$ %{aylik:+5.2f}':>22}"
        print(sat)
    print("\nDETAY (islem sayisi · kazanan · en buyuk dusus)")
    print(f"{'giris':>7} " + "".join(f"{'ATRx'+str(m):>19}" for m in (0.6,1.0,1.5,2.0)))
    for ofset in (0,1,2,3):
        sat=f"{('-%'+str(ofset) if ofset else 'yok'):>7} "
        for mult in (0.6,1.0,1.5,2.0):
            p,n,k,dd,_=tablo[(ofset,mult)]
            sat+=f"{f'{n:>3} isl %{k/max(n,1)*100:.0f} dd%{dd:.0f}':>19}"
        print(sat)

if __name__=="__main__": main()
