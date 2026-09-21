from __future__ import annotations

import argparse
import importlib.util
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
MFD_PATH = HERE.parent / "movement_family_discovery" / "movement_family_discovery.py"
spec = importlib.util.spec_from_file_location("mfd", MFD_PATH)
mfd = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mfd)

START = mfd.START
END = mfd.END
FETCH_START = mfd.FETCH_START
PLANS = mfd.PLANS
COST = mfd.COST_PCT
COOLDOWN_HOURS = 12
FAMILIES = (
    "DEFENSIVE_LEADER_RELEASE",
    "MARKET_LAG_CATCHUP",
    "RELATIVE_COMPRESSION_RELEASE",
    "LEADER_PULLBACK_RESUME",
    "RELATIVE_WASHOUT_RECLAIM",
)

PATH_FEATURES = (
    "btc_ret_3h", "btc_ret_6h", "btc_prev_3h",
    "rel_ret_1h", "rel_ret_3h", "rel_ret_6h", "rel_ret_12h", "rel_ret_24h",
    "rel_prev_1h", "rel_prev_3h", "rel_accel_1h",
    "rel_dd_12h", "rel_dd_24h", "rel_range_pos_24h", "rel_vol_ratio",
)


def add_relative_features(z: pd.DataFrame, btc_base: pd.DataFrame) -> pd.DataFrame:
    """Causal closed-bar coin/BTC path features at each decision timestamp."""
    x = z.copy()
    btc = btc_base[["close"]].copy()
    btc.index = btc.index + pd.Timedelta(minutes=15)
    btc = btc[~btc.index.duplicated(keep="last")]
    btc_close = btc.close.reindex(x.index, method="ffill")
    ratio = x.close / btc_close.replace(0, np.nan)

    x["btc_close_ref"] = btc_close
    x["rel_ratio"] = ratio
    for name, bars in (("1h", 4), ("3h", 12), ("6h", 24), ("12h", 48), ("24h", 96)):
        x[f"coin_ret_{name}"] = x.close.pct_change(bars) * 100
        x[f"btc_ret_{name}"] = btc_close.pct_change(bars) * 100
        x[f"rel_ret_{name}"] = ratio.pct_change(bars) * 100

    # Prior path segments end one hour before the decision, so catch-up rules
    # cannot accidentally reuse the activation leg as their lag definition.
    x["btc_prev_3h"] = btc_close.shift(4).pct_change(12) * 100
    x["rel_prev_1h"] = ratio.shift(4).pct_change(4) * 100
    x["rel_prev_3h"] = ratio.shift(4).pct_change(12) * 100
    x["rel_accel_1h"] = x.rel_ret_1h - x.rel_prev_1h

    for bars, label in ((32, "8h"), (48, "12h"), (96, "24h")):
        x[f"rel_prev_high_{label}"] = ratio.shift(1).rolling(bars).max()
        x[f"rel_prev_low_{label}"] = ratio.shift(1).rolling(bars).min()
    x["rel_dd_12h"] = (ratio / x.rel_prev_high_12h - 1) * 100
    x["rel_dd_24h"] = (ratio / x.rel_prev_high_24h - 1) * 100
    den = (x.rel_prev_high_24h - x.rel_prev_low_24h).replace(0, np.nan)
    x["rel_range_pos_24h"] = (ratio - x.rel_prev_low_24h) / den

    idio = x.close.pct_change() - btc_close.pct_change()
    rel_vol_2h = idio.rolling(8).std(ddof=0)
    rel_vol_base = idio.shift(8).rolling(7 * 24 * 4).std(ddof=0)
    x["rel_vol_ratio"] = rel_vol_2h / rel_vol_base.replace(0, np.nan)
    x["rel_break_8h"] = ratio > x.rel_prev_high_8h
    x["rel_break_12h"] = ratio > x.rel_prev_high_12h

    x["m15_mom_turn_score"] = (
        (x.macd_hist_d1 > 0).astype(int)
        + (x.rsi_d1 > 0).astype(int)
        + (x.stoch_spread_d1 > 0).astype(int)
        + (x.di_spread_d1 > 0).astype(int)
        + (x.obv_d1 > 0).astype(int)
    )
    return x


