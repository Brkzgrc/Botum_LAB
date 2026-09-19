from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

COST = 0.20
PRIMARY_DIP_PCT = 0.50
PRIMARY_WINDOW_BARS = 8  # 8 x 15m = 2h
EXIT_BARS = 96           # 24h after entry

REQUIRED_EVENT_COLS = {
    "event_id", "symbol", "decision_time", "entry_time", "hash_mod",
    "net_24h",
}
REQUIRED_PATH_COLS = {
    "event_id", "bar_i", "open", "high", "low", "close",
}


def split_masks(d: pd.DataFrame) -> dict[str, pd.Series]:
    t = d["decision_time"]
    return {
        "DISCOVERY": (d.hash_mod >= 30) & (t < pd.Timestamp("2025-01-01", tz="UTC")),
        "CALIBRATION": (
            (d.hash_mod >= 30)
            & (t >= pd.Timestamp("2025-01-01", tz="UTC"))
            & (t < pd.Timestamp("2026-01-01", tz="UTC"))
        ),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod < 30) & (t < pd.Timestamp("2026-01-01", tz="UTC")),
        "FINAL_HOLDOUT_2026": (d.hash_mod < 30) & (t >= pd.Timestamp("2026-01-01", tz="UTC")),
    }


def net_ret(exit_px: float, entry_px: float) -> float:
    return (exit_px / entry_px - 1.0) * 100.0 - COST


def metrics(v: pd.Series) -> dict:
    x = pd.to_numeric(v, errors="coerce").dropna()
    if not len(x):
        return {"n": 0}
    gp = float(x[x > 0].sum())
    gl = float(-x[x < 0].sum())
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win": float((x > 0).mean() * 100.0),
        "pf": (gp / gl) if gl > 0 else None,
        "q10": float(x.quantile(0.10)),
        "q25": float(x.quantile(0.25)),
        "q75": float(x.quantile(0.75)),
        "q90": float(x.quantile(0.90)),
    }


def load_dataset(dataset_dir: Path):
    ev = pd.read_csv(dataset_dir / "r2_events.csv", low_memory=False)
    pa = pd.read_csv(dataset_dir / "r2_paths.csv", low_memory=False)

    missing_e = sorted(REQUIRED_EVENT_COLS - set(ev.columns))
    missing_p = sorted(REQUIRED_PATH_COLS - set(pa.columns))
    if missing_e or missing_p:
        raise RuntimeError(f"missing columns events={missing_e} paths={missing_p}")

    ev["decision_time"] = pd.to_datetime(ev["decision_time"], utc=True)
    ev["entry_time"] = pd.to_datetime(ev["entry_time"], utc=True)
    ev["event_id"] = pd.to_numeric(ev["event_id"], errors="raise").astype(int)
    ev["hash_mod"] = pd.to_numeric(ev["hash_mod"], errors="raise").astype(int)
    ev["net_24h"] = pd.to_numeric(ev["net_24h"], errors="coerce")

    for c in ["event_id", "bar_i"]:
        pa[c] = pd.to_numeric(pa[c], errors="raise").astype(int)
    for c in ["open", "high", "low", "close"]:
        pa[c] = pd.to_numeric(pa[c], errors="coerce")

    paths = {
        int(eid): g.sort_values("bar_i").reset_index(drop=True)
        for eid, g in pa.groupby("event_id")
    }
    return ev, pa, paths


def preflight(dataset_dir: Path) -> dict:
    ev, pa, paths = load_dataset(dataset_dir)
    masks = split_masks(ev)
    split_counts = {k: int(v.sum()) for k, v in masks.items()}

    if len(ev) < 150:
        raise RuntimeError(f"r2 event count unexpectedly low: {len(ev)}")
    if min(split_counts.values()) < 20:
        raise RuntimeError(f"split count unexpectedly low: {split_counts}")
    if len(paths) != ev.event_id.nunique():
        raise RuntimeError(f"path/event mismatch paths={len(paths)} events={ev.event_id.nunique()}")

    min_bars = min(len(g) for g in paths.values())
    if min_bars < 110:
        raise RuntimeError(f"insufficient path length for 2h wait + 24h exit: min_bars={min_bars}")

    # Exact baseline reproduction check: bar0 open -> bar96 open should match stored net_24h.
    diffs = []
    checked = 0
    for r in ev.itertuples(index=False):
        g = paths.get(int(r.event_id))
        if g is None or len(g) <= EXIT_BARS:
            continue
        calc = net_ret(float(g.open.iloc[EXIT_BARS]), float(g.open.iloc[0]))
        if np.isfinite(r.net_24h):
            diffs.append(abs(calc - float(r.net_24h)))
            checked += 1
    max_diff = max(diffs) if diffs else np.nan
    if checked < 150 or not np.isfinite(max_diff) or max_diff > 1e-8:
        raise RuntimeError(f"baseline reproduction failed checked={checked} max_diff={max_diff}")

    return {
        "events": int(len(ev)),
        "symbols": int(ev.symbol.nunique()),
        "path_rows": int(len(pa)),
        "min_path_bars": int(min_bars),
        "split_counts": split_counts,
        "baseline_reproduction_checked": int(checked),
        "baseline_reproduction_max_abs_diff": float(max_diff),
    }


