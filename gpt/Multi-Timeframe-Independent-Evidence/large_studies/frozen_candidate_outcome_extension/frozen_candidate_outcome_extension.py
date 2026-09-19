from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

F1 = "btc1_tsi_d1"
F1_MAX = -0.211069
F2 = "btc4_bb_width"
F2_MIN = 0.0942267
COST = 0.20

BB_FEATURES = ["m15_bb_width", "h1_bb_width", "h4_bb_width"]
PULLBACK_HOURS = [1, 2, 4, 8, 12, 24, 48]
BB_QUANTILES = [0.35, 0.50, 0.65]
PB_QUANTILES = [0.25, 0.40, 0.50, 0.60]

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Botum-LAB-Frozen-Candidate-Extension/1.0"})


def get_json(path, params=None, attempts=6):
    last = None
    for i in range(attempts):
        for base in BASE_URLS:
            try:
                r = HTTP.get(base + path, params=params or {}, timeout=20)
                if r.status_code in (418, 429):
                    last = RuntimeError(f"rate limit {r.status_code}")
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last = exc
        time.sleep(min(8.0, 0.5 * (2 ** i)))
    raise RuntimeError(f"Binance request failed: {path}: {last}")


def profit_factor(v):
    v = pd.to_numeric(v, errors="coerce").dropna()
    gp = float(v[v > 0].sum())
    gl = float(-v[v < 0].sum())
    return gp / gl if gl > 0 else np.nan


def metrics(x):
    out = {"n": int(len(x)), "symbols": int(x.symbol.nunique()) if len(x) else 0}
    if not len(x):
        return out
    for h in (12, 24, 72):
        v = pd.to_numeric(x[f"net_{h}h"], errors="coerce").dropna()
        out[f"net{h}_mean"] = float(v.mean())
        out[f"net{h}_median"] = float(v.median())
        out[f"win{h}"] = float((v > 0).mean() * 100)
        out[f"pf{h}"] = profit_factor(v)
    out["up3_before_dn2"] = float(pd.to_numeric(x.up3_before_dn2, errors="coerce").mean() * 100)
    out["danger_dn2_first"] = float(pd.to_numeric(x.danger_dn2_first, errors="coerce").mean() * 100)
    out["mfe72"] = float(pd.to_numeric(x.mfe_72h, errors="coerce").mean())
    out["mae72"] = float(pd.to_numeric(x.mae_72h, errors="coerce").mean())
    return out


def load_frozen_candidate(indir: Path):
    fs = sorted(indir.rglob("features.csv"))
    frames = [pd.read_csv(f, low_memory=False) for f in fs]
    frames = [x for x in frames if len(x)]
    if not frames:
        raise RuntimeError("No Indicator Augmentation features.csv artifacts found")
    d = pd.concat(frames, ignore_index=True)
    d["decision_time"] = pd.to_datetime(d.decision_time, utc=True)
    d["entry_time"] = pd.to_datetime(d.entry_time, utc=True)
    for c in [F1, F2, "net_12h", "net_24h", "net_72h"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[F1, F2, "net_12h", "net_24h", "net_72h"]).copy()
    d = d[(d[F1] <= F1_MAX) & (d[F2] >= F2_MIN)].copy()
    d = d.sort_values(["symbol", "decision_time"]).drop_duplicates(["symbol", "decision_time"])
    return d


def fetch_causal_pullback(row):
    symbol = str(row.symbol)
    t = pd.Timestamp(row.decision_time)
    end_ms = int(t.timestamp() * 1000) - 1
    start_ms = int((t - pd.Timedelta(hours=50)).timestamp() * 1000)
    try:
        rows = get_json(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": "15m",
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            },
        )
        if not isinstance(rows, list) or len(rows) < 193:
            return {"_idx": int(row._idx), "pullback_error": f"short:{len(rows) if isinstance(rows,list) else -1}"}
        cols = ["open_time","open","high","low","close","volume","close_time","qv","trades","tb","tq","ignore"]
        z = pd.DataFrame(rows, columns=cols)
        for c in ["open","high","low","close"]:
            z[c] = pd.to_numeric(z[c], errors="coerce")
        z = z.dropna(subset=["open","high","low","close"])
        if len(z) < 193:
            return {"_idx": int(row._idx), "pullback_error": "nan_short"}
        ref = float(z.close.iloc[-1])
        rec = {"_idx": int(row._idx), "decision_close": ref, "pullback_error": ""}
        for h in PULLBACK_HOURS:
            n = h * 4
            sl = z.iloc[-n:] if len(z) >= n else z
            first_open = float(sl.open.iloc[0])
            hi = float(sl.high.max())
            lo = float(sl.low.min())
            rec[f"causal_pre_ret_{h}h"] = (ref / first_open - 1.0) * 100.0 if first_open > 0 else np.nan
            rec[f"causal_dd_high_{h}h"] = (ref / hi - 1.0) * 100.0 if hi > 0 else np.nan
            rec[f"causal_bounce_low_{h}h"] = (ref / lo - 1.0) * 100.0 if lo > 0 else np.nan
        return rec
    except Exception as exc:
        return {"_idx": int(row._idx), "pullback_error": repr(exc)}