def candidate_rules() -> list[dict]:
    rules: list[dict] = []
    rid = 0
    for btc_max in (-0.5, -1.5):
        for rel_min in (1.0, 2.0, 3.0):
            for mom in (2, 3):
                rid += 1
                rules.append({"id": f"DLR_{rid:03d}", "family": FAMILIES[0],
                              "btc_max": btc_max, "rel_min": rel_min, "mom": mom})
    for btc_min in (1.0, 2.0):
        for lag_max in (-0.5, -1.5, -2.5):
            for flip_min in (0.25, 0.75):
                rid += 1
                rules.append({"id": f"MLC_{rid:03d}", "family": FAMILIES[1],
                              "btc_min": btc_min, "lag_max": lag_max, "flip_min": flip_min})
    for squeeze in (0.55, 0.75, 0.95):
        for window in (8, 12):
            for rvol in (0.8, 1.2):
                rid += 1
                rules.append({"id": f"RCR_{rid:03d}", "family": FAMILIES[2],
                              "squeeze": squeeze, "window": window, "rvol": rvol})
    for rel_trend in (2.0, 4.0, 6.0):
        for pullback in (-0.5, -1.5):
            for btc_floor in (-2.0, -4.0):
                rid += 1
                rules.append({"id": f"LPR_{rid:03d}", "family": FAMILIES[3],
                              "rel_trend": rel_trend, "pullback": pullback, "btc_floor": btc_floor})
    for rel_dd in (-3.0, -5.0, -8.0):
        for btc_floor in (-2.0, -4.0):
            for mom in (2, 3):
                rid += 1
                rules.append({"id": f"RWR_{rid:03d}", "family": FAMILIES[4],
                              "rel_dd": rel_dd, "btc_floor": btc_floor, "mom": mom})
    return rules


def rule_mask(z: pd.DataFrame, r: dict) -> pd.Series:
    fam = r["family"]
    local_break = (z.close > z.prev_high_8) & (z.close_loc >= 0.55)
    if fam == FAMILIES[0]:
        return (
            (z.btc_ret_6h <= r["btc_max"])
            & (z.rel_ret_6h >= r["rel_min"])
            & (z.rel_ret_1h > 0.25)
            & local_break
            & (z.m15_mom_turn_score >= r["mom"])
        ).fillna(False)
    if fam == FAMILIES[1]:
        return (
            (z.btc_prev_3h >= r["btc_min"])
            & (z.rel_prev_3h <= r["lag_max"])
            & (z.rel_ret_1h >= r["flip_min"])
            & (z.rel_accel_1h > 0)
            & local_break
            & (z.m15_mom_turn_score >= 3)
        ).fillna(False)
    if fam == FAMILIES[2]:
        rel_break = z.rel_break_8h if r["window"] == 8 else z.rel_break_12h
        return (
            (z.rel_vol_ratio.shift(1) <= r["squeeze"])
            & rel_break
            & local_break
            & (z.rvol20 >= r["rvol"])
            & (z.btc_ret_3h > -3.0)
        ).fillna(False)
    if fam == FAMILIES[3]:
        return (
            (z.rel_ret_12h >= r["rel_trend"])
            & (z.rel_ret_3h <= r["pullback"])
            & (z.rel_ret_3h >= -5.0)
            & (z.rel_range_pos_24h >= 0.45)
            & (z.rel_ret_1h > 0.20)
            & (z.btc_ret_6h >= r["btc_floor"])
            & local_break
        ).fillna(False)
    if fam == FAMILIES[4]:
        return (
            (z.rel_dd_24h <= r["rel_dd"])
            & (z.rel_ratio > z.rel_prev_high_8h)
            & (z.rel_ret_1h > 0.25)
            & (z.btc_ret_6h >= r["btc_floor"])
            & local_break
            & (z.m15_mom_turn_score >= r["mom"])
        ).fillna(False)
    raise KeyError(fam)


