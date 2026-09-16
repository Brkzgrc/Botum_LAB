# -*- coding: utf-8 -*-
"""DIP TARAMA ofset dogrulamasi — 2023-2024 ve 2025-2026. Olcut: PARA."""
import io, json, os, pickle, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
sys.path.insert(0,"/home/user/botum_lab/claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama")
import dip_tarama as DT

S3="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h"); os.makedirs(V1,exist_ok=True)
KOM=0.2; DOLUM=24; EXP=24
otur=requests.Session()
DONEM={"2023-2024":(2023,2024),"2025-2026":(2025,2026)}
def aylar(y0,y1):
    o=[f"{y0-1}-11",f"{y0-1}-12"]
    for y in range(y0,y1+1):
        for m in range(1,13):
            if y==2026 and m>9: break
            o.append(f"{y}-{m:02d}")
    if y1<2026: o.append(f"{y1+1}-01")
    return o

def dl1h(sym, al, et):
    yol=os.path.join(V1,f"{sym}__{et}.pkl")
    if os.path.exists(yol):
        try: return pickle.load(open(yol,"rb"))
        except Exception: pass
    sat=[]
    for ay in al:
        for d in range(3):
            try:
                r=otur.get(f"{S3}/{sym}/1h/{sym}-1h-{ay}.zip",timeout=45)
                if r.status_code==404: break
                if r.status_code==200:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        for s in z.read(z.namelist()[0]).decode("utf-8","ignore").splitlines():
                            p=s.split(",")
                            if len(p)<7 or not p[0].strip() or p[0].startswith("open_time"): continue
                            try:
                                _t=int(p[6])
                                if _t>1e14: _t//=1000
                                sat.append((_t,float(p[2]),float(p[3]),float(p[4])))
                            except ValueError: pass
                    break
                time.sleep(1.5*(d+1))
            except Exception: time.sleep(1.5*(d+1))
    if len(sat)<500: return None
    sat.sort()
    a=tuple(np.array([r[i] for r in sat],dtype=np.int64 if i==0 else np.float64) for i in range(4))
    pickle.dump(a,open(yol,"wb"),protocol=4); return a

def atr14(h,l,c):
    tr=np.maximum(h[1:]-l[1:],np.maximum(np.abs(h[1:]-c[:-1]),np.abs(l[1:]-c[:-1])))
    a=np.full(len(c),np.nan)
    if len(tr)<14: return a
    a[14]=tr[:14].mean()
    for i in range(15,len(c)): a[i]=(a[i-1]*13+tr[i-1])/14
    return a

def islem(s,t15,h15,l15,c15,t1h,a1h,of,mult):
    i0=np.searchsorted(t15,s["t"],side="left")
    if i0>=len(c15)-4: return None
    g=s["giris"]*(1-of/100); stop=s["stop"]; tp1=s["tp1"]
    if g<=stop: return None
    dol=None; son=s["t"]+DOLUM*3600_000
    for i in range(i0,len(c15)):
        if t15[i]>son: break
        if l15[i]<=g: dol=i; break
    if dol is None: return None
    lim=t15[dol]+EXP*3600_000; zir=g; tp=False
    for j in range(dol+1,len(c15)):
        if not tp:
            if l15[j]<=stop: return (stop/g-1)*100-KOM,int(t15[j])
            if h15[j]>=tp1: tp=True; zir=max(zir,h15[j])
            elif t15[j]>=lim: return (c15[j]/g-1)*100-KOM,int(t15[j])
        if tp:
            zir=max(zir,h15[j])
            k=np.searchsorted(t1h,t15[j],side="right")-1
            a=a1h[k] if 0<=k<len(a1h) and not np.isnan(a1h[k]) else g*0.02
            tr=max(g,zir-a*mult)
            if c15[j]<=tr: return (tr/g-1)*100-KOM,int(t15[j])
    return (c15[-1]/g-1)*100-KOM,int(t15[-1])

