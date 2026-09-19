from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
EXT_DIR = PARENT / "frozen_candidate_outcome_extension"
sys.path.insert(0, str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

# Frozen r2 rule. These values are NOT re-optimized here.
R2_H4_BB_MIN = 0.19233492
R2_DD48_MAX = -7.3594696


def pf(v):
    v = pd.to_numeric(v, errors="coerce").dropna()
    gp = float(v[v > 0].sum())
    gl = float(-v[v < 0].sum())
    return gp / gl if gl > 0 else np.nan


def metrics(x):
    o = {"n": int(len(x)), "symbols": int(x.symbol.nunique()) if len(x) else 0}
    if not len(x):
        return o
    for h in (12, 24, 72):
        v = pd.to_numeric(x[f"net_{h}h"], errors="coerce").dropna()
        o[f"net{h}_mean"] = float(v.mean())
        o[f"net{h}_median"] = float(v.median())
        o[f"win{h}"] = float((v > 0).mean() * 100)
        o[f"pf{h}"] = pf(v)
        if len(v) >= 20:
            drop_n = max(1, int(np.ceil(len(v) * .01)))
            rem = v.drop(v.nlargest(drop_n).index)
            o[f"net{h}_drop_top1pct"] = float(rem.mean()) if len(rem) else np.nan
    o["up3_before_dn2"] = float(pd.to_numeric(x.up3_before_dn2, errors="coerce").mean() * 100)
    o["danger_dn2_first"] = float(pd.to_numeric(x.danger_dn2_first, errors="coerce").mean() * 100)
    return o


def cluster_bootstrap(x, col="net_24h", reps=10000, seed=260919):
    z = x[["symbol", col]].copy()
    z[col] = pd.to_numeric(z[col], errors="coerce")
    z = z.dropna()
    g = z.groupby("symbol")[col].agg(["sum", "count"])
    if len(g) < 8:
        return None
    sums = g["sum"].to_numpy(float)
    counts = g["count"].to_numpy(float)
    n = len(g)
    rng = np.random.default_rng(seed)
    vals = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        vals[i] = sums[idx].sum() / counts[idx].sum()
    return {
        "mean": float(vals.mean()),
        "ci_low": float(np.quantile(vals, .025)),
        "ci_high": float(np.quantile(vals, .975)),
        "p_gt_0": float((vals > 0).mean()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    d = ext.load_frozen_candidate(args.artifact_dir)
    d = ext.add_causal_pullbacks(d, workers=max(1, args.workers))
    d = d[d.pullback_error.fillna("") == ""].copy()

    # Fixed r2 only.
    d["r2"] = (
        (pd.to_numeric(d.h4_bb_width, errors="coerce") >= R2_H4_BB_MIN)
        & (pd.to_numeric(d.causal_dd_high_48h, errors="coerce") <= R2_DD48_MAX)
    )

    splits = ext.split_masks(d)
    out = {
        "rule": f"h4_bb_width >= {R2_H4_BB_MIN} AND causal_dd_high_48h <= {R2_DD48_MAX}",
        "reoptimized": False,
        "events_base": int(len(d)),
        "events_r2": int(d.r2.sum()),
        "sections": {},
    }
    for name, mask in splits.items():
        base = d[mask]
        sel = d[mask & d.r2]
        out["sections"][name] = {
            "base": metrics(base),
            "r2": metrics(sel),
            "keep_pct": float(len(sel) / len(base) * 100) if len(base) else np.nan,
            "boot24_symbol_cluster": cluster_bootstrap(sel, "net_24h"),
            "boot72_symbol_cluster": cluster_bootstrap(sel, "net_72h"),
        }

    # Year and month stability.
    sel = d[d.r2].copy()
    sel["year"] = sel.decision_time.dt.year
    sel["month"] = sel.decision_time.dt.to_period("M").astype(str)
    out["yearly"] = {str(int(y)): metrics(g) for y, g in sel.groupby("year")}
    out["monthly"] = {m: metrics(g) for m, g in sel.groupby("month")}

    # Frozen-threshold neighborhood sensitivity only; diagnostic, not selection.
    # +/-10% relative threshold perturbations around r2.
    sensitivity = []
    for bb_mult in (0.90, 0.95, 1.00, 1.05, 1.10):
        for dd_mult in (0.90, 0.95, 1.00, 1.05, 1.10):
            bb = R2_H4_BB_MIN * bb_mult
            # Threshold is negative. A multiplier >1 means stricter/deeper pullback.
            dd = R2_DD48_MAX * dd_mult
            m = (
                (pd.to_numeric(d.h4_bb_width, errors="coerce") >= bb)
                & (pd.to_numeric(d.causal_dd_high_48h, errors="coerce") <= dd)
            )
            rec = {"bb_mult": bb_mult, "dd_mult": dd_mult, "bb": bb, "dd48": dd}
            for name, sm in splits.items():
                q = metrics(d[sm & m])
                rec[name] = q
            sensitivity.append(rec)
    out["threshold_neighborhood"] = sensitivity

    # Symbol concentration on holdouts.
    hold = d[(splits["CROSS_HOLDOUT_PRE2026"] | splits["FINAL_HOLDOUT_2026"]) & d.r2].copy()
    sym = hold.groupby("symbol").agg(n=("net_24h","size"), mean24=("net_24h","mean"), sum24=("net_24h","sum")).sort_values("sum24", ascending=False)
    pos = float(sym.sum24.clip(lower=0).sum())
    out["holdout_concentration"] = {
        "symbols": int(len(sym)),
        "positive_symbols_pct": float((sym.mean24 > 0).mean() * 100) if len(sym) else np.nan,
        "top5_share_positive_sum24_pct": float(sym.head(5).sum24.clip(lower=0).sum() / pos * 100) if pos > 0 else np.nan,
    }

    (args.outdir / "summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    sym.to_csv(args.outdir / "holdout_symbol_contribution.csv")

    lines = [
        "# Frozen r2 Robustness Audit",
        "",
        f"Rule: {out['rule']}",
        "No threshold re-optimization in this audit.",
        f"Base events={out['events_base']} | r2 events={out['events_r2']}",
        "",
    ]
    for k, v in out["sections"].items():
        lines += [f"## {k}", str(v), ""]
    lines += ["## Holdout concentration", str(out["holdout_concentration"])]
    (args.outdir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
