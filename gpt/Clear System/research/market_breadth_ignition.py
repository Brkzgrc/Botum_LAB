from __future__ import annotations

"""Causal market-breadth ignition followed by coin-local structure transition.

All breadth and coin features are indexed at closed-candle decision times.
Discovery fits the model; Calibration and a symbol cross-holdout gate selection.
Only then is the 2026 final holdout opened.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd


COST_PCT = 0.20
PLANS = ("TP3_SL2", "TP4_SL2P5", "TP5_SL3")
COOLDOWN_HOURS = 12
FEATURES = [
    "breadth_pos1h", "breadth_pos4h", "breadth_high16", "breadth_vol_expand",
    "breadth_accel", "breadth_pos1h_d1", "breadth_pos1h_d4",
    "breadth_high16_d4", "breadth_vol_expand_d4", "breadth_ignition_age",
    "coin_mom_now", "coin_mom_prev", "coin_mom_delta", "coin_ret3",
    "coin_price_accel", "coin_close_loc", "coin_body_frac", "coin_rvol20",
    "coin_hl_count4", "coin_hh_count4", "coin_bb_expand",
    "h1_mom_delta", "h1_ema20_slope", "h4_mom_delta", "h4_ema20_slope",
]

mfd = None
bp = None


def load_dependencies() -> None:
    global mfd, bp
    if mfd is not None:
        return
    import movement_family_discovery as _mfd
    import market_breadth_preflight as _bp
    if abs(float(_mfd.COST_PCT) - COST_PCT) > 1e-12:
        raise RuntimeError("round-trip cost contract changed")
    if tuple(_mfd.PLANS) != PLANS:
        raise RuntimeError("outcome-plan contract changed")
    mfd, bp = _mfd, _bp


def enrich_context(x: pd.DataFrame) -> pd.DataFrame:
    z = x.copy()
    z["breadth_pos1h_d1"] = z.breadth_pos1h - z.breadth_pos1h.shift(1)
    z["breadth_pos1h_d4"] = z.breadth_pos1h - z.breadth_pos1h.shift(4)
    z["breadth_high16_d4"] = z.breadth_high16 - z.breadth_high16.shift(4)
    z["breadth_vol_expand_d4"] = z.breadth_vol_expand - z.breadth_vol_expand.shift(4)
    seq = np.arange(len(z), dtype=float)
    last = pd.Series(np.where(z.ignition.fillna(False).to_numpy(bool), seq, np.nan), index=z.index).ffill()
    z["breadth_ignition_age"] = pd.Series(seq, index=z.index) - last
    z.loc[last.isna(), "breadth_ignition_age"] = np.nan
    return z


def build_context(fetch_start: pd.Timestamp, end: pd.Timestamp, outdir: Path) -> None:
    load_dependencies()
    frames, rows = {}, []
    for symbol in bp.REFERENCES:
        frame, rec = bp.closed_frame(symbol, fetch_start, end + pd.Timedelta(days=2))
        frames[symbol] = frame
        rows.append(rec)
        print(json.dumps(rec), flush=True)
    context = enrich_context(bp.build_breadth(frames))
    outdir.mkdir(parents=True, exist_ok=True)
    context.to_csv(outdir / "breadth.csv.gz", index_label="decision_time", compression="gzip")
    expected = int(((end + pd.Timedelta(days=2)) - fetch_start).total_seconds() // 900)
    meta = {
        "status": "BREADTH_CONTEXT_READY",
        "fetch_start": str(fetch_start), "end": str(end),
        "references": list(bp.REFERENCES), "reference_count": len(bp.REFERENCES),
        "rows": int(len(context)),
        "coverage_pct": float(len(context) / max(1, expected) * 100),
        "ignitions": int(context.ignition.sum()),
        "closed_candle_contract": "Reference open_time shifted +15m before breadth construction.",
        "reference_audit": rows,
    }
    if meta["reference_count"] != 6 or len(rows) != 6:
        raise RuntimeError("reference context cardinality mismatch")
    if min(r["coverage_pct"] for r in rows) < 95 or meta["coverage_pct"] < 95:
        raise RuntimeError("full breadth context coverage below 95%")
    if meta["ignitions"] < 100:
        raise RuntimeError("insufficient full-period breadth ignitions")
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta), flush=True)


def load_context(path: Path) -> pd.DataFrame:
    x = pd.read_csv(path, parse_dates=["decision_time"]).set_index("decision_time")
    x.index = pd.to_datetime(x.index, utc=True)
    if not set(FEATURES[:10]).issubset(x.columns):
        raise RuntimeError("breadth context schema mismatch")
    if not x.index.is_monotonic_increasing or x.index.has_duplicates:
        raise RuntimeError("breadth context timeline invalid")
    return x


def motion_score(z: pd.DataFrame, prefix: str = "") -> pd.Series:
    return (
        (z[prefix + "macd_hist_d1"] > 0).astype(int)
        + (z[prefix + "rsi_d1"] > 0).astype(int)
        + (z[prefix + "stoch_spread_d1"] > 0).astype(int)
        + (z[prefix + "obv_d1"] > 0).astype(int)
        + (z[prefix + "di_spread_d1"] > 0).astype(int)
    )


def add_features(z: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    x = z.join(context.reindex(z.index, method="ffill"))
    m15 = motion_score(x)
    h1 = motion_score(x, "h1_")
    h4 = motion_score(x, "h4_")
    x["coin_mom_now"] = m15
    x["coin_mom_prev"] = m15.shift(1)
    x["coin_mom_delta"] = m15 - m15.shift(1)
    x["coin_ret3"] = x.ret_3p
    x["coin_price_accel"] = x.ret_3p - x.ret_3p.shift(3)
    x["coin_close_loc"] = x.close_loc
    x["coin_body_frac"] = x.body_frac
    x["coin_rvol20"] = x.rvol20.clip(0, 10)
    x["coin_hl_count4"] = x.hl_count4
    x["coin_hh_count4"] = x.hh_count4
    x["coin_bb_expand"] = np.sign(x.bb_width_d1)
    x["h1_mom_delta"] = h1 - h1.shift(4)
    x["h1_ema20_slope"] = x.h1_ema20_d1
    x["h4_mom_delta"] = h4 - h4.shift(16)
    x["h4_ema20_slope"] = x.h4_ema20_d1
    recent_ignition = x.breadth_ignition_age.between(0, 16)
    phase_change = (m15 >= 3) & ((m15.shift(1) <= 2) | ((m15 - m15.shift(1)) >= 2))
    structure_break = (x.close > x.prev_high_8) & (x.close.shift(1) <= x.prev_high_8.shift(1))
    local_trigger = (phase_change | structure_break) & (x.close_loc >= 0.50)
    x["event_gate"] = recent_ignition & local_trigger
    return x


def process_symbol(symbol: str, context: pd.DataFrame, fetch_start: pd.Timestamp,
                   study_start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, dict | None]:
    try:
        base = mfd.core.fetch_15m(symbol, start=fetch_start, end=end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": "too_short:" + str(len(base))}
        z = add_features(mfd.build_symbol_frame(base, study_start, end), context)
        gate = mfd.compress(z.event_gate.fillna(False), z.index, COOLDOWN_HOURS)
        rows = []
        for t in z.index[gate.to_numpy(bool)]:
            outcome = mfd.outcome(base, t)
            if outcome is None:
                continue
            r = z.loc[t]
            rows.append({
                "symbol": symbol, "hash_mod": mfd.hmod(symbol), "decision_time": t,
                **{c: float(r[c]) if pd.notna(r[c]) else np.nan for c in FEATURES},
                **outcome,
            })
        return pd.DataFrame(rows), None
    except Exception as ex:
        return pd.DataFrame(), {"symbol": symbol, "error": type(ex).__name__ + ":" + str(ex)}


def shard_main(shard: int, shards: int, outdir: Path, context_path: Path,
               symbols_arg: str | None, fetch_start: pd.Timestamp,
               study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    load_dependencies()
    context = load_context(context_path)
    symbols = mfd.load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        symbols = [s for s in symbols if s in wanted]
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(process_symbol, s, context, fetch_start, study_start, end): s for s in mine}
        for n, f in enumerate(as_completed(futures), 1):
            data, error = f.result()
            if len(data):
                frames.append(data)
            if error:
                errors.append(error)
            if n % 3 == 0 or n == len(futures):
                print("[SHARD {}] {}/{} events={} errors={}".format(
                    shard, n, len(futures), sum(len(q) for q in frames), len(errors)), flush=True)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    events.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {"shard": shard, "shards": shards, "symbols": len(mine),
            "events": int(len(events)), "errors": len(errors),
            "study_start": str(study_start), "end": str(end)}
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if symbols_arg and mine and events.empty:
        raise RuntimeError("real-data smoke produced zero breadth-ignition events")
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


def metrics(x: pd.DataFrame, plan: str) -> dict:
    if x.empty:
        return {"n": 0, "symbols": 0}
    ret = pd.to_numeric(x["ret_" + plan], errors="coerce").dropna()
    z = x.loc[ret.index]
    gp, gl = float(ret[ret > 0].sum()), float(-ret[ret < 0].sum())
    days = max(1, int((z.decision_time.max().floor("D") - z.decision_time.min().floor("D")).days) + 1)
    active = int(z.decision_time.dt.floor("D").nunique())
    return {
        "n": int(len(z)), "symbols": int(z.symbol.nunique()),
        "signals_per_day": float(len(z) / days), "signals_per_week": float(len(z) / days * 7),
        "active_days": active, "active_day_share_pct": float(active / days * 100),
        "expectancy_pct": float(ret.mean()), "median_pct": float(ret.median()),
        "win_pct": float((ret > 0).mean() * 100), "pf": gp / gl if gl > 0 else None,
        "target_first_pct": float(pd.to_numeric(z["win_" + plan], errors="coerce").mean() * 100),
        "stop_first_pct": float(pd.to_numeric(z["loss_" + plan], errors="coerce").mean() * 100),
        "net24_mean_pct": float(pd.to_numeric(z.net24, errors="coerce").mean()),
        "mfe24_mean_pct": float(pd.to_numeric(z.mfe24, errors="coerce").mean()),
        "mae24_mean_pct": float(pd.to_numeric(z.mae24, errors="coerce").mean()),
    }


def aggregate_main(indir: Path, outdir: Path, expected_shards: int) -> None:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    metas = [json.loads(p.read_text()) for p in indir.rglob("meta.json")]
    ids = {int(m["shard"]) for m in metas}
    if len(metas) != expected_shards or ids != set(range(expected_shards)):
        raise RuntimeError("incomplete shard set: {}".format(sorted(ids)))
    if sum(int(m["symbols"]) for m in metas) < 400:
        raise RuntimeError("unexpectedly small universe")
    hard, benign = [], []
    for p in indir.rglob("errors.csv"):
        try:
            e = pd.read_csv(p)
        except pd.errors.EmptyDataError:
            continue
        for _, r in e.iterrows():
            rec = {"symbol": str(r.get("symbol", "")), "error": str(r.get("error", ""))}
            (benign if rec["error"].startswith("too_short:") else hard).append(rec)
    if hard:
        raise RuntimeError("hard shard errors: " + json.dumps(hard[:10]))
    frames = []
    for p in indir.rglob("events.csv"):
        try:
            q = pd.read_csv(p, low_memory=False)
            if len(q):
                frames.append(q)
        except pd.errors.EmptyDataError:
            pass
    if not frames:
        raise RuntimeError("no events")
    d = pd.concat(frames, ignore_index=True)
    d.decision_time = pd.to_datetime(d.decision_time, utc=True)
    d = d.drop_duplicates(["symbol", "decision_time"]).sort_values(["decision_time", "symbol"])
    masks = split_masks(d)
    candidates = []
    for plan in PLANS:
        train = d[masks["DISCOVERY"]].copy()
        cal = d[masks["CALIBRATION"]].copy()
        cross = d[masks["CROSS_HOLDOUT_PRE2026"]].copy()
        y = pd.to_numeric(train["win_" + plan], errors="coerce").fillna(0).astype(int)
        if y.nunique() < 2:
            continue
        model = Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(C=0.10, class_weight="balanced", max_iter=700, random_state=42)),
        ])
        model.fit(train[FEATURES], y)
        for q in (train, cal, cross):
            q["prob"] = model.predict_proba(q[FEATURES])[:, 1]
        for threshold in np.arange(0.55, 0.91, 0.025):
            mt = metrics(train[train.prob >= threshold], plan)
            mc = metrics(cal[cal.prob >= threshold], plan)
            mx = metrics(cross[cross.prob >= threshold], plan)
            periods = (mt, mc, mx)
            if min(x.get("n", 0) for x in periods) < 60:
                continue
            if min(x.get("expectancy_pct", -99) for x in periods) <= 0:
                continue
            if min((x.get("pf", 0) or 0) for x in periods) <= 1.10:
                continue
            if min(x.get("target_first_pct", 0) for x in periods) < 45:
                continue
            if min(x.get("signals_per_day", 0) for x in periods) < 0.15:
                continue
            score = min(x["expectancy_pct"] for x in periods) + 0.02 * min(x["target_first_pct"] for x in periods) + 0.20 * min(x["signals_per_day"] for x in periods)
            candidates.append((score, plan, float(threshold), model, mt, mc, mx))
    summary = {
        "status": "NO_STABLE_MARKET_BREADTH_IGNITION",
        "data_period": [str(d.decision_time.min()), str(d.decision_time.max())],
        "events": int(len(d)), "symbols": int(d.symbol.nunique()),
        "features": FEATURES, "cost_pct": COST_PCT,
        "benign_short_history_exclusions": len(benign),
        "selection_lock": "Fit Discovery; gate on Discovery+Calibration+CROSS_HOLDOUT_PRE2026; open 2026 only after freeze.",
        "champion": {},
    }
    if candidates:
        score, plan, threshold, model, mt, mc, mx = max(candidates, key=lambda x: x[0])
        result = {"score": float(score), "plan": plan, "threshold": threshold,
                  "DISCOVERY": mt, "CALIBRATION": mc, "CROSS_HOLDOUT_PRE2026": mx}
        for name in ("FINAL_HOLDOUT_2026", "ALL_2026"):
            q = d[masks[name]].copy()
            q["prob"] = model.predict_proba(q[FEATURES])[:, 1]
            result[name] = metrics(q[q.prob >= threshold], plan)
        oos = result["FINAL_HOLDOUT_2026"]
        summary["status"] = "DEV_CHAMPION_HOLDOUT_EVALUATED"
        if oos.get("n", 0) >= 30 and oos.get("expectancy_pct", -99) > 0 and (oos.get("pf", 0) or 0) > 1 and oos.get("target_first_pct", 0) >= 40:
            summary["status"] = "PROMISING_BREADTH_REQUIRES_R2_OR_VALIDATION"
        result["coefficients"] = dict(sorted(
            zip(FEATURES, map(float, model.named_steps["logit"].coef_[0])),
            key=lambda kv: abs(kv[1]), reverse=True))
        summary["champion"] = result
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, allow_nan=False), flush=True)


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=80, freq="15min", tz="UTC")
    c = pd.DataFrame({
        "breadth_pos1h": np.linspace(0.2, 0.9, 80),
        "breadth_pos4h": np.linspace(0.3, 0.8, 80),
        "breadth_high16": np.linspace(0.0, 0.6, 80),
        "breadth_vol_expand": np.linspace(0.1, 0.7, 80),
        "breadth_accel": np.r_[np.zeros(40), np.full(40, 0.5)],
        "ignition": [False] * 40 + [True] + [False] * 39,
    }, index=idx)
    e = enrich_context(c)
    assert e.loc[idx[40], "breadth_ignition_age"] == 0
    assert e.loc[idx[44], "breadth_ignition_age"] == 4
    assert pd.isna(e.loc[idx[39], "breadth_ignition_age"])
    assert len(FEATURES) == 25
    print(json.dumps({"self_test": "ok", "features": len(FEATURES)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-context", action="store_true")
    ap.add_argument("--context", type=Path)
    ap.add_argument("--shard", type=int)
    ap.add_argument("--shards", type=int, default=64)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--aggregate-dir", type=Path)
    ap.add_argument("--expected-shards", type=int, default=64)
    ap.add_argument("--symbols")
    ap.add_argument("--fetch-start")
    ap.add_argument("--study-start")
    ap.add_argument("--end")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.aggregate_dir:
        aggregate_main(a.aggregate_dir, a.outdir, a.expected_shards)
        return
    load_dependencies()
    fs = pd.Timestamp(a.fetch_start, tz="UTC") if a.fetch_start else mfd.FETCH_START
    ss = pd.Timestamp(a.study_start, tz="UTC") if a.study_start else mfd.START
    ee = pd.Timestamp(a.end, tz="UTC") if a.end else mfd.END
    if a.build_context:
        build_context(fs, ee, a.outdir)
        return
    if a.shard is None or a.context is None:
        raise SystemExit("--shard and --context required")
    shard_main(a.shard, a.shards, a.outdir, a.context, a.symbols, fs, ss, ee)


if __name__ == "__main__":
    main()
