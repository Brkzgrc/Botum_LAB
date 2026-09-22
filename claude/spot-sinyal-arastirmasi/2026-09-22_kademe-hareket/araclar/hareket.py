# -*- coding: utf-8 -*-
"""SADECE GOSTERGE HAREKETI — dip sarti YOK.

Soru: kac gosterge BIRDEN donerse fark ediyor? (2/3/4/5/6)
Her zaman dilimi AYRI olculur, yaninda TABAN (ayni donemde rastgele bar) durur.
Taban olmadan "%38 iyi mi" sorusunun cevabi yok.
"""
import numpy as np
import donus

HEDEFLER = ((10,5),(20,10),(30,15))
UFUK = {"4h":168, "1h":672, "15m":2688}   # ucu de 28 gun
SOGUMA = {"4h":6,  "1h":24,  "15m":96}    # ucu de 24 saat: ayni hareketi tekrar sayma

def yol(h, l, i, giris, hedef, stop, ufuk):
    ust=giris*(1+hedef/100); alt=giris*(1-stop/100)
    son=min(len(l), i+1+ufuk); dip=giris
    for j in range(i+1, son):
        if l[j]<dip: dip=l[j]
        if l[j]<=alt: return 0,(dip/giris-1)*100
        if h[j]>=ust: return 1,(dip/giris-1)*100
    return -1,(dip/giris-1)*100

def tara(d, itv, esikler, birik, taban, rng):
    t,h,l,c,v = d
    if len(t) < 400: return
    _, say, _ = donus.sartlar(h,l,c,v)
    uf=UFUK[itv]; sg=SOGUMA[itv]
    bas=60; son=len(t)-1
    # --- sinyaller
    for N in esikler:
        i=bas; sonr=-10**9
        while i<son:
            if say[i]>=N and i-sonr>=sg:
                gp=float(c[i])
                birik[N].append([yol(h,l,i,gp,hd,st,uf) for hd,st in HEDEFLER])
                sonr=i
            i+=1
    # --- TABAN: ayni coin, ayni donem, rastgele barlar (sinyal sayisi mertebesinde)
    k=max(5, len(range(bas,son))//sg)
    for i in rng.choice(np.arange(bas,son), size=min(k,son-bas), replace=False):
        gp=float(c[i])
        taban.append([yol(h,l,int(i),gp,hd,st,uf) for hd,st in HEDEFLER])

def ozet(ad, kayitlar):
    if not kayitlar: return
    sat=f"  {ad:<20}{len(kayitlar):>9}"
    for k,(hd,st) in enumerate(HEDEFLER):
        r=[x[k] for x in kayitlar]
        belli=[a for a,_ in r if a>=0]
        mae=[m for _,m in r]
        o=100*np.mean(belli) if belli else 0
        sat+=f"{f'%{o:.1f} (mae -%{abs(np.median(mae)):.1f})':>22}"
    print(sat)
