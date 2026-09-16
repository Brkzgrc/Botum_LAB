# -*- coding: utf-8 -*-
"""CHUNK KOSUCUSU — parca parca kosar, birikimi kaydeder, kaldigi yerden devam eder.
GitHub Actions'ta da ayni sekilde calisir."""
import io, os, sys, json, time, zipfile
import numpy as np, requests
KOK = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KOK)
from analiz import coin_isle, birlestir, rapor
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
ERA = {"2021-2022": ("2020-11","2023-01"), "2023-2024": ("2022-11","2025-01")}
DURUM = os.path.join(KOK, "durum.json")
BIRIK = os.path.join(KOK, "birikim.json")
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

def main(parca=25, sure_siniri=None):
    evren = json.load(open(os.path.join(KOK,"evren.json")))
    durum = json.load(open(DURUM)) if os.path.exists(DURUM) else {"bitti":[], "bolum":0}
    birik = json.load(open(BIRIK)) if os.path.exists(BIRIK) else {}
    bitti = set(durum["bitti"])
    kalan = [(e,s) for e in ERA for s in evren if f"{e}|{s}" not in bitti]
    print(f"kalan is: {len(kalan)} / {len(evren)*len(ERA)}", flush=True)
    t0 = time.time(); n = 0
    for era, sym in kalan[:parca]:
        if sure_siniri and time.time()-t0 > sure_siniri:
            print("sure siniri, duruluyor", flush=True); break
        try:
            a = cek(sym, era)
            if a is not None:
                yeni = {}
                k = coin_isle(*a, yeni)
                if k:
                    birlestir(birik, yeni); durum["bolum"] += k
                    print(f"  {sym} {era}: {k} bolum", flush=True)
        except Exception as exc:
            print(f"  {sym} {era} HATA: {type(exc).__name__} {exc}", flush=True)
        durum["bitti"].append(f"{era}|{sym}"); n += 1
    json.dump(durum, open(DURUM,"w"))
    json.dump(birik, open(BIRIK,"w"))
    print(f"\nbu parcada {n} coin islendi. toplam bolum: {durum['bolum']}, "
          f"kalan is: {len(kalan)-n}  ({time.time()-t0:.0f}sn)", flush=True)
    if durum["bolum"] >= 300: rapor(birik)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv)>1 else 25,
         float(sys.argv[2]) if len(sys.argv)>2 else None)
