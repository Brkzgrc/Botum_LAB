from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
LARGE = HERE.parent / "large_studies"
EXT_DIR = LARGE / "frozen_candidate_outcome_extension"
sys.path.insert(0, str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

R2_H4_BB_MIN = 0.19233492
R2_DD48_MAX = -7.3594696
COST = 0.20


def load_r2(artifact_dir: Path, workers: int = 12) -> pd.DataFrame:
    d = ext.load_frozen_candidate(artifact_dir)
    d = ext.add_causal_pullbacks(d, workers=max(1, workers))
    d = d[d.pullback_error.fillna("") == ""].copy()
    d["r2"] = (
        (pd.to_numeric(d.h4_bb_width, errors="coerce") >= R2_H4_BB_MIN)
        & (pd.to_numeric(d.causal_dd_high_48h, errors="coerce") <= R2_DD48_MAX)
    )
    return d[d.r2].copy()


def split_masks(d: pd.DataFrame) -> dict[str, pd.Series]:
    return ext.split_masks(d)


def profit_factor(v) -> float:
    v = pd.to_numeric(v, errors="coerce").dropna()
    gp = float(v[v > 0].sum())
    gl = float(-v[v < 0].sum())
    return gp / gl if gl > 0 else np.nan


def basic_metrics(d: pd.DataFrame, col: str = "net_24h") -> dict:
    v = pd.to_numeric(d[col], errors="coerce").dropna()
    if not len(v):
        return {"n": 0}
    return {
        "n": int(len(v)),
        "symbols": int(d.loc[v.index, "symbol"].nunique()),
        "mean": float(v.mean()),
        "median": float(v.median()),
        "win": float((v > 0).mean() * 100),
        "pf": profit_factor(v),
        "q10": float(v.quantile(.10)),
        "q25": float(v.quantile(.25)),
        "q75": float(v.quantile(.75)),
        "q90": float(v.quantile(.90)),
    }


def cluster_bootstrap_mean(d: pd.DataFrame, col: str, reps: int = 5000, seed: int = 260919):
    z = d[["symbol", col]].copy()
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
