# -*- coding: utf-8 -*-
"""HACIM + PARA AKISI verisi indir: volume, quote_volume, taker_quote.
Cikti: veri_akis/{sym}__{era}__{itv}.pkl = (t_kapanis,h,l,c,vol,qvol,taker_q)"""
import io, os, pickle, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests
KOK=os.path.dirname(os.path.abspath(__file__))
S3="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
VA=os.path.join(KOK,"veri_akis"); os.makedirs(VA,exist_ok=True)
VESKI=os.path.join(KOK,"veri"); VD=os.path.join(KOK,"veri_dogrulama")
otur=requests.Session()
ERA={"2021-2022":("2020-11","2023-01"),"2023-2024":("2022-11","2025-01"),"2025-2026":("2024-11","2026-09")}

def aylar(a,b):
    y0,m0=map(int,a.split("-")); y1,m1=map(int,b.split("-")); o=[]
    while (y0,m0)<=(y1,m1):
        o.append(f"{y0}-{m0:02d}"); m0+=1
        if m0>12: m0=1; y0+=1
    return o

def indir(sym,era,itv):
    yol=os.path.join(VA,f"{sym}__{era}__{itv}.pkl")
    if os.path.exists(yol): return True
    sat=[]
    for ay in aylar(*ERA[era]):
        for d in range(3):
            try:
                r=otur.get(f"{S3}/{sym}/{itv}/{sym}-{itv}-{ay}.zip",timeout=60)
                if r.status_code==404: break
                if r.status_code==200:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        for s in z.read(z.namelist()[0]).decode("utf-8","ignore").splitlines():
                            p=s.split(",")
                            if len(p)<11 or not p[0].strip() or p[0].startswith("open_time"): continue
                            try:
                                t=int(p[6])
                                if t>1e14: t//=1000
                                sat.append((t,float(p[2]),float(p[3]),float(p[4]),
                                            float(p[5]),float(p[7]),float(p[10])))
                            except ValueError: pass
                    break
                time.sleep(1.5*(d+1))
            except Exception: time.sleep(1.5*(d+1))
    if len(sat)<300: return False
    sat.sort()
    a=tuple(np.array([r[i] for r in sat], dtype=np.int64 if i==0 else np.float64) for i in range(7))
    pickle.dump(a,open(yol,"wb"),protocol=4); return True

def main():
    isler=[]
    for era in ERA:
        if era=="2021-2022":
            syms=sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
        else:
            syms=sorted(f.split("__")[0] for f in os.listdir(VD) if f.endswith(f"__{era}.pkl"))
        for s in syms:
            for itv in ("1h","4h"): isler.append((s,era,itv))
    print(f"toplam is: {len(isler)}",flush=True)
    ok=0; n=0; t0=time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(lambda a: indir(*a), isler):
            n+=1; ok+=1 if r else 0
            if n%400==0: print(f"  {n}/{len(isler)} ok:{ok} {time.time()-t0:.0f}sn",flush=True)
    print(f"BITTI  {ok}/{len(isler)} dosya  {time.time()-t0:.0f}sn",flush=True)

if __name__=="__main__": main()
