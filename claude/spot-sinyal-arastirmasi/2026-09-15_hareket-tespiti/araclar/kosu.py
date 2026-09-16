# -*- coding: utf-8 -*-
"""2021-2022 ARAMA KOSUSU — 4H RSI esik taramasi.

- Evren: arsivde 2021-2022 verisi olan TUM USDT pariteleri (DELIST OLANLAR DAHIL)
- Veri : s3-ap-northeast-1.amazonaws.com/data.binance.vision aylik ZIP
- Kural : dip_tarama.py'nin KENDI gosterge ve cikis kodu (degistirilmedi)
- Degisken: K4_RSI_MIN in {60, 55, 50, 45}
- Cikti : her esik icin ayri JSON
- Yarida kalirsa kaldigi yerden devam eder (sembol basina pkl onbellek)
"""
import io, json, os, pickle, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import numpy as np, requests

KOK   = os.path.dirname(os.path.abspath(__file__))
VERI  = os.path.join(KOK, "veri")
LAB   = "/home/user/botum_lab/claude/spot-sinyal-arastirmasi/2026-09-15_dip-tarama"
sys.path.insert(0, LAB)
import dip_tarama as DT

TR   = timezone(timedelta(hours=3))
S3   = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/spot/monthly/klines"
BAS  = datetime(2021,1,1,tzinfo=TR); BIT = datetime(2023,1,1,tzinfo=TR)
AYLAR = ["2020-11","2020-12"] + [f"{y}-{m:02d}" for y in (2021,2022) for m in range(1,13)] + ["2023-01"]
TFLER = ("15m","1h","4h")
ESIKLER = [60.0, 55.0, 50.0, 45.0]
os.makedirs(VERI, exist_ok=True)
oturum = requests.Session()

def _indir(sym, tf, ay):
    for d in range(3):
        try:
            r = oturum.get(f"{S3}/{sym}/{tf}/{sym}-{tf}-{ay}.zip", timeout=45)
            if r.status_code == 404: return None
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    ad = z.namelist()[0]
                    return z.read(ad).decode("utf-8", "ignore")
            time.sleep(1.5*(d+1))
        except Exception:
            time.sleep(1.5*(d+1))
    return None

def sembol_hazirla(sym):
    """Sembolun 3 TF verisini indir, (kapanis_ms, high, low, close) olarak sakla."""
    yol = os.path.join(VERI, f"{sym}.pkl")
    if os.path.exists(yol):
        try:
            with open(yol,"rb") as f: return pickle.load(f)
        except Exception: pass
    veri = {}
    for tf in TFLER:
        sat = []
        for ay in AYLAR:
            csv = _indir(sym, tf, ay)
            if not csv: continue
            for satir in csv.splitlines():
                p = satir.split(",")
                if len(p) < 7 or not p[0].strip() or p[0].startswith("open_time"): continue
                try: sat.append((int(p[6]), float(p[2]), float(p[3]), float(p[4])))
                except ValueError: continue
        if not sat: return None
        sat.sort()
        veri[tf] = (np.array([r[0] for r in sat], dtype=np.int64),
                    np.array([r[1] for r in sat], dtype=np.float64),
                    np.array([r[2] for r in sat], dtype=np.float64),
                    np.array([r[3] for r in sat], dtype=np.float64))
    with open(yol,"wb") as f: pickle.dump(veri, f, protocol=4)
    return veri

# ---- dip_tarama.mumlar'i arsiv okuyucusuyla degistir --------------------
_AKTIF = {}
def _mumlar_arsiv(sym, itv, bas, bit):
    v = _AKTIF.get(sym)
    if v is None or itv not in v: raise RuntimeError("veri yok")
    return v[itv]
DT.mumlar = _mumlar_arsiv