def dip_entry_return(g: pd.DataFrame, dip_pct: float, window_bars: int):
    base = float(g.open.iloc[0])
    trigger_px = base * (1.0 - dip_pct / 100.0)

    for i in range(min(window_bars, len(g) - EXIT_BARS - 2)):
        # Trigger is known only after this 15m candle closes.
        if float(g.close.iloc[i]) <= trigger_px:
            entry_i = i + 1
            exit_i = entry_i + EXIT_BARS
            if exit_i >= len(g):
                return None
            return {
                "return": net_ret(float(g.open.iloc[exit_i]), float(g.open.iloc[entry_i])),
                "entry_bar": int(entry_i),
                "trigger_bar": int(i),
                "entry_price": float(g.open.iloc[entry_i]),
            }
    return None


def fallback_return(g: pd.DataFrame, dip_pct: float, window_bars: int):
    hit = dip_entry_return(g, dip_pct, window_bars)
    if hit is not None:
        return {**hit, "mode": "DIP"}

    entry_i = window_bars
    exit_i = entry_i + EXIT_BARS
    if exit_i >= len(g):
        return None
    return {
        "return": net_ret(float(g.open.iloc[exit_i]), float(g.open.iloc[entry_i])),
        "entry_bar": int(entry_i),
        "trigger_bar": None,
        "entry_price": float(g.open.iloc[entry_i]),
        "mode": "FALLBACK",
    }


def paired_symbol_bootstrap(d: pd.DataFrame, delta_col: str, reps: int = 10000, seed: int = 260919):
    z = d[["symbol", delta_col]].copy()
    z[delta_col] = pd.to_numeric(z[delta_col], errors="coerce")
    z = z.dropna()
    by = z.groupby("symbol")[delta_col].agg(["sum", "count"])
    if len(by) < 8:
        return None
    sums = by["sum"].to_numpy(float)
    counts = by["count"].to_numpy(float)
    n = len(by)
    rng = np.random.default_rng(seed)
    vals = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        vals[i] = sums[idx].sum() / counts[idx].sum()
    return {
        "mean_delta": float(vals.mean()),
        "ci_low": float(np.quantile(vals, 0.025)),
        "ci_high": float(np.quantile(vals, 0.975)),
        "p_gt_0": float((vals > 0).mean()),
    }


def evaluate_rule(ev: pd.DataFrame, paths: dict[int, pd.DataFrame], dip_pct: float, window_bars: int):
    rows = []
    for r in ev.itertuples(index=False):
        g = paths[int(r.event_id)]
        base = float(r.net_24h)

        dip = dip_entry_return(g, dip_pct, window_bars)
        fb = fallback_return(g, dip_pct, window_bars)

        rows.append({
            "event_id": int(r.event_id),
            "symbol": r.symbol,
            "decision_time": r.decision_time,
            "hash_mod": int(r.hash_mod),
            "baseline": base,
            "dip_entered": dip is not None,
            "dip_return": None if dip is None else dip["return"],
            "dip_entry_bar": None if dip is None else dip["entry_bar"],
            "fallback_return": None if fb is None else fb["return"],
            "fallback_mode": None if fb is None else fb["mode"],
            "fallback_entry_bar": None if fb is None else fb["entry_bar"],
        })
    return pd.DataFrame(rows)


