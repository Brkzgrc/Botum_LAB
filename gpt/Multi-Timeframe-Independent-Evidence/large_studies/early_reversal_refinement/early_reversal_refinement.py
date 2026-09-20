from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MTF_ROOT = HERE.parents[1]
MFD_PATH = MTF_ROOT / "large_studies" / "movement_family_discovery" / "movement_family_discovery.py"
spec = importlib.util.spec_from_file_location("mfd", MFD_PATH)
mfd = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mfd)

FETCH_START = mfd.FETCH_START
START = mfd.START
END = mfd.END
PLANS = mfd.PLANS
RULE_COOLDOWN_HOURS = 6

BASE_RULE = {
    "name": "ER_043_BASELINE",
    "ret2_max": -2.0,
    "dd12_max": -4.0,
    "mom_min": 2,
}

BASE_FEATURES = [
    "rsi","rsi_d1","rsi_d3",
    "macd_hist","macd_hist_d1","macd_hist_d3",
    "stoch_spread","stoch_spread_d1","stoch_spread_d3",
    "obv_d1","obv_d3",
    "adx","adx_d1","adx_d3",
    "di_spread","di_spread_d1","di_spread_d3",
    "rvol20","rvol20_d1","rvol20_d3",
    "bb_width_ratio","bb_width_d1",
    "ema20_d1","ema50_d1","atr_pct",
    "body_frac","close_loc","lower_wick_frac",
    "hl_count4","hh_count4","mom_score",
    "ret_3p","ret_6p","ret_2h_prev","dd_12h_prev",
]
H1_FEATURES = [
    "rsi","rsi_d1","rsi_d3",
    "macd_hist","macd_hist_d1","macd_hist_d3",
    "stoch_spread","stoch_spread_d1","stoch_spread_d3",
    "obv_d1","obv_d3",
    "adx","adx_d1","adx_d3",
    "di_spread","di_spread_d1","di_spread_d3",
    "rvol20","rvol20_d1","rvol20_d3",
    "bb_width_ratio","bb_width_d1",
    "ema20_d1","ema50_d1","atr_pct",
    "close_loc","lower_wick_frac","hl_count4","hh_count4","mom_score",
    "ret_3p","ret_6p",
]
H4_FEATURES = [
    "rsi","rsi_d1","rsi_d3",
    "macd_hist","macd_hist_d1","macd_hist_d3",
    "stoch_spread","stoch_spread_d1","stoch_spread_d3",
    "adx","adx_d1","adx_d3",
    "di_spread","di_spread_d1","di_spread_d3",
    "bb_width_ratio","bb_width_d1",
    "ema20_d1","ema50_d1","atr_pct",
    "hl_count4","hh_count4","mom_score",
]
FEATURE_COLUMNS = (
    BASE_FEATURES
    + ["h1_" + x for x in H1_FEATURES]
    + ["h4_" + x for x in H4_FEATURES]
    + [
        "mom_accel_15m","mom_accel_1h","mom_accel_4h",
        "break_strength_pct","bounce_from_low_pct",
        "ema20_dist_pct","ema50_dist_pct",
        "h1_ema20_dist_pct","h1_ema50_dist_pct",
        "h4_ema20_dist_pct","h4_ema50_dist_pct",
        "h4_trend_score",
    ]
)


def baseline_mask(z: pd.DataFrame) -> pd.Series:
    return (
        (z.ret_2h_prev <= BASE_RULE["ret2_max"])
        & (z.dd_12h_prev <= BASE_RULE["dd12_max"])
        & (z.close > z.prev_high_8)
        & (z.mom_score >= BASE_RULE["mom_min"])
        & (z.macd_hist_d1 > 0)
    ).fillna(False)


