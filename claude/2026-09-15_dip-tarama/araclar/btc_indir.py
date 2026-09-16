# -*- coding: utf-8 -*-
"""BTCUSDT surekli seri: 2024-10 -> 2026-09 (isinma payiyla). 15m/1h/4h/1d."""
import time, pickle, requests, os
BASE="https://data-api.binance.vision"; OUT=os.path.dirname(os.path.abspath(__file__))
BAS=int(time.mktime(time.strptime("2024-10-01","%Y-%m-%d"))*1000)
BIT=int(time.mktime(time.strptime("2026-09-12","%Y-%m-%d"))*1000)
s=requests.Session(); veri={}
for tf in ("15m","1h","4h","1d"):
    rows=[]; cur=BAS
    while cur<BIT:
        for d in range(4):
            try:
                r=s.get(f"{BASE}/api/v3/klines",timeout=20,params={"symbol":"BTCUSDT","interval":tf,"startTime":cur,"endTime":BIT,"limit":1000})
                if r.status_code==200: break
                time.sleep(2**d)
            except Exception: time.sleep(1.5*(d+1))
        else: raise SystemExit(f"{tf} indirilemedi")
        b=r.json()
        if not b: break
        rows += [[float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5]),int(k[6])] for k in b]
        cur = b[-1][6]+1
        if len(b)<1000: break
    veri[tf]=rows
    print(f"  {tf}: {len(rows)} mum", flush=True)
pickle.dump(veri, open(os.path.join(OUT,"btc.pkl"),"wb"), protocol=4)
print(f"kaydedildi {os.path.getsize(os.path.join(OUT,'btc.pkl'))/1048576:.1f} MB", flush=True)
