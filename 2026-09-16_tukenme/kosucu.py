# -*- coding: utf-8 -*-
"""KOSUCU — yukselis imzasi. Parca parca kosar, kaldigi yerden devam eder."""
import io, os, sys, json, time, zipfile
import numpy as np, requests
KOK = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KOK)
import imza
from tukenme import olcumler
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
ERA = {"2021-2022": ("2020-11","2023-01"), "2023-2024": ("2022-11","2025-01")}
DURUM = os.path.join(KOK, "durum.json")
BIRIK = os.path.join(KOK, "birikim.npz")
otur = requests.Session()

def aylar(a,b):
    y0,m0 = map(int,a.split("-")); y1,m1 = map(int,b.split("-")); o=[]
    while (y0,m0) <= (y1,m1):
        o.append(f"{y0}-{m0:02d}"); m0 += 1
        if m0 > 12: m0=1; y0+=1
    return o

def cek(sym, era):
    sat = []
    for ay in aylar(*ERA[era]):
        for d in range(3):
            try:
                r = otur.get(f"{S3}/{sym}/1h/{sym}-1h-{ay}.zip", timeout=60)
                if r.status_code == 404: break
                if r.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        for s in z.read(z.namelist()[0]).decode("utf-8","ignore").splitlines():
                            p = s.split(",")
                            if len(p)<11 or not p[0].strip() or p[0].startswith("open_time"): continue
                            try:
                                tt = int(p[6])
                                if tt > 1e14: tt //= 1000
                                sat.append((tt,float(p[2]),float(p[3]),float(p[4]),
                                            float(p[5]),float(p[7]),float(p[10])))
                            except ValueError: pass
                    break
                time.sleep(1.5*(d+1))
            except Exception: time.sleep(1.5*(d+1))
    if len(sat) < 600: return None
    sat.sort()
    return tuple(np.array([r[i] for r in sat], dtype=np.int64 if i==0 else np.float64) for i in range(7))

def main(parca=120, sure_siniri=None):
    evren = json.load(open(os.path.join(KOK,"evren.json")))
    durum = json.load(open(DURUM)) if os.path.exists(DURUM) else {"bitti":[]}
    bitti = set(durum["bitti"])
    kalan = [(e,s) for e in ERA for s in evren if f"{e}|{s}" not in bitti]
    print(f"kalan is: {len(kalan)} / {len(evren)*len(ERA)}", flush=True)
    birik = imza.yukle(BIRIK) if os.path.exists(BIRIK) else None
    t0 = time.time(); n = 0
    for era, sym in kalan[:parca]:
        if sure_siniri and time.time()-t0 > sure_siniri:
            print("sure siniri", flush=True); break
        try:
            a = cek(sym, era)
            if a is not None:
                t,h,l,c,v,qv,tq = a
                O = olcumler(t,h,l,c,v,qv,tq)
                if birik is None: birik = imza.bos_birikim(sorted(O))
                k = imza.coin_isle(h,l,c,O,birik)
                if k: print(f"  {sym} {era}: {k} aday", flush=True)
        except Exception as exc:
            print(f"  {sym} {era} HATA: {type(exc).__name__} {exc}", flush=True)
        durum["bitti"].append(f"{era}|{sym}"); n += 1
    json.dump(durum, open(DURUM,"w"))
    if birik is not None: imza.kaydet(birik, BIRIK)
    print(f"\n{n} coin islendi. toplam aday: {birik['aday'] if birik else 0}. "
          f"kalan: {len(kalan)-n}  ({time.time()-t0:.0f}sn)", flush=True)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv)>1 else 120,
         float(sys.argv[2]) if len(sys.argv)>2 else None)