def add_derived(z: pd.DataFrame) -> pd.DataFrame:
    x = z.copy()
    x["mom_accel_15m"] = x.mom_score - x.mom_score.shift(1)
    x["mom_accel_1h"] = x.h1_mom_score - x.h1_mom_score.shift(4)
    x["mom_accel_4h"] = x.h4_mom_score - x.h4_mom_score.shift(16)
    x["break_strength_pct"] = (x.close / x.prev_high_8 - 1.0) * 100.0
    x["bounce_from_low_pct"] = (x.close / x.low - 1.0) * 100.0
    x["ema20_dist_pct"] = (x.close / x.ema20 - 1.0) * 100.0
    x["ema50_dist_pct"] = (x.close / x.ema50 - 1.0) * 100.0
    x["h1_ema20_dist_pct"] = (x.h1_close / x.h1_ema20 - 1.0) * 100.0
    x["h1_ema50_dist_pct"] = (x.h1_close / x.h1_ema50 - 1.0) * 100.0
    x["h4_ema20_dist_pct"] = (x.h4_close / x.h4_ema20 - 1.0) * 100.0
    x["h4_ema50_dist_pct"] = (x.h4_close / x.h4_ema50 - 1.0) * 100.0
    x["h4_trend_score"] = (
        (x.h4_close > x.h4_ema50).astype(float)
        + (x.h4_ema20 > x.h4_ema50).astype(float)
        + (x.h4_ema20_d1 > 0).astype(float)
    )
    return x


def process_symbol(symbol: str, fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp):
    try:
        base = mfd.core.fetch_15m(symbol, start=fetch_start, end=end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"too_short:{len(base)}"}
        z = add_derived(mfd.build_symbol_frame(base, study_start, end))
        if len(z) < 1000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"study_too_short:{len(z)}"}
        mask = mfd.compress(baseline_mask(z), z.index, RULE_COOLDOWN_HOURS)
        rows = []
        cols = [c for c in FEATURE_COLUMNS if c in z.columns]
        for t in z.index[mask.to_numpy(bool)]:
            oc = mfd.outcome(base, t)
            if oc is None:
                continue
            row = z.loc[t]
            rec = {
                "symbol": symbol,
                "hash_mod": mfd.hmod(symbol),
                "decision_time": t,
                **oc,
            }
            for c in cols:
                v = row[c]
                if pd.isna(v):
                    rec[c] = np.nan
                elif isinstance(v, (bool, np.bool_)):
                    rec[c] = int(v)
                else:
                    rec[c] = float(v)
            rows.append(rec)
        return pd.DataFrame(rows), None
    except Exception as ex:
        return pd.DataFrame(), {"symbol": symbol, "error": f"{type(ex).__name__}:{ex}"}


