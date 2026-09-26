# -*- coding: utf-8 -*-
"""Frozen TSI+BB candidate layer for SPOT_SCANNER.

Research lineage:
  broad causal setup -> frozen lead/lag rule -> frozen BTC regime pair.
This module is intentionally isolated from the legacy v11 setup logic.

Frozen pair:
  BTC 1H TSI d1 <= -0.211069
  BTC 4H BB width >= 0.0942267

Base/lead-lag:
  BTC 4H motion permission
  coin 4H motion permission
  coin 15M >=4 positive motion families + turn/acceleration + structure
  StochRSI movement pattern in {-0++, -00+}
  bullish engulf + higher-low + higher-high
  15M motion_net - latest closed 1H motion_net >= 4

Causality:
  only closed candles are used; a qualified 15M decision is emitted one full
  15M bar later to match the conservative research fill convention.
"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

CANDIDATE_NAME = "TSI_BB_FROZEN_CANDIDATE"
CANDIDATE_VERSION = "2026-09-19-r1"
TSI_D1_MAX = -0.211069
BTC4_BB_WIDTH_MIN = 0.0942267
COOLDOWN_BARS = 16
MIN_LISTING_DAYS = 45

BASE_URLS = (
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
)
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Botum-TSI-BB-Frozen/1.0"})

STABLE_BASES = {
    "USDT","USDC","FDUSD","TUSD","USDP","DAI","BUSD","USDS","USDE","USD1",
    "USDJ","PYUSD","EURC","AEUR","EURI","RLUSD","XUSD","U","KGST","USTC",
    "BFUSD",
}
FIAT_BASES = {
    "USD","EUR","TRY","GBP","JPY","CHF","AUD","CAD","BRL","ARS","MXN","PLN",
    "RON","RUB","UAH","ZAR","NGN","IDR","BIDR","KGS",
}
LEVERAGED_SUFFIXES = ("UP","DOWN","BULL","BEAR","2L","2S","3L","3S","5L","5S","10L","10S")
LEVERAGED_NAME_EXCEPTIONS = {"JUP","SYRUP"}


def _get(path, params=None, attempts=4):
    last = None
    for n in range(attempts):
        for base in BASE_URLS:
            try:
                r = HTTP.get(base + path, params=params or {}, timeout=15)
                if r.status_code in (418, 429):
                    last = RuntimeError(f"rate-limit {r.status_code}")
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last = exc
        time.sleep(min(5.0, 0.4 * (2 ** n)))
    raise RuntimeError(f"Binance API failed {path}: {last}")


def _closed_ohlcv(symbol, interval, limit):
    rows = _get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"no candles {symbol} {interval}")
    cols = [
        "open_time","open","high","low","close","volume","close_time",
        "quote_volume","trades","taker_base","taker_quote","ignore",
    ]
    d = pd.DataFrame(rows, columns=cols)
    for c in ("open","high","low","close","volume","quote_volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["open_time"] = pd.to_datetime(d.open_time, unit="ms", utc=True)
    d["close_time"] = pd.to_datetime(d.close_time, unit="ms", utc=True)
    now = pd.Timestamp.now(tz="UTC")
    d = d[d.close_time < now]
    return d.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)


def _rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100/(1+rs)
    return out.where(~((au == 0) & (ad == 0)), 50.0)


def _indicators(df):
    x = df.copy()
    x["rsi"] = _rsi(x.close)
    e12 = x.close.ewm(span=12, adjust=False).mean()
    e26 = x.close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    x["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()

    ll9 = x.low.rolling(9).min()
    hh9 = x.high.rolling(9).max()
    rsv = 100 * (x.close - ll9) / (hh9 - ll9).replace(0, np.nan)
    x["kdj_k"] = rsv.ewm(alpha=1/3, adjust=False).mean()
    x["kdj_d"] = x.kdj_k.ewm(alpha=1/3, adjust=False).mean()
    x["kdj_j"] = 3*x.kdj_k - 2*x.kdj_d
    x["kdj_spread"] = x.kdj_k - x.kdj_d

    ll14 = x.low.rolling(14).min()
    hh14 = x.high.rolling(14).max()
    x["wpr"] = -100 * (hh14 - x.close) / (hh14 - ll14).replace(0, np.nan)
    x["obv"] = (np.sign(x.close.diff()).fillna(0) * x.volume).cumsum()

    rrmin = x.rsi.rolling(14).min()
    rrmax = x.rsi.rolling(14).max()
    x["stoch_raw"] = 100 * (x.rsi - rrmin) / (rrmax - rrmin).replace(0, np.nan)
    x["stoch_k"] = x.stoch_raw.rolling(3).mean()
    x["stoch_d"] = x.stoch_k.rolling(3).mean()
    x["stoch_spread"] = x.stoch_k - x.stoch_d

    for c in ("rsi","macd_hist","kdj_j","kdj_spread","wpr","obv","stoch_k","stoch_spread"):
        x[c + "_d1"] = x[c].diff()
        x[c + "_d3"] = x[c].diff(3)

    rng = (x.high - x.low).replace(0, np.nan)
    body = (x.close - x.open).abs()
    x["body_frac"] = body / rng
    x["close_loc"] = (x.close - x.low) / rng
    x["lower_wick"] = (np.minimum(x.open, x.close) - x.low) / rng
    x["hammer"] = (x.lower_wick >= 0.5) & (x.body_frac <= 0.4) & (x.close_loc >= 0.55)
    prev_bear = x.close.shift(1) < x.open.shift(1)
    x["bull_engulf"] = (
        (x.close > x.open) & prev_bear
        & (x.open <= x.close.shift(1))
        & (x.close >= x.open.shift(1))
    )
    x["higher_low"] = x.low > x.low.shift(1)
    x["higher_high"] = x.high > x.high.shift(1)
    prev8 = x.low.shift(1).rolling(8).min()
    x["sweep_reclaim"] = (x.low < prev8) & (x.close > prev8)
    x["reclaim_prev_high"] = x.close > x.high.shift(1)
    x["structure"] = (
        x.hammer | x.bull_engulf | x.sweep_reclaim | x.reclaim_prev_high
        | (x.higher_low & x.higher_high)
    )

    fam = pd.DataFrame(index=x.index)
    fam["RSI"] = np.sign(x.rsi_d1.fillna(0)) + np.sign(x.rsi_d3.fillna(0))
    fam["MACD"] = np.sign(x.macd_hist_d1.fillna(0)) + np.sign(x.macd_hist_d3.fillna(0))
    fam["KDJ"] = np.sign(x.kdj_j_d1.fillna(0)) + np.sign(x.kdj_spread_d1.fillna(0))
    fam["WPR"] = np.sign(x.wpr_d1.fillna(0)) + np.sign(x.wpr_d3.fillna(0))
    fam["OBV"] = np.sign(x.obv_d1.fillna(0)) + np.sign(x.obv_d3.fillna(0))
    fam["STOCH"] = np.sign(x.stoch_k_d1.fillna(0)) + np.sign(x.stoch_spread_d1.fillna(0))
    x["motion_pos"] = (fam > 0).sum(axis=1)
    x["motion_neg"] = (fam < 0).sum(axis=1)
    x["motion_net"] = x.motion_pos - x.motion_neg
    x["motion_rise"] = x.motion_pos.diff()
    x["turn4"] = (x.motion_pos >= 4) & ((x.motion_pos.shift(1) < 4) | (x.motion_rise >= 2))
    return x


def _tsi_and_bb(df):
    x = df.copy()
    mom = x.close.diff()
    a1 = mom.ewm(span=25, adjust=False).mean().ewm(span=13, adjust=False).mean()
    a2 = mom.abs().ewm(span=25, adjust=False).mean().ewm(span=13, adjust=False).mean()
    x["tsi"] = 100 * a1 / a2.replace(0, np.nan)
    x["tsi_d1"] = x.tsi.diff()
    mid = x.close.rolling(20).mean()
    sd = x.close.rolling(20).std(ddof=0)
    x["bb_width"] = ((mid + 2*sd) - (mid - 2*sd)) / mid.replace(0, np.nan)
    return x


def _stoch_pattern(x):
    score = np.sign(x.stoch_k_d1.fillna(0)) + np.sign(x.stoch_spread_d1.fillna(0))
    state = np.where(score > 0, "+", np.where(score < 0, "-", "0"))
    if len(state) < 4:
        return ""
    return "".join(state[-4:])


def _bar_seconds(interval):
    return {"15m": 900, "1h": 3600, "4h": 14400}[interval]


def _global_btc_context():
    b1 = _tsi_and_bb(_closed_ohlcv("BTCUSDT", "1h", 320))
    b4raw = _closed_ohlcv("BTCUSDT", "4h", 320)
    b4x = _indicators(b4raw)
    b4 = _tsi_and_bb(b4raw)
    if len(b1) < 40 or len(b4) < 40 or len(b4x) < 40:
        raise ValueError("BTC context too short")

    tsi_d1 = float(b1.tsi_d1.iloc[-1])
    bb4 = float(b4.bb_width.iloc[-1])
    h4 = b4x.iloc[-1]
    h4_prev16 = b4x.iloc[-17]
    btc_h4_ok = bool(
        h4.motion_pos >= 2
        and (h4.motion_rise >= 0 or h4.motion_net > h4_prev16.motion_net)
    )
    gate = bool(tsi_d1 <= TSI_D1_MAX and bb4 >= BTC4_BB_WIDTH_MIN and btc_h4_ok)
    return {
        "gate": gate,
        "btc1_tsi_d1": tsi_d1,
        "btc4_bb_width": bb4,
        "btc4_motion_pos": int(h4.motion_pos),
        "btc4_motion_net": int(h4.motion_net),
        "btc4_motion_rise": float(h4.motion_rise),
        "btc_h4_ok": btc_h4_ok,
    }


def _is_leveraged_name(base):
    if base in LEVERAGED_NAME_EXCEPTIONS:
        return False
    return any(base.endswith(sfx) for sfx in LEVERAGED_SUFFIXES)


def _universe(state):
    cache = state.setdefault("tsi_bb_universe_cache", {})
    now_s = time.time()
    if cache.get("symbols") and now_s - float(cache.get("checked_at", 0)) < 86400:
        return list(cache["symbols"]), dict(cache.get("audit", {}))

    ex = _get("/api/v3/exchangeInfo")
    candidates = []
    audit = {"active_usdt_spot": 0, "stable_fiat_removed": 0, "leveraged_removed": 0, "listing_warmup_removed": 0}
    for it in ex.get("symbols", []):
        sym = it.get("symbol", "")
        base = it.get("baseAsset", "")
        if it.get("quoteAsset") != "USDT" or it.get("status") != "TRADING" or it.get("isSpotTradingAllowed") is False:
            continue
        audit["active_usdt_spot"] += 1
        if base in STABLE_BASES or base in FIAT_BASES:
            audit["stable_fiat_removed"] += 1
            continue
        if _is_leveraged_name(base):
            audit["leveraged_removed"] += 1
            continue
        candidates.append(sym)

    cutoff_ms = int((pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=MIN_LISTING_DAYS)).timestamp() * 1000)
    eligible = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {
            pool.submit(_get, "/api/v3/klines", {"symbol": s, "interval": "1d", "endTime": cutoff_ms, "limit": 1}): s
            for s in candidates
        }
        for f in as_completed(futs):
            s = futs[f]
            try:
                rows = f.result()
                if isinstance(rows, list) and rows:
                    eligible.append(s)
                else:
                    audit["listing_warmup_removed"] += 1
            except Exception:
                audit["listing_warmup_removed"] += 1

    eligible.sort()
    cache.clear()
    cache.update({"checked_at": now_s, "symbols": eligible, "audit": audit})
    return eligible, audit


def _raw_setup(symbol):
    x15 = _indicators(_closed_ohlcv(symbol, "15m", 700))
    x1 = _indicators(_closed_ohlcv(symbol, "1h", 260))
    x4 = _indicators(_closed_ohlcv(symbol, "4h", 260))
    if min(len(x15), len(x1), len(x4)) < 80:
        return None

    a15 = x15.iloc[-1]
    a1 = x1.iloc[-1]
    a4 = x4.iloc[-1]
    a4_16 = x4.iloc[-17]

    coin_h4_ok = bool(
        a4.motion_pos >= 2
        and (a4.motion_rise >= 0 or a4.motion_net > a4_16.motion_net)
    )
    trigger = bool(
        a15.motion_pos >= 4
        and (bool(a15.turn4) or a15.motion_rise >= 1)
        and bool(a15.structure)
    )
    pattern = _stoch_pattern(x15)
    pat_ok = pattern in {"-0++", "-00+"}
    raw = bool(coin_h4_ok and trigger and pat_ok)

    lead_gap = float(a15.motion_net - a1.motion_net)
    leadlag = bool(
        bool(a15.bull_engulf)
        and bool(a15.higher_low)
        and bool(a15.higher_high)
        and lead_gap >= 4
    )
    decision_time = pd.Timestamp(x15.open_time.iloc[-1]) + pd.Timedelta(minutes=15)
    return {
        "symbol": symbol,
        "raw": raw,
        "leadlag": leadlag,
        "decision_time": decision_time.isoformat(),
        "decision_epoch": int(decision_time.timestamp()),
        "stoch_pattern": pattern,
        "m15_motion_pos": int(a15.motion_pos),
        "m15_motion_net": int(a15.motion_net),
        "h1_motion_net": int(a1.motion_net),
        "h4_motion_pos": int(a4.motion_pos),
        "lead_gap": lead_gap,
        "bull_engulf": bool(a15.bull_engulf),
        "higher_low": bool(a15.higher_low),
        "higher_high": bool(a15.higher_high),
        "decision_close": float(a15.close),
    }


def _cooldown_allows(state, rec):
    last_map = state.setdefault("tsi_bb_raw_last_bar", {})
    sym = rec["symbol"]
    cur = int(rec["decision_epoch"])
    last = int(last_map.get(sym, 0) or 0)
    if last and cur - last <= COOLDOWN_BARS * 15 * 60:
        return False
    last_map[sym] = cur
    return True


def _collect_ready_pending(state):
    now_s = time.time()
    pending = state.setdefault("tsi_bb_pending", {})
    ready = []
    stale = []
    for sym, rec in list(pending.items()):
        eligible = float(rec.get("eligible_after_epoch", 0) or 0)
        if eligible and now_s > eligible + 2 * 3600:
            stale.append(sym)
            continue
        if now_s >= eligible:
            ready.append(dict(rec))
    for sym in stale:
        pending.pop(sym, None)
    return ready


def scan(state, max_workers=8):
    """Return (ready_candidates, stats). Mutates scanner state for cooldown/pending."""
    ready = _collect_ready_pending(state)
    stats = {
        "name": CANDIDATE_NAME,
        "version": CANDIDATE_VERSION,
        "ready_from_pending": len(ready),
        "new_pending": 0,
        "errors": 0,
        "universe": 0,
        "global_gate": False,
        "btc": {},
    }

    try:
        btc = _global_btc_context()
        stats["btc"] = btc
        stats["global_gate"] = bool(btc["gate"])
    except Exception as exc:
        stats["errors"] += 1
        stats["btc_error"] = repr(exc)
        return ready, stats

    # Existing pending decisions remain valid even if the BTC gate has changed
    # by their delayed fill time. New decisions are only searched while gate is open.
    if not btc["gate"]:
        return ready, stats

    symbols, audit = _universe(state)
    stats["universe"] = len(symbols)
    stats["universe_audit"] = audit

    pending = state.setdefault("tsi_bb_pending", {})
    found = []
    with ThreadPoolExecutor(max_workers=max(2, min(12, int(max_workers)))) as pool:
        futs = {pool.submit(_raw_setup, s): s for s in symbols}
        for f in as_completed(futs):
            s = futs[f]
            try:
                rec = f.result()
                if not rec or not rec["raw"]:
                    continue
                if not _cooldown_allows(state, rec):
                    continue
                # Research compression happens BEFORE lead/lag. Therefore a raw
                # setup that fails lead/lag still consumes the 16-bar cooldown.
                if not rec["leadlag"]:
                    continue
                rec.update({
                    "candidate_name": CANDIDATE_NAME,
                    "candidate_version": CANDIDATE_VERSION,
                    "btc1_tsi_d1": float(btc["btc1_tsi_d1"]),
                    "btc4_bb_width": float(btc["btc4_bb_width"]),
                    "btc4_motion_pos": int(btc["btc4_motion_pos"]),
                    "eligible_after_epoch": int(rec["decision_epoch"]) + 15 * 60,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
                pending[s] = rec
                found.append(rec)
            except Exception:
                stats["errors"] += 1

    stats["new_pending"] = len(found)
    return ready, stats
