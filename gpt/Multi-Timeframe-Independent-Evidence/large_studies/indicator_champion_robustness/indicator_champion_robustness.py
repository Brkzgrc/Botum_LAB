from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

F1 = "btc1_tsi_d1"
F1_MAX = -0.211069
F2 = "btc4_bb_width"
F2_MIN = 0.0942267
COST = 0.20

def profit_factor(v):
    v = pd.to_numeric(v, errors="coerce").dropna()
    gp = v[v > 0].sum()
    gl = -v[v < 0].sum()
    return float(gp / gl) if gl > 0 else np.nan

def metrics(x):
    o = {"n": int(len(x)), "symbols": int(x.symbol.nunique()) if len(x) else 0}
    if not len(x):
        return o
    for h in (12, 24, 72):
        v = pd.to_numeric(x[f"net_{h}h"], errors="coerce").dropna()
        o[f"net{h}_mean"] = float(v.mean())
        o[f"net{h}_median"] = float(v.median())
        o[f"win{h}"] = float((v > 0).mean() * 100)
        o[f"pf{h}"] = profit_factor(v)
        o[f"p10_{h}"] = float(v.quantile(.10))
        o[f"p90_{h}"] = float(v.quantile(.90))
        if len(v) >= 20:
            lo, hi = v.quantile([.01, .99])
            w = v.clip(lo, hi)
            o[f"net{h}_winsor1_mean"] = float(w.mean())
            drop_n = max(1, int(np.ceil(len(v)*.01)))
            cutoff = v.nlargest(drop_n).index
            rem = v.drop(cutoff)
            o[f"net{h}_drop_top1pct_mean"] = float(rem.mean()) if len(rem) else np.nan
    o["up3_before_dn2"] = float(pd.to_numeric(x.up3_before_dn2, errors="coerce").mean()*100)
    o["up3_72"] = float(pd.to_numeric(x.up3_within72, errors="coerce").mean()*100)
    o["danger_dn2_first"] = float(pd.to_numeric(x.danger_dn2_first, errors="coerce").mean()*100)
    return o

def cluster_bootstrap(x, col, reps=10000, seed=260918):
    rng = np.random.default_rng(seed)
    z = x[["symbol", col]].copy()
    z[col] = pd.to_numeric(z[col], errors="coerce")
    z = z.dropna()
    g = z.groupby("symbol")[col].agg(["sum", "count"])
    if len(g) < 5:
        return None
    sums = g["sum"].to_numpy(float)
    counts = g["count"].to_numpy(float)
    n = len(g)
    vals = np.empty(reps, float)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        vals[i] = sums[idx].sum() / counts[idx].sum()
    return {
        "mean": float(vals.mean()),
        "ci_low": float(np.quantile(vals, .025)),
        "ci_high": float(np.quantile(vals, .975)),
        "p_gt_0": float((vals > 0).mean())
    }