def shard_main(shard: int, shards: int, outdir: Path, symbols_arg: str | None,
               fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    syms = mfd.load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        syms = [s for s in syms if s in wanted]
    mine = [s for i, s in enumerate(syms) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(process_symbol, s, fetch_start, study_start, end): s for s in mine}
        for k, fut in enumerate(as_completed(futs), 1):
            x, e = fut.result()
            if e:
                errors.append(e)
                print("[SYMBOL_ERROR] " + json.dumps(e, ensure_ascii=False), flush=True)
            if x is not None and len(x):
                frames.append(x)
            if k % 3 == 0 or k == len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} er_events={sum(len(q) for q in frames)} errors={len(errors)}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {
        "shard": shard, "shards": shards, "symbols": len(mine), "events": int(len(out)),
        "errors": len(errors), "study_start": str(study_start), "end": str(end),
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if symbols_arg and len(mine) and len(out) == 0:
        raise RuntimeError(f"smoke produced zero early-reversal events for {mine}")
    print(json.dumps(meta), flush=True)


def split_masks(d: pd.DataFrame) -> dict[str, pd.Series]:
    return mfd.split_masks(d)


def plan_metrics(x: pd.DataFrame, plan: str) -> dict:
    if x.empty:
        return {"n": 0}
    q = pd.to_numeric(x[f"ret_{plan}"], errors="coerce").dropna()
    if q.empty:
        return {"n": 0}
    g = float(q[q > 0].sum())
    l = float(-q[q < 0].sum())
    return {
        "n": int(len(q)),
        "mean": float(q.mean()),
        "median": float(q.median()),
        "win": float((q > 0).mean() * 100),
        "pf": float(g / l) if l > 0 else None,
        "target_first": float(pd.to_numeric(x.loc[q.index, f"win_{plan}"], errors="coerce").mean() * 100),
        "stop_first": float(pd.to_numeric(x.loc[q.index, f"loss_{plan}"], errors="coerce").mean() * 100),
    }


def keep_mask(d: pd.DataFrame, gate: dict) -> pd.Series:
    x = pd.to_numeric(d[gate["feature"]], errors="coerce")
    if gate["op"] == ">=":
        return (x >= gate["threshold"]).fillna(False)
    return (x <= gate["threshold"]).fillna(False)


def gate_repr(g: dict) -> str:
    return f'{g["feature"]}{g["op"]}{g["threshold"]:.8g}'


def eval_subset(d: pd.DataFrame, mask: pd.Series, plan: str) -> dict:
    sm = split_masks(d)
    out = {}
    for name, sp in sm.items():
        z = d[sp & mask]
        out[name] = {
            "metrics": plan_metrics(z, plan),
            "frequency": mfd.frequency(z, mfd.period_days(name)),
        }
    return out


def candidate_gates(dev: pd.DataFrame) -> list[dict]:
    out = []
    for f in FEATURE_COLUMNS:
        if f not in dev:
            continue
        x = pd.to_numeric(dev[f], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(x) < 500 or x.nunique() < 8:
            continue
        qs = x.quantile([0.10,0.20,0.30,0.70,0.80,0.90]).to_dict()
        for q in [0.10,0.20,0.30]:
            out.append({"feature": f, "op": ">=", "threshold": float(qs[q]), "quantile": q})
        for q in [0.70,0.80,0.90]:
            out.append({"feature": f, "op": "<=", "threshold": float(qs[q]), "quantile": q})
    return out


def dev_score(d: pd.DataFrame, mask: pd.Series, plan: str, min_keep: float) -> dict | None:
    sm = split_masks(d)
    D0 = d[sm["DISCOVERY"]]
    C0 = d[sm["CALIBRATION"]]
    D = d[sm["DISCOVERY"] & mask]
    C = d[sm["CALIBRATION"] & mask]
    if min(len(D0), len(C0)) == 0:
        return None
    keepD = len(D) / len(D0)
    keepC = len(C) / len(C0)
    if min(keepD, keepC) < min_keep:
        return None
    if min(len(D), len(C)) < 250:
        return None
    dm = plan_metrics(D, plan)
    cm = plan_metrics(C, plan)
    if min(dm.get("mean", -999), cm.get("mean", -999)) <= 0:
        return None
    if min(dm.get("pf") or 0, cm.get("pf") or 0) <= 1.0:
        return None
    bdm = plan_metrics(D0, plan)
    bcm = plan_metrics(C0, plan)
    impD = dm["mean"] - bdm["mean"]
    impC = cm["mean"] - bcm["mean"]
    if min(impD, impC) <= 0:
        return None
    score = (
        min(dm["mean"], cm["mean"])
        + 0.35 * min(impD, impC)
        + 0.15 * min(keepD, keepC)
        + 0.05 * min(dm["win"], cm["win"]) / 100.0
    )
    return {
        "score": float(score),
        "plan": plan,
        "keep_discovery": float(keepD),
        "keep_calibration": float(keepC),
        "discovery": dm,
        "calibration": cm,
        "improvement_discovery": float(impD),
        "improvement_calibration": float(impC),
    }


def winner_loser_profile(dev: pd.DataFrame, plan: str) -> list[dict]:
    w = pd.to_numeric(dev[f"win_{plan}"], errors="coerce") == 1
    l = pd.to_numeric(dev[f"loss_{plan}"], errors="coerce") == 1
    rows = []
    for f in FEATURE_COLUMNS:
        if f not in dev:
            continue
        a = pd.to_numeric(dev.loc[w, f], errors="coerce").dropna()
        b = pd.to_numeric(dev.loc[l, f], errors="coerce").dropna()
        if min(len(a), len(b)) < 50:
            continue
        pooled = pd.to_numeric(dev[f], errors="coerce").dropna()
        scale = float(pooled.quantile(.75) - pooled.quantile(.25))
        if not np.isfinite(scale) or abs(scale) < 1e-12:
            continue
        delta = float((a.median() - b.median()) / scale)
        rows.append({
            "feature": f,
            "winner_median": float(a.median()),
            "loser_median": float(b.median()),
            "median_delta_iqr": delta,
            "abs_delta": abs(delta),
        })
    rows.sort(key=lambda x: x["abs_delta"], reverse=True)
    return rows[:25]


def aggregate_main(indir: Path, outdir: Path) -> None:
    metas = sorted(indir.rglob("meta.json"))
    if len(metas) != 64:
        raise RuntimeError(f"expected 64 shard metas, found {len(metas)}")
    meta_rows = [json.loads(p.read_text(encoding="utf-8")) for p in metas]
    if {int(m["shard"]) for m in meta_rows} != set(range(64)):
        raise RuntimeError("missing/duplicate shard ids")
    if sum(int(m["symbols"]) for m in meta_rows) < 400:
        raise RuntimeError("unexpected symbol coverage")
    if sum(int(m["errors"]) for m in meta_rows) != 0:
        raise RuntimeError("symbol errors present; refusing aggregate")

    frames = []
    for p in sorted(indir.rglob("events.csv")):
        try:
            q = pd.read_csv(p, low_memory=False)
            if len(q):
                frames.append(q)
        except pd.errors.EmptyDataError:
            pass
    if not frames:
        raise RuntimeError("no events")
    d = pd.concat(frames, ignore_index=True)
    d["decision_time"] = pd.to_datetime(d.decision_time, utc=True)
    d["entry_time"] = pd.to_datetime(d.entry_time, utc=True)
    d = d.drop_duplicates(["symbol","decision_time"]).sort_values(["decision_time","symbol"]).reset_index(drop=True)
    if len(d) < 2000 or d.symbol.nunique() < 250:
        raise RuntimeError(f"unexpected ER coverage rows={len(d)} symbols={d.symbol.nunique()}")

    sm = split_masks(d)
    dev = d[sm["DISCOVERY"] | sm["CALIBRATION"]].copy()
    gates = candidate_gates(dev)

    singles = []
    for g in gates:
        gm = keep_mask(d, g)
        for plan in PLANS:
            sc = dev_score(d, gm, plan, min_keep=0.65)
            if sc:
                singles.append({"gates":[g], **sc})
    singles.sort(key=lambda x: x["score"], reverse=True)

    pairs = []
    seeds = singles[:24]
    seen = set()
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            g1, g2 = seeds[i]["gates"][0], seeds[j]["gates"][0]
            if g1["feature"] == g2["feature"]:
                continue
            key = tuple(sorted([gate_repr(g1), gate_repr(g2)]))
            if key in seen:
                continue
            seen.add(key)
            mask = keep_mask(d, g1) & keep_mask(d, g2)
            for plan in PLANS:
                sc = dev_score(d, mask, plan, min_keep=0.55)
                if sc:
                    pairs.append({"gates":[g1,g2], **sc})
    pairs.sort(key=lambda x: x["score"], reverse=True)

    candidates = sorted(singles[:50] + pairs[:50], key=lambda x: x["score"], reverse=True)
    champion = candidates[0] if candidates else None

    baseline = {}
    for plan in PLANS:
        baseline[plan] = eval_subset(d, pd.Series(True, index=d.index), plan)

    result = None
    if champion:
        mask = pd.Series(True, index=d.index)
        for g in champion["gates"]:
            mask &= keep_mask(d, g)
        result = {
            "gates": champion["gates"],
            "gate_text": [gate_repr(g) for g in champion["gates"]],
            "selection": {k:v for k,v in champion.items() if k != "gates"},
            "evaluation": eval_subset(d, mask, champion["plan"]),
            "retained_events": int(mask.sum()),
        }

    profile = winner_loser_profile(dev, "TP5_SL3")
    all2026 = result["evaluation"]["ALL_2026"] if result else None
    status = "NO_DEV_STABLE_REFINEMENT"
    if result:
        status = "DEV_STABLE_REFINEMENT_HOLDOUT_EVALUATED"
        a = all2026
        if a and a["frequency"].get("signals_per_day", 0) >= 1.0 and a["metrics"].get("mean", -999) > 0 and (a["metrics"].get("pf") or 0) > 1.0:
            status = "PROMISING_REFINED_EARLY_REVERSAL"
        if a and a["frequency"].get("signals_per_day", 0) >= 2.0 and a["metrics"].get("mean", -999) > 0 and (a["metrics"].get("pf") or 0) > 1.0:
            status = "TARGET_FREQUENCY_POSITIVE_OOS"

    summary = {
        "status": status,
        "purpose": "Refine the frequent ER_043 early-reversal family by separating toxic vs productive movement states while preserving most signal frequency.",
        "base_rule": BASE_RULE,
        "causality": {
            "closed_15m_1h_4h_only": True,
            "entry": "next 15m open at decision t+15m",
            "round_trip_cost_pct": mfd.COST_PCT,
            "same_bar_tp_sl": "pessimistic stop first",
            "selection_data": "DISCOVERY + CALIBRATION only",
            "holdouts": "never used for gate/plan selection",
        },
        "events": int(len(d)),
        "symbols": int(d.symbol.nunique()),
        "feature_count": int(len([f for f in FEATURE_COLUMNS if f in d.columns])),
        "candidate_gate_count": int(len(gates)),
        "eligible_single_count": int(len(singles)),
        "eligible_pair_count": int(len(pairs)),
        "baseline": baseline,
        "champion": result,
        "winner_loser_profile_tp5_sl3": profile,
        "top_dev_candidates": [
            {
                "gates": [gate_repr(g) for g in x["gates"]],
                "plan": x["plan"],
                "score": x["score"],
                "keep_discovery": x["keep_discovery"],
                "keep_calibration": x["keep_calibration"],
                "discovery": x["discovery"],
                "calibration": x["calibration"],
            }
            for x in candidates[:20]
        ],
    }

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    report = [
        "# Early Reversal Refinement",
        "",
        f"Status: {status}",
        f"Events: {len(d):,} | Symbols: {d.symbol.nunique()} | Features: {summary['feature_count']} | Gates: {len(gates)}",
        "",
        "## Champion",
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        "",
        "## Winner/Loser profile",
        json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False),
    ]
    (outdir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    if result:
        mask = pd.Series(True, index=d.index)
        for g in result["gates"]:
            mask &= keep_mask(d, g)
        keep_cols = ["symbol","hash_mod","decision_time","entry_time","net24","mfe24","mae24"]
        keep_cols += [f"ret_{p}" for p in PLANS] + [f"win_{p}" for p in PLANS] + [f"loss_{p}" for p in PLANS]
        d.loc[mask, keep_cols].to_csv(outdir / "selected_events.csv", index=False)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False), flush=True)


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=120, freq="15min", tz="UTC")
    z = pd.DataFrame(index=idx)
    z["ret_2h_prev"] = -3.0
    z["dd_12h_prev"] = -5.0
    z["close"] = 101.0
    z["prev_high_8"] = 100.0
    z["mom_score"] = 3.0
    z["macd_hist_d1"] = 0.1
    assert baseline_mask(z).all()
    d = pd.DataFrame({
        "decision_time": idx[:10],
        "hash_mod": [50]*10,
        "ret_TP5_SL3": [4,-3,4,-3,4,-3,4,-3,4,-3],
        "win_TP5_SL3": [1,0,1,0,1,0,1,0,1,0],
        "loss_TP5_SL3": [0,1,0,1,0,1,0,1,0,1],
        "x": np.arange(10,dtype=float),
    })
    g={"feature":"x","op":">=","threshold":5.0}
    assert int(keep_mask(d,g).sum()) == 5
    print(json.dumps({"self_test":"ok","feature_columns":len(FEATURE_COLUMNS)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int)
    ap.add_argument("--shards", type=int, default=64)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--aggregate-dir", type=Path)
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
