from __future__ import annotations

"""Outcome-first, causal multi-timeframe movement-transition research.

The model never receives a future value as a feature.  It learns only from
closed-candle movement paths in Discovery, selects its probability threshold
in Calibration, and opens 2026 only after the rule is frozen.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import movement_family_discovery as mfd


FETCH_START = mfd.FETCH_START
START = mfd.START
END = mfd.END
PLANS = mfd.PLANS
COST = mfd.COST_PCT
COOLDOWN_HOURS = 6

FEATURES = [
    "m15_mom_now", "m15_mom_prev", "m15_mom_delta",
    "m15_rsi_turn", "m15_macd_turn", "m15_stoch_turn",
    "m15_obv_dir", "m15_di_turn", "m15_price_accel",
    "m15_hl_count", "m15_hh_count", "m15_close_loc",
    "m15_body_frac", "m15_rvol", "m15_bb_expand",
    "h1_mom_now", "h1_mom_prev", "h1_mom_delta",
    "h1_price_accel", "h1_ema20_slope", "h1_bb_expand",
    "h4_mom_now", "h4_mom_prev", "h4_mom_delta",
    "h4_ema20_slope", "h4_bb_expand",
]


def signed(s: pd.Series) -> pd.Series:
    return np.sign(pd.to_numeric(s, errors="coerce")).astype(float)


def motion_score(z: pd.DataFrame, prefix: str = "") -> pd.Series:
    return (
        (z[prefix + "macd_hist_d1"] > 0).astype(int)
        + (z[prefix + "rsi_d1"] > 0).astype(int)
        + (z[prefix + "stoch_spread_d1"] > 0).astype(int)
        + (z[prefix + "obv_d1"] > 0).astype(int)
        + (z[prefix + "di_spread_d1"] > 0).astype(int)
    )


def add_transition_features(z: pd.DataFrame) -> pd.DataFrame:
    x = z.copy()
    m15 = motion_score(x)
    h1 = motion_score(x, "h1_")
    h4 = motion_score(x, "h4_")

    x["m15_mom_now"] = m15
    x["m15_mom_prev"] = m15.shift(1)
    x["m15_mom_delta"] = m15 - m15.shift(1)
    x["m15_rsi_turn"] = signed(x.rsi_d1) + signed(x.rsi_d3)
    x["m15_macd_turn"] = signed(x.macd_hist_d1) + signed(x.macd_hist_d3)
    x["m15_stoch_turn"] = signed(x.stoch_spread_d1) + signed(x.stoch_spread_d3)
    x["m15_obv_dir"] = signed(x.obv_d3)
    x["m15_di_turn"] = signed(x.di_spread_d1) + signed(x.di_spread_d3)
    x["m15_price_accel"] = x.ret_3p - x.ret_3p.shift(3)
    x["m15_hl_count"] = x.hl_count4
    x["m15_hh_count"] = x.hh_count4
    x["m15_close_loc"] = x.close_loc
    x["m15_body_frac"] = x.body_frac
    x["m15_rvol"] = x.rvol20.clip(0, 10)
    x["m15_bb_expand"] = signed(x.bb_width_d1)

    x["h1_mom_now"] = h1
    x["h1_mom_prev"] = h1.shift(4)
    x["h1_mom_delta"] = h1 - h1.shift(4)
    x["h1_price_accel"] = x.h1_ret_3p - x.h1_ret_3p.shift(4)
    x["h1_ema20_slope"] = x.h1_ema20_d1
    x["h1_bb_expand"] = signed(x.h1_bb_width_d1)

    x["h4_mom_now"] = h4
    x["h4_mom_prev"] = h4.shift(16)
    x["h4_mom_delta"] = h4 - h4.shift(16)
    x["h4_ema20_slope"] = x.h4_ema20_d1
    x["h4_bb_expand"] = signed(x.h4_bb_width_d1)

    # Broad causal event gate, not a hand-tuned entry rule.  It admits either
    # a fresh momentum phase change or a fresh local structure break.
    phase_change = (m15 >= 3) & ((m15.shift(1) <= 2) | ((m15 - m15.shift(1)) >= 2))
    structure_change = (x.close > x.prev_high_8) & (x.close.shift(1) <= x.prev_high_8.shift(1))
    x["event_gate"] = (phase_change | structure_change) & (x.close_loc >= 0.45)
    return x


def process_symbol(symbol: str, fetch_start: pd.Timestamp, study_start: pd.Timestamp,
                   end: pd.Timestamp) -> tuple[pd.DataFrame, dict | None]:
    try:
        base = mfd.core.fetch_15m(symbol, start=fetch_start, end=end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": "too_short:" + str(len(base))}
        z = add_transition_features(mfd.build_symbol_frame(base, study_start, end))
        gate = mfd.compress(z.event_gate.fillna(False), z.index, COOLDOWN_HOURS)
        rows = []
        for t in z.index[gate.to_numpy(bool)]:
            oc = mfd.outcome(base, t)
            if oc is None:
                continue
            row = z.loc[t]
            rec = {
                "symbol": symbol,
                "hash_mod": mfd.hmod(symbol),
                "decision_time": t,
                **{c: float(row[c]) if pd.notna(row[c]) else np.nan for c in FEATURES},
                **oc,
            }
            rows.append(rec)
        return pd.DataFrame(rows), None
    except Exception as ex:
        return pd.DataFrame(), {"symbol": symbol, "error": type(ex).__name__ + ":" + str(ex)}


def shard_main(shard: int, shards: int, outdir: Path, symbols_arg: str | None,
               fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    symbols = mfd.load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        symbols = [s for s in symbols if s in wanted]
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(process_symbol, s, fetch_start, study_start, end): s for s in mine}
        for n, fut in enumerate(as_completed(futs), 1):
            data, error = fut.result()
            if len(data):
                frames.append(data)
            if error:
                errors.append(error)
            if n % 3 == 0 or n == len(futs):
                print("[SHARD {}] {}/{} events={} errors={}".format(
                    shard, n, len(futs), sum(len(x) for x in frames), len(errors)), flush=True)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    events.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {"shard": shard, "shards": shards, "symbols": len(mine),
            "events": int(len(events)), "errors": len(errors)}
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
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
    r = pd.to_numeric(x["ret_" + plan], errors="coerce").dropna()
    z = x.loc[r.index]
    gp, gl = float(r[r > 0].sum()), float(-r[r < 0].sum())
    days = max(1, int((z.decision_time.max().floor("D") - z.decision_time.min().floor("D")).days) + 1)
    active = int(z.decision_time.dt.floor("D").nunique())
    return {
        "n": int(len(z)), "symbols": int(z.symbol.nunique()),
        "signals_per_day": float(len(z) / days),
        "active_days": active, "active_day_share_pct": float(active / days * 100),
        "mean": float(r.mean()), "median": float(r.median()),
        "win": float((r > 0).mean() * 100), "pf": gp / gl if gl > 0 else None,
        "target_first": float(pd.to_numeric(z["win_" + plan], errors="coerce").mean() * 100),
        "stop_first": float(pd.to_numeric(z["loss_" + plan], errors="coerce").mean() * 100),
        "mean24": float(pd.to_numeric(z.net24, errors="coerce").mean()),
        "mfe24": float(pd.to_numeric(z.mfe24, errors="coerce").mean()),
        "mae24": float(pd.to_numeric(z.mae24, errors="coerce").mean()),
    }


def aggregate_main(indir: Path, outdir: Path, expected_shards: int = 64) -> None:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    metas = [json.loads(p.read_text()) for p in indir.rglob("meta.json")]
    if len(metas) != expected_shards or {int(m["shard"]) for m in metas} != set(range(expected_shards)):
        raise RuntimeError("incomplete shard set")
    if sum(int(m["symbols"]) for m in metas) < 400:
        raise RuntimeError("unexpectedly small universe")
    hard_errors = []
    benign_errors = []
    for p in indir.rglob("errors.csv"):
        try:
            e = pd.read_csv(p)
        except pd.errors.EmptyDataError:
            continue
        for _, row in e.iterrows():
            rec = {"symbol": str(row.get("symbol", "")), "error": str(row.get("error", ""))}
            if rec["error"].startswith("too_short:"):
                benign_errors.append(rec)
            else:
                hard_errors.append(rec)
    if hard_errors:
        raise RuntimeError("hard shard errors: " + json.dumps(hard_errors[:10]))

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
        y = pd.to_numeric(train["win_" + plan], errors="coerce").fillna(0).astype(int)
        model = Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(C=0.10, class_weight="balanced", max_iter=600, random_state=42)),
        ])
        model.fit(train[FEATURES], y)
        train["prob"] = model.predict_proba(train[FEATURES])[:, 1]
        cal["prob"] = model.predict_proba(cal[FEATURES])[:, 1]
        for threshold in np.arange(0.55, 0.91, 0.025):
            tr = train[train.prob >= threshold]
            ca = cal[cal.prob >= threshold]
            mt, mc = metrics(tr, plan), metrics(ca, plan)
            if min(mt.get("n", 0), mc.get("n", 0)) < 80:
                continue
            if min(mt.get("mean", -99), mc.get("mean", -99)) <= 0:
                continue
            if min(mt.get("pf", 0) or 0, mc.get("pf", 0) or 0) <= 1:
                continue
            if min(mt.get("target_first", 0), mc.get("target_first", 0)) < 45:
                continue
            if min(mt.get("signals_per_day", 0), mc.get("signals_per_day", 0)) < 0.10:
                continue
            score = min(mt["mean"], mc["mean"]) + 0.02 * min(mt["target_first"], mc["target_first"])
            candidates.append((score, plan, float(threshold), model, mt, mc))

    summary = {
        "status": "NO_STABLE_OUTCOME_FIRST_TRANSITION",
        "events": int(len(d)), "symbols": int(d.symbol.nunique()),
        "features": FEATURES, "cost_pct": COST,
        "benign_short_history_exclusions": len(benign_errors),
        "selection_lock": "Model fits Discovery; plan/threshold selection uses Discovery+Calibration; holdouts untouched until frozen.",
        "champion": {},
    }
    if candidates:
        score, plan, threshold, model, mt, mc = max(candidates, key=lambda x: x[0])
        result = {"score": float(score), "plan": plan, "threshold": threshold,
                  "DISCOVERY": mt, "CALIBRATION": mc}
        for name in ["CROSS_HOLDOUT_PRE2026", "FINAL_HOLDOUT_2026", "ALL_2026"]:
            q = d[masks[name]].copy()
            q["prob"] = model.predict_proba(q[FEATURES])[:, 1]
            result[name] = metrics(q[q.prob >= threshold], plan)
        oos = result["FINAL_HOLDOUT_2026"]
        summary["status"] = "DEV_CHAMPION_HOLDOUT_EVALUATED"
        if oos.get("n", 0) >= 30 and oos.get("mean", -99) > 0 and (oos.get("pf", 0) or 0) > 1:
            summary["status"] = "PROMISING_OUTCOME_FIRST_TRANSITION"
        summary["champion"] = result
        coefs = model.named_steps["logit"].coef_[0]
        summary["coefficients"] = dict(sorted(zip(FEATURES, map(float, coefs)), key=lambda x: abs(x[1]), reverse=True))

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, allow_nan=False))


def self_test() -> None:
    assert len(FEATURES) == 26
    idx = pd.date_range("2026-01-01", periods=120, freq="15min", tz="UTC")
    base = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0,
                         "close": 100.0, "volume": 1000.0, "quote_volume": 100000.0}, index=idx)
    base.loc[idx[3], ["high", "low"]] = [104.0, 97.0]
    rec = mfd.outcome(base, idx[2])
    assert rec is not None
    assert abs(rec["ret_TP3_SL2"] - (-2.0 - COST)) < 1e-9
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
    if a.shard is None:
        raise SystemExit("--shard required")
    fs = pd.Timestamp(a.fetch_start, tz="UTC") if a.fetch_start else FETCH_START
    ss = pd.Timestamp(a.study_start, tz="UTC") if a.study_start else START
    ee = pd.Timestamp(a.end, tz="UTC") if a.end else END
    shard_main(a.shard, a.shards, a.outdir, a.symbols, fs, ss, ee)


if __name__ == "__main__":
    main()
