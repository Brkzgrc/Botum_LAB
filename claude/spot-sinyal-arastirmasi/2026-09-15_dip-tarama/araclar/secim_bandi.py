# -*- coding: utf-8 -*-
"""Ayni anda gelen sinyallerden hangisi secilir? Belirsizlik bandi + kural karsilastirmasi."""
import os, pickle, sys, time
import numpy as np
sys.path.insert(0,"."); sys.path.insert(0,"/home/user/botum_lab/claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem
VD="veri_dogrulama"; V1="veri_1h"; VESKI="veri"

def yukle(s,era):
    if era=="2021-2022":
        d=pickle.load(open(os.path.join(VESKI,f"{s}.pkl"),"rb"))
        return {"15m":tuple(d["15m"][:4]),"1h":tuple(d["1h"][:4]),"4h":tuple(d["4h"][:4])}
    v=pickle.load(open(os.path.join(VD,f"{s}__{era}.pkl"),"rb"))
    h1=pickle.load(open(os.path.join(V1,f"{s}__{era}.pkl"),"rb"))
    return {"15m":tuple(v["15m"][:4]),"4h":tuple(v["4h"][:4]),"1h":tuple(h1[:4])}
def semboller(era):
    if era=="2021-2022": return sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{era}.pkl") and os.path.exists(os.path.join(V1,f.split('__')[0]+f"__{era}.pkl")))

C={}
def coin(s,era):
    k=(s,era)
    if k not in C:
        try:
            d=yukle(s,era); t1,h1,l1,c1=d["1h"]
            C[k]=(d["15m"],(t1,atr14(h1,l1,c1)))
        except Exception: C[k]=None
    return C[k]

def sim(sg,era):
    para=10000.0; acik=0; n=0
    for x in sg:
        if x["t"]<=acik: continue
        c=coin(x["s"],era)
        if c is None: continue
        (t15,h15,l15,c15),(t1h,a1h)=c
        r=islem(x,t15,h15,l15,c15,t1h,a1h,3,0.6)
        if r is None: continue
        p,ct=r; para*=(1+p/100); acik=ct; n+=1
    return para,n

def sirala(tum,anahtar,rng=None):
    """ayni t'li sinyalleri anahtar'a gore sirala"""
    if anahtar=="rastgele":
        j=rng.random(len(tum))
        return [tum[i] for i in np.lexsort((j,[x["t"] for x in tum]))]
    key={"rr":      lambda x: -((x["tp1"]-x["giris"])/max(1e-9,x["giris"]-x["stop"])),
         "yakin_stop":lambda x: (x["giris"]-x["stop"])/x["giris"],
         "alfabetik":lambda x: x["s"]}[anahtar]
    return sorted(tum,key=lambda x:(x["t"],key(x)))

def main():
    for era,b0,b1 in (("2021-2022","2021-01-01","2023-01-01"),
                      ("2023-2024","2023-01-01","2025-01-01"),
                      ("2025-2026","2025-01-01","2026-10-01")):
        syms=semboller(era); _A={}
        DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
        bas=int(time.mktime(time.strptime(b0,"%Y-%m-%d"))*1000)
        bit=int(time.mktime(time.strptime(b1,"%Y-%m-%d"))*1000)
        tum=[]
        for s in syms:
            try:
                _A[s]=yukle(s,era); sg,_=DT.coin_tara(s,bas,bit); tum+=sg
            except Exception: pass
            finally: _A.pop(s,None)
        import collections
        c=collections.Counter(x["t"] for x in tum)
        cak=sum(n for t,n in c.items() if n>1)
        print(f"\n{'='*70}\n{era}: {len(tum)} sinyal, {cak} tanesi ({100*cak/len(tum):.0f}%) baskasiyla ayni anda")
        print(f"  en kalabalik an: {max(c.values())} coin",flush=True)
        rng=np.random.default_rng(1)
        sonuc=[]
        for i in range(200):
            p,n=sim(sirala(tum,"rastgele",rng),era); sonuc.append(p)
        sonuc=np.array(sonuc)
        print(f"\n  RASTGELE SECIM (200 deneme):")
        print(f"    en kotu  {sonuc.min():>10,.0f}$")
        print(f"    %25      {np.percentile(sonuc,25):>10,.0f}$")
        print(f"    ORTANCA  {np.median(sonuc):>10,.0f}$")
        print(f"    %75      {np.percentile(sonuc,75):>10,.0f}$")
        print(f"    en iyi   {sonuc.max():>10,.0f}$")
        print(f"    zarar eden deneme: {(sonuc<10000).sum()}/200")
        print(f"\n  KURALA GORE SECIM:")
        for a,ad in (("rr","en yuksek R:R"),("yakin_stop","stop'a en yakin"),("alfabetik","alfabetik (anlamsiz)")):
            p,n=sim(sirala(tum,a),era)
            yuzde=100*(sonuc<p).mean()
            print(f"    {ad:<22}{p:>10,.0f}$  {n:>3} isl   (rastgelelerin %{yuzde:.0f}'inden iyi)",flush=True)

if __name__=="__main__": main()
