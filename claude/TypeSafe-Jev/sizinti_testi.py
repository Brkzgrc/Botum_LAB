#!/usr/bin/env python3
"""Jev sizinti testi — Jev gecmis piyasayi 'hatirliyor' mu? (gecmis veri backtest'inden ONCE)

Soru: Ayni teknik durum Jev'e (A) adsiz, (B) coin adiyla, (C) coin adi + tarihle verilince
Jev'in sonucu tahmin gucu artiyor mu? Artiyorsa Jev o donemi egitimden biliyordur ve gecmis
veri backtest'i gecersizdir (ya da ad/tarih mutlaka gizlenmelidir).

KURALLAR (sonuc gorulmeden sabitlendi, 2026-09-29):
  Evren    : ZEC NEAR SUI XRP LINK SOL (canli liste); BTC yalniz piyasa cumlesi.
  Donem    : son 60 gun; zaman noktalari 15 dk kapanislari arasindan sabit tohumla (20260929)
             rastgele N tane (sonrasinda en az 24 saat veri olan).
  Durum    : canli gozlemcinin (Botum jev_golge.gozlem) birebir cumleleri, 15 dk mum, 250 mum geri;
             haber YOK (gecmis arsiv yok); kasa ozeti sabit (hepsi nakit, 3 bos yer).
  Surumler : A = "Coin A..F", sektor yok · B = gercek ad + sektor · C = B + "Date: YYYY-MM-DD HH:MM UTC"
  Sorular  : coin basina 2 noul: buy_now (canli metin) ve up_24h ("Will X's price be higher
             24 hours from now than it is now?").
  Olcut    : AUC(up_24h, fiyat 24s sonra daha yuksek) ve AUC(buy_now, fiyat 6s sonra daha yuksek),
             her surum icin; fark C−A ve B−A, gun-blok bootstrap %95 araligi (2000 tekrar).
  Hukum    : SIZINTI = AUC(C,up_24h) − AUC(A,up_24h) > 0,05 VE %95 araligi 0'i dislar.
             Ayrica ortalama |C−A| ve |B−A| olasilik farki raporlanir.
  Butce    : cagri basina tahmin basilir; toplam tahmin > MAX_USD ise GONDERILMEZ.
             Kodda sabit tavan: MAX_USD ve MAX_CALLS. billing/401/402/403 -> tekrar deneme YOK, dur.
             429/5xx -> en fazla 3 deneme. Varsayilan KURU KOSU; gercek cagri icin --canli.
  Anahtar  : kodda YOK. Claude cloud ortami api.typesafe.ai istegine kimligi kendisi ekler.
  Kaynak   : gozlemci Botum'dan (private) calisma aninda ice aktarilir, bu depoya KOPYALANMAZ.
Cikti: script klasorune tek JSON.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, os.getenv("BOTUM_DIR", "/home/user/Botum"))
os.environ.setdefault("DATA_DIR", "/tmp/sizinti_testi_data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
import jev_golge as J  # noqa: E402  (Botum, private — yalniz calisma aninda)

API_KL = "https://data-api.binance.vision/api/v3/klines"
API_JEV = "https://api.typesafe.ai/v1/systemone"
OUT = Path(__file__).resolve().parent
COINS = dict(J.COINS)
DAYS = 60
SEED = 20260929
N = int(os.getenv("SIZINTI_N", "150"))
MAX_USD = 0.10
MAX_CALLS = 3 * 160
HTTP = requests.Session()


def kl(sym: str, interval: str, start_ms: int, end_ms: int) -> np.ndarray:
    out, cur = [], start_ms
    while cur < end_ms:
        r = HTTP.get(API_KL, params={"symbol": sym, "interval": interval, "startTime": cur, "limit": 1000},
                     timeout=30)
        r.raise_for_status()
        rows = [x for x in r.json() if x[6] < end_ms]
        if not rows:
            break
        out += [[float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]), float(x[6])]
                for x in rows]
        cur = int(rows[-1][0]) + 1
    return np.array(out)


def market_text(btc4: np.ndarray, btc1: np.ndarray) -> str:
    c4, c1 = btc4[:, 4], btc1[:, 4]
    p = c1[-1]
    r24 = (p / c1[-25] - 1) * 100
    med = float(np.median([J.atr(btc1[i - 20:i]) / btc1[i - 1, 4] * 100 for i in range(25, 60, 5)]))
    return (f"Bitcoin: 4h trend {J._trend(c4)}. Last 24 hours: {J._move_word(r24)}. "
            f"Bitcoin is {J._atr_word(J.atr(btc1) / p * 100, med)}.")


def questions(names: list[str]) -> dict:
    q = {}
    for n in names:
        q[f"{n}__buy_now"] = J.coin_questions(n)[f"{n}__buy_now"]
        q[f"{n}__up_24h"] = {"type": "noul",
                             "instructions": f"Will {n}'s price be higher 24 hours from now than it is now?",
                             "criteria": {"true": "The price 24 hours from now will be higher.",
                                          "false": "The price 24 hours from now will be the same or lower."}}
    return q


KASA = "Account: about 100% in cash. Open positions: none. Free slots: 3 of 3."


def build(t_idx: int, data: dict, surum: str, t_ms: float) -> tuple[dict, dict]:
    """t_idx: 15 dk dizisinde karar mumunun indeksi (kapanmis). Donus: (istek, ad eslemesi)."""
    paras, names, esle = [], [], {}
    for k, (sym, sector) in enumerate(COINS.items()):
        J._ARR[sym] = data[sym][t_idx - 249:t_idx + 1]
        text, _w, _tr = J.gozlem(sym, sector)
        gercek = sym[:-4]
        if surum == "A":
            ad = f"Coin {'ABCDEF'[k]}"
            text = text.replace(f"{gercek} ({sector}):", f"{ad}:", 1)
        else:
            ad = gercek
        esle[ad] = sym
        names.append(ad)
        paras.append(text)
    b4 = data["BTC4"]
    b1 = data["BTC1"]
    i4 = np.searchsorted(b4[:, 6], t_ms, side="right")
    i1 = np.searchsorted(b1[:, 6], t_ms, side="right")
    state = "Market: " + market_text(b4[i4 - 200:i4], b1[i1 - 60:i1]) + "\n\n" + KASA + "\n\n" + "\n\n".join(paras)
    if surum == "C":
        state = f"Date: {datetime.fromtimestamp(t_ms / 1000, timezone.utc):%Y-%m-%d %H:%M} UTC.\n\n" + state
    return {"model": J.MODEL, "state": state, "questions": questions(names)}, esle


def est_usd(body: dict) -> float:
    return math.ceil(len(json.dumps(body, ensure_ascii=False)) / 3.0) * J.USD_PER_TOKEN


class Dur(RuntimeError):
    pass


def send(body: dict) -> dict:
    for dn in range(3):
        r = HTTP.post(API_JEV, json=body, timeout=30)
        if r.status_code == 200:
            return r.json()
        txt = r.text[:300]
        if r.status_code in (401, 402, 403) or "billing" in txt.lower() or "authentication" in txt.lower():
            raise Dur(f"HTTP {r.status_code} {txt}")
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (dn + 1))
            continue
        raise Dur(f"HTTP {r.status_code} {txt}")
    raise Dur("3 denemede basarisiz (429/5xx)")


def auc(p: np.ndarray, y: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    # esitliklerde ortalama sira
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            r = r.astype(float)
            r[m] = r[m].mean()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canli", action="store_true")
    a = ap.parse_args()

    end_ms = int(time.time() // 900 * 900 * 1000)
    start_ms = end_ms - DAYS * 86_400_000
    look = 250 * 900_000
    data = {}
    for sym in COINS:
        data[sym] = kl(sym, "15m", start_ms - look - 86_400_000, end_ms)
        print(f"[VERI] {sym} {len(data[sym])} mum", flush=True)
    data["BTC4"] = kl("BTCUSDT", "4h", start_ms - 40 * 86_400_000, end_ms)
    data["BTC1"] = kl("BTCUSDT", "1h", start_ms - 5 * 86_400_000, end_ms)

    ref = data["ZECUSDT"][:, 6]
    ok = [i for i in range(len(ref)) if ref[i] >= start_ms and i + 96 < len(ref) and i >= 260
          and all(len(data[s]) == len(ref) and data[s][i, 6] == ref[i] for s in COINS)]
    rnd = random.Random(SEED)
    secim = sorted(rnd.sample(ok, min(N, len(ok))))
    print(f"[SECIM] {len(secim)} zaman noktasi / {len(ok)} aday", flush=True)

    istek = [(i, s, *build(i, data, s, ref[i])) for i in secim for s in "ABC"]
    toplam = sum(est_usd(b) for _, _, b, _ in istek)
    print(f"[TAHMIN] {len(istek)} cagri, ~${toplam:.4f} (tavan ${MAX_USD}, {MAX_CALLS} cagri)", flush=True)
    if toplam > MAX_USD or len(istek) > MAX_CALLS:
        print("[DUR] tahmin tavani asiyor — gonderilmedi.")
        return 2
    if not a.canli:
        print("[KURU] gonderilmedi. Ornek state (A):\n" + istek[0][2]["state"][:900])
        return 0

    kayit, harcanan, hata = [], 0.0, None
    for n_, (i, s, body, esle) in enumerate(istek):
        if harcanan + est_usd(body) > MAX_USD:
            hata = "harcama tavani"
            break
        try:
            resp = send(body)
        except Dur as e:
            hata = str(e)
            print(f"[DUR] {e}", flush=True)
            break
        tok = (resp.get("usage") or {}).get("input_tokens") or 0
        harcanan += tok * J.USD_PER_TOKEN if tok else est_usd(body)
        ans = resp.get("answers") or {}
        for ad, sym in esle.items():
            c = data[sym][:, 4]
            kayit.append({"i": i, "t": int(ref[i]), "surum": s, "sym": sym[:-4],
                          "buy_now": (ans.get(f"{ad}__buy_now") or {}).get("noul"),
                          "up_24h": (ans.get(f"{ad}__up_24h") or {}).get("noul"),
                          "y6": int(c[i + 24] > c[i]), "y24": int(c[i + 96] > c[i])})
        if n_ % 30 == 0:
            print(f"[CANLI] {n_ + 1}/{len(istek)} ${harcanan:.4f}", flush=True)

    # analiz
    rows = [r for r in kayit if r["buy_now"] is not None and r["up_24h"] is not None]
    def arr(s, k):
        z = sorted((r for r in rows if r["surum"] == s), key=lambda r: (r["i"], r["sym"]))
        return z, np.array([r[k] for r in z], float)
    zA, _ = arr("A", "up_24h")
    ortak = {(r["i"], r["sym"]) for r in zA}
    for s in "BC":
        ortak &= {(r["i"], r["sym"]) for r in rows if r["surum"] == s}
    R = {s: {(r["i"], r["sym"]): r for r in rows if r["surum"] == s and (r["i"], r["sym"]) in ortak} for s in "ABC"}
    keys = sorted(ortak)
    gun = np.array([int(R["A"][k]["t"] // 86_400_000) for k in keys])
    y24 = np.array([R["A"][k]["y24"] for k in keys])
    y6 = np.array([R["A"][k]["y6"] for k in keys])
    P = {(s, q): np.array([R[s][k][q] for k in keys]) for s in "ABC" for q in ("up_24h", "buy_now")}
    sonuc = {"n": len(keys), "harcanan_usd": round(harcanan, 5), "hata": hata}
    for s in "ABC":
        sonuc[f"auc_up24_{s}"] = round(auc(P[(s, "up_24h")], y24), 4)
        sonuc[f"auc_buy6_{s}"] = round(auc(P[(s, "buy_now")], y6), 4)
    ug = np.unique(gun)
    brnd = np.random.default_rng(SEED)
    for s in "BC":
        for q, y in (("up_24h", y24), ("buy_now", y6)):
            d = []
            for _ in range(2000):
                g = brnd.choice(ug, len(ug), replace=True)
                m = np.concatenate([np.where(gun == x)[0] for x in g])
                d.append(auc(P[(s, q)][m], y[m]) - auc(P[("A", q)][m], y[m]))
            d = np.array([x for x in d if np.isfinite(x)])
            sonuc[f"fark_{q}_{s}-A"] = round(float(auc(P[(s, q)], y) - auc(P[("A", q)], y)), 4)
            sonuc[f"ci95_{q}_{s}-A"] = [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]
            sonuc[f"ort_mutlak_fark_{q}_{s}-A"] = round(float(np.mean(np.abs(P[(s, q)] - P[("A", q)]))), 4)
    lo = sonuc["ci95_up_24h_C-A"][0]
    sonuc["HUKUM"] = ("SIZINTI" if sonuc["fark_up_24h_C-A"] > 0.05 and lo > 0 else "SIZINTI GORULMEDI")
    print(json.dumps(sonuc, indent=1, ensure_ascii=False))
    t0 = datetime.now(timezone.utc)
    s0 = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    e0 = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    fn = OUT / f"sizinti_testi_{s0:%Y%m%d}_{e0:%Y%m%d}_{t0:%Y%m%d_%H%M}.json"
    fn.write_text(json.dumps({"kurallar": __doc__, "sonuc": sonuc, "kayit": kayit}, ensure_ascii=False),
                  encoding="utf-8")
    print(f"[KAYIT] {fn.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
