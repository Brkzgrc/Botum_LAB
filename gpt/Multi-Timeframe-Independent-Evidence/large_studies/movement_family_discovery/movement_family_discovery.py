from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
CAUSAL = PARENT / "coin_mtf_causal_validation"
sys.path.insert(0, str(CAUSAL))
import coin_mtf_causal_validation as core  # noqa: E402

# Broad, causal movement-start detection. This is NOT another r2 filter.
# Candidate selection uses Discovery + Calibration only.
FETCH_START = pd.Timestamp("2022-11-01", tz="UTC")
START = pd.Timestamp("2023-01-01", tz="UTC")
END = pd.Timestamp("2026-09-18", tz="UTC")
COST_PCT = 0.20
RULE_COOLDOWN_HOURS = 6
COMBINED_COOLDOWN_HOURS = 4

STABLE_BASE_ASSETS = {
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USDS", "USDE", "USD1",
    "USDJ", "PYUSD", "EURC", "AEUR", "EURI", "RLUSD", "XUSD", "U", "KGST", "USTC", "BFUSD",
}
FIAT_BASE_ASSETS = {
    "USD", "EUR", "TRY", "GBP", "JPY", "CHF", "AUD", "CAD", "BRL", "ARS", "MXN", "PLN",
    "RON", "RUB", "UAH", "ZAR", "NGN", "IDR", "BIDR", "KGS",
}
EXCLUDED_BASE_ASSETS = STABLE_BASE_ASSETS | FIAT_BASE_ASSETS

PLANS = {
    "TP3_SL2": (3.0, 2.0),
    "TP4_SL2P5": (4.0, 2.5),
    "TP5_SL3": (5.0, 3.0),
}


def hmod(s: str) -> int:
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8], 16) % 100


def load_symbols() -> list[str]:
    info, _ = core.get_json("/api/v3/exchangeInfo", {})
    syms = []
    for s in info.get("symbols", []):
        symbol = str(s.get("symbol", "")).upper()
        base = str(s.get("baseAsset", "")).upper()
        quote = str(s.get("quoteAsset", "")).upper()
        if s.get("status") != "TRADING":
            continue
        if quote != "USDT":
            continue
        if not bool(s.get("isSpotTradingAllowed", True)):
            continue
        if base in EXCLUDED_BASE_ASSETS:
            continue
        if symbol == "BTCUSDT":
            continue
        syms.append(symbol)
    return sorted(set(syms))


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(~((au == 0) & (ad == 0)), 50.0)