def main():
    ev_dosya = os.path.join(KOK, "evren.json")
    usdt = json.load(open(ev_dosya))["tum_usdt"]
    print(f"arsivdeki toplam USDT paritesi: {len(usdt)}", flush=True)

    # 1) VERI INDIR (sembol basina onbellek — yarida kalirsa devam eder)
    print("\n[1/3] veri indiriliyor (2020-11 .. 2023-01)", flush=True)
    hazir = []
    t0 = time.time(); n = 0
    def isle(s):
        try: return s, sembol_hazirla(s)
        except Exception: return s, None
    with ThreadPoolExecutor(max_workers=10) as ex:
        for sym, v in ex.map(isle, usdt):
            n += 1
            if v: hazir.append(sym)
            if n % 25 == 0:
                mb = sum(os.path.getsize(os.path.join(VERI,f)) for f in os.listdir(VERI))/1048576
                print(f"  {n}/{len(usdt)}  verisi olan: {len(hazir)}  {mb:.0f} MB  {time.time()-t0:.0f}sn", flush=True)
    print(f"\n2021-2022 verisi olan parite: {len(hazir)} / {len(usdt)}", flush=True)
    json.dump(hazir, open(os.path.join(KOK,"evren_2021_2022.json"),"w"))

    bas_ms = int(BAS.astimezone(timezone.utc).timestamp()*1000)
    bit_ms = int(BIT.astimezone(timezone.utc).timestamp()*1000)

    # 2) HER ESIK ICIN TARA
    for esik in ESIKLER:
        cikti = os.path.join(KOK, f"esik_{int(esik)}.json")
        if os.path.exists(cikti):
            print(f"\n[2/3] 4H RSI >= {esik:.0f} — zaten var, atlaniyor", flush=True)
            continue
        DT.K4_RSI_MIN = esik
        print(f"\n[2/3] 4H RSI >= {esik:.0f} taraniyor...", flush=True)
        tum = []; t1 = time.time(); m = 0
        for sym in hazir:
            m += 1
            try:
                with open(os.path.join(VERI, f"{sym}.pkl"),"rb") as f: _AKTIF[sym] = pickle.load(f)
                sig, _ = DT.coin_tara(sym, bas_ms, bit_ms)
                tum += sig
            except Exception:
                pass
            finally:
                _AKTIF.pop(sym, None)
            if m % 50 == 0:
                print(f"    {m}/{len(hazir)}  {len(tum)} sinyal  {time.time()-t1:.0f}sn", flush=True)
        tum.sort(key=lambda x: x["t"])
        print(f"  -> {len(tum)} sinyal. cikislar hesaplaniyor...", flush=True)

        kapali = []
        for sg in tum:
            try:
                with open(os.path.join(VERI, f"{sg['s']}.pkl"),"rb") as f: v = pickle.load(f)
                t15,h15,l15,c15 = v["15m"]
                sebep, fiyat, ct, zirve = DT.cikis(sg, t15, h15, l15, c15)
            except Exception:
                continue
            brut = (fiyat/sg["giris"]-1)*100
            kapali.append({**sg, "sebep":sebep, "cikis":fiyat, "ct":ct,
                           "net":brut-DT.KOMISYON, "zirve_pct":(zirve/sg["giris"]-1)*100})
        json.dump({"kural":{"K4_RSI_MIN":esik,"K4_SRSI_MAX":DT.K4_SRSI_MAX,
                            "K1_RSI_MAX":DT.K1_RSI_MAX,"K1_SRSI_MAX":DT.K1_SRSI_MAX,
                            "K1_KDJ_J_MAX":DT.K1_KDJ_J_MAX,"K1_WR_MAX":DT.K1_WR_MAX,
                            "K15_RSI_MAX":DT.K15_RSI_MAX,"K15_SRSI_MAX":DT.K15_SRSI_MAX,
                            "K15_WR_MAX":DT.K15_WR_MAX,"TRAIL_PCT":DT.TRAIL_PCT,
                            "EXPIRE_H":DT.EXPIRE_H,"donem":"2021-01-01/2023-01-01",
                            "evren":len(hazir),"delist_dahil":True},
                   "islemler":kapali}, open(cikti,"w"))
        print(f"  KAYDEDILDI {cikti}  ({len(kapali)} kapali islem)", flush=True)

    # 3) OZET
    print("\n[3/3] OZET", flush=True)
    print(f"{'4H RSI':>7} {'sinyal':>7} {'ay/aday':>8} {'ort %':>8} {'medyan':>8} {'WR':>7}", flush=True)
    for esik in ESIKLER:
        p = os.path.join(KOK, f"esik_{int(esik)}.json")
        if not os.path.exists(p): continue
        d = json.load(open(p))["islemler"]
        if not d: print(f"{esik:>7.0f} {0:>7}", flush=True); continue
        v = np.array([x["net"] for x in d])
        print(f"{esik:>7.0f} {len(v):>7} {len(v)/24:>8.1f} {v.mean():>+8.3f} "
              f"{np.median(v):>+8.3f} {(v>0).mean()*100:>6.1f}%", flush=True)

if __name__ == "__main__":
    main()