def process_symbol(symbol: str, btc_base: pd.DataFrame, fetch_start: pd.Timestamp,
                   study_start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, dict | None]:
    try:
        base = mfd.core.fetch_15m(symbol, start=fetch_start, end=end + pd.Timedelta(days=2))
        if len(base) < 2000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"too_short:{len(base)}"}
        z = add_relative_features(mfd.build_symbol_frame(base, study_start, end), btc_base)
        if len(z) < 1000:
            return pd.DataFrame(), {"symbol": symbol, "error": f"study_too_short:{len(z)}"}
        matches: dict[pd.Timestamp, list[str]] = defaultdict(list)
        for r in candidate_rules():
            mask = mfd.compress(rule_mask(z, r), z.index, COOLDOWN_HOURS)
            for t in z.index[mask.to_numpy(bool)]:
                matches[t].append(r["id"])
        rows = []
        for t in sorted(matches):
            oc = mfd.outcome(base, t)
            if oc is None:
                continue
            row = {"symbol": symbol, "hash_mod": mfd.hmod(symbol), "decision_time": t,
                   "rules": ";".join(matches[t]), **oc}
            for col in PATH_FEATURES:
                val = z.at[t, col]
                row[col] = float(val) if pd.notna(val) else np.nan
            rows.append(row)
        return pd.DataFrame(rows), None
    except Exception as ex:
        return pd.DataFrame(), {"symbol": symbol, "error": f"{type(ex).__name__}:{ex}"}


def shard_main(shard: int, shards: int, outdir: Path, symbols_arg: str | None,
               fetch_start: pd.Timestamp, study_start: pd.Timestamp, end: pd.Timestamp) -> None:
    symbols = mfd.load_symbols()
    if symbols_arg:
        wanted = {x.strip().upper() for x in symbols_arg.split(",") if x.strip()}
        symbols = [s for s in symbols if s in wanted]
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    btc_base = mfd.core.fetch_15m("BTCUSDT", start=fetch_start, end=end + pd.Timedelta(days=2))
    if len(btc_base) < 2000:
        raise RuntimeError(f"BTC reference too short: {len(btc_base)}")
    frames, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(process_symbol, s, btc_base, fetch_start, study_start, end): s for s in mine}
        for k, future in enumerate(as_completed(futs), 1):
            frame, error = future.result()
            if error:
                errors.append(error)
                print("[SYMBOL_ERROR] " + json.dumps(error, ensure_ascii=False), flush=True)
            if frame is not None and len(frame):
                frames.append(frame)
            if k % 3 == 0 or k == len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errors)}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {"shard": shard, "shards": shards, "symbols": len(mine), "events": int(len(out)),
            "errors": len(errors), "btc_rows": int(len(btc_base))}
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if symbols_arg and mine and out.empty:
        raise RuntimeError(f"smoke produced zero relative-path events for {mine}")
    print(json.dumps(meta), flush=True)


def split_masks(d: pd.DataFrame) -> dict[str, pd.Series]:
    return mfd.split_masks(d)


def evaluate_frame(d: pd.DataFrame) -> dict:
    masks = split_masks(d)
    return {
        name: {
            "metrics": mfd.metrics(d[mask]),
            "frequency": mfd.frequency(d[mask], mfd.period_days(name)),
            "distribution": distribution(d[mask]),
        }
        for name, mask in masks.items()
    }


def distribution(d: pd.DataFrame) -> dict:
    if d.empty:
        return {"year": {}, "top_symbols": [], "max_symbol_share_pct": 0.0, "top10_share_pct": 0.0}
    z = d.copy()
    z["year"] = z.decision_time.dt.year
    years = {}
    for year, q in z.groupby("year"):
        years[str(int(year))] = {"n": int(len(q)), "symbols": int(q.symbol.nunique()),
                                 "mean24": float(pd.to_numeric(q.net24, errors="coerce").mean())}
    counts = z.symbol.value_counts()
    return {
        "year": years,
        "top_symbols": [{"symbol": str(s), "n": int(n)} for s, n in counts.head(10).items()],
        "max_symbol_share_pct": float(counts.iloc[0] / len(z) * 100),
        "top10_share_pct": float(counts.head(10).sum() / len(z) * 100),
    }


def plan_score(rec: dict, plan: str) -> float | None:
    discovery = rec["DISCOVERY"]
    calibration = rec["CALIBRATION"]
    if min(discovery["metrics"].get("n", 0), calibration["metrics"].get("n", 0)) < 80:
        return None
    dm = discovery["metrics"].get(plan, {})
    cm = calibration["metrics"].get(plan, {})
    if min(dm.get("mean", -999), cm.get("mean", -999)) <= 0:
        return None
    if min(dm.get("pf", 0) or 0, cm.get("pf", 0) or 0) <= 1:
        return None
    if min(dm.get("target_first", 0), cm.get("target_first", 0)) < 45:
        return None
    freq = min(discovery["frequency"].get("signals_per_day", 0),
               calibration["frequency"].get("signals_per_day", 0))
    if freq < 0.08:
        return None
    return (min(dm["mean"], cm["mean"])
            + 0.02 * min(dm["target_first"], cm["target_first"])
            + 0.20 * min(freq, 1.5))


