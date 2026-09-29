#!/usr/bin/env python3
"""Jev golge modu — 6 coin, 15 dakikalik mum kapanisinda 1 tur (+ olay tetikleyici).

VARSAYILAN: KURU KOSU. Jev'e istek HAZIRLANIR, sayilir, maliyeti hesaplanir,
kaydedilir — ama GONDERILMEZ. Gercek cagri icin `--canli` gerekir ve butce
kontrolunu gecmek zorundadir.

Neden bu kadar koruma: 2026-09-29'da bir terminal oturumu Jev'e 109.690 cagri
gonderdi, 5$ kredi tek seferde bitti. Bkz. Botum CLAUDE.md kural 8.

Tasarim ilkeleri (TypeSafe'in kendi jev-1.13 zayiflik dokumanindan):
  - Sayi/aritmetik KODDA. Jev'e sadece kova ve cumle gider (RSI=48.57 DEGIL).
  - State ve sorular INGILIZCE (Jev'in birincil dili).
  - Surum SABIT: jev-1.13.0 (alias kayabilir, olcum bozulur).
  - Sadece KAPANMIS mumlar kullanilir; Jev olusmakta olan mumu gormez.
  - Jev ile GECMIS VERI BACKTEST'I YOK (egitim verisinden sizinti riski).

Bu dosya Lab'dadir (public). API anahtari burada YOK ve olmayacak — anahtar
Claude cloud ortaminin "API credentials" bolumunden istege otomatik eklenir.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

# ---------------------------------------------------------------- sabitler
MODEL = "jev-1.13.0"
API = "https://api.typesafe.ai/v1/systemone"
BINANCE = "https://data-api.binance.vision/api/v3/klines"

# Evren kurali (ON_KAYIT.md): sektorunde piyasa degerine gore ilk, Binance 24s
# hacmi >= 40M$, bir coin tek sektorde. Secim 2026-09-29, Binance etiketleri.
COINS = {
    "ETHUSDT": "layer 1",
    "ZECUSDT": "privacy",
    "TAOUSDT": "AI",
    "DOGEUSDT": "meme",
    "LINKUSDT": "DeFi / oracle",
    "AVAXUSDT": "real world assets",
}
REF = "BTCUSDT"

# Maliyet ve butce. Fiyat: 0.042$ / 1M GIRDI tokeni, cikti ucretsiz.
USD_PER_TOKEN = 0.042 / 1_000_000
CHARS_PER_TOKEN = 3.0          # muhafazakar (fazla tahmin eder); ilk canli cagrida kalibre edilir
MAX_USD_PER_RUN = 0.01         # tek tur tavani
MAX_CALLS_PER_RUN = 2          # tek tur: 1 ana istek (+1 olay istegi)
APPROVAL_USD = 0.10            # bunun ustunde tahmin -> dur, onay iste (kural 8)

# Olay tetikleyici: bir coin son 5 dakikada bu kadar oynadiysa ara tur.
EVENT_MOVE_PCT = 2.0

OUT = Path(__file__).resolve().parent   # CLAUDE.md: cikti script klasorune, alt klasor YOK
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Botum-Lab-JevGolge/1.0"})


# ---------------------------------------------------------------- veri
def klines(symbol: str, interval: str, limit: int) -> np.ndarray:
    """Sadece KAPANMIS mumlar. Donus: [open_time, o, h, l, c, v, close_time]."""
    r = HTTP.get(BINANCE, params={"symbol": symbol, "interval": interval,
                                  "limit": limit + 1}, timeout=20)
    r.raise_for_status()
    rows = r.json()
    now_ms = time.time() * 1000
    rows = [x for x in rows if x[6] < now_ms]          # olusmakta olan mumu at
    a = np.array([[float(x[0]), float(x[1]), float(x[2]), float(x[3]),
                   float(x[4]), float(x[5]), float(x[6])] for x in rows])
    return a[-limit:]


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.empty_like(x)
    k = 2 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder RSI (CLAUDE.md dogrulanmis formul)."""
    d = np.diff(c)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = np.empty(len(d)), np.empty(len(d))
    au[:n] = np.nan
    ad[:n] = np.nan
    au[n - 1] = up[:n].mean()
    ad[n - 1] = dn[:n].mean()
    for i in range(n, len(d)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    rs = au / np.where(ad == 0, np.nan, ad)
    r = 100 - 100 / (1 + rs)
    r = np.where(ad == 0, 100.0, r)
    return np.concatenate([[np.nan], r])


def stoch_rsi(c: np.ndarray) -> float:
    """StochRSI %K (14/14/3/3) son deger."""
    r = rsi(c)
    s = np.full(len(r), np.nan)
    for i in range(27, len(r)):
        w = r[i - 13:i + 1]
        lo, hi = np.nanmin(w), np.nanmax(w)
        s[i] = 50.0 if hi == lo else (r[i] - lo) / (hi - lo) * 100
    k = np.convolve(np.nan_to_num(s), np.ones(3) / 3, mode="valid")
    return float(k[-1])


def atr(a: np.ndarray, n: int = 14) -> float:
    h, l, c = a[:, 2], a[:, 3], a[:, 4]
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    v = tr[:n].mean()
    for x in tr[n:]:
        v = (v * (n - 1) + x) / n
    return float(v)


# ---------------------------------------------------------------- gozlemci (kova + cumle)
def _trend_kod(c: np.ndarray) -> str:
    """'up' / 'down' / 'flat' — _trend() ile AYNI esikler (cumle ile kural ayni seyi gorur)."""
    e20, e50 = ema(c, 20), ema(c, 50)
    above20, above50 = c[-1] > e20[-1], c[-1] > e50[-1]
    slope = (e20[-1] / e20[-6] - 1) * 100
    if above20 and above50 and slope > 0.3:
        return "up"
    if not above20 and not above50 and slope < -0.3:
        return "down"
    return "flat"


def _trend(c: np.ndarray) -> str:
    e20, e50 = ema(c, 20), ema(c, 50)
    above20, above50 = c[-1] > e20[-1], c[-1] > e50[-1]
    slope = (e20[-1] / e20[-6] - 1) * 100
    if above20 and above50 and slope > 0.3:
        return "rising, price above its 20 and 50 bar averages"
    if not above20 and not above50 and slope < -0.3:
        return "falling, price below its 20 and 50 bar averages"
    return "flat or mixed, price near its averages"


def _rsi_word(v: float) -> str:
    if v >= 70:
        return "high (overheated)"
    if v >= 55:
        return "moderately high"
    if v > 45:
        return "neutral"
    if v > 30:
        return "moderately low"
    return "low (oversold)"


def _stoch_word(v: float) -> str:
    if v >= 80:
        return "near the top of its recent range"
    if v <= 20:
        return "near the bottom of its recent range"
    return "in the middle of its recent range"


def _move_word(pct: float) -> str:
    a = abs(pct)
    size = ("flat" if a < 1 else "small" if a < 3 else "moderate" if a < 7
            else "strong" if a < 15 else "very strong")
    if size == "flat":
        return "flat"
    return f"{size} {'rise' if pct > 0 else 'drop'}"


def _stretch_word(k: float) -> str:
    """Fiyatin 4h EMA20'den ATR cinsinden uzakligi."""
    if k > 3:
        return "far above its 4h 20-bar average (stretched)"
    if k > 1.5:
        return "clearly above its 4h 20-bar average"
    if k > -1.5:
        return "close to its 4h 20-bar average"
    if k > -3:
        return "clearly below its 4h 20-bar average"
    return "far below its 4h 20-bar average (washed out)"


def _range_word(pos: float) -> str:
    if pos >= 0.85:
        return "at the top of its last 60 hourly bars"
    if pos >= 0.6:
        return "in the upper part of its last 60 hourly bars"
    if pos > 0.4:
        return "in the middle of its last 60 hourly bars"
    if pos > 0.15:
        return "in the lower part of its last 60 hourly bars"
    return "at the bottom of its last 60 hourly bars"


def _vol_word(ratio: float) -> str:
    if ratio >= 2.5:
        return "far above normal"
    if ratio >= 1.4:
        return "above normal"
    if ratio > 0.7:
        return "normal"
    return "below normal"


def _atr_word(atr_pct: float, med_pct: float) -> str:
    r = atr_pct / med_pct if med_pct else 1
    if r >= 1.5:
        return "much more volatile than usual"
    if r >= 1.15:
        return "more volatile than usual"
    if r > 0.85:
        return "normally volatile"
    return "calmer than usual"


def describe(symbol: str, sector: str) -> tuple[str, dict]:
    """Bir coin icin Ingilizce cumleler + kayit icin ham olculer (Jev'e GITMEZ)."""
    m15, h1, h4, d1 = (klines(symbol, "15m", 200), klines(symbol, "1h", 200),
                       klines(symbol, "4h", 200), klines(symbol, "1d", 100))
    c15, c1, c4, cd = m15[:, 4], h1[:, 4], h4[:, 4], d1[:, 4]
    p = c15[-1]

    ret24 = (p / c1[-25] - 1) * 100
    ret3 = (p / c1[-4] - 1) * 100
    atr4 = atr(h4)
    stretch = (p - ema(c4, 20)[-1]) / atr4 if atr4 else 0
    hi60, lo60 = h1[-60:, 2].max(), h1[-60:, 3].min()
    pos60 = (p - lo60) / (hi60 - lo60) if hi60 > lo60 else 0.5
    from_hi = (p / h1[-24:, 2].max() - 1) * 100
    v1 = h1[:, 5]
    vol_ratio = v1[-6:].mean() / v1[-126:-6].mean() if v1[-126:-6].mean() else 1
    atr_pct = atr(h1) / p * 100
    atr_hist = [atr(h1[i - 60:i]) / h1[i - 1, 4] * 100 for i in range(80, len(h1), 10)]
    rsi1 = float(rsi(c1)[-1])
    rsi1_prev = float(rsi(c1[:-3])[-1])
    sto4 = stoch_rsi(c4)
    green = int((h1[-6:, 4] > h1[-6:, 1]).sum())
    # en yakin destek: son 48 saatin en dusugu (kodda hesaplanir, kova olarak gider)
    sup = h1[-48:, 3].min()
    sup_dist = (p / sup - 1) * 100

    rsi_dir = "rising" if rsi1 > rsi1_prev + 2 else "falling" if rsi1 < rsi1_prev - 2 else "flat"
    pull = ("no pullback, still at the recent high" if from_hi > -1
            else "a small pullback from the recent high" if from_hi > -4
            else "a deep pullback from the recent high")
    sup_word = ("very close below (under 2%)" if sup_dist < 2 else
                "close below (2-5%)" if sup_dist < 5 else "far below (more than 5%)")

    text = (
        f"{symbol[:-4]} ({sector}). "
        f"Daily trend: {_trend(cd)}. 4h trend: {_trend(c4)}. 1h trend: {_trend(c1)}. "
        f"Last 24 hours: {_move_word(ret24)}. Last 3 hours: {_move_word(ret3)}. "
        f"Price is {_stretch_word(stretch)}. 4h StochRSI is {_stoch_word(sto4)}. "
        f"Price is {_range_word(pos60)}, with {pull}. "
        f"1h RSI is {_rsi_word(rsi1)} and {rsi_dir}. "
        f"{green} of the last 6 hourly candles are green. "
        f"Volume in the last 6 hours is {_vol_word(vol_ratio)}. "
        f"The coin is {_atr_word(atr_pct, float(np.median(atr_hist)))}. "
        f"The nearest support is {sup_word}."
    )
    raw = {"price": p, "ret24": ret24, "ret3": ret3, "stretch_atr": stretch,
           "stoch4": sto4, "pos60": pos60, "from_hi24": from_hi, "rsi1": rsi1,
           "vol_ratio": vol_ratio, "atr1_pct": atr_pct, "support_dist": sup_dist,
           "green6": green, "bar15_close_ms": m15[-1, 6],
           "rsi1_prev3": rsi1_prev, "trend_d": _trend_kod(cd), "trend_4h": _trend_kod(c4)}
    return text, raw


def describe_market() -> tuple[str, dict]:
    h4, h1 = klines(REF, "4h", 200), klines(REF, "1h", 60)
    p = h1[-1, 4]
    r24 = (p / h1[-25, 4] - 1) * 100
    text = (f"Bitcoin: 4h trend {_trend(h4[:, 4])}. Last 24 hours: {_move_word(r24)}. "
            f"Bitcoin is {_atr_word(atr(h1) / p * 100, float(np.median([atr(h1[i-20:i]) / h1[i-1,4] * 100 for i in range(25, 60, 5)])))}.")
    return text, {"btc_price": p, "btc_ret24": r24}


def event_moves() -> dict:
    """Son 5 kapanmis 1 dakikalik mumda %EVENT_MOVE_PCT'den buyuk hareket eden coinler."""
    out = {}
    for s in COINS:
        m = klines(s, "1m", 6)
        mv = (m[-1, 4] / m[0, 1] - 1) * 100
        if abs(mv) >= EVENT_MOVE_PCT:
            out[s] = round(mv, 2)
    return out


# ---------------------------------------------------------------- KONTROL KURALI (ON_KAYIT ile birebir, DONDURULDU)
def kontrol_skoru(r: dict) -> dict:
    """Jev'in karsilastirilacagi bedava kod kurali. Jev ile AYNI olculeri gorur.

    Veriye bakilarak AYARLANMADI. Bes bilesen, her biri 0 / 0.5 / 1, esit agirlik.
    Ilkeler Botum'un daha once olctuklerinden: gerilmis/asiri isinmis giris zararli
    (2026-09-11), yakin destek kaybi kucultur (dip_tarama), trend uyumu.
    """
    t = {"up": 1.0, "flat": 0.5, "down": 0.0}
    trend = (t[r["trend_d"]] + t[r["trend_4h"]]) / 2
    stretch = 1.0 if r["stretch_atr"] <= 1.5 else 0.5 if r["stretch_atr"] <= 3 else 0.0
    sicak = (r["rsi1"] >= 70) + (r["stoch4"] >= 80)
    overheat = 1.0 if sicak == 0 else 0.5 if sicak == 1 else 0.0
    support = 1.0 if r["support_dist"] < 2 else 0.5 if r["support_dist"] < 5 else 0.0
    d = r["rsi1"] - r["rsi1_prev3"]
    momentum = 1.0 if d > 2 else 0.0 if d < -2 else 0.5
    parca = {"trend": trend, "not_stretched": stretch, "not_overheated": overheat,
             "support_close": support, "momentum_turning": momentum}
    skor = sum(parca.values()) / len(parca)
    return {"score": round(skor, 3), "buy": skor >= 0.7, "parts": parca}


# ---------------------------------------------------------------- sorular (ON_KAYIT ile birebir)
def _n(instr: str, yes: str, no: str) -> dict:
    return {"type": "noul", "instructions": instr, "criteria": {"true": yes, "false": no}}


def coin_questions(name: str) -> dict:
    q = {
        # ANA SORULAR (hukum bunlarla verilir — degismez)
        "entry_quality": _n(
            f"Is this a good moment to open a long position in {name} for the next 24 hours?",
            "Trend up on higher timeframes, price not stretched, momentum turning up, support close below.",
            "Trend down or unclear, or the price is already stretched after a strong run, or support is far away."),
        "target_before_stop": _n(
            f"Is {name} more likely to rise about 3% before it falls about 2%?",
            "Conditions favor a move up first: trend aligned, room above, not overheated.",
            "Conditions favor a dip first: overheated, stretched, weak trend, or hostile market."),
        # KESIF SORULARI
        "chasing": _n(
            f"Has {name} already risen too far too fast, so buying now would be chasing the move?",
            "Strong recent rise, price stretched above its averages, overheated momentum, at the top of its range.",
            "Price is near its averages or pulling back; no strong run just happened."),
        "pullback_buy": _n(
            f"Would buying {name} now be buying a pullback within an uptrend, rather than buying into a spike?",
            "Uptrend on higher timeframes and the price has pulled back toward its averages.",
            "No uptrend, or the price is at a fresh high after a sharp rise."),
        "late_in_move": _n(
            f"Is the current move in {name} in a late stage rather than an early one?",
            "Long, strong run already happened; price stretched; momentum high or fading.",
            "Move is just starting or the price is still near its base."),
        "trend_aligned": _n(
            f"Do the daily and 4h trends of {name} both point up?",
            "Both daily and 4h trends are rising.",
            "At least one of them is flat or falling."),
        "momentum_fading": _n(
            f"Is upward momentum in {name} weakening?",
            "RSI falling from high levels, fewer green candles, rise slowing.",
            "Momentum steady or strengthening."),
        "volume_confirms": _n(
            f"Does recent trading volume support the price move in {name}?",
            "Volume above normal in the direction of the move.",
            "Volume normal or below normal, or against the move."),
        "support_close": _n(
            f"Is there a clear support level close below the current price of {name}?",
            "The nearest support is very close or close below.",
            "The nearest support is far below."),
        "reward_worth_risk": _n(
            f"Is the likely upside in {name} worth the risk down to the nearest support?",
            "Support close below and room to rise above.",
            "Support far below, or the price is already at the top of its range."),
        "volatility_hostile": _n(
            f"Is {name} volatile enough right now to hit a tight stop without a real reversal?",
            "Much more volatile than usual.",
            "Normal or calmer than usual volatility."),
        "btc_drag": _n(
            f"Is there a real risk that Bitcoin drags {name} down in the next 24 hours?",
            "Bitcoin trend falling or Bitcoin very volatile.",
            "Bitcoin trend rising or calm."),
        "opportunity": {
            "type": "score",
            "instructions": f"How strong is the long opportunity in {name} right now?",
            "criteria": ["No opportunity", "Weak opportunity", "Moderate opportunity", "Strong opportunity"]},
        "setup_type": {
            "type": "choice",
            "instructions": f"What kind of setup is {name} showing right now?",
            "criteria": {"pullback": "Pullback within an uptrend",
                         "breakout": "Breaking above a recent range or high",
                         "bottom_reversal": "Turning up after a decline",
                         "unclear": "No clear setup"}},
    }
    return {f"{name}__{k}": v for k, v in q.items()}


def market_questions(names: list[str]) -> dict:
    opts = {n: f"{n} has the best long setup right now" for n in names}
    opts["none"] = "None of them has a good long setup right now"
    return {
        "market__best_of_six": {"type": "choice",
                                "instructions": "Which of these six coins offers the best long setup right now?",
                                "criteria": opts},
        "market__weather": {"type": "choice",
                            "instructions": "How is the overall crypto market backdrop for opening new long positions?",
                            "criteria": {"sunny": "Favorable: Bitcoin rising or calm",
                                         "mixed": "Unclear or choppy",
                                         "stormy": "Hostile: Bitcoin falling or very volatile"}},
        "market__risk_off": _n("Is the overall crypto market in a risk-off phase?",
                               "Bitcoin falling or very volatile; most coins falling.",
                               "Bitcoin stable or rising; no broad selling."),
    }


# ---------------------------------------------------------------- butce ve gonderim
def estimate(body: dict) -> dict:
    chars = len(json.dumps(body, ensure_ascii=False))
    tok = math.ceil(chars / CHARS_PER_TOKEN)
    return {"chars": chars, "est_tokens": tok, "est_usd": tok * USD_PER_TOKEN,
            "questions": len(body["questions"])}


class ButceAsildi(RuntimeError):
    pass


def send(body: dict, calls_made: int, spent_usd: float) -> dict:
    """Tek gercek cagri. Kural 8: billing/auth hatasinda TEKRAR DENEME YOK."""
    est = estimate(body)
    if calls_made + 1 > MAX_CALLS_PER_RUN:
        raise ButceAsildi(f"cagri tavani ({MAX_CALLS_PER_RUN}) asilir")
    if spent_usd + est["est_usd"] > MAX_USD_PER_RUN:
        raise ButceAsildi(f"$ tavani asilir: {spent_usd + est['est_usd']:.5f} > {MAX_USD_PER_RUN}")
    for deneme in range(3):
        r = HTTP.post(API, json=body, timeout=30)
        if r.status_code == 200:
            return r.json()
        txt = r.text[:300]
        if r.status_code in (401, 402, 403) or "billing" in txt or "authentication" in txt:
            raise RuntimeError(f"DUR (tekrar deneme yok): HTTP {r.status_code} {txt}")
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (deneme + 1))
            continue
        raise RuntimeError(f"HTTP {r.status_code} {txt}")
    raise RuntimeError("3 denemede basarisiz (429/5xx)")