def main():
    for et,(y0,y1) in DONEM.items():
        al=aylar(y0,y1)
        semboller=[os.path.basename(f).split("__")[0] for f in os.listdir(VD) if f.endswith(f"__{et}.pkl")]
        print(f"\n{'='*66}\n{et}  ({len(semboller)} coin)\n{'='*66}",flush=True)
        print("[1h indiriliyor]",flush=True); t0=time.time(); n=0; ok=[]
        with ThreadPoolExecutor(max_workers=10) as ex:
            for sym,a in ex.map(lambda s:(s,dl1h(s,al,et)), semboller):
                n+=1
                if a is not None: ok.append(sym)
                if n%100==0: print(f"   {n}/{len(semboller)} ok:{len(ok)} {time.time()-t0:.0f}sn",flush=True)
        print(f"  1h verisi olan: {len(ok)}",flush=True)
        # sinyal uret
        print("[sinyal uretiliyor]",flush=True)
        _A={}
        def _m(sym,itv,b,e): return _A[sym][itv]
        DT.mumlar=_m
        bas=int(time.mktime(time.strptime(f"{y0}-01-01","%Y-%m-%d"))*1000)
        bit=int(time.mktime(time.strptime(f"{min(y1+1,2026)}-{'10' if y1==2026 else '01'}-01","%Y-%m-%d"))*1000)
        tum=[]; m=0
        for sym in ok:
            m+=1
            try:
                v=pickle.load(open(os.path.join(VD,f"{sym}__{et}.pkl"),"rb"))
                h1=pickle.load(open(os.path.join(V1,f"{sym}__{et}.pkl"),"rb"))
                _A[sym]={"15m":(v["15m"][0],v["15m"][1],v["15m"][2],v["15m"][3]),
                         "4h" :(v["4h"][0],v["4h"][1],v["4h"][2],v["4h"][3]),
                         "1h" : h1}
                sg,_=DT.coin_tara(sym,bas,bit); tum+=sg
            except Exception: pass
            finally: _A.pop(sym,None)
            if m%150==0: print(f"   {m}/{len(ok)}  {len(tum)} sinyal",flush=True)
        tum.sort(key=lambda x:x["t"])
        print(f"  toplam sinyal: {len(tum)}",flush=True)
        if len(tum)<30: print("  yetersiz"); continue
        ay=(tum[-1]["t"]-tum[0]["t"])/1000/86400/30.44
        cache={}
        print(f"\n{'giris':>7}{'ATRx0.6':>28}{'ATRx2.0':>28}")
        for of in (0,2,3):
            sat=f"{('-%'+str(of) if of else 'yok'):>7}"
            for mult in (0.6,2.0):
                para=10000.0; acik=0; n2=0; kz=0; tp=para; dd=0.0
                for x in tum:
                    if x["t"]<=acik: continue
                    s=x["s"]
                    if s not in cache:
                        if len(cache)>25: cache.clear()
                        try:
                            v=pickle.load(open(os.path.join(VD,f"{s}__{et}.pkl"),"rb"))
                            h1=pickle.load(open(os.path.join(V1,f"{s}__{et}.pkl"),"rb"))
                            cache[s]=(v["15m"],(h1[0],atr14(h1[1],h1[2],h1[3])))
                        except Exception: cache[s]=None
                    if cache[s] is None: continue
                    (t15,h15,l15,c15,_),(t1h,a1h)=cache[s]
                    r=islem(x,t15,h15,l15,c15,t1h,a1h,of,mult)
                    if r is None: continue
                    p,ct=r; para*=(1+p/100); acik=ct; n2+=1; kz+=1 if p>0 else 0
                    tp=max(tp,para); dd=min(dd,(para/tp-1)*100)
                aa=((para/10000)**(1/ay)-1)*100 if para>0 else -99
                sat+=f"{f'{para:>9,.0f}$ %{aa:+5.2f} {n2:>3}isl %{dd:.0f}':>28}"
            print(sat,flush=True)

if __name__=="__main__": main()