def feature_effects(d: pd.DataFrame) -> dict:
    """Outcome-first audit; never used to select thresholds on holdouts."""
    out = {}
    masks = split_masks(d)
    for split, mask in masks.items():
        q = d[mask]
        win = pd.to_numeric(q.win_TP3_SL2, errors="coerce") == 1
        stop = pd.to_numeric(q.loss_TP3_SL2, errors="coerce") == 1
        rows = []
        for col in PATH_FEATURES:
            a = pd.to_numeric(q.loc[win, col], errors="coerce").dropna()
            b = pd.to_numeric(q.loc[stop, col], errors="coerce").dropna()
            if min(len(a), len(b)) < 20:
                continue
            pooled = pd.concat([a, b])
            scale = float((pooled - pooled.median()).abs().median())
            effect = float((a.median() - b.median()) / scale) if scale > 0 else 0.0
            rows.append({"feature": col, "target_n": int(len(a)), "stop_n": int(len(b)),
                         "target_median": float(a.median()), "stop_median": float(b.median()),
                         "robust_effect": effect})
        rows.sort(key=lambda x: abs(x["robust_effect"]), reverse=True)
        out[split] = rows
    return out


def benign_errors(indir: Path) -> tuple[list[dict], list[dict]]:
    benign, hard = [], []
    for path in indir.rglob("errors.csv"):
        try:
            errors = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            continue
        for _, row in errors.iterrows():
            rec = {"symbol": str(row.get("symbol", "")), "error": str(row.get("error", ""))}
            (benign if rec["error"].startswith(("too_short:", "study_too_short:")) else hard).append(rec)
    return benign, hard


def load_r2_reference(dataset_dir: Path) -> pd.DataFrame:
    events_path = dataset_dir / "r2_events.csv"
    paths_path = dataset_dir / "r2_paths.csv"
    if not events_path.exists() or not paths_path.exists():
        raise RuntimeError("missing exact frozen r2 dataset")
    events = pd.read_csv(events_path, low_memory=False)
    paths = pd.read_csv(paths_path, low_memory=False)
    if len(events) != 225 or events.event_id.nunique() != 225:
        raise RuntimeError(f"unexpected frozen r2 cohort: {len(events)}")
    if paths.event_id.nunique() != 225 or paths.groupby("event_id").size().min() < 97:
        raise RuntimeError("incomplete frozen r2 price paths")
    rows = []
    by_event = {int(k): q.sort_values("bar_i") for k, q in paths.groupby("event_id", sort=False)}
    for _, event in events.iterrows():
        q = by_event[int(event.event_id)].iloc[:97]
        entry = float(q.open.iloc[0])
        rec = {
            "symbol": str(event.symbol),
            "hash_mod": int(event.hash_mod),
            "decision_time": pd.Timestamp(event.decision_time),
            "entry_time": pd.Timestamp(event.entry_time),
            "entry_open": entry,
            "rules": "FROZEN_R2",
            "source": "FROZEN_R2",
            "net24": float(event.net_24h),
            "mfe24": float(event.mfe_24h),
            "mae24": float(event.mae_24h),
        }
        for name, (tp, stop) in PLANS.items():
            val, win, loss = mfd.first_touch_plan(q, entry, tp, stop)
            if not np.isfinite(val):
                val = rec["net24"]
            rec[f"ret_{name}"] = float(val)
            rec[f"win_{name}"] = int(win)
            rec[f"loss_{name}"] = int(loss)
        rows.append(rec)
    out = pd.DataFrame(rows)
    out.decision_time = pd.to_datetime(out.decision_time, utc=True)
    out.entry_time = pd.to_datetime(out.entry_time, utc=True)
    return out