def split_report(z: pd.DataFrame):
    masks = split_masks(z)
    out = {}
    for name, m in masks.items():
        q = z[m].copy()
        entered = q[q.dip_entered].copy()
        q["dip_delta_vs_same_event_base"] = q["dip_return"] - q["baseline"]
        q["fallback_delta"] = q["fallback_return"] - q["baseline"]

        out[name] = {
            "baseline": metrics(q["baseline"]),
            "dip_only": metrics(q["dip_return"]),
            "dip_coverage_pct": float(q["dip_entered"].mean() * 100.0),
            "dip_triggered_baseline": metrics(entered["baseline"]),
            "dip_delta_vs_same_event_baseline": metrics(q["dip_delta_vs_same_event_base"]),
            "dip_opportunity_adjusted_mean_per_original_signal": float(q["dip_return"].fillna(0.0).mean()),
            "fallback_all_signals": metrics(q["fallback_return"]),
            "fallback_delta_vs_baseline": metrics(q["fallback_delta"]),
            "fallback_dip_fill_pct": float((q["fallback_mode"] == "DIP").mean() * 100.0),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--preflight", action="store_true")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    pf = preflight(args.dataset_dir)
    if args.preflight:
        (args.outdir / "preflight.json").write_text(json.dumps(pf, indent=2), encoding="utf-8")
        print(json.dumps(pf), flush=True)
        return

    ev, _, paths = load_dataset(args.dataset_dir)

    # PRIMARY is frozen from the prior entry-timing study. No holdout is used to change it.
    primary = evaluate_rule(ev, paths, PRIMARY_DIP_PCT, PRIMARY_WINDOW_BARS)
    primary["decision_time"] = pd.to_datetime(primary["decision_time"], utc=True)
    primary_report = split_report(primary)

    masks = split_masks(primary)
    hold = masks["CROSS_HOLDOUT_PRE2026"] | masks["FINAL_HOLDOUT_2026"]

    primary["dip_delta_vs_same_event_base"] = primary["dip_return"] - primary["baseline"]
    primary["fallback_delta"] = primary["fallback_return"] - primary["baseline"]

    hold_dip = primary[hold & primary.dip_entered].copy()
    hold_fb = primary[hold].copy()

    bootstrap = {
        "dip_only_paired_on_triggered_events": paired_symbol_bootstrap(
            hold_dip, "dip_delta_vs_same_event_base"
        ),
        "fallback_all_events": paired_symbol_bootstrap(
            hold_fb, "fallback_delta"
        ),
    }

    trig_bars = pd.to_numeric(primary.loc[primary.dip_entered, "dip_entry_bar"], errors="coerce")
    timing = {
        "entered_events": int(primary.dip_entered.sum()),
        "coverage_pct": float(primary.dip_entered.mean() * 100.0),
        "entry_delay_minutes_median": float(trig_bars.median() * 15.0),
        "entry_delay_minutes_p90": float(trig_bars.quantile(0.90) * 15.0),
    }

    # Neighborhood robustness only. These variants are NOT candidates selected on holdout.
    neighborhood = []
    for dip_pct in (0.25, 0.50, 0.75, 1.00):
        for hours in (1, 2, 3, 4):
            z = evaluate_rule(ev, paths, dip_pct, hours * 4)
            z["decision_time"] = pd.to_datetime(z["decision_time"], utc=True)
            rep = split_report(z)
            neighborhood.append({
                "dip_pct": dip_pct,
                "window_hours": hours,
                "splits": rep,
            })

    yearly = []
    primary["year"] = primary.decision_time.dt.year
    for year, q in primary.groupby("year"):
        yearly.append({
            "year": int(year),
            "events": int(len(q)),
            "coverage_pct": float(q.dip_entered.mean() * 100.0),
            "baseline": metrics(q.baseline),
            "dip_only": metrics(q.dip_return),
            "fallback": metrics(q.fallback_return),
        })

    monthly = []
    primary["month"] = primary.decision_time.dt.to_period("M").astype(str)
    for month, q in primary.groupby("month"):
        monthly.append({
            "month": month,
            "events": int(len(q)),
            "coverage_pct": float(q.dip_entered.mean() * 100.0),
            "baseline_mean": metrics(q.baseline).get("mean"),
            "dip_mean": metrics(q.dip_return).get("mean"),
            "fallback_mean": metrics(q.fallback_return).get("mean"),
        })

    summary = {
        "purpose": (
            "Promotion audit of frozen DIP_0.5_2H entry refinement on r2. "
            "Primary rule was chosen previously from Discovery+Calibration; this audit does not "
            "reselect it from holdouts."
        ),
        "preflight": pf,
        "primary_rule": {
            "dip_pct": PRIMARY_DIP_PCT,
            "window_hours": PRIMARY_WINDOW_BARS / 4,
            "trigger": "15m close <= original entry open * 0.995",
            "fill": "next 15m candle open",
            "exit": "24h after actual fill",
        },
        "primary_splits": primary_report,
        "holdout_cluster_bootstrap": bootstrap,
        "timing": timing,
        "yearly": yearly,
        "monthly": monthly,
        "neighborhood": neighborhood,
    }

    primary.to_csv(args.outdir / "primary_event_audit.csv", index=False)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    (args.outdir / "REPORT.md").write_text(
        "# r2 DIP_0.5_2H Promotion Audit\n\n"
        + json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "SUCCESS",
        "primary_splits": primary_report,
        "bootstrap": bootstrap,
        "timing": timing,
    }, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