def add_causal_pullbacks(d, workers=12):
    x = d.reset_index(drop=True).copy()
    x["_idx"] = np.arange(len(x), dtype=int)
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_causal_pullback, r): int(r._idx) for r in x.itertuples(index=False)}
        for k, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if k % 50 == 0 or k == len(futs):
                ok = sum(not r.get("pullback_error") for r in rows)
                print(f"[PULLBACK] {k}/{len(futs)} ok={ok} errors={k-ok}", flush=True)
    p = pd.DataFrame(rows)
    x = x.merge(p, on="_idx", how="left").drop(columns=["_idx"])
    return x


def split_masks(d):
    t = d.decision_time
    return {
        "DISCOVERY": (d.hash_mod >= 30) & (t < pd.Timestamp("2025-01-01", tz="UTC")),
        "CALIBRATION": (d.hash_mod >= 30) & (t >= pd.Timestamp("2025-01-01", tz="UTC")) & (t < pd.Timestamp("2026-01-01", tz="UTC")),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod < 30) & (t < pd.Timestamp("2026-01-01", tz="UTC")),
        "FINAL_HOLDOUT_2026": (d.hash_mod < 30) & (t >= pd.Timestamp("2026-01-01", tz="UTC")),
    }


def improvements(base, sub):
    if not sub.get("n", 0):
        return {}
    return {
        "net12": sub["net12_mean"] - base["net12_mean"],
        "net24": sub["net24_mean"] - base["net24_mean"],
        "net72": sub["net72_mean"] - base["net72_mean"],
        "success": sub["up3_before_dn2"] - base["up3_before_dn2"],
        "danger_reduction": base["danger_dn2_first"] - sub["danger_dn2_first"],
    }


def cluster_bootstrap_delta(d, mask, col="net_24h", reps=5000, seed=260919):
    z = d[["symbol", col]].copy()
    z[col] = pd.to_numeric(z[col], errors="coerce")
    z = z.dropna()
    z["selected"] = mask.reindex(z.index).fillna(False).astype(bool)
    syms = z.symbol.unique()
    if len(syms) < 8:
        return None
    by = {s: z[z.symbol == s] for s in syms}
    rng = np.random.default_rng(seed)
    vals = np.empty(reps)
    for i in range(reps):
        sample = rng.choice(syms, size=len(syms), replace=True)
        parts = [by[s] for s in sample]
        q = pd.concat(parts, ignore_index=True)
        a = q.loc[q.selected, col]
        b = q[col]
        vals[i] = float(a.mean() - b.mean()) if len(a) else np.nan
    vals = vals[np.isfinite(vals)]
    if not len(vals):
        return None
    return {
        "mean_delta": float(vals.mean()),
        "ci_low": float(np.quantile(vals, .025)),
        "ci_high": float(np.quantile(vals, .975)),
        "p_gt_0": float((vals > 0).mean()),
    }