def incremental_or_with_r2(new_events: pd.DataFrame, r2: pd.DataFrame,
                           hours: int = COOLDOWN_HOURS) -> tuple[pd.DataFrame, dict]:
    new_events = mfd.dedupe_combined(new_events, hours) if len(new_events) else new_events.copy()
    overlap = np.zeros(len(new_events), dtype=bool)
    r2_times = {
        s: q.decision_time.sort_values().astype("int64").to_numpy()
        for s, q in r2.groupby("symbol")
    }
    delta_ns = int(pd.Timedelta(hours=hours).value)
    for i, row in enumerate(new_events.itertuples(index=False)):
        times = r2_times.get(row.symbol)
        if times is not None and len(times):
            t_ns = int(pd.Timestamp(row.decision_time).value)
            overlap[i] = bool(np.any(np.abs(times - t_ns) <= delta_ns))
    incremental = new_events.iloc[np.flatnonzero(~overlap)].copy()
    incremental["source"] = "RELATIVE_FAMILY"
    union = pd.concat([r2, incremental], ignore_index=True, sort=False)
    union = union.sort_values(["decision_time", "symbol"]).reset_index(drop=True)
    audit = {"new_selected": int(len(new_events)), "overlap_with_r2_12h": int(overlap.sum()),
             "incremental_new": int(len(incremental)), "frozen_r2_preserved": int(len(r2)),
             "union": int(len(union))}
    return union, audit