def adx_di(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df.high.diff()
    dn = -df.low.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    prev_close = df.close.shift(1)
    tr = pd.concat([
        df.high - df.low,
        (df.high - prev_close).abs(),
        (df.low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr.replace(0, np.nan)
    mdi = 100 * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr.replace(0, np.nan)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return adx, pdi, mdi


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ema20"] = x.close.ewm(span=20, adjust=False).mean()
    x["ema50"] = x.close.ewm(span=50, adjust=False).mean()
    x["ema20_d1"] = x.ema20.pct_change() * 100
    x["ema50_d1"] = x.ema50.pct_change() * 100

    pc = x.close.shift(1)
    tr = pd.concat([(x.high - x.low), (x.high - pc).abs(), (x.low - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    x["atr_pct"] = atr / x.close.replace(0, np.nan) * 100

    mid = x.close.rolling(20).mean()
    sd = x.close.rolling(20).std(ddof=0)
    x["bb_width"] = (4 * sd) / mid.replace(0, np.nan)
    x["bb_width_med48"] = x.bb_width.shift(1).rolling(48).median()
    x["bb_width_ratio"] = x.bb_width / x.bb_width_med48.replace(0, np.nan)
    x["bb_width_d1"] = x.bb_width.diff()

    x["rsi"] = rsi(x.close)
    e12 = x.close.ewm(span=12, adjust=False).mean()
    e26 = x.close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig = macd.ewm(span=9, adjust=False).mean()
    x["macd_hist"] = macd - sig

    rrmin = x.rsi.rolling(14).min()
    rrmax = x.rsi.rolling(14).max()
    raw = 100 * (x.rsi - rrmin) / (rrmax - rrmin).replace(0, np.nan)
    x["stoch_k"] = raw.rolling(3).mean()
    x["stoch_d"] = x.stoch_k.rolling(3).mean()
    x["stoch_spread"] = x.stoch_k - x.stoch_d

    sign = np.sign(x.close.diff()).fillna(0)
    x["obv"] = (sign * x.volume).cumsum()
    x["rvol20"] = x.volume / x.volume.shift(1).rolling(20).median().replace(0, np.nan)

    x["adx"], x["plus_di"], x["minus_di"] = adx_di(x)
    x["di_spread"] = x.plus_di - x.minus_di

    for c in ["rsi", "macd_hist", "stoch_spread", "obv", "adx", "di_spread", "rvol20"]:
        x[c + "_d1"] = x[c].diff()
        x[c + "_d3"] = x[c].diff(3)

    rng = (x.high - x.low).replace(0, np.nan)
    body = (x.close - x.open).abs()
    x["body_frac"] = body / rng
    x["close_loc"] = (x.close - x.low) / rng
    x["lower_wick_frac"] = (np.minimum(x.open, x.close) - x.low) / rng
    prev_bear = x.close.shift(1) < x.open.shift(1)
    x["bull_engulf"] = (x.close > x.open) & prev_bear & (x.open <= x.close.shift(1)) & (x.close >= x.open.shift(1))
    x["hammer"] = (x.lower_wick_frac >= 0.50) & (x.body_frac <= 0.40) & (x.close_loc >= 0.60)
    x["reclaim_prev_high"] = x.close > x.high.shift(1)

    for n in [8, 16, 32, 96]:
        x[f"prev_high_{n}"] = x.high.shift(1).rolling(n).max()
        x[f"prev_low_{n}"] = x.low.shift(1).rolling(n).min()

    x["ret_3p"] = x.close.pct_change(3) * 100
    x["ret_6p"] = x.close.pct_change(6) * 100
    # These names are intentionally used only on the native 15M frame.
    x["ret_2h"] = x.close.pct_change(8) * 100
    x["ret_6h"] = x.close.pct_change(24) * 100
    x["dd_12h"] = (x.close / x.high.shift(1).rolling(48).max() - 1) * 100
    x["ret_2h_prev"] = x.ret_2h.shift(1)
    x["dd_12h_prev"] = x.dd_12h.shift(1)

    x["hl_count4"] = (x.low.diff() > 0).astype(float).rolling(4).sum()
    x["hh_count4"] = (x.high.diff() > 0).astype(float).rolling(4).sum()
    x["mom_score"] = (
        (x.macd_hist_d1 > 0).astype(int)
        + (x.rsi_d1 > 0).astype(int)
        + (x.stoch_spread_d1 > 0).astype(int)
        + (x.obv_d1 > 0).astype(int)
        + (x.di_spread_d1 > 0).astype(int)
    )
    return x


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, origin="epoch", label="left", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), quote_volume=("quote_volume", "sum"),
    ).dropna()


def align_closed(tf: pd.DataFrame, delta: pd.Timedelta, decision_index: pd.DatetimeIndex, prefix: str) -> pd.DataFrame:
    z = tf.copy()
    z.index = z.index + delta
    z = z.add_prefix(prefix + "_")
    return z.reindex(decision_index, method="ffill")


def candidate_rules() -> list[dict]:
    rules = []
    rid = 0

    # A) Compression -> pressure -> breakout.
    for bb_max in [0.75, 1.00, 1.25]:
        for hl_min in [2, 3]:
            for mom_min in [2, 3]:
                rid += 1
                rules.append({
                    "id": f"CB_{rid:03d}", "family": "COMPRESSION_BREAKOUT",
                    "bb_ratio_max": bb_max, "hl_min": hl_min, "mom_min": mom_min,
                })

    # B) Established 4H uptrend -> 1H pullback -> 15M re-acceleration.
    for trend_min in [2, 3]:
        for ema_dist in [1.0, 2.0, 3.0]:
            for mom_min in [2, 3]:
                rid += 1
                rules.append({
                    "id": f"PB_{rid:03d}", "family": "PULLBACK_REACCEL",
                    "trend_min": trend_min, "ema_dist_max": ema_dist, "mom_min": mom_min,
                })

    # C) Liquidity sweep / bear trap -> reclaim.
    for window in [8, 16, 32]:
        for close_loc in [0.55, 0.70]:
            for mom_min in [2, 3]:
                rid += 1
                rules.append({
                    "id": f"RC_{rid:03d}", "family": "RECLAIM_BEAR_TRAP",
                    "window": window, "close_loc_min": close_loc, "mom_min": mom_min,
                })

    # D) Prior decline -> first micro-structure break with momentum acceleration.
    for ret2_max in [-1.0, -2.0, -3.0]:
        for dd12_max in [-2.0, -4.0]:
            for mom_min in [2, 3]:
                rid += 1
                rules.append({
                    "id": f"ER_{rid:03d}", "family": "EARLY_REVERSAL",
                    "ret2_max": ret2_max, "dd12_max": dd12_max, "mom_min": mom_min,
                })
    return rules


def rule_mask(z: pd.DataFrame, r: dict) -> pd.Series:
    fam = r["family"]
    if fam == "COMPRESSION_BREAKOUT":
        resistance = z.h1_prev_high_24
        return (
            (z.close > resistance)
            & (z.close.shift(1) <= resistance)
            & (z.h1_bb_width_ratio <= r["bb_ratio_max"])
            & (z.h1_hl_count4 >= r["hl_min"])
            & (z.mom_score >= r["mom_min"])
            & (z.rvol20 >= 0.8)
        ).fillna(False)

    if fam == "PULLBACK_REACCEL":
        trend_score = (
            (z.h4_close > z.h4_ema50).astype(int)
            + (z.h4_ema20 > z.h4_ema50).astype(int)
            + (z.h4_ema20_d1 > 0).astype(int)
        )
        d20 = (z.h1_close - z.h1_ema20).abs() / z.h1_close.replace(0, np.nan) * 100
        d50 = (z.h1_close - z.h1_ema50).abs() / z.h1_close.replace(0, np.nan) * 100
        near_ema = pd.concat([d20, d50], axis=1).min(axis=1) <= r["ema_dist_max"]
        trigger = z.bull_engulf | z.hammer | z.reclaim_prev_high
        return (
            (trend_score >= r["trend_min"])
            & near_ema
            & (z.h1_ret_3p < 0)
            & trigger
            & (z.mom_score >= r["mom_min"])
        ).fillna(False)

    if fam == "RECLAIM_BEAR_TRAP":
        w = int(r["window"])
        support = z[f"prev_low_{w}"]
        sweep = (z.low < support) & (z.close > support)
        return (
            sweep
            & (z.close_loc >= r["close_loc_min"])
            & (z.mom_score >= r["mom_min"])
            & (z.macd_hist_d1 > 0)
        ).fillna(False)

    if fam == "EARLY_REVERSAL":
        micro_break = z.close > z.prev_high_8
        return (
            (z.ret_2h_prev <= r["ret2_max"])
            & (z.dd_12h_prev <= r["dd12_max"])
            & micro_break
            & (z.mom_score >= r["mom_min"])
            & (z.macd_hist_d1 > 0)
        ).fillna(False)

    raise KeyError(fam)


def compress(mask: pd.Series, decision_index: pd.DatetimeIndex, hours: int) -> pd.Series:
    a = mask.fillna(False).to_numpy(bool)
    out = np.zeros(len(a), dtype=bool)
    last = None
    for i, v in enumerate(a):
        if not v:
            continue
        t = decision_index[i]
        if last is None or t - last >= pd.Timedelta(hours=hours):
            out[i] = True
            last = t
    return pd.Series(out, index=decision_index)


def first_touch_plan(sl: pd.DataFrame, entry: float, tp: float, stop: float) -> tuple[float, int, int]:
    hi = (sl.high.to_numpy(float) / entry - 1) * 100
    lo = (sl.low.to_numpy(float) / entry - 1) * 100
    u = np.flatnonzero(hi >= tp)
    d = np.flatnonzero(lo <= -stop)
    iu = int(u[0]) if len(u) else None
    idn = int(d[0]) if len(d) else None
    # Same-bar ambiguity is scored pessimistically as stop first.
    if idn is not None and (iu is None or idn <= iu):
        return -stop - COST_PCT, 0, 1
    if iu is not None:
        return tp - COST_PCT, 1, 0
    return np.nan, 0, 0


def outcome(base: pd.DataFrame, decision_time: pd.Timestamp) -> dict | None:
    entry_time = decision_time + pd.Timedelta(minutes=15)
    if entry_time not in base.index:
        return None
    i = base.index.get_loc(entry_time)
    if not isinstance(i, (int, np.integer)):
        return None
    j = i + 24 * 4
    if j >= len(base):
        return None
    entry = float(base.open.iloc[i])
    if not np.isfinite(entry) or entry <= 0:
        return None
    sl = base.iloc[i:j + 1]
    rec = {"entry_time": entry_time, "entry_open": entry}
    for h in [6, 12, 24]:
        q = i + h * 4
        px = float(base.open.iloc[q])
        rec[f"net{h}"] = (px / entry - 1) * 100 - COST_PCT
    hi = (sl.high.to_numpy(float) / entry - 1) * 100
    lo = (sl.low.to_numpy(float) / entry - 1) * 100
    rec["mfe24"] = float(np.nanmax(hi))
    rec["mae24"] = float(np.nanmin(lo))
    for name, (tp, stop) in PLANS.items():
        val, win, loss = first_touch_plan(sl, entry, tp, stop)
        if not np.isfinite(val):
            val = rec["net24"]
        rec[f"ret_{name}"] = float(val)
        rec[f"win_{name}"] = int(win)
        rec[f"loss_{name}"] = int(loss)
    return rec


def build_symbol_frame(base: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    t15 = enrich(base)
    d15 = t15.copy()
    d15.index = d15.index + pd.Timedelta(minutes=15)
    d15 = d15[~d15.index.duplicated(keep="last")]
    idx = d15.index

    h1 = enrich(resample(base, "1h"))
    h4 = enrich(resample(base, "4h"))
    a1 = align_closed(h1, pd.Timedelta(hours=1), idx, "h1")
    a4 = align_closed(h4, pd.Timedelta(hours=4), idx, "h4")
    z = d15.join(a1).join(a4)
    return z[(z.index >= start) & (z.index < end)].copy()


def process_symbol(symbol: str, fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, dict | None]:
    try:
        base = core.fetch_15m(symbol, start=fetch_start, end=end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"too_short:{len(base)}"}
        z = build_symbol_frame(base, study_start, end)
        if len(z) < 1000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"study_too_short:{len(z)}"}

        matches: dict[pd.Timestamp, list[str]] = defaultdict(list)
        for r in candidate_rules():
            m = compress(rule_mask(z, r), z.index, RULE_COOLDOWN_HOURS)
            for t in z.index[m.to_numpy(bool)]:
                matches[t].append(r["id"])

        rows = []
        for t in sorted(matches):
            oc = outcome(base, t)
            if oc is None:
                continue
            rows.append({
                "symbol": symbol,
                "hash_mod": hmod(symbol),
                "decision_time": t,
                "rules": ";".join(matches[t]),
                **oc,
            })
        return pd.DataFrame(rows), None
    except Exception as ex:
        return pd.DataFrame(), {"symbol": symbol, "error": f"{type(ex).__name__}:{ex}"}


def shard_main(shard: int, shards: int, outdir: Path, symbols_arg: str | None,
               fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    syms = load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        syms = [s for s in syms if s in wanted]
    mine = [s for i, s in enumerate(syms) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(process_symbol, s, fetch_start, study_start, end): s for s in mine}
        for k, f in enumerate(as_completed(futs), 1):
            x, e = f.result()
            if e:
                errors.append(e)
            if x is not None and len(x):
                frames.append(x)
            if k % 3 == 0 or k == len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} union_events={sum(len(q) for q in frames)} errors={len(errors)}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {
        "shard": shard, "shards": shards, "symbols": len(mine), "events": int(len(out)),
        "errors": len(errors), "study_start": str(study_start), "end": str(end),
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if symbols_arg and len(mine) and len(out) == 0:
        raise RuntimeError(f"smoke produced zero movement-family events for {mine}")
    print(json.dumps(meta), flush=True)


def split_masks(d: pd.DataFrame) -> dict[str, pd.Series]:
    t = d.decision_time
    return {
        "DISCOVERY": (d.hash_mod >= 30) & (t < pd.Timestamp("2025-01-01", tz="UTC")),
        "CALIBRATION": (d.hash_mod >= 30) & (t >= pd.Timestamp("2025-01-01", tz="UTC")) & (t < pd.Timestamp("2026-01-01", tz="UTC")),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod < 30) & (t < pd.Timestamp("2026-01-01", tz="UTC")),
        "FINAL_HOLDOUT_2026": (d.hash_mod < 30) & (t >= pd.Timestamp("2026-01-01", tz="UTC")),
        "ALL_2026": t >= pd.Timestamp("2026-01-01", tz="UTC"),
    }


def period_days(name: str) -> int:
    if name == "DISCOVERY":
        return 731
    if name == "CALIBRATION":
        return 365
    if name == "CROSS_HOLDOUT_PRE2026":
        return 1096
    if name in {"FINAL_HOLDOUT_2026", "ALL_2026"}:
        return int((END.normalize() - pd.Timestamp("2026-01-01", tz="UTC")).days)
    return 1


def metrics(x: pd.DataFrame) -> dict:
    if len(x) == 0:
        return {"n": 0, "symbols": 0}
    v = pd.to_numeric(x.net24, errors="coerce").dropna()
    z = x.loc[v.index]
    gp = float(v[v > 0].sum())
    gl = float(-v[v < 0].sum())
    out = {
        "n": int(len(v)), "symbols": int(z.symbol.nunique()),
        "mean24": float(v.mean()), "median24": float(v.median()),
        "win24": float((v > 0).mean() * 100), "pf24": gp / gl if gl > 0 else None,
        "mfe24": float(pd.to_numeric(z.mfe24, errors="coerce").mean()),
        "mae24": float(pd.to_numeric(z.mae24, errors="coerce").mean()),
    }
    for name in PLANS:
        q = pd.to_numeric(z[f"ret_{name}"], errors="coerce").dropna()
        g = float(q[q > 0].sum())
        l = float(-q[q < 0].sum())
        out[name] = {
            "mean": float(q.mean()), "median": float(q.median()),
            "win": float((q > 0).mean() * 100), "pf": g / l if l > 0 else None,
            "target_first": float(pd.to_numeric(z.loc[q.index, f"win_{name}"], errors="coerce").mean() * 100),
            "stop_first": float(pd.to_numeric(z.loc[q.index, f"loss_{name}"], errors="coerce").mean() * 100),
        }
    return out


def frequency(x: pd.DataFrame, days: int) -> dict:
    if len(x) == 0:
        return {"signals": 0, "signals_per_day": 0.0, "active_days": 0, "active_day_share_pct": 0.0}
    c = x.groupby(x.decision_time.dt.floor("D")).size()
    return {
        "signals": int(len(x)), "signals_per_day": float(len(x) / max(1, days)),
        "active_days": int(len(c)), "active_day_share_pct": float(len(c) / max(1, days) * 100),
        "median_on_active_day": float(c.median()), "p90_on_active_day": float(c.quantile(.90)),
        "max_in_day": int(c.max()),
    }


def dedupe_combined(x: pd.DataFrame, hours: int = COMBINED_COOLDOWN_HOURS) -> pd.DataFrame:
    if x.empty:
        return x.copy()
    x = x.sort_values(["symbol", "decision_time"]).reset_index(drop=True)
    keep = np.zeros(len(x), dtype=bool)
    for _, idxs in x.groupby("symbol", sort=False).groups.items():
        last = None
        for i in idxs:
            t = x.at[i, "decision_time"]
            if last is None or t - last >= pd.Timedelta(hours=hours):
                keep[i] = True
                last = t
    return x.iloc[np.flatnonzero(keep)].copy()


def aggregate_main(indir: Path, outdir: Path) -> None:
    metas = sorted(indir.rglob("meta.json"))
    if len(metas) != 64:
        raise RuntimeError(f"expected exactly 64 shard meta files, found {len(metas)}")
    meta_rows = [json.loads(p.read_text(encoding="utf-8")) for p in metas]
    if any(int(m.get("shards", 0)) != 64 for m in meta_rows):
        raise RuntimeError("shard cardinality mismatch")
    if sum(int(m.get("symbols", 0)) for m in meta_rows) < 400:
        raise RuntimeError("unexpectedly small universe")

    frames = []
    for f in sorted(indir.rglob("events.csv")):
        try:
            q = pd.read_csv(f, low_memory=False)
            if len(q):
                frames.append(q)
        except pd.errors.EmptyDataError:
            pass
    if not frames:
        raise RuntimeError("no movement-family events")
    d = pd.concat(frames, ignore_index=True)
    d["decision_time"] = pd.to_datetime(d.decision_time, utc=True)
    d["entry_time"] = pd.to_datetime(d.entry_time, utc=True)
    d = d.drop_duplicates(["symbol", "decision_time"]).sort_values(["decision_time", "symbol"]).reset_index(drop=True)
    if d.symbol.nunique() < 350 or len(d) < 10000:
        raise RuntimeError(f"unexpected aggregate coverage rows={len(d)} symbols={d.symbol.nunique()}")

    rule_defs = {r["id"]: r for r in candidate_rules()}
    long = d.assign(rule_id=d.rules.str.split(";")).explode("rule_id", ignore_index=True)
    long = long[long.rule_id.isin(rule_defs)].reset_index(drop=True)

    evals = []
    for rid, r in rule_defs.items():
        q = long[long.rule_id == rid].copy()
        qsm = split_masks(q)
        rec = {"rule": r, "splits": {}}
        for name, mask in qsm.items():
            z = q[mask]
            rec["splits"][name] = {"metrics": metrics(z), "frequency": frequency(z, period_days(name))}
        evals.append(rec)

    # One rule + one 3-5% target plan per family, selected on Discovery+Calibration only.
    champions = {}
    for fam in ["COMPRESSION_BREAKOUT", "PULLBACK_REACCEL", "RECLAIM_BEAR_TRAP", "EARLY_REVERSAL"]:
        cands = []
        for rec in evals:
            if rec["rule"]["family"] != fam:
                continue
            D = rec["splits"]["DISCOVERY"]
            C = rec["splits"]["CALIBRATION"]
            if min(D["metrics"].get("n", 0), C["metrics"].get("n", 0)) < 80:
                continue
            if min(D["frequency"].get("signals_per_day", 0), C["frequency"].get("signals_per_day", 0)) < 0.15:
                continue
            for plan in PLANS:
                dm = D["metrics"].get(plan, {})
                cm = C["metrics"].get(plan, {})
                if min(dm.get("mean", -999), cm.get("mean", -999)) <= 0:
                    continue
                if min(dm.get("win", 0), cm.get("win", 0)) < 35:
                    continue
                if min(dm.get("pf", 0) or 0, cm.get("pf", 0) or 0) <= 1.0:
                    continue
                min_exp = min(dm["mean"], cm["mean"])
                min_win = min(dm["win"], cm["win"])
                train_freq = min(D["frequency"]["signals_per_day"], C["frequency"]["signals_per_day"])
                score = min_exp + 0.01 * min_win + 0.25 * min(train_freq, 1.0)
                cands.append((score, rec, plan))
        if cands:
            cands.sort(key=lambda x: x[0], reverse=True)
            score, rec, plan = cands[0]
            champions[fam] = {"score": float(score), "plan": plan, **rec}

    champion_ids = {v["rule"]["id"] for v in champions.values()}
    selected = d[d.rules.apply(lambda s: any(r in champion_ids for r in str(s).split(";")))].copy()
    if len(selected):
        selected["selected_families"] = selected.rules.apply(
            lambda s: ";".join(sorted({rule_defs[r]["family"] for r in str(s).split(";") if r in champion_ids}))
        )
        selected = dedupe_combined(selected, COMBINED_COOLDOWN_HOURS)

    combined = {}
    if len(selected):
        csm = split_masks(selected)
        for name, mask in csm.items():
            z = selected[mask]
            combined[name] = {"metrics": metrics(z), "frequency": frequency(z, period_days(name))}

    holdout_family = {}
    for fam, champ in champions.items():
        rid = champ["rule"]["id"]
        q = long[long.rule_id == rid].copy()
        qsm = split_masks(q)
        holdout_family[fam] = {
            "rule": champ["rule"], "plan": champ["plan"], "score": champ["score"],
            "DISCOVERY": champ["splits"]["DISCOVERY"],
            "CALIBRATION": champ["splits"]["CALIBRATION"],
            "CROSS_HOLDOUT_PRE2026": {"metrics": metrics(q[qsm["CROSS_HOLDOUT_PRE2026"]]), "frequency": frequency(q[qsm["CROSS_HOLDOUT_PRE2026"]], period_days("CROSS_HOLDOUT_PRE2026"))},
            "FINAL_HOLDOUT_2026": {"metrics": metrics(q[qsm["FINAL_HOLDOUT_2026"]]), "frequency": frequency(q[qsm["FINAL_HOLDOUT_2026"]], period_days("FINAL_HOLDOUT_2026"))},
            "ALL_2026": {"metrics": metrics(q[qsm["ALL_2026"]]), "frequency": frequency(q[qsm["ALL_2026"]], period_days("ALL_2026"))},
        }

    goal = {
        "desired_signals_per_day": "2-3 across Spot; >=1/day acceptable only if movement quality is strong",
        "target_move_pct": "3-5",
        "win_rate_floor_context": "~40% can be acceptable if 3-5% winners and expectancy/PF remain positive",
    }
    all2026_freq = combined.get("ALL_2026", {}).get("frequency", {}).get("signals_per_day", 0.0)
    final_metrics = combined.get("FINAL_HOLDOUT_2026", {}).get("metrics", {})
    status = "NO_STABLE_MOVEMENT_FAMILY"
    if champions:
        status = "TRAIN_STABLE_HOLDOUT_EVALUATED"
        best_oos = max((final_metrics.get(p, {}).get("mean", -999) for p in PLANS), default=-999)
        if all2026_freq >= 1.0 and best_oos > 0:
            status = "PROMISING_MOVEMENT_FAMILY_SET"
        if all2026_freq >= 2.0 and best_oos > 0:
            status = "TARGET_FREQUENCY_REACHED_WITH_POSITIVE_OOS_PLAN"

    summary = {
        "status": status,
        "purpose": "Broad causal Spot movement-start discovery from video-derived price/momentum/volatility ideas. Four independent setup families are evaluated; they are NOT AND-stacked into one rare r2-style filter.",
        "goal": goal,
        "causality": {
            "closed_15m_only": True,
            "closed_1h_4h_only": True,
            "entry": "next 15m open at decision t+15m",
            "round_trip_cost_pct": COST_PCT,
            "same_bar_tp_sl_ambiguity": "pessimistic: stop first",
            "rule_selection": "Discovery + Calibration only; holdouts diagnostic",
        },
        "universe": "active Binance Spot/USDT, exact stable/fiat base exclusions, BTC excluded",
        "study_window": [str(START), str(END)],
        "candidate_rules": len(rule_defs),
        "aggregate_union_events": int(len(d)),
        "aggregate_symbols": int(d.symbol.nunique()),
        "champions": holdout_family,
        "combined_selected_families": combined,
    }

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    report = [
        "# Movement Family Discovery",
        "",
        "Amaç: r2'yi daraltmak değil; Spot evreninde hareket başlangıcını dört ayrı aileyle geniş ve nedensel biçimde yakalamak.",
        "",
        f"Status: {status}",
        f"Union events: {len(d):,} | Symbols: {d.symbol.nunique()} | Candidate rules: {len(rule_defs)}",
        f"Selected family champions: {len(champions)}",
        "",
        "## Combined",
        json.dumps(combined, indent=2, ensure_ascii=False, allow_nan=False),
        "",
        "## Family champions",
        json.dumps(holdout_family, indent=2, ensure_ascii=False, allow_nan=False),
    ]
    (outdir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    if len(selected):
        selected.to_csv(outdir / "selected_events.csv", index=False)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False), flush=True)


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=110, freq="15min", tz="UTC")
    base = pd.DataFrame({
        "open": np.full(len(idx), 100.0), "high": np.full(len(idx), 100.0),
        "low": np.full(len(idx), 100.0), "close": np.full(len(idx), 100.0),
        "volume": np.full(len(idx), 1000.0), "quote_volume": np.full(len(idx), 100000.0),
    }, index=idx)
    base.loc[idx[2], "high"] = 104.0
    base.loc[idx[2], "low"] = 97.0
    rec = outcome(base, idx[1])
    assert rec is not None
    assert abs(rec["ret_TP3_SL2"] - (-2.0 - COST_PCT)) < 1e-9
    m = pd.Series([True, True, False, True] + [False] * 6, index=pd.date_range("2026-01-01", periods=10, freq="15min", tz="UTC"))
    c = compress(m, m.index, 1)
    assert int(c.sum()) == 1
    assert len(candidate_rules()) == 48
    print(json.dumps({"self_test": "ok", "rules": len(candidate_rules())}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int)
    ap.add_argument("--shards", type=int, default=64)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--aggregate-dir", type=Path)
    ap.add_argument("--symbols", type=str)
    ap.add_argument("--fetch-start", type=str)
    ap.add_argument("--study-start", type=str)
    ap.add_argument("--end", type=str)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.aggregate_dir:
        aggregate_main(a.aggregate_dir, a.outdir)
        return
    if a.shard is None:
        raise SystemExit("--shard required")
    fs = pd.Timestamp(a.fetch_start, tz="UTC") if a.fetch_start else FETCH_START
    ss = pd.Timestamp(a.study_start, tz="UTC") if a.study_start else START
    ee = pd.Timestamp(a.end, tz="UTC") if a.end else END
    shard_main(a.shard, a.shards, a.outdir, a.symbols, fs, ss, ee)


if __name__ == "__main__":
    main()
