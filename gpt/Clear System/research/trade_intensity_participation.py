from __future__ import annotations

"""Closed-candle trade-intensity and average-trade-size transition study."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd


COST_PCT = 0.20
PLANS = ("TP3_SL2", "TP4_SL2P5", "TP5_SL3")
COOLDOWN_HOURS = 6
FEATURES = [
    "m15_count_ratio", "m15_size_ratio", "m15_count_delta", "m15_size_delta",
    "m15_count_slope", "m15_size_slope", "m15_price_ret4", "m15_price_accel",
    "m15_churn", "m15_close_loc", "m15_range_pct", "m15_body_frac",
    "m15_break8", "m15_hl_count4",
    "h1_count_ratio", "h1_size_ratio", "h1_count_delta", "h1_size_delta",
    "h1_price_ret4", "h1_churn", "h1_break8",
    "h4_count_ratio", "h4_size_ratio", "h4_count_delta", "h4_size_delta",
    "h4_price_ret4", "h4_churn", "h4_break8",
]

mfd = None
tf = None


def load_dependencies() -> None:
    global mfd, tf
    if mfd is not None:
        return
    import movement_family_discovery as _mfd
    import taker_flow_preflight as _tf
    if abs(float(_mfd.COST_PCT) - COST_PCT) > 1e-12:
        raise RuntimeError("round-trip cost contract changed")
    if tuple(_mfd.PLANS) != PLANS:
        raise RuntimeError("outcome-plan contract changed")
    mfd, tf = _mfd, _tf


def aggregate_bars(base: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    x = base[["open", "high", "low", "close", "volume", "quote_volume", "trades"]].copy()
    x["trades"] = pd.to_numeric(x.trades, errors="coerce")
    if rule is None:
        return x
    return x.resample(rule, label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "quote_volume": "sum", "trades": "sum",
    }).dropna(subset=["open", "high", "low", "close"])


def intensity_features(base: pd.DataFrame, prefix: str, rule: str | None,
                       close_delay: pd.Timedelta) -> pd.DataFrame:
    x = aggregate_bars(base, rule)
    count = x.trades.replace(0, np.nan)
    avg_size = x.quote_volume / count
    count_ref = count.shift(1).rolling(20, min_periods=10).median()
    size_ref = avg_size.shift(1).rolling(20, min_periods=10).median()
    count_ratio = count / count_ref.replace(0, np.nan)
    size_ratio = avg_size / size_ref.replace(0, np.nan)
    count4 = count_ratio.rolling(4, min_periods=4).mean()
    size4 = size_ratio.rolling(4, min_periods=4).mean()
    count_prev = count_ratio.shift(4).rolling(4, min_periods=4).mean()
    size_prev = size_ratio.shift(4).rolling(4, min_periods=4).mean()
    price4 = x.close.pct_change(4) * 100
    ret1 = x.close.pct_change() * 100
    participation = count_ratio.clip(0, 10) * size_ratio.clip(0, 10)
    churn = participation / (ret1.abs() + 0.10)
    rng = (x.high - x.low).replace(0, np.nan)
    prev_high8 = x.high.shift(1).rolling(8, min_periods=8).max()
    out = pd.DataFrame(index=x.index)
    out[prefix + "count_ratio"] = count_ratio.clip(0, 10)
    out[prefix + "size_ratio"] = size_ratio.clip(0, 10)
    out[prefix + "count_delta"] = count4 - count_prev
    out[prefix + "size_delta"] = size4 - size_prev
    if prefix == "m15_":
        out[prefix + "count_slope"] = count_ratio.rolling(3, min_periods=3).mean() - count_ratio.shift(3).rolling(3, min_periods=3).mean()
        out[prefix + "size_slope"] = size_ratio.rolling(3, min_periods=3).mean() - size_ratio.shift(3).rolling(3, min_periods=3).mean()
    out[prefix + "price_ret4"] = price4
    if prefix == "m15_":
        out[prefix + "price_accel"] = price4 - price4.shift(2)
    out[prefix + "churn"] = churn.clip(0, 100)
    if prefix == "m15_":
        out[prefix + "close_loc"] = ((x.close - x.low) / rng).clip(0, 1)
        out[prefix + "range_pct"] = (rng / x.close.replace(0, np.nan) * 100).clip(0, 100)
        out[prefix + "body_frac"] = ((x.close - x.open).abs() / rng).clip(0, 1)
    out[prefix + "break8"] = (x.close > prev_high8).astype(float)
    if prefix == "m15_":
        out[prefix + "hl_count4"] = (x.low > x.low.shift(1)).rolling(4, min_periods=4).sum()
    out.index = out.index + close_delay
    return out[~out.index.duplicated(keep="last")]


def build_frame(base: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    idx = base.index + pd.Timedelta(minutes=15)
    idx = idx[(idx >= start) & (idx < end)]
    z = intensity_features(base, "m15_", None, pd.Timedelta(minutes=15)).reindex(idx)
    h1 = intensity_features(base, "h1_", "1h", pd.Timedelta(hours=1))
    h4 = intensity_features(base, "h4_", "4h", pd.Timedelta(hours=4))
    z = z.join(h1.reindex(idx, method="ffill")).join(h4.reindex(idx, method="ffill"))
    quiet_participation = (
        (z.m15_price_ret4.abs() < 2.0)
        & ((z.m15_count_ratio > 1.20) | (z.m15_size_ratio > 1.20))
        & ((z.m15_count_delta > 0) | (z.m15_size_delta > 0))
    )
    participation_release = (
        (z.m15_break8 > 0)
        & ((z.m15_count_ratio > 1.10) | (z.m15_size_ratio > 1.10))
        & (z.m15_close_loc >= 0.55)
    )
    joint_expansion = (
        (z.m15_count_delta > 0) & (z.m15_size_delta > 0)
        & (z.m15_price_accel > 0) & (z.m15_close_loc >= 0.55)
    )
    state = quiet_participation | participation_release | joint_expansion
    z["event_gate"] = state & ~state.shift(1, fill_value=False)
    return z


def process_symbol(symbol: str, fetch_start: pd.Timestamp, study_start: pd.Timestamp,
                   end: pd.Timestamp) -> tuple[pd.DataFrame, dict | None]:
    try:
        base = tf.fetch_15m(symbol, fetch_start, end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": "too_short:" + str(len(base))}
        z = build_frame(base, study_start, end)
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


def shard_main(shard: int, shards: int, outdir: Path, symbols_arg: str | None,
               fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    load_dependencies()
    symbols = mfd.load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        symbols = [s for s in symbols if s in wanted]
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(process_symbol, s, fetch_start, study_start, end): s for s in mine}
        for n, f in enumerate(as_completed(futures), 1):
            data, error = f.result()
            if len(data):
                frames.append(data)
            if error:
                errors.append(error)
            if n % 3 == 0 or n == len(futures):
                print("[SHARD {}] {}/{} events={} errors={}".format(
                    shard, n, len(futures), sum(len(x) for x in frames), len(errors)), flush=True)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    events.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {"shard": shard, "shards": shards, "symbols": len(mine),
            "events": int(len(events)), "errors": len(errors),
            "study_start": str(study_start), "end": str(end)}
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if symbols_arg and mine and events.empty:
        raise RuntimeError("real-data smoke produced zero trade-intensity events")
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
        train, cal = d[masks["DISCOVERY"]].copy(), d[masks["CALIBRATION"]].copy()
        y = pd.to_numeric(train["win_" + plan], errors="coerce").fillna(0).astype(int)
        if y.nunique() < 2:
            continue
        model = Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(C=0.10, class_weight="balanced", max_iter=700, random_state=42)),
        ])
        model.fit(train[FEATURES], y)
        train["prob"] = model.predict_proba(train[FEATURES])[:, 1]
        cal["prob"] = model.predict_proba(cal[FEATURES])[:, 1]
        for threshold in np.arange(0.55, 0.91, 0.025):
            tr, ca = train[train.prob >= threshold], cal[cal.prob >= threshold]
            mt, mc = metrics(tr, plan), metrics(ca, plan)
            if min(mt.get("n", 0), mc.get("n", 0)) < 80:
                continue
            if min(mt.get("expectancy_pct", -99), mc.get("expectancy_pct", -99)) <= 0:
                continue
            if min(mt.get("pf", 0) or 0, mc.get("pf", 0) or 0) <= 1.10:
                continue
            if min(mt.get("target_first_pct", 0), mc.get("target_first_pct", 0)) < 45:
                continue
            if min(mt.get("signals_per_day", 0), mc.get("signals_per_day", 0)) < 0.20:
                continue
            score = min(mt["expectancy_pct"], mc["expectancy_pct"]) + 0.02 * min(mt["target_first_pct"], mc["target_first_pct"]) + 0.20 * min(mt["signals_per_day"], mc["signals_per_day"])
            candidates.append((score, plan, float(threshold), model, mt, mc))
    summary = {
        "status": "NO_STABLE_TRADE_INTENSITY_PARTICIPATION",
        "data_period": [str(d.decision_time.min()), str(d.decision_time.max())],
        "events": int(len(d)), "symbols": int(d.symbol.nunique()),
        "features": FEATURES, "cost_pct": COST_PCT,
        "benign_short_history_exclusions": len(benign),
        "selection_lock": "Fit Discovery; select plan/threshold on Discovery+Calibration; open holdouts only after freeze.",
        "champion": {},
    }
    if candidates:
        score, plan, threshold, model, mt, mc = max(candidates, key=lambda x: x[0])
        result = {"score": float(score), "plan": plan, "threshold": threshold,
                  "DISCOVERY": mt, "CALIBRATION": mc}
        for name in ("CROSS_HOLDOUT_PRE2026", "FINAL_HOLDOUT_2026", "ALL_2026"):
            q = d[masks[name]].copy()
            q["prob"] = model.predict_proba(q[FEATURES])[:, 1]
            result[name] = metrics(q[q.prob >= threshold], plan)
        oos = result["FINAL_HOLDOUT_2026"]
        summary["status"] = "DEV_CHAMPION_HOLDOUT_EVALUATED"
        if oos.get("n", 0) >= 30 and oos.get("expectancy_pct", -99) > 0 and (oos.get("pf", 0) or 0) > 1 and oos.get("target_first_pct", 0) >= 40:
            summary["status"] = "PROMISING_TRADE_INTENSITY_REQUIRES_R2_OR_VALIDATION"
        result["coefficients"] = dict(sorted(
            zip(FEATURES, map(float, model.named_steps["logit"].coef_[0])),
            key=lambda kv: abs(kv[1]), reverse=True))
        summary["champion"] = result
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, allow_nan=False), flush=True)


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=50, freq="15min", tz="UTC")
    trades = np.r_[np.full(25, 100.0), np.full(25, 180.0)]
    quote = np.r_[np.full(25, 10000.0), np.full(25, 27000.0)]
    base = pd.DataFrame({
        "open": np.linspace(100, 101, 50), "high": np.linspace(101, 102, 50),
        "low": np.linspace(99, 100, 50), "close": np.linspace(100, 101, 50),
        "volume": quote / 100, "quote_volume": quote, "trades": trades,
    }, index=idx)
    f = intensity_features(base, "m15_", None, pd.Timedelta(minutes=15))
    assert f.index[0] == idx[0] + pd.Timedelta(minutes=15)
    # Check the transition itself; after a full rolling window the new regime
    # correctly becomes its own median reference.
    assert float(f.m15_count_ratio.iloc[27]) > 1
    assert float(f.m15_size_ratio.iloc[27]) > 1
    assert float(f.m15_count_delta.iloc[27]) > 0
    assert len(FEATURES) == 28
    print(json.dumps({"self_test": "ok", "features": len(FEATURES)}))


def main() -> None:
    ap = argparse.ArgumentParser()
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
    if a.shard is None:
        raise SystemExit("--shard required")
    fs = pd.Timestamp(a.fetch_start, tz="UTC") if a.fetch_start else mfd.FETCH_START
    ss = pd.Timestamp(a.study_start, tz="UTC") if a.study_start else mfd.START
    ee = pd.Timestamp(a.end, tz="UTC") if a.end else mfd.END
    shard_main(a.shard, a.shards, a.outdir, a.symbols, fs, ss, ee)


if __name__ == "__main__":
    main()
