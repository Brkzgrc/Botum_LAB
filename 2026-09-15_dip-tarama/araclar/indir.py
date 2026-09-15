# -*- coding: utf-8 -*-
"""451 islemin sinyal anina kadar KAPANMIS mumlarini indirir. Ileriye bakma yok."""
import json, os, time, pickle, sys
from concurrent.futures import ThreadPoolExecutor
import requests

BASE = "https://data-api.binance.vision"
OUT  = os.path.dirname(os.path.abspath(__file__))
SRC  = "/home/user/botum_lab/2026-09-15_dip-tarama/sonuclar/dip_tarama_TUMEVREN_20250101_20261001_20260912_1310.json"

# her TF icin kac mum geriye (gosterge isinmasi + yapi olculeri icin bol tutuldu)
PENCERE = {"15m": 400, "1h": 400, "4h": 400}
MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}

oturum = requests.Session()

def klines(sym, tf, bitis_ms, limit):
    """bitis_ms'den ONCE kapanmis son `limit` mum."""
    for deneme in range(4):
        try:
            r = oturum.get(f"{BASE}/api/v3/klines", timeout=20, params={
                "symbol": sym, "interval": tf, "endTime": bitis_ms - 1, "limit": limit})
            if r.status_code == 200:
                return [[float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5]),int(k[6])] for k in r.json()]
            if r.status_code in (418, 429):
                time.sleep(2 ** deneme * 2); continue
            return None
        except Exception:
            time.sleep(1.5 * (deneme + 1))
    return None

islemler = json.load(open(SRC))["islemler"]
print(f"islem sayisi: {len(islemler)}", flush=True)

sonuc = {}
sayac = [0]

def isle(i_t):
    i, t = i_t
    anahtar = f"{t['s']}|{t['t']}"
    veri = {}
    for tf, lim in PENCERE.items():
        k = klines(t["s"], tf, t["t"], lim)
        if k is None or len(k) < 60:
            return anahtar, None
        veri[tf] = k
    sayac[0] += 1
    if sayac[0] % 25 == 0:
        print(f"  {sayac[0]}/{len(islemler)}", flush=True)
    return anahtar, veri

with ThreadPoolExecutor(max_workers=6) as ex:
    for anahtar, veri in ex.map(isle, enumerate(islemler)):
        sonuc[anahtar] = veri

basarili = sum(1 for v in sonuc.values() if v)
print(f"\nbasarili {basarili} / {len(islemler)}", flush=True)
with open(os.path.join(OUT, "mumlar.pkl"), "wb") as f:
    pickle.dump(sonuc, f, protocol=4)
print(f"kaydedildi: {os.path.getsize(os.path.join(OUT,'mumlar.pkl'))/1048576:.1f} MB", flush=True)
