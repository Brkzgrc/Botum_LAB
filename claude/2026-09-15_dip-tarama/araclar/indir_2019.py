# -*- coding: utf-8 -*-
"""2019-2020 verisi (hacim dahil): 15m, 1h, 4h. Isinma icin 2018-11'den baslar."""
import io, json, os, pickle, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests
KOK=os.path.dirname(os.path.abspath(__file__))
S3="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
V=os.path.join(KOK,"veri_2019"); os.makedirs(V,exist_ok=True)
otur=requests.Session()
AYLAR=[]
y,m=2018,11
while (y,m)<=(2021,1):
    AYLAR.append(f"{y}-{m:02d}"); m+=1
    if m>12: m=1; y+=1

IGN={'USDT','USDC','BUSD','TUSD','DAI','PAX','HUSD','USDP','GUSD','FDUSD','EUR','TRY','GBP','USD',
     'BRL','RUB','AUD','XUSD','USD1','USDE','BFUSD','USDS','USDD','PYUSD','AEUR','EURI','USTC','FRAX',
     'LUSD','SUSD','USDX','CUSD','OUSD','MUSD','RLUSD','BIDR','IDRT','VAI','PAXG','XAUT','WBTC','WETH',
     'WBNB','BETH','BTCB','HBTC','U'}
LEV=('UP','DOWN','BULL','BEAR','2L','2S','3L','3S','5L','5S','10L','10S')
OKB={'BNB','DGB','TRB','CKB','SHIB','ARB','BB','YB','JUP','SYRUP'}

def indir(sym,itv):
    yol=os.path.join(V,f"{sym}__{itv}.pkl")
    if os.path.exists(yol): return True
    sat=[]
    for ay in AYLAR:
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
    if len(sat)<600: return False
    sat.sort()
    a=tuple(np.array([r[i] for r in sat],dtype=np.int64 if i==0 else np.float64) for i in range(7))
    pickle.dump(a,open(yol,"wb"),protocol=4); return True

def main():
    evren=json.load(open('/home/user/botum_lab/claude/veri/binance_evren_delist_dahil.json'))
    if not isinstance(evren,list): evren=list(evren.values())[0]
    syms=[s for s in evren if s.endswith("USDT")
          and not (s[:-4] in IGN or (s[:-4].endswith(LEV) and s[:-4] not in OKB))]
    print(f"aday parite: {len(syms)}",flush=True)
    # once 1h dene -> o donemde var miydi anla
    print("[1] 1h taraniyor (o donemde hangi coinler vardi)",flush=True)
    var=[]; n=0; t0=time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        for s,ok in zip(syms,ex.map(lambda x: indir(x,"1h"), syms)):
            n+=1
            if ok: var.append(s)
            if n%100==0: print(f"   {n}/{len(syms)} var:{len(var)} {time.time()-t0:.0f}sn",flush=True)
    print(f"2019-2020'de veri bulunan: {len(var)} parite",flush=True)
    for itv in ("15m","4h"):
        print(f"[2] {itv} iniyor",flush=True); n=0; ok2=0
        with ThreadPoolExecutor(max_workers=12) as ex:
            for r in ex.map(lambda x: indir(x,itv), var):
                n+=1; ok2+=1 if r else 0
                if n%100==0: print(f"   {n}/{len(var)} ok:{ok2} {time.time()-t0:.0f}sn",flush=True)
        print(f"   {itv}: {ok2}/{len(var)}",flush=True)
    json.dump(var,open(os.path.join(KOK,"evren_2019.json"),"w"))
    print(f"BITTI  {time.time()-t0:.0f}sn",flush=True)

if __name__=="__main__": main()
