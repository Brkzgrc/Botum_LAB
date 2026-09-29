#!/usr/bin/env python3
"""Jev 60 gunluk gecmis testi — canli sistemin (Botum jev_golge) birebir tekrari, sanal kasa.

KURALLAR (sonuc gorulmeden sabitlendi, 2026-09-30; kullanici onayi: ~1,0-1,5$):
  Kod       : gozlemci, kontrol kurali, sorular, esikler Botum jev_golge'den calisma aninda ice aktarilir
              (bu public depoya KOPYALANMAZ). Kural defteri canli _karar ile ayni sirada yeniden kuruldu.
  Evren     : ZEC NEAR SUI XRP LINK SOL (canli liste); BTC yalniz piyasa cumlesi.
  Donem     : 2026-07-31 19:00 -> 2026-09-29 19:00 UTC (60 gun, 5.760 tur).
  Sizinti   : coin adlari gizli (Coin A-F, sektor yok), tarih yok (sizinti_testi: sizinti gorulmedi).
  Farklar   : haber arsivi yok -> "News: no notable crypto headlines..." (canlida sessiz donem cumlesi);
              neden olcumu yok (karara etkisi yok, yalniz aciklama).
  Tur       : her 15 dk kapanisi T'de kapanmis mumlarla durum; tek Jev cagrisi; kasa ozeti sanal
              kasadan. Alis ve Jev satisi T'den sonraki ilk 1 dk mumun ACILISINDAN (spread modellenmedi).
  Guvenlik  : 1 dk mum, canli sira: stop -> kar koruma (onceki zirve) -> kar al (tam hedef) -> sure;
              zirve en son. Stop/koruma dolumu min(acilis, seviye).
  Kasalar   : Jev ve Kural, ikisi 6.000$, ayni turlarda. Komisyon %0,20. Donem sonunda acik
              pozisyonlar son fiyattan degerlenir (satilmis sayilmaz).
  Rapor     : 60 gun + 2 x 30 gun dilim ayri (CLAUDE.md kural 6). Tek kosu, sonuca bakip ayar YOK.
  Butce     : tahmin basilir; MAX_USD / MAX_CALLS kodda sabit; billing/401/402/403 -> dur, tekrar deneme
              yok; 429/5xx -> en fazla 3. Her cevap veri/ altina yazilir ve periyodik olarak depoya
              gonderilir: yeniden calistirmada ayni tur tekrar ucretlendirilmez.
Cikti: script klasorune .json (veri) + .html (rapor); cevap onbellegi veri/ altinda.
Kosu: --canli (varsayilan kuru), --rapor JSON (yalniz HTML).
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, os.getenv("BOTUM_DIR", "/home/user/Botum"))
os.environ.setdefault("DATA_DIR", "/tmp/geri_test_data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
import jev_golge as J  # noqa: E402

API_KL = "https://data-api.binance.vision/api/v3/klines"
API_JEV = "https://api.typesafe.ai/v1/systemone"
OUT = Path(__file__).resolve().parent
SCR = Path(os.getenv("GERI_TEST_SCRATCH", "/tmp/geri_test_scratch"))
SCR.mkdir(parents=True, exist_ok=True)
ANS_CACHE = Path(os.getenv("GERI_TEST_CACHE", str(OUT / "veri" / "geri_test_60g_cevaplar.jsonl")))
ANS_CACHE.parent.mkdir(parents=True, exist_ok=True)
PUSH_EVERY = int(os.getenv("GERI_TEST_PUSH_EVERY", "300"))      # 0 -> depoya gonderme
START = int(datetime(2026, 7, 31, 19, 0, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 9, 29, 19, 0, tzinfo=timezone.utc).timestamp() * 1000)
M15 = 900_000
MAX_USD = 1.60
MAX_CALLS = 6000
COINS = dict(J.COINS)
ANON = {sym: f"Coin {'ABCDEF'[k]}" for k, sym in enumerate(COINS)}
HTTP = requests.Session()


# ---------------------------------------------------------------- veri
def kl(sym, interval, start_ms, end_ms, cols=7):
    f = SCR / f"{sym}_{interval}_{start_ms}_{end_ms}.npy"
    if f.exists():
        return np.load(f)
    out, cur = [], start_ms
    while cur < end_ms:
        for dn in range(4):
            try:
                r = HTTP.get(API_KL, params={"symbol": sym, "interval": interval, "startTime": cur, "limit": 1000},
                             timeout=30)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 * (dn + 1))
        else:
            raise RuntimeError(f"{sym} {interval} veri alinamadi")
        rows = [x for x in r.json() if x[6] < end_ms]
        if not rows:
            break
        out += [[float(v) for v in x[:cols]] for x in rows]
        cur = int(rows[-1][0]) + 1
    a = np.array(out)
    np.save(f, a)
    return a


LOOK = {"15m": 4 * 86_400_000, "1h": 10 * 86_400_000, "4h": 36 * 86_400_000, "1d": 105 * 86_400_000}
D: dict = {}
NOW = {"T": 0}


def fake_klines(symbol, interval, limit):
    a = D[symbol][interval]
    i = int(np.searchsorted(a[:, 6], NOW["T"], side="left"))   # yalniz T'den once KAPANMIS mumlar
    return a[max(0, i - limit):i]


# ---------------------------------------------------------------- sanal kasa (canli kurallar)
def new_book():
    return {"cash": J.START_USD, "pos": {}, "trades": [], "fees": 0.0, "sold": {}}


def equity(b, last):
    return b["cash"] + sum(x["qty"] * last[s] for s, x in b["pos"].items())


def expo(b, last):
    e = equity(b, last)
    return sum(x["qty"] * last[s] for s, x in b["pos"].items()) / e if e else 0.0


def buy(b, sym, px, t, usd, why):
    usd = min(usd, b["cash"])
    if usd < J.MIN_USD:
        return False
    b["cash"] -= usd
    b["fees"] += usd * J.FEE_SIDE
    b["pos"][sym] = {"entry": px, "qty": usd * (1 - J.FEE_SIDE) / px, "usd": usd, "peak": px,
                     "opened": t, "why": why}
    return True


def sell(b, sym, px, t, reason, kind):
    x = b["pos"].pop(sym)
    g = x["qty"] * px
    b["cash"] += g * (1 - J.FEE_SIDE)
    b["fees"] += g * J.FEE_SIDE
    pnl = g * (1 - J.FEE_SIDE) - x["usd"]
    b["trades"].append({"sym": sym[:-4], "entry": x["entry"], "exit": px, "usd": round(x["usd"], 2),
                        "pnl": round(pnl, 2), "pct": round(pnl / x["usd"] * 100, 3), "reason": reason,
                        "kind": kind, "opened": x["opened"], "closed": t, "why": x["why"]})
    b["sold"][sym] = t


def guard_bar(b, sym, o, h, l, c, t):
    """Canli portfoy_kontrol ile ayni sira. True -> pozisyon kapandi."""
    x = b["pos"][sym]
    sl = x["entry"] * (1 - J.SL_PCT / 100)
    tp = x["entry"] * (1 + J.TP_PCT / 100)
    koru = x["peak"] >= x["entry"] * (1 + J.PROTECT_START / 100)
    trail = x["peak"] * (1 - J.PROTECT_GIVEBACK / 100)
    if l <= sl:
        sell(b, sym, min(o, sl), t, f"zarar durdur −%{J.SL_PCT:g}", "guvenlik")
    elif koru and l <= trail:
        sell(b, sym, min(o, trail), t, f"kâr koruma (zirveden −%{J.PROTECT_GIVEBACK:g})", "guvenlik")
    elif h >= tp:
        sell(b, sym, tp, t, f"kâr al +%{J.TP_PCT:g}", "guvenlik")
    elif t + 60_000 >= x["opened"] + J.MAX_HOLD_H * 3_600_000:
        sell(b, sym, c, t, f"{J.MAX_HOLD_H} saat doldu", "guvenlik")
    else:
        x["peak"] = max(x["peak"], h)
        return False
    return True


def kasa_ozeti(b, last):
    e = equity(b, last)
    cash = b["cash"] / e * 100 if e else 100
    pos = "; ".join(f"{ANON[s]} ({'up' if last[s] >= x['entry'] else 'down'} "
                    f"{'a little' if abs(last[s] / x['entry'] - 1) < 0.02 else 'clearly'})"
                    for s, x in b["pos"].items()) or "none"
    return (f"Account: about {cash:.0f}% in cash. Open positions: {pos}. "
            f"Free slots: {J.MAX_POS - len(b['pos'])} of {J.MAX_POS}.")


def build(T, jb, last):
    NOW["T"] = T
    mtext, _ = J.describe_market()
    paras, raws = [], {}
    for sym, sector in COINS.items():
        _t, r = J.describe(sym, sector)
        raws[sym] = r
        text, _w, _tr = J.gozlem(sym, sector)
        paras.append(text.replace(f"{sym[:-4]} ({sector}):", f"{ANON[sym]}:", 1))
    names = [ANON[s] for s in COINS]
    state = ("Market: " + mtext + "\n\nNews: no notable crypto headlines in the last 6 hours.\n\n"
             + kasa_ozeti(jb, last) + "\n\n" + "\n\n".join(paras))
    q = {}
    for n in names:
        q.update(J.coin_questions(n))
    q.update(J.market_questions(names))
    return {"model": J.MODEL, "state": state, "questions": q}, raws


# ---------------------------------------------------------------- Jev
class Dur(RuntimeError):
    pass


def send(body):
    for dn in range(3):
        try:
            r = HTTP.post(API_JEV, json=body, timeout=30)
        except requests.RequestException:          # baglanti kopmasi: 5xx gibi, en fazla 3 deneme
            time.sleep(2 * (dn + 1))
            continue
        if r.status_code == 200:
            return r.json()
        txt = r.text[:300]
        if r.status_code in (401, 402, 403) or "billing" in txt.lower() or "authentication" in txt.lower():
            raise Dur(f"HTTP {r.status_code} {txt}")
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (dn + 1))
            continue
        raise Dur(f"HTTP {r.status_code} {txt}")
    raise Dur("3 denemede basarisiz (429/5xx/baglanti)")


def est_usd(body):
    return math.ceil(len(json.dumps(body, ensure_ascii=False)) / 3.0) * J.USD_PER_TOKEN


def load_cache():
    c = {}
    if ANS_CACHE.exists():
        for ln in ANS_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                c[r["T"]] = r
            except Exception:
                pass
    return c


def push_cache(n):
    """Odenmis cevaplari depoya gonder (container yeniden baslarsa kaybolmasin)."""
    if not PUSH_EVERY:
        return
    try:
        repo = subprocess.run(["git", "-C", str(OUT), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", repo, "add", str(ANS_CACHE)], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", f"Jev geri test: cevap onbellegi ({n} tur)"],
                       capture_output=True)
        subprocess.run(["git", "-C", repo, "pull", "-q", "--rebase", "origin", "main"], capture_output=True)
        r = subprocess.run(["git", "-C", repo, "push", "-q", "origin", "main"], capture_output=True, text=True)
        print(f"[ONBELLEK] {n} tur depoya {'gonderildi' if r.returncode == 0 else 'GONDERILEMEDI'}", flush=True)
    except Exception as e:
        print(f"[ONBELLEK] gonderilemedi: {e}", flush=True)


# ---------------------------------------------------------------- ana dongu
def run(canli):
    for sym in list(COINS) + ["BTCUSDT"]:
        D[sym] = {iv: kl(sym, iv, START - LOOK[iv], END + 86_400_000) for iv in LOOK}
    one = {}
    for sym in COINS:
        a = kl(sym, "1m", START - 3_600_000, END + 3_600_000, cols=5)     # [ot, o, h, l, c]
        assert a[0, 0] <= START and a[-1, 0] >= END - 60_000, f"{sym} 1dk veri donemi kapsamiyor"
        one[sym] = a
        print(f"[VERI] {sym} 1dk {len(a)}", flush=True)
    J.klines = fake_klines           # canli kod artik gecmis veriyi, T'den once kapananlari gorur
    idx1 = {s: int(np.searchsorted(a[:, 0], START)) for s, a in one.items()}
    turns = list(range(START, END, M15))
    cache = load_cache()

    last0 = {s: float(one[s][idx1[s] - 1, 4]) for s in COINS}
    body0, _ = build(turns[0], new_book(), last0)
    kalan = sum(1 for T in turns if T not in cache)
    tahmin = est_usd(body0) * kalan
    print(f"[TAHMIN] {len(turns)} tur, onbellekte {len(turns) - kalan}, yeni {kalan} cagri, "
          f"~${tahmin:.3f} (sizinti testinde gercek/tahmin ~0,87) · tavan ${MAX_USD}/{MAX_CALLS}", flush=True)
    if tahmin > MAX_USD or kalan > MAX_CALLS:
        print("[DUR] tahmin tavani asiyor — gonderilmedi.")
        return None
    if not canli and kalan:
        print("[KURU] gonderilmedi. Ornek state:\n" + body0["state"][:1200])
        return None

    jb, kb = new_book(), new_book()
    cnt = {"temkinli": 0, "veto": 0, "danisman": 0, "turlar": 0, "cevapsiz": 0}
    curve, harcanan, cagri, hata = [], 0.0, 0, None
    last = dict(last0)
    ptr = dict(idx1)
    f_cache = ANS_CACHE.open("a", encoding="utf-8")
    t_basla = time.time()
    for n_, T in enumerate(turns):
        for s in COINS:                      # 1) guvenlik: T'den once acilan 1dk mumlar
            a = one[s]
            while ptr[s] < len(a) and a[ptr[s], 0] < T:
                ot, o, h, l, c = a[ptr[s]]
                for b in (jb, kb):
                    if s in b["pos"]:
                        guard_bar(b, s, o, h, l, c, ot)
                last[s] = c
                ptr[s] += 1
        body, raws = build(T, jb, last)      # 2) karar
        if T in cache:
            ans = cache[T]["answers"]
        else:
            if harcanan + est_usd(body) > MAX_USD or cagri >= MAX_CALLS:
                hata = "butce tavani"
                break
            try:
                resp = send(body)
            except Dur as e:
                hata = str(e)
                print(f"[DUR] {e}", flush=True)
                break
            cagri += 1
            tok = (resp.get("usage") or {}).get("input_tokens") or 0
            harcanan += tok * J.USD_PER_TOKEN if tok else est_usd(body)
            ans = J._compact_answers(resp)
            f_cache.write(json.dumps({"T": T, "answers": ans, "tok": tok}, ensure_ascii=False) + "\n")
            f_cache.flush()
            if PUSH_EVERY and cagri % PUSH_EVERY == 0:
                push_cache(n_ + 1)
        cnt["turlar"] += 1
        fill = {s: float(one[s][ptr[s], 1]) for s in COINS}            # T'den sonraki ilk 1dk acilisi
        wt = ans.get("market__weather") or {}
        hava, guven = wt.get("choice"), wt.get("conf")
        temkinli = isinstance(guven, (int, float)) and guven <= J.CAUTIOUS_CONF
        cnt["temkinli"] += int(temkinli)
        tavan = J.EXPOSURE.get(hava, J.EXPOSURE["mixed"])
        kontrol = {s: J.kontrol_skoru(r)["score"] for s, r in raws.items()}
        for s in COINS:
            n = ANON[s]
            g = lambda k: ans.get(f"{n}__{k}") if isinstance(ans.get(f"{n}__{k}"), (int, float)) else None
            bn, sn, bf, ch = g("buy_now"), g("sell_now"), g("buy_fresh"), g("chasing")
            if bn is None:
                cnt["cevapsiz"] += 1
            edge = bn - 0.5 if bn is not None else None
            if s in jb["pos"]:
                held = (T - jb["pos"][s]["opened"]) / 60000
                sat = sn is not None and sn >= J.SELL_TH
                kuc = bf is not None and bf < J.FRESH_TH
                if (sat or kuc) and held >= J.MIN_HOLD_MIN:
                    sell(jb, s, fill[s], T, (f"Jev: satalım mı {sn:.2f}" if sat else f"Jev: sıfırdan alır mıydın {bf:.2f}"),
                         "danisman")
                    cnt["danisman"] += 1
            elif edge is None or edge <= J.EDGE_MIN:
                pass
            elif ch is not None and ch > J.CHASE_VETO:
                cnt["veto"] += 1
            elif jb["sold"].get(s, -1e18) > T - J.MIN_HOLD_MIN * 60000:
                pass
            elif len(jb["pos"]) < J.MAX_POS:
                oran = min(J.MAX_FRAC, J.SIZE_PER_EDGE * edge) * (J.CAUTIOUS_MULT if temkinli else 1)
                e = equity(jb, last)
                bos = max(0.0, tavan * e - expo(jb, last) * e)
                buy(jb, s, fill[s], T, min(oran * e, bos), f"alınır {bn:.2f}, kenar {edge:+.2f}")
            ks = kontrol[s]
            if (ks >= J.KURAL_ENTRY and s not in kb["pos"] and len(kb["pos"]) < J.MAX_POS
                    and kb["sold"].get(s, -1e18) <= T - J.MIN_HOLD_MIN * 60000):
                buy(kb, s, fill[s], T, J.KURAL_FRAC * equity(kb, last), f"kural puanı {ks:.2f}")
        curve.append({"T": T, "jev": round(equity(jb, last), 2), "kural": round(equity(kb, last), 2),
                      "jev_expo": round(expo(jb, last), 3)})
        if n_ % 200 == 0:
            gecen = time.time() - t_basla
            print(f"[TUR] {n_ + 1}/{len(turns)} {datetime.fromtimestamp(T / 1000, timezone.utc):%m-%d %H:%M} "
                  f"Jev {equity(jb, last):,.0f}$ Kural {equity(kb, last):,.0f}$ · ${harcanan:.3f} · {gecen / 60:.1f} dk",
                  flush=True)
    f_cache.close()
    if cagri:
        push_cache(len(curve))
    return {"jb": jb, "kb": kb, "cnt": cnt, "curve": curve, "harcanan": round(harcanan, 4), "cagri": cagri,
            "hata": hata, "last": last, "tamam": hata is None,
            "bench": {s: round((last[s] / float(one[s][idx1[s], 1]) - 1) * 100, 2) for s in COINS}}


# ---------------------------------------------------------------- ozet + HTML
def stats(b, curve, key, t0, t1):
    tr = [x for x in b["trades"] if t0 <= x["closed"] < t1]
    cv = [c[key] for c in curve if t0 <= c["T"] < t1]
    dd, pk = 0.0, None
    for v in cv:
        pk = v if pk is None else max(pk, v)
        dd = min(dd, (v / pk - 1) * 100)
    by = {}
    for x in tr:
        k = "Jev satışı" if x["kind"] == "danisman" else x["reason"]
        by.setdefault(k, []).append(x["pct"])
    return {"islem": len(tr), "kazanan": sum(1 for x in tr if x["pnl"] > 0),
            "net_pnl": round(sum(x["pnl"] for x in tr), 2),
            "ort_%": round(float(np.mean([x["pct"] for x in tr])), 3) if tr else None,
            "medyan_%": round(float(np.median([x["pct"] for x in tr])), 3) if tr else None,
            "bas": cv[0] if cv else None, "son": cv[-1] if cv else None,
            "getiri_%": round((cv[-1] / cv[0] - 1) * 100, 2) if cv else None, "max_dusus_%": round(dd, 2),
            "cikis": {k: {"n": len(v), "ort_%": round(float(np.mean(v)), 2)} for k, v in by.items()}}


def fmt(v, suf="", nd=2):
    return "—" if v is None else f"{v:,.{nd}f}{suf}"


def html_rapor(R, fn):
    curve = R["curve"]
    T0, T1 = curve[0]["T"], curve[-1]["T"] + M15
    mid = T0 + (T1 - T0) // 2
    dil = [("60 gün", T0, T1), ("ilk 30 gün", T0, mid), ("son 30 gün", mid, T1)]
    S = {b: [stats(R[b[0] + "b"], curve, b, a, z) for _, a, z in dil] for b in ("jev", "kural")}
    R["ozet"] = {b: {d[0]: s for d, s in zip(dil, S[b])} for b in S}

    W, H = 1000, 260
    vals = [c["jev"] for c in curve] + [c["kural"] for c in curve] + [J.START_USD]
    lo, hi = min(vals), max(vals)
    X = lambda i: 10 + i * (W - 20) / max(1, len(curve) - 1)
    Y = lambda v: 10 + (hi - v) / (hi - lo or 1) * (H - 30)
    pl = lambda k: " ".join(f"{X(i):.1f},{Y(c[k]):.1f}" for i, c in enumerate(curve))
    svg = (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:280px" preserveAspectRatio="none">'
           f'<line x1="0" x2="{W}" y1="{Y(J.START_USD):.1f}" y2="{Y(J.START_USD):.1f}" stroke="#2a3444" stroke-dasharray="4 4"/>'
           f'<line x1="{X(len(curve) // 2):.1f}" x2="{X(len(curve) // 2):.1f}" y1="0" y2="{H}" stroke="#2a3444"/>'
           f'<polyline fill="none" stroke="#8a96a3" stroke-width="1.5" points="{pl("kural")}"/>'
           f'<polyline fill="none" stroke="#00b4d8" stroke-width="2" points="{pl("jev")}"/>'
           f'<text x="12" y="{H - 4}" fill="#5a6a7a" font-size="11">{datetime.fromtimestamp(T0 / 1000, timezone.utc):%d.%m}</text>'
           f'<text x="{W - 12}" y="{H - 4}" fill="#5a6a7a" font-size="11" text-anchor="end">{datetime.fromtimestamp(T1 / 1000, timezone.utc):%d.%m}</text>'
           f'<text x="{W - 12}" y="16" fill="#5a6a7a" font-size="11" text-anchor="end">{hi:,.0f}$</text>'
           f'<text x="{W - 12}" y="{H - 18}" fill="#5a6a7a" font-size="11" text-anchor="end">{lo:,.0f}$</text></svg>')

    def kart(b, ad, renk):
        s = S[b][0]
        son = equity(R[b[0] + "b"], R["last"])
        g = (son / J.START_USD - 1) * 100
        return (f'<div class="card" style="border-top:3px solid {renk}"><div class="dim">{ad}</div>'
                f'<div class="big">{son:,.2f}$ <span class="{"g" if g >= 0 else "r"}">{g:+.2f}%</span></div>'
                f'<div class="grid4">'
                f'<div><span>işlem</span><b>{s["islem"]}</b></div><div><span>kazanan</span><b>{s["kazanan"]}/{s["islem"]} '
                f'(%{(s["kazanan"] / s["islem"] * 100 if s["islem"] else 0):.0f})</b></div>'
                f'<div><span>işlem başı ort.</span><b>{fmt(s["ort_%"], "%", 3)}</b></div>'
                f'<div><span>en büyük düşüş</span><b class="r">{fmt(s["max_dusus_%"], "%")}</b></div>'
                f'<div><span>komisyon</span><b>{R[b[0] + "b"]["fees"]:,.2f}$</b></div>'
                f'<div><span>medyan işlem</span><b>{fmt(s["medyan_%"], "%", 3)}</b></div>'
                f'<div><span>açık pozisyon</span><b>{len(R[b[0] + "b"]["pos"])}</b></div>'
                f'<div><span>net kapanan K/Z</span><b>{s["net_pnl"]:+,.2f}$</b></div></div></div>')

    def dilim_tablo():
        rows = ""
        for k, (ad, _, _) in enumerate(dil):
            j, q = S["jev"][k], S["kural"][k]
            rows += (f"<tr><td>{ad}</td><td class='{'g' if (j['getiri_%'] or 0) >= 0 else 'r'}'>{fmt(j['getiri_%'], '%')}</td>"
                     f"<td>{j['islem']}</td><td>{fmt(j['ort_%'], '%', 3)}</td><td>{fmt(j['max_dusus_%'], '%')}</td>"
                     f"<td class='{'g' if (q['getiri_%'] or 0) >= 0 else 'r'}'>{fmt(q['getiri_%'], '%')}</td>"
                     f"<td>{q['islem']}</td><td>{fmt(q['ort_%'], '%', 3)}</td><td>{fmt(q['max_dusus_%'], '%')}</td></tr>")
        return rows

    def cikis_tablo(b):
        return "".join(f"<tr><td>{html.escape(k)}</td><td>{v['n']}</td><td class='{'g' if v['ort_%'] >= 0 else 'r'}'>{v['ort_%']:+.2f}%</td></tr>"
                       for k, v in sorted(S[b][0]["cikis"].items(), key=lambda z: -z[1]["n"]))

    def coin_tablo():
        rows = ""
        for s in COINS:
            n = s[:-4]
            jt = [x for x in R["jb"]["trades"] if x["sym"] == n]
            kt = [x for x in R["kb"]["trades"] if x["sym"] == n]
            rows += (f"<tr><td><b>{n}</b></td><td class='{'g' if R['bench'][s] >= 0 else 'r'}'>{R['bench'][s]:+.2f}%</td>"
                     f"<td>{len(jt)}</td><td>{sum(x['pnl'] for x in jt):+,.2f}$</td>"
                     f"<td>{len(kt)}</td><td>{sum(x['pnl'] for x in kt):+,.2f}$</td></tr>")
        return rows

    def islem_listesi(b):
        return "".join(
            f"<tr><td>{datetime.fromtimestamp(x['opened'] / 1000, timezone.utc):%d.%m %H:%M}</td><td><b>{x['sym']}</b></td>"
            f"<td>{x['usd']:,.0f}$</td><td>{x['entry']:.6g}</td><td>{x['exit']:.6g}</td>"
            f"<td>{(x['closed'] - x['opened']) / 3_600_000:.1f} s</td>"
            f"<td class='{'g' if x['pnl'] >= 0 else 'r'}'>{x['pct']:+.2f}%</td><td class='{'g' if x['pnl'] >= 0 else 'r'}'>{x['pnl']:+.2f}$</td>"
            f"<td class='dim'>{html.escape(x['reason'])}</td></tr>" for x in reversed(R[b[0] + "b"]["trades"]))

    c = R["cnt"]
    ort_bench = float(np.mean(list(R["bench"].values())))
    durum = ("tamamlandı" if R["tamam"] else f"YARIDA KALDI: {html.escape(str(R['hata']))}")
    page = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Jev 60 Gün Testi</title>
<style>
:root{{--bg:#0a0e14;--card:#0f1319;--border:#1a2030;--text:#c0cdd8;--dim:#5a6a7a;--accent:#00b4d8}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;max-width:1200px;margin:0 auto;padding:20px 16px;font-size:.88rem}}
h1{{color:var(--accent);font-size:1.3rem;margin:0 0 4px}} h2{{font-size:1rem;margin:0 0 10px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:14px;overflow-x:auto}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} @media(max-width:800px){{.two{{grid-template-columns:1fr}}}}
.big{{font-size:1.8rem;font-weight:700;font-family:ui-monospace,monospace;margin:4px 0 10px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}} .grid4 div{{border:1px solid var(--border);border-radius:5px;padding:6px;text-align:center}}
@media(max-width:600px){{.grid4{{grid-template-columns:repeat(2,1fr)}}}}
.grid4 span{{display:block;color:var(--dim);font-size:.66rem;text-transform:uppercase}} .grid4 b{{font-family:ui-monospace,monospace}}
.dim{{color:var(--dim)}} .g{{color:#2ecc71}} .r{{color:#e74c3c}} .note{{color:var(--dim);font-size:.8rem;line-height:1.6}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid var(--border);padding:6px;text-align:left;white-space:nowrap}}
th{{color:var(--dim);font-weight:normal;font-size:.72rem}} summary{{cursor:pointer}}
.warn{{border-left:3px solid #e67e22;padding:8px 12px;background:#1a150c;border-radius:4px;margin-bottom:14px;line-height:1.6}}
</style></head><body>
<h1>Jev — 60 günlük geçmiş testi</h1>
<div class="dim">{datetime.fromtimestamp(T0 / 1000, timezone.utc):%d.%m.%Y %H:%M} → {datetime.fromtimestamp(T1 / 1000, timezone.utc):%d.%m.%Y %H:%M} UTC ·
{c['turlar']} tur · Jev çağrısı {R['cagri']} (bu koşu) · harcama {R['harcanan']:.4f}$ · {durum}</div>
<p></p>
<div class="warn"><b>Nasıl okunmalı:</b> tek dönem, tek koşu. Aynı yöntem farklı dönemlerde çok farklı sonuç verebilir
(CLAUDE.md kural 6). Coin adları gizli ve haber yok — canlı sistemden farkı bu. Alışlar sonraki 1 dk açılışından; alış-satış
farkı (spread) modellenmedi, sert düşüşte stop dolumu gerçekte daha kötü olabilir. Bu bir <b>aday</b> sonuçtur, kanıt değil.</div>
<div class="two">{kart("jev", "JEV KASASI — alış ve satışı Jev verir", "#00b4d8")}{kart("kural", "KURAL KASASI — bedava kod kuralı (karşılaştırma)", "#8a96a3")}</div>
<div class="card"><h2>Özsermaye <span class="dim" style="font-weight:normal">— <span style="color:#00b4d8">■ Jev</span> · <span style="color:#8a96a3">■ Kural</span> · kesikli: 6.000$ · dikey çizgi: 30. gün</span></h2>{svg}</div>
<div class="card"><h2>Dönemlere göre</h2><table>
<tr><th></th><th colspan="4" style="color:#00b4d8">JEV</th><th colspan="4">KURAL</th></tr>
<tr><th>dilim</th><th>getiri</th><th>işlem</th><th>işlem başı</th><th>max düşüş</th><th>getiri</th><th>işlem</th><th>işlem başı</th><th>max düşüş</th></tr>
{dilim_tablo()}</table></div>
<div class="two">
<div class="card"><h2>Jev — çıkış nedenleri</h2><table><tr><th>neden</th><th>adet</th><th>ortalama</th></tr>{cikis_tablo("jev")}</table></div>
<div class="card"><h2>Kural — çıkış nedenleri</h2><table><tr><th>neden</th><th>adet</th><th>ortalama</th></tr>{cikis_tablo("kural")}</table></div>
</div>
<div class="two">
<div class="card"><h2>Coinler</h2><table><tr><th>coin</th><th>60 gün al-tut</th><th>Jev işlem</th><th>Jev K/Z</th><th>Kural işlem</th><th>Kural K/Z</th></tr>{coin_tablo()}</table>
<div class="note">6 coinin eşit ağırlıklı al-tut getirisi: <b class="{'g' if ort_bench >= 0 else 'r'}">{ort_bench:+.2f}%</b> (komisyonsuz).</div></div>
<div class="card"><h2>Jev ne yaptı</h2><table>
<tr><td>karar turu</td><td><b>{c['turlar']}</b></td></tr>
<tr><td>temkinli mod (hava güveni ≤ {J.CAUTIOUS_CONF})</td><td><b>{c['temkinli']}</b></td></tr>
<tr><td>"çok yükseldi" vetosu</td><td><b>{c['veto']}</b></td></tr>
<tr><td>Jev satışı</td><td><b>{c['danisman']}</b></td></tr>
<tr><td>cevapsız soru</td><td><b>{c['cevapsiz']}</b></td></tr></table></div>
</div>
<details class="card"><summary><b>Jev işlemleri ({len(R['jb']['trades'])})</b></summary><table>
<tr><th>alış (UTC)</th><th>coin</th><th>tutar</th><th>giriş</th><th>çıkış</th><th>süre</th><th>%</th><th>$</th><th>neden</th></tr>{islem_listesi("jev")}</table></details>
<details class="card"><summary><b>Kural işlemleri ({len(R['kb']['trades'])})</b></summary><table>
<tr><th>alış (UTC)</th><th>coin</th><th>tutar</th><th>giriş</th><th>çıkış</th><th>süre</th><th>%</th><th>$</th><th>neden</th></tr>{islem_listesi("kural")}</table></details>
<div class="card note"><b>Kurallar:</b> {html.escape(__doc__).replace(chr(10), "<br>")}</div>
</body></html>"""
    fn.write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canli", action="store_true")
    ap.add_argument("--rapor", help="mevcut JSON'dan yalniz HTML uret")
    a = ap.parse_args()
    t0 = datetime.now(timezone.utc)
    s0 = datetime.fromtimestamp(START / 1000, timezone.utc)
    e0 = datetime.fromtimestamp(END / 1000, timezone.utc)
    if a.rapor:
        R = json.loads(Path(a.rapor).read_text(encoding="utf-8"))
        html_rapor(R, Path(a.rapor).with_suffix(".html"))
        return 0
    R = run(a.canli)
    if R is None:
        return 0
    base = OUT / f"jev_geri_test_{s0:%Y%m%d}_{e0:%Y%m%d}_{t0:%Y%m%d_%H%M}"
    html_rapor(R, base.with_suffix(".html"))
    base.with_suffix(".json").write_text(json.dumps(R, ensure_ascii=False, default=float), encoding="utf-8")
    print(json.dumps(R["ozet"], ensure_ascii=False, indent=1))
    print(f"[KAYIT] {base.name}.json / .html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
