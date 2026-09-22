# -*- coding: utf-8 -*-
"""BTC 15.09.2026 civari 15m/1h/4h — donus sartlari zaman dilimlerinde ne zaman olusuyor?"""
import io, zipfile, datetime as dt
import numpy as np, requests
S3D="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/daily/klines"
TR=dt.timezone(dt.timedelta(hours=3))
otur=requests.Session()

def gun_cek(sym, itv, gun):
    r=otur.get(f"{S3D}/{sym}/{itv}/{sym}-{itv}-{gun}.zip", timeout=60)
    if r.status_code!=200: return []
    out=[]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for s in z.read(z.namelist()[0]).decode("utf-8","ignore").splitlines():
            p=s.split(",")
            if len(p)<7 or not p[0].strip() or p[0].startswith("open_time"): continue
            try:
                t=int(p[6])
                if t>1e14: t//=1000
                out.append((t,float(p[2]),float(p[3]),float(p[4]),float(p[5])))
            except ValueError: pass
    return out

def cek(sym, itv, gunler):
    o=[]
    for g in gunler: o+=gun_cek(sym,itv,g)
    o=sorted(set(o))
    return tuple(np.array([r[i] for r in o], dtype=np.int64 if i==0 else float) for i in range(5))

if __name__=="__main__":
    import pickle
    gunler=[(dt.date(2026,9,13)+dt.timedelta(days=i)).isoformat() for i in range(4)]
    d={}
    for itv in ("15m","1h","4h"):
        a=cek("BTCUSDT",itv,gunler)
        d[itv]=a
        print(f"{itv}: {len(a[0])} mum  {dt.datetime.fromtimestamp(a[0][0]/1000,TR):%d.%m %H:%M} -> {dt.datetime.fromtimestamp(a[0][-1]/1000,TR):%d.%m %H:%M}")
    pickle.dump(d, open("btc.pkl","wb"))
