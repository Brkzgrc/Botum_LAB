# -*- coding: utf-8 -*-
"""PARA AKISI olcumu — on kayda uyar + secim sirasi bandi ile raporlar."""
import os, pickle, sys, time, json
import numpy as np
sys.path.insert(0,"."); sys.path.insert(0,"/home/user/botum_lab/claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama")
import dip_tarama as DT
from dip_dogrula import atr14, islem
from akis_olc import akis_seri, OZ
VA="veri_akis"; VD="veri_dogrulama"; V1="veri_1h"; VESKI="veri"
TUR=200

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

def ozellik_al(sym,era,ts,AK):
    o={}
    for itv in ("1h","4h"):
        k=(sym,itv)
        if k not in AK:
            try: AK[k]=akis_seri(pickle.load(open(os.path.join(VA,f"{sym}__{era}__{itv}.pkl"),"rb")))
            except Exception: AK[k]=None
        A=AK[k]
        if A is None: return None
        i=np.searchsorted(A["t"],ts,side="right")-1
        if i<30: return None
        g=lambda kk: float(A[kk][i]) if i<len(A[kk]) and np.isfinite(A[kk][i]) else np.nan
        if itv=="1h":
            o["1h_taker"]=g("taker"); o["1h_obv"]=g("obv"); o["1h_hacim"]=g("hacim"); o["1h_mfi"]=g("mfi")
        else:
            o["4h_taker"]=g("taker"); o["4h_para_trend"]=g("ptr")
    return o if all(np.isfinite(v) for v in o.values()) else None

def sim_hizli(sg):
    """sg: (t, pnl, kapanis) listesi, zamana gore sirali. Tek islem kurali."""
    para=10000.0; acik=-1; n=0
    for t,p,ct in sg:
        if t<=acik: continue
        para*=(1+p/100); acik=ct; n+=1
    return para,n

def band(kayit,rng,tur=TUR):
    if len(kayit)<10: return None
    t=np.array([k[0] for k in kayit]); res=[]
    for _ in range(tur):
        j=rng.random(len(kayit)); idx=np.lexsort((j,t))
        p,n=sim_hizli([kayit[i] for i in idx]); res.append((p,n))
    P=np.array([r[0] for r in res]); N=np.array([r[1] for r in res])
    return np.percentile(P,25),np.median(P),np.percentile(P,75),N.mean(),(P<10000).mean()

def main():
    rng=np.random.default_rng(42)
    for era,b0,b1 in (("2021-2022","2021-01-01","2023-01-01"),
                      ("2023-2024","2023-01-01","2025-01-01"),
                      ("2025-2026","2025-01-01","2026-10-01")):
        print(f"\n{'='*100}\n{era}   (ARAMA)" if era=="2021-2022" else f"\n{'='*100}\n{era}   (DOGRULAMA)",flush=True)
        syms=semboller(era); _A={}
        DT.mumlar=lambda sym,itv,b,e:_A[sym][itv]
        bas=int(time.mktime(time.strptime(b0,"%Y-%m-%d"))*1000)
        bit=int(time.mktime(time.strptime(b1,"%Y-%m-%d"))*1000)
        tum=[]; AK={}; t0=time.time(); n=0
        for s in syms:
            n+=1
            try:
                _A[s]=yukle(s,era); sg,_=DT.coin_tara(s,bas,bit)
                if sg:
                    d=yukle(s,era); t1,h1,l1,c1=d["1h"]
                    t15,h15,l15,c15=d["15m"]; a1h=atr14(h1,l1,c1)
                    for x in sg:
                        o=ozellik_al(s,era,x["t"],AK)
                        if o is None: continue
                        r=islem(x,t15,h15,l15,c15,t1,a1h,3,0.6)
                        if r is None: continue
                        tum.append((int(x["t"]),float(r[0]),int(r[1]),o))
            except Exception: pass
            finally:
                _A.pop(s,None); AK.pop((s,"1h"),None); AK.pop((s,"4h"),None)
            if n%150==0: print(f"    {n}/{len(syms)}  {len(tum)} dolan islem  {time.time()-t0:.0f}sn",flush=True)
        if len(tum)<40: print("  yetersiz"); continue
        tum.sort(key=lambda z:z[0])
        ay=(tum[-1][0]-tum[0][0])/1000/86400/30.44
        kayit=[(a,b,c) for a,b,c,_ in tum]
        f=lambda p:f"{p:,.0f}$ %{((p/10000)**(1/ay)-1)*100:+5.2f}"
        r=band(kayit,rng)
        print(f"\n  Dolan islem havuzu: {len(tum)},  {ay:.1f} ay,  200 rastgele sira")
        print(f"  TABAN (filtresiz):  {f(r[1])}   [{f(r[0])} .. {f(r[2])}]   ort {r[3]:.0f} isl   zarar %{100*r[4]:.0f}")
        print(f"\n  {'ozellik':<15}{'medyan':>9}   {'UST YARI (ortanca)':<34}{'ALT YARI (ortanca)':<34}")
        for k in OZ:
            vals=np.array([o[k] for *_,o in tum]); med=np.median(vals)
            sat=f"  {k:<15}{med:>9.3f}   "
            for ust in (True,False):
                sub=[(a,b,c) for a,b,c,o in tum if (o[k]>=med if ust else o[k]<med)]
                rr=band(sub,rng)
                sat+=f"{(f(rr[1])+f'  {rr[3]:.0f}isl' if rr else '-'):<34}"
            print(sat,flush=True)

if __name__=="__main__": main()
