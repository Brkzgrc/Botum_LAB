#!/usr/bin/env python3
"""Coin uyum olcumu — hangi coin Jev'in cikis kurallarina UYUYOR? (getiri testi DEGIL)

Soru: Jev sisteminin sabit kurallari (15 dk karar, -%3,5 stop, +%6,5 kar al, kar %2'yi
gecince zirveden -%1,3, en fazla 6 saat) hangi coinlerin hareket karakterine uyuyor?
Jev'e HIC sorulmaz. Sinyal YOK: her 15 dk kapanisinda rastgele giris.

KURALLAR (sonuc gorulmeden sabitlendi, 2026-09-29):
  Evren  : Binance USDT spot, TRADING; BTC, stablecoin, sarili token ve hisse tokeni haric;
           24s hacim >= 100M$ olan ilk 20 + mevcut 6 (ETH SOL BNB XRP ZEC LINK). Referans BTC.
  Veri   : son 90 gun, 1 DAKIKALIK mum (CLAUDE.md kural 7: stop/hedef 1dk low/high ile).
  Giris  : her 15 dk mum kapanisi (sonraki 1dk mumdan itibaren izlenir), giris = o kapanis.
  Cikis  : canli guvenlik kurallariyla BIREBIR (jev_golge.portfoy_kontrol):
           ayni mumda sira stop -> kar koruma (onceki zirveye gore) -> kar al -> sure; zirve en son.
           Komisyon %0,20.
  Olculer:
    hareket     : 6 saatte fiyatin +%6,5 VEYA -%6,5'e degdigi girislerin orani (yonsuz hareket kapasitesi)
    gurultu     : medyan 15dk ATR(14) % / %3,5  (stop'un gurultuye oranla ne kadar genis oldugu)
    cikis dagilimi (uzun, rastgele giris): kar al / stop / kar koruma / sure yuzdeleri
    ort_net     : rastgele uzun girisin ortalama net getirisi — DONEMIN TRENDINE BAGLI,
                  SECIM OLCUTU DEGIL (sadece bilgi)
    btc_korelasyon, ikili korelasyon: 1 saatlik log getiriler
    cift_temas  : ayni 1dk mumda hem stop hem hedef — sayi raporlanir (kural 7)
  Dilimler: 90 gun + 3 x 30 gun ayri (tek donem hukum vermez, kural 6).

Cikti: script klasorune tek JSON (CLAUDE.md cikti kurali). Ham veri scratch onbellekte, repoya girmez.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

API = "https://data-api.binance.vision/api/v3"
OUT = Path(__file__).resolve().parent
CACHE = Path(os.getenv("COIN_UYUM_CACHE", "/tmp/coin_uyum_cache"))
DAYS = 90
MEVCUT = ["ETH", "SOL", "BNB", "XRP", "ZEC", "LINK"]
MIN_QV = 100e6
TOP_N = 20
SL, TP, PSTART, PGIVE, HOLD_MIN = 3.5, 6.5, 2.0, 1.3, 360
FEE = 0.2
HAREKET = 6.5
STABLE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "USD1", "EUR", "EURI", "PAXG", "XAUT", "USDE",
          "BFUSD", "RLUSD", "PYUSD", "AEUR", "U", "USDS", "XUSD", "WBTC", "WBETH", "BETH", "BNSOL", "BTC"}
HTTP = requests.Session()


def universe() -> list[str]:
    t = HTTP.get(f"{API}/ticker/24hr", timeout=30).json()
    info = HTTP.get(f"{API}/exchangeInfo", params={"permissions": "SPOT"}, timeout=30).json()
    ok = {s["symbol"]: s["baseAsset"] for s in info["symbols"]
          if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"}
    rows = []
    for x in t:
        b = ok.get(x["symbol"])
        if not b or b in STABLE or b.endswith("UP") or b.endswith("DOWN"):
            continue
        if b.endswith("B") and b[:-1].isupper() and len(b) >= 4 and b[:-1] in (
                "NVDA", "AAPL", "MSFT", "AMZN", "TSM", "META", "GOOGL", "SPCX", "AVGO", "MU", "TSLA", "AMD"):
            continue                                   # hisse tokenleri
        qv = float(x["quoteVolume"])
        if qv >= MIN_QV:
            rows.append((qv, b))
    rows.sort(reverse=True)
    sec = [b for _, b in rows[:TOP_N]]
    for b in MEVCUT:
        if b not in sec:
            sec.append(b)
    return sec


def kline_1m(base: str, start_ms: int, end_ms: int) -> np.ndarray:
    f = CACHE / f"{base}_{start_ms}_{end_ms}.npy"
    if f.exists():
        return np.load(f)
    out, cur = [], start_ms
    while cur < end_ms:
        for dn in range(4):
            try:
                r = HTTP.get(f"{API}/klines", params={"symbol": base + "USDT", "interval": "1m",
                                                     "startTime": cur, "limit": 1000}, timeout=30)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 * (dn + 1))
        else:
            raise RuntimeError(f"{base} veri alinamadi")
        rows = [x for x in r.json() if x[6] < end_ms]
        if not rows:
            break
        out.extend([[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in rows])
        cur = rows[-1][0] + 60_000
    a = np.array(out, dtype=float)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(f, a)
    return a


def atr_pct_15m(a: np.ndarray) -> float:
    n = len(a) // 15 * 15
    b = a[:n].reshape(-1, 15, 5)
    h, l, c = b[:, :, 2].max(1), b[:, :, 3].min(1), b[:, -1, 4]
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    atr = np.convolve(tr, np.ones(14) / 14, mode="valid")
    return float(np.median(atr / c[13:] * 100))


def simulate(a: np.ndarray, i0: int, i1: int) -> dict:
    """Girisler: a[i,0] 15 dk'nin katlari olan mumlarin KAPANISI (i = 15dk'nin son dakikasi)."""
    ot, o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]
    idx = [i for i in range(i0, min(i1, len(a) - HOLD_MIN - 1)) if (ot[i] / 60000 + 1) % 15 == 0]
    res = {"tp": 0, "stop": 0, "koru": 0, "sure": 0}
    nets, hareket, cift = [], 0, 0
    for i in idx:
        e = c[i]
        sl, tp = e * (1 - SL / 100), e * (1 + TP / 100)
        peak = e
        hh = h[i + 1:i + 1 + HOLD_MIN].max()
        ll = l[i + 1:i + 1 + HOLD_MIN].min()
        if hh >= e * (1 + HAREKET / 100) or ll <= e * (1 - HAREKET / 100):
            hareket += 1
        why, px = "sure", c[i + HOLD_MIN]
        for k in range(i + 1, i + 1 + HOLD_MIN):
            if l[k] <= sl and h[k] >= tp:
                cift += 1
            if l[k] <= sl:
                why, px = "stop", min(o[k], sl)
                break
            if peak >= e * (1 + PSTART / 100) and l[k] <= peak * (1 - PGIVE / 100):
                why, px = "koru", min(o[k], peak * (1 - PGIVE / 100))
                break
            if h[k] >= tp:
                why, px = "tp", max(o[k], tp)
                break
            peak = max(peak, h[k])
        res[why] += 1
        nets.append((px / e - 1) * 100 - FEE)
    n = len(idx)
    return {"n": n,
            "hareket_%": round(hareket / n * 100, 1) if n else None,
            **{f"{k}_%": round(v / n * 100, 1) if n else None for k, v in res.items()},
            "ort_net_%": round(float(np.mean(nets)), 3) if n else None,
            "cift_temas": cift}


def hourly_ret(a: np.ndarray) -> dict:
    c = a[:, 4]
    t = a[:, 0]
    m = ((t / 60000 + 1) % 60 == 0)
    return dict(zip((t[m] // 3_600_000).astype(int), np.log(c[m])))


def main() -> int:
    end_ms = int(time.time() // 60 * 60 * 1000) - 60_000
    start_ms = end_ms - DAYS * 86_400_000
    coins = universe()
    print(f"[EVREN] {len(coins)} coin: {' '.join(coins)}", flush=True)
    data = {}

    def al(b):
        return b, kline_1m(b, start_ms, end_ms)

    with ThreadPoolExecutor(max_workers=4) as ex:
        for b, a in ex.map(al, coins + ["BTC"]):
            data[b] = a
            print(f"[VERI] {b}: {len(a)} dakika", flush=True)

    # 1 saatlik getiriler -> korelasyon
    hr = {b: hourly_ret(a) for b, a in data.items()}
    ortak = sorted(set.intersection(*[set(v) for v in hr.values()]))
    R = {b: np.diff([hr[b][k] for k in ortak]) for b in hr}

    sonuc = {}
    for b in coins:
        a = data[b]
        n = len(a)
        dil = [(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)]
        tum = simulate(a, 0, n)
        dilimler = [simulate(a, x, y) for x, y in dil]
        sonuc[b] = {"mevcut_listede": b in MEVCUT, "atr15_%": round(atr_pct_15m(a), 3),
                    "gurultu_stop_orani": round(atr_pct_15m(a) / SL, 3),
                    "btc_korelasyon": round(float(np.corrcoef(R[b], R["BTC"])[0, 1]), 3),
                    "90gun": tum, "30gun_dilimler": dilimler}
        print(f"[OLCUM] {b:6} hareket %{tum['hareket_%']:5}  tp %{tum['tp_%']:5}  stop %{tum['stop_%']:5}  "
              f"koru %{tum['koru_%']:5}  sure %{tum['sure_%']:5}  atr15 %{sonuc[b]['atr15_%']:.2f}  "
              f"btc r {sonuc[b]['btc_korelasyon']:.2f}  | dilim hareket "
              + " / ".join(str(d["hareket_%"]) for d in dilimler), flush=True)
    kor = {b1: {b2: round(float(np.corrcoef(R[b1], R[b2])[0, 1]), 3) for b2 in coins} for b1 in coins}

    t0 = datetime.now(timezone.utc)
    s = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    e = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    fn = OUT / f"coin_uyum_{s:%Y%m%d}_{e:%Y%m%d}_{t0:%Y%m%d_%H%M}.json"
    fn.write_text(json.dumps({"kurallar": __doc__, "baslangic": s.isoformat(), "bitis": e.isoformat(),
                              "coinler": sonuc, "korelasyon_1s": kor}, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    print(f"[KAYIT] {fn.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