# ---------------------------------------------------------------- tur
def build_request() -> tuple[dict, dict]:
    parts, raws, names = [], {}, []
    mtext, mraw = describe_market()
    for sym, sector in COINS.items():
        t, r = describe(sym, sector)
        parts.append(t)
        raws[sym] = r
        names.append(sym[:-4])
    state = "Market: " + mtext + "\n\n" + "\n\n".join(parts)
    questions = {}
    for n in names:
        questions.update(coin_questions(n))
    questions.update(market_questions(names))
    body = {"model": MODEL, "state": state, "questions": questions}
    return body, {"market": mraw, "coins": raws}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--canli", action="store_true", help="GERCEK cagri gonder (varsayilan: kuru kosu)")
    ap.add_argument("--onay", action="store_true", help=f"tahmin {APPROVAL_USD}$ ustundeyse bile gonder")
    a = ap.parse_args()

    t0 = datetime.now(timezone.utc)
    body, raw = build_request()
    est = estimate(body)
    events = event_moves()
    print(f"[TAHMIN] soru={est['questions']} karakter={est['chars']} "
          f"token~{est['est_tokens']} maliyet~${est['est_usd']:.6f}")
    print(f"[TAHMIN] 15dk ritim: gunde 96 tur -> ~${est['est_usd']*96:.4f}/gun, ~${est['est_usd']*96*30:.2f}/ay")
    if events:
        print(f"[OLAY] son 5 dakikada >= %{EVENT_MOVE_PCT}: {events}")

    kontrol = {sym: kontrol_skoru(r) for sym, r in raw["coins"].items()}
    print("[KONTROL] " + "  ".join(f"{k[:-4]}={v['score']:.2f}{'*' if v['buy'] else ''}" for k, v in kontrol.items()))
    rec = {"ts_utc": t0.isoformat(), "kontrol": kontrol, "mode": "canli" if a.canli else "kuru",
           "model": MODEL, "estimate": est, "events": events, "raw": raw,
           "request": body, "response": None, "error": None}

    if a.canli:
        if est["est_usd"] > APPROVAL_USD and not a.onay:
            print(f"[DUR] tahmin ${est['est_usd']:.4f} > ${APPROVAL_USD}: kullanici onayi gerekli (--onay).")
            return 2
        try:
            rec["response"] = send(body, 0, 0.0)
            u = rec["response"].get("usage", {})
            print(f"[CANLI] gercek girdi tokeni={u.get('input_tokens')} "
                  f"(tahmin {est['est_tokens']}) maliyet=${(u.get('input_tokens') or 0)*USD_PER_TOKEN:.6f}")
        except Exception as e:
            rec["error"] = str(e)
            print(f"[HATA] {e}")
    else:
        print("[KURU] istek gonderilmedi.")

    fn = OUT / f"jev_golge_6coin_{t0:%Y%m%d}_{t0:%Y%m%d}_{t0:%Y%m%d_%H%M}.json"
    fn.write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"[KAYIT] {fn.name}")
    return 0 if rec["error"] is None else 1


if __name__ == "__main__":
    sys.exit(main())