def aggregate_main(indir: Path, outdir: Path, r2_dataset: Path) -> None:
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in indir.rglob("meta.json")]
    if len(metas) != 64 or {int(x["shard"]) for x in metas} != set(range(64)):
        raise RuntimeError("incomplete shard set")
    if sum(int(x["symbols"]) for x in metas) < 400:
        raise RuntimeError("small universe")
    if min(int(x["btc_rows"]) for x in metas) < 100000:
        raise RuntimeError("short BTC reference")
    benign, hard = benign_errors(indir)
    if hard:
        raise RuntimeError(f"hard symbol errors: {hard[:10]}")
    frames = []
    for path in indir.rglob("events.csv"):
        try:
            q = pd.read_csv(path, low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if len(q):
            frames.append(q)
    if not frames:
        raise RuntimeError("no relative-path events")
    d = pd.concat(frames, ignore_index=True)
    d.decision_time = pd.to_datetime(d.decision_time, utc=True)
    d.entry_time = pd.to_datetime(d.entry_time, utc=True)
    d = d.drop_duplicates(["symbol", "decision_time"]).sort_values(["decision_time", "symbol"]).reset_index(drop=True)
    if d.symbol.nunique() < 350 or len(d) < 1000:
        raise RuntimeError(f"unexpected coverage rows={len(d)} symbols={d.symbol.nunique()}")

    defs = {r["id"]: r for r in candidate_rules()}
    long = d.assign(rule_id=d.rules.str.split(";")).explode("rule_id", ignore_index=True)
    evals, champions, table = [], {}, []
    for rid, rule in defs.items():
        q = long[long.rule_id == rid].copy()
        rec = evaluate_frame(q)
        evals.append({"rule": rule, "splits": rec})
        for plan in PLANS:
            row = {"rule_id": rid, "family": rule["family"], "plan": plan}
            for split in ("DISCOVERY", "CALIBRATION", "CROSS_HOLDOUT_PRE2026", "FINAL_HOLDOUT_2026", "ALL_2026"):
                m = rec[split]["metrics"].get(plan, {})
                f = rec[split]["frequency"]
                row.update({f"{split}_n": rec[split]["metrics"].get("n", 0),
                            f"{split}_mean": m.get("mean"), f"{split}_pf": m.get("pf"),
                            f"{split}_target_first": m.get("target_first"),
                            f"{split}_stop_first": m.get("stop_first"),
                            f"{split}_signals_per_day": f.get("signals_per_day", 0)})
            table.append(row)

    for family in FAMILIES:
        candidates = []
        for item in evals:
            if item["rule"]["family"] != family:
                continue
            for plan in PLANS:
                score = plan_score(item["splits"], plan)
                if score is not None:
                    candidates.append((score, plan, item))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            score, plan, item = candidates[0]
            champions[family] = {"score": float(score), "plan": plan,
                                 "rule": item["rule"], **item["splits"]}

    champion_ids = {v["rule"]["id"] for v in champions.values()}
    selected = d[d.rules.apply(lambda s: any(x in champion_ids for x in str(s).split(";")))].copy()
    selected = mfd.dedupe_combined(selected, COOLDOWN_HOURS) if len(selected) else selected
    combined = evaluate_frame(selected) if len(selected) else {}

    r2 = load_r2_reference(r2_dataset)
    union, overlap_audit = incremental_or_with_r2(selected, r2)
    or_metrics = evaluate_frame(union)

    all_2026 = combined.get("ALL_2026", {})
    final_oos = combined.get("FINAL_HOLDOUT_2026", {})
    status = "NO_STABLE_RELATIVE_PATH_FAMILY"
    if champions:
        status = "DEV_STABLE_RELATIVE_FAMILIES_HOLDOUT_EVALUATED"
        freq = all_2026.get("frequency", {}).get("signals_per_day", 0)
        active = all_2026.get("frequency", {}).get("active_day_share_pct", 0)
        positive = []
        for plan in PLANS:
            q = final_oos.get("metrics", {}).get(plan, {})
            positive.append(q.get("mean", -999) > 0 and (q.get("pf", 0) or 0) > 1 and q.get("target_first", 0) >= 45)
        if any(positive):
            status = "OOS_POSITIVE_RELATIVE_FAMILY_SET"
        if freq >= 2 and active >= 60 and any(positive):
            status = "OOS_QUALIFIED_2PLUS_PER_DAY_RELATIVE_FAMILY_SET"

    summary = {
        "status": status,
        "purpose": "Independent coin/BTC relative-price path mechanisms; frozen r2 is preserved and evaluated only as an OR baseline.",
        "causality": {"closed_15m_1h_4h_only": True, "entry": "next 15m open",
                      "round_trip_cost_pct": COST, "same_bar_ambiguity": "pessimistic stop first",
                      "selection": "Discovery+Calibration only; both holdouts are diagnostics"},
        "candidate_rules": len(defs), "events": int(len(d)), "symbols": int(d.symbol.nunique()),
        "families": list(FAMILIES), "benign_short_history_exclusions": benign,
        "champions": champions, "combined_relative_families": combined,
        "frozen_r2_reference": {"events": int(len(r2)), "symbols": int(r2.symbol.nunique()),
                                "immutable": True, "source": "r2-round2-dataset artifact"},
        "or_with_frozen_r2": {"overlap_audit": overlap_audit, "splits": or_metrics},
        "outcome_first_relative_feature_effects": feature_effects(d),
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    pd.DataFrame(table).to_csv(outdir / "candidate_plan_table.csv", index=False)
    print(json.dumps({"status": status, "events": len(d), "symbols": d.symbol.nunique(),
                      "champions": list(champions), "or_audit": overlap_audit}, ensure_ascii=False), flush=True)


def self_test() -> None:
    assert len(candidate_rules()) == 60, len(candidate_rules())
    idx = pd.date_range("2026-01-01", periods=800, freq="15min", tz="UTC")
    base = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                         "volume": 1000.0, "quote_volume": 100000.0}, index=idx)
    z = mfd.build_symbol_frame(base, idx[200], idx[-1])
    out = add_relative_features(z, base)
    required = set(PATH_FEATURES) | {"rel_ratio", "rel_break_8h", "m15_mom_turn_score"}
    assert not (required - set(out.columns)), required - set(out.columns)
    assert out.btc_close_ref.notna().all()
    print(json.dumps({"self_test": "ok", "rules": len(candidate_rules()), "features": len(PATH_FEATURES)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int)
    ap.add_argument("--shards", type=int, default=64)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--aggregate-dir", type=Path)
    ap.add_argument("--r2-dataset", type=Path)
    ap.add_argument("--symbols")
    ap.add_argument("--fetch-start")
    ap.add_argument("--study-start")
    ap.add_argument("--end")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if args.aggregate_dir:
        if args.r2_dataset is None:
            raise SystemExit("--r2-dataset required for aggregate")
        aggregate_main(args.aggregate_dir, args.outdir, args.r2_dataset)
        return
    if args.shard is None:
        raise SystemExit("--shard required")
    fetch_start = pd.Timestamp(args.fetch_start, tz="UTC") if args.fetch_start else FETCH_START
    study_start = pd.Timestamp(args.study_start, tz="UTC") if args.study_start else START
    end = pd.Timestamp(args.end, tz="UTC") if args.end else END
    shard_main(args.shard, args.shards, args.outdir, args.symbols, fetch_start, study_start, end)


if __name__ == "__main__":
    main()