def aggregate(indir: Path, outdir: Path):
    files = sorted(indir.rglob("features.csv"))
    frames = [pd.read_csv(f, low_memory=False) for f in files]
    frames = [x for x in frames if len(x)]
    if not frames:
        raise RuntimeError("No indicator augmentation features artifacts found")
    d = pd.concat(frames, ignore_index=True)
    d["decision_time"] = pd.to_datetime(d.decision_time, utc=True)
    d = d.dropna(subset=[F1, F2, "net_12h", "net_24h", "net_72h"]).copy()
    d["selected"] = (pd.to_numeric(d[F1], errors="coerce") <= F1_MAX) & (pd.to_numeric(d[F2], errors="coerce") >= F2_MIN)
    s = d[d.selected].copy()

    masks = {
        "ALL": pd.Series(True, index=d.index),
        "DISCOVERY_2023_2024_DEV": (d.hash_mod >= 30) & (d.decision_time < pd.Timestamp("2025-01-01", tz="UTC")),
        "CALIBRATION_2025_DEV": (d.hash_mod >= 30) & (d.decision_time >= pd.Timestamp("2025-01-01", tz="UTC")) & (d.decision_time < pd.Timestamp("2026-01-01", tz="UTC")),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod < 30) & (d.decision_time < pd.Timestamp("2026-01-01", tz="UTC")),
        "FINAL_HOLDOUT_2026": (d.hash_mod < 30) & (d.decision_time >= pd.Timestamp("2026-01-01", tz="UTC")),
    }
    sections = {}
    for k,m in masks.items():
        base = d[m]
        sel = d[m & d.selected]
        sections[k] = {
            "base": metrics(base),
            "selected": metrics(sel),
            "keep_pct": float(len(sel)/len(base)*100) if len(base) else np.nan,
            "boot24_symbol_cluster": cluster_bootstrap(sel, "net_24h"),
            "boot72_symbol_cluster": cluster_bootstrap(sel, "net_72h"),
        }

    yearly = {}
    for y,g in s.groupby(s.decision_time.dt.year):
        yearly[str(int(y))] = metrics(g)
    monthly = {}
    s["month"] = s.decision_time.dt.to_period("M").astype(str)
    for mo,g in s.groupby("month"):
        monthly[mo] = metrics(g)

    hold = d[(d.hash_mod < 30) & d.selected].copy()
    sym = hold.groupby("symbol").agg(
        n=("net_24h","size"),
        mean24=("net_24h","mean"),
        sum24=("net_24h","sum"),
        mean72=("net_72h","mean"),
        sum72=("net_72h","sum"),
    ).sort_values("sum24", ascending=False)
    outdir.mkdir(parents=True, exist_ok=True)
    sym.to_csv(outdir/"holdout_symbol_contribution.csv")

    seq_sections = {}
    seq = hold.sort_values("decision_time").copy()
    for h in (24,72):
        r = pd.to_numeric(seq[f"net_{h}h"], errors="coerce").fillna(0)/100.0
        eq = (1+r).cumprod()
        dd = eq/eq.cummax()-1
        seq_sections[str(h)] = {
            "events": int(len(seq)),
            "compounded_pct": float((eq.iloc[-1]-1)*100) if len(eq) else np.nan,
            "max_event_sequence_drawdown_pct": float(dd.min()*100) if len(dd) else np.nan,
        }

    pos_sum = sym.sum24.clip(lower=0).sum()
    summary = {
        "frozen_rule": F1 + " <= " + str(F1_MAX) + " AND " + F2 + " >= " + str(F2_MIN),
        "rule_reoptimized": False,
        "round_trip_cost_pct": COST,
        "source": "existing Indicator Augmentation Discovery shard artifacts; no refetch and no new threshold search",
        "events_total": int(len(d)),
        "events_selected": int(len(s)),
        "sections": sections,
        "yearly_selected": yearly,
        "monthly_selected": monthly,
        "holdout_symbol_concentration": {
            "symbols": int(len(sym)),
            "top5_share_of_positive_sum24_pct": float(sym.head(5).sum24.clip(lower=0).sum()/pos_sum*100) if pos_sum > 0 else np.nan,
            "positive_symbols_pct": float((sym.mean24 > 0).mean()*100) if len(sym) else np.nan,
        },
        "holdout_equal_event_sequence": seq_sections,
    }
    (outdir/"summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frozen Indicator Champion — Robustness Audit",
        "",
        "Rule: " + summary["frozen_rule"],
        "Events: " + str(summary["events_total"]) + " | selected: " + str(summary["events_selected"]) + " | cost: 0.20%",
        "",
        "No threshold was tuned in this audit. The previously selected pair is frozen.",
        "",
    ]
    for k,v in sections.items():
        lines.append("## " + k)
        lines.append("Keep=" + f"{v['keep_pct']:.2f}%" + " | selected=" + str(v["selected"]))
        lines.append("Boot24=" + str(v["boot24_symbol_cluster"]) + " | Boot72=" + str(v["boot72_symbol_cluster"]))
        lines.append("")
    lines.append("## Yearly selected")
    for y,v in yearly.items():
        lines.append("- " + y + ": " + str(v))
    lines.append("")
    lines.append("## Holdout concentration")
    lines.append(str(summary["holdout_symbol_concentration"]))
    (outdir/"REPORT.md").write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggregate-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, default=OUT)
    args = ap.parse_args()
    aggregate(args.aggregate_dir, args.outdir)