def discover_rules(d):
    masks = split_masks(d)
    base = {k: metrics(d[m]) for k, m in masks.items()}
    disc = masks["DISCOVERY"]
    cal = masks["CALIBRATION"]

    rows = []
    rule_masks = {}

    # Outcome-First directional hypothesis, fixed BEFORE this threshold search:
    # higher coin BB width is favorable; deeper causal pullback from recent high is favorable.
    for feat in BB_FEATURES:
        s = pd.to_numeric(d.loc[disc, feat], errors="coerce").dropna()
        for q in BB_QUANTILES:
            th = float(s.quantile(q))
            name = f"{feat} GE DQ{int(q*100)}({th:.8g})"
            m = pd.to_numeric(d[feat], errors="coerce") >= th
            rule_masks[name] = m
            rows.append(("BB", name, feat, "GE", q, th, m))

    for h in PULLBACK_HOURS:
        feat = f"causal_dd_high_{h}h"
        s = pd.to_numeric(d.loc[disc, feat], errors="coerce").dropna()
        if len(s) < 40:
            continue
        for q in PB_QUANTILES:
            th = float(s.quantile(q))
            name = f"{feat} LE DQ{int(q*100)}({th:.8g})"
            m = pd.to_numeric(d[feat], errors="coerce") <= th
            rule_masks[name] = m
            rows.append(("PULLBACK", name, feat, "LE", q, th, m))

    scored = []
    for family, name, feat, side, q, th, m in rows:
        md = metrics(d[disc & m]); mc = metrics(d[cal & m])
        bd = base["DISCOVERY"]; bc = base["CALIBRATION"]
        if md.get("n", 0) < 25 or mc.get("n", 0) < 18:
            continue
        kd = md["n"] / max(1, bd["n"]); kc = mc["n"] / max(1, bc["n"])
        if not (0.12 <= kd <= 0.85 and 0.12 <= kc <= 0.85):
            continue
        idd = improvements(bd, md); ic = improvements(bc, mc)
        score = (
            min(idd["net24"], ic["net24"])
            + 0.35 * min(idd["net12"], ic["net12"])
            + 0.03 * min(idd["success"], ic["success"])
            + 0.02 * min(idd["danger_reduction"], ic["danger_reduction"])
        )
        stable = (
            idd["net24"] > 0 and ic["net24"] > 0
            and idd["net12"] > -0.20 and ic["net12"] > -0.20
        )
        scored.append({
            "type": "single", "family": family, "name": name, "feature": feat,
            "side": side, "quantile": q, "threshold": th,
            "disc_n": md["n"], "cal_n": mc["n"],
            "disc_keep": kd, "cal_keep": kc,
            "disc_net24_imp": idd["net24"], "cal_net24_imp": ic["net24"],
            "disc_net12_imp": idd["net12"], "cal_net12_imp": ic["net12"],
            "disc_success_imp": idd["success"], "cal_success_imp": ic["success"],
            "disc_danger_imp": idd["danger_reduction"], "cal_danger_imp": ic["danger_reduction"],
            "score": score, "stable_train_cal": stable,
        })

    singles = pd.DataFrame(scored)
    if len(singles):
        singles = singles.sort_values("score", ascending=False)

    # Only cross-family BB + corrected pullback pairs; no combinatorial BB+BB or PB+PB search.
    pairs = []
    if len(singles):
        arows = singles[(singles.family == "BB") & singles.stable_train_cal].head(8)
        brows = singles[(singles.family == "PULLBACK") & singles.stable_train_cal].head(10)
        for _, a in arows.iterrows():
            for _, b in brows.iterrows():
                name = a["name"] + " & " + b["name"]
                m = rule_masks[a["name"]] & rule_masks[b["name"]]
                md = metrics(d[disc & m]); mc = metrics(d[cal & m])
                bd = base["DISCOVERY"]; bc = base["CALIBRATION"]
                if md.get("n", 0) < 20 or mc.get("n", 0) < 15:
                    continue
                idd = improvements(bd, md); ic = improvements(bc, mc)
                score = (
                    min(idd["net24"], ic["net24"])
                    + 0.35 * min(idd["net12"], ic["net12"])
                    + 0.03 * min(idd["success"], ic["success"])
                    + 0.02 * min(idd["danger_reduction"], ic["danger_reduction"])
                )
                stable = (
                    idd["net24"] > 0 and ic["net24"] > 0
                    and idd["net12"] > -0.20 and ic["net12"] > -0.20
                )
                rule_masks[name] = m
                pairs.append({
                    "type": "pair", "family": "BB+PULLBACK", "name": name,
                    "disc_n": md["n"], "cal_n": mc["n"],
                    "disc_net24_imp": idd["net24"], "cal_net24_imp": ic["net24"],
                    "disc_net12_imp": idd["net12"], "cal_net12_imp": ic["net12"],
                    "disc_success_imp": idd["success"], "cal_success_imp": ic["success"],
                    "disc_danger_imp": idd["danger_reduction"], "cal_danger_imp": ic["danger_reduction"],
                    "score": score, "stable_train_cal": stable,
                })
    pairs = pd.DataFrame(pairs)
    if len(pairs):
        pairs = pairs.sort_values("score", ascending=False)

    candidates = []
    if len(singles):
        candidates += singles[singles.stable_train_cal].head(12).to_dict("records")
    if len(pairs):
        candidates += pairs[pairs.stable_train_cal].head(12).to_dict("records")

    champion = None
    if candidates:
        candidates = sorted(candidates, key=lambda r: float(r["score"]), reverse=True)
        champion = candidates[0]

    diagnostics = []
    for rec in candidates:
        name = rec["name"]; m = rule_masks[name]
        out = {"type": rec["type"], "family": rec["family"], "name": name, "score": float(rec["score"])}
        for k, sm in masks.items():
            sub = metrics(d[sm & m]); b = base[k]
            out[k.lower()] = {
                "metrics": sub,
                "improvement_vs_frozen_tsi_bb": improvements(b, sub),
                "keep_pct": float(sub.get("n", 0) / max(1, b.get("n", 0)) * 100),
            }
        diagnostics.append(out)

    champion_diag = next((x for x in diagnostics if champion and x["name"] == champion["name"]), None)
    if champion_diag:
        cmask = rule_masks[champion["name"]]
        hold = masks["CROSS_HOLDOUT_PRE2026"] | masks["FINAL_HOLDOUT_2026"]
        champion_diag["holdout_cluster_bootstrap_net24_delta"] = cluster_bootstrap_delta(
            d[hold].copy(), cmask[hold].copy(), "net_24h"
        )

    return base, singles, pairs, diagnostics, champion, champion_diag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    d = load_frozen_candidate(args.artifact_dir)
    print(f"[BASE] frozen TSI+BB events={len(d)} symbols={d.symbol.nunique()}", flush=True)

    d = add_causal_pullbacks(d, workers=max(1, args.workers))
    pullback_ok = int((d.pullback_error.fillna("") == "").sum())
    print(f"[PULLBACK] usable={pullback_ok}/{len(d)}", flush=True)

    base, singles, pairs, diagnostics, champion, champion_diag = discover_rules(d)

    d.to_csv(args.outdir / "enriched_frozen_candidate_events.csv", index=False)
    singles.to_csv(args.outdir / "single_rules.csv", index=False)
    pairs.to_csv(args.outdir / "pair_rules.csv", index=False)

    summary = {
        "purpose": "Test whether Outcome-First coin volatility expansion and a corrected causal pullback measure add value on top of the frozen BTC1 TSI + BTC4 BB candidate.",
        "baseline_rule": f"{F1} <= {F1_MAX} AND {F2} >= {F2_MIN}",
        "round_trip_cost_pct": COST,
        "candidate_events": int(len(d)),
        "symbols": int(d.symbol.nunique()),
        "pullback_rows_usable": pullback_ok,
        "causality_fix": "Outcome-First pre_dd_from_high included the entry candle high. This extension does NOT reuse that measure. causal_dd_high_* is recomputed from candles fully closed by decision_time only.",
        "selection_policy": "Feature directions came from Outcome-First discovery/calibration. Thresholds and champion are selected only with frozen-candidate DISCOVERY + CALIBRATION. Cross-holdout and 2026 are diagnostics only and never select the rule.",
        "features_tested": {
            "bb_absolute": BB_FEATURES,
            "corrected_pullback": [f"causal_dd_high_{h}h" for h in PULLBACK_HOURS],
        },
        "baseline_by_split": base,
        "stable_single_count": int(singles.stable_train_cal.sum()) if len(singles) else 0,
        "stable_pair_count": int(pairs.stable_train_cal.sum()) if len(pairs) else 0,
        "champion_selected_without_holdouts": champion,
        "champion_diagnostics": champion_diag,
        "top_candidate_diagnostics": diagnostics,
    }
    (args.outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frozen TSI+BB Candidate — Outcome-First Extension",
        "",
        f"Baseline: {summary['baseline_rule']}",
        f"Events={summary['candidate_events']} | symbols={summary['symbols']} | pullback usable={pullback_ok}",
        "",
        "## Causality correction",
        summary["causality_fix"],
        "",
        "## Selection discipline",
        summary["selection_policy"],
        "",
        "## Baseline by split",
    ]
    for k, v in base.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Champion selected WITHOUT holdouts", str(champion), "", "## Champion diagnostics", str(champion_diag)]
    (args.outdir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
