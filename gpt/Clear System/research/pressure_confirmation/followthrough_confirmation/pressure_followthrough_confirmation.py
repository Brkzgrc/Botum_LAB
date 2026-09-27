"""Preregistered PRESSURE early closed-candle follow-through confirmation.

Two independent 2023 Discovery months are replayed with the archived scanner.
Only the three gates locked in preregistration.json are evaluated.  This file
must not tune periods, horizons or thresholds from the resulting outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
DISCOVERY = PARENT / "discovery_month"
SOURCE = PARENT.parents[1] / "sources" / "botum_2026-09-26"
sys.path[:0] = [str(PARENT), str(DISCOVERY), str(SOURCE)]

import pressure_discovery_month as dm  # type: ignore
import pressure_fullmarket_benchmark as engine  # type: ignore
import pressure_path_exit as path_exit  # type: ignore

PREREG_PATH = HERE / "preregistration.json"
FETCH_HISTORY_START = pd.Timestamp("2023-01-20T00:00:00Z")
FETCH_END = pd.Timestamp("2023-12-01T00:00:00Z")
FUTURE_HOURS = 72
FEE_PCT = 0.20
PERIODS = {
    "D1": (pd.Timestamp("2023-05-01T00:00:00Z"), pd.Timestamp("2023-06-01T00:00:00Z")),
    "D2": (pd.Timestamp("2023-11-01T00:00:00Z"), pd.Timestamp("2023-12-01T00:00:00Z")),
}
GATES = ("G30_CLOSE", "G60_PRICE_VOLUME", "G60_MOTION_FLOW")
POLICIES = ("baseline_fixed_gross_0.50",) + GATES


def preregistration() -> dict:
    x = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert x["status"] == "PREREGISTERED_NOT_RUN"
    assert [p["id"] for p in x["locked_periods"]] == list(PERIODS)
    assert [g["id"] for g in x["locked_gates"]] == list(GATES)
    assert x["universe"]["round_trip_cost_pct"] == FEE_PCT
    assert x["action_budget"]["hard_runner_minute_ceiling"] == 80
    return x


def configure(start: pd.Timestamp, end: pd.Timestamp, history: pd.Timestamp = FETCH_HISTORY_START) -> None:
    engine.HISTORY_START = history
    engine.REPLAY_START = start
    engine.REPLAY_END = end
    engine.DATA_FUTURE_HOURS = FUTURE_HOURS
    engine.SHARDS = dm.SHARDS
    engine.EXPECTED_SYMBOLS = tuple(s for values in dm.SHARDS.values() for s in values)


def configure_fetch() -> None:
    configure(PERIODS["D1"][0], FETCH_END)


def load_15m(files: dict[str, Path]) -> dict[str, pd.DataFrame]:
    return dm.load_15m(files)


def event_key(e: dict) -> tuple:
    return dm.event_key(e)


def early_path(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float,
               stop: float, minutes: int) -> dict:
    """Resolve stop/target before gate; otherwise return causal gate-close state."""
    end = entry_time + pd.Timedelta(minutes=minutes)
    bars = bars5[(bars5.open_time >= entry_time) & (bars5.close_time <= end)]
    if bars.empty or pd.Timestamp(bars.close_time.iloc[-1]) < end - pd.Timedelta(seconds=1):
        raise RuntimeError(f"GATE_PATH_INCOMPLETE:{entry_time}:{minutes}")
    target = entry * 1.005
    for row in bars.itertuples(index=False):
        hit_stop, hit_target = float(row.low) <= stop, float(row.high) >= target
        if hit_stop:
            gross = (stop / entry - 1) * 100
            return {"resolved": path_exit.result("STOP_AMBIGUOUS" if hit_target else "STOP_FIRST",
                                                   gross, row.close_time, hit_target)}
        if hit_target:
            return {"resolved": path_exit.result("TARGET_FIRST", .50, row.close_time)}
    last = bars.iloc[-1]
    return {
        "resolved": None,
        "close_time": str(last.close_time),
        "close_return_pct": (float(last.close) / entry - 1) * 100,
        "mfe_pct": (float(bars.high.max()) / entry - 1) * 100,
        "gate_close": float(last.close),
    }


def flow_features(raw15: pd.DataFrame, entry_time: pd.Timestamp, minutes: int = 60) -> dict:
    end = entry_time + pd.Timedelta(minutes=minutes)
    post = raw15[(raw15.open_time >= entry_time) & (raw15.close_time <= end)]
    pre = raw15[(raw15.close_time <= entry_time) &
                (raw15.close_time > entry_time - pd.Timedelta(minutes=minutes))]
    if len(post) != minutes // 15 or len(pre) != minutes // 15:
        raise RuntimeError(f"GATE_15M_CONTEXT_INCOMPLETE:{entry_time}:{len(pre)}:{len(post)}")
    post_qv, pre_qv = float(post.quote_volume.sum()), float(pre.quote_volume.sum())
    taker = float(post.taker_quote.sum()) / post_qv if post_qv > 0 else math.nan
    if not math.isfinite(taker):
        raise RuntimeError("INVALID_TAKER_SHARE")
    return {"post_quote_volume": post_qv, "pre_quote_volume": pre_qv,
            "volume_ratio": post_qv / pre_qv if pre_qv > 0 else math.inf,
            "taker_buy_share": taker}


def gated_result(gate: str, event: dict, bars5: pd.DataFrame,
                 raw15: pd.DataFrame, baseline: dict) -> tuple[dict, dict]:
    t, entry, stop = (pd.Timestamp(event["decision_time"]), float(event["entry"]),
                      float(event["stop"]))
    minutes = 30 if gate == "G30_CLOSE" else 60
    early = early_path(bars5, t, entry, stop, minutes)
    features = {"gate_minutes": minutes}
    if early["resolved"] is not None:
        features["decision"] = "RESOLVED_BEFORE_GATE"
        return early["resolved"], features
    features.update({k: round(float(v), 6) if isinstance(v, (int, float)) else v
                     for k, v in early.items() if k != "resolved"})
    if gate == "G30_CLOSE":
        passed = early["close_return_pct"] > 0
    else:
        flow = flow_features(raw15, t)
        features.update({k: round(float(v), 6) for k, v in flow.items()})
        if gate == "G60_PRICE_VOLUME":
            passed = early["close_return_pct"] > 0 and flow["volume_ratio"] >= 1.0
        elif gate == "G60_MOTION_FLOW":
            passed = (early["mfe_pct"] >= .25 and early["close_return_pct"] >= -.25
                      and flow["taker_buy_share"] >= .50)
        else:
            raise ValueError(gate)
    features["decision"] = "PASS" if passed else "FAIL_EXIT"
    if passed:
        return dict(baseline), features
    return path_exit.result("GATE_FAIL_EXIT", early["close_return_pct"], early["close_time"]), features


def evaluate_event(event: dict, bars5: pd.DataFrame, raw15: pd.DataFrame) -> dict:
    t, entry, stop = (pd.Timestamp(event["decision_time"]), float(event["entry"]),
                      float(event["stop"]))
    future24 = path_exit.future_bars(bars5, t, 24)
    baseline = dm.fixed_target(bars5, t, entry, stop)
    policies = {"baseline_fixed_gross_0.50": baseline}
    features = {}
    for gate in GATES:
        policies[gate], features[gate] = gated_result(gate, event, bars5, raw15, baseline)
    return {
        "mfe_pct": round((float(future24.high.max()) / entry - 1) * 100, 6),
        "mae_pct": round((float(future24.low.min()) / entry - 1) * 100, 6),
        "policies": policies,
        "gate_features": features,
    }


def metrics(records: list[dict], policy: str) -> dict:
    rows = [r["result"]["policies"][policy] for r in records]
    nets = [float(x["net_pct"]) for x in rows]
    outcomes = Counter(x["outcome"] for x in rows)
    gains, losses = sum(x for x in nets if x > 0), -sum(x for x in nets if x < 0)
    baseline_targets = sum(r["result"]["policies"]["baseline_fixed_gross_0.50"]["outcome"] == "TARGET_FIRST"
                           for r in records)
    targets = outcomes.get("TARGET_FIRST", 0)
    return {
        "events": len(rows), "positive": sum(x > 0 for x in nets),
        "negative": sum(x < 0 for x in nets), "flat": sum(x == 0 for x in nets),
        "net_total_pct": round(sum(nets), 6),
        "expectancy_pct": round(sum(nets) / len(nets), 6) if nets else None,
        "profit_factor": round(gains / losses, 6) if losses else None,
        "target_first": targets,
        "stop_first": sum(v for k, v in outcomes.items() if k.startswith("STOP")),
        "worst_trade_pct": round(min(nets), 6) if nets else None,
        "preserved_target_ratio_pct": round(targets / baseline_targets * 100, 6) if baseline_targets else None,
        "outcomes": dict(sorted(outcomes.items())),
    }


def period_replay(period: str, input_root: Path, outdir: Path,
                  raw15: dict[str, pd.DataFrame]) -> dict:
    start, end = PERIODS[period]
    configure(start, end)
    base = engine.replay_central(input_root, outdir / "candidate")
    unique = {}
    for h in ("0", "24", "48"):
        for event in base["comparison"][h]["events"]:
            unique[event_key(event)] = event
    if not unique:
        raise RuntimeError(f"NO_SELECTED_EVENTS:{period}")
    events = list(unique.values())
    paths5, path_data = dm.fetch_selected_paths(events)
    evaluated = {event_key(e): evaluate_event(e, paths5[e["symbol"]], raw15[e["symbol"]])
                 for e in events}
    cooldowns = {}
    days = (end - start).total_seconds() / 86400
    for h in ("0", "24", "48"):
        selected = base["comparison"][h]["events"]
        records = [{"period": period, "event": e, "result": evaluated[event_key(e)]}
                   for e in selected]
        active = len({e["decision_time"][:10] for e in selected})
        cooldowns[h] = {
            "signals": len(records), "signals_per_day": round(len(records) / days, 6),
            "active_days": active, "active_day_ratio_pct": round(active / days * 100, 6),
            "mfe_mean_pct": round(sum(r["result"]["mfe_pct"] for r in records) / len(records), 6),
            "mae_mean_pct": round(sum(r["result"]["mae_pct"] for r in records) / len(records), 6),
            "policies": {p: metrics(records, p) for p in POLICIES}, "records": records,
        }
    return {"period": period, "window": [str(start), str(end)], "candidate_replay": base,
            "selected_path_data": path_data, "cooldowns": cooldowns}


def pooled(periods: dict, cooldown: str, policy: str) -> tuple[dict, list[dict]]:
    records = []
    for period in PERIODS:
        records.extend(periods[period]["cooldowns"][cooldown]["records"])
    m = metrics(records, policy)
    positive_contribution = defaultdict(float)
    for r in records:
        net = float(r["result"]["policies"][policy]["net_pct"])
        if net > 0:
            e = r["event"]
            positive_contribution[("period", r["period"])] += net
            positive_contribution[("symbol", e["symbol"])] += net
            positive_contribution[("setup_kind", e["setup_kind"])] += net
    total = sum(v for (kind, _), v in positive_contribution.items() if kind == "period")
    m["max_positive_concentration_pct"] = round(max(positive_contribution.values(), default=0) / total * 100, 6) if total else None
    return m, records


def decide(periods: dict) -> dict:
    decisions = {}
    for cooldown in ("0", "24", "48"):
        base_pool, _ = pooled(periods, cooldown, "baseline_fixed_gross_0.50")
        for gate in GATES:
            pool, _ = pooled(periods, cooldown, gate)
            each = []
            for pid in PERIODS:
                z = periods[pid]["cooldowns"][cooldown]["policies"]
                each.append(z[gate]["events"] >= 5 and
                            z[gate]["net_total_pct"] > z["baseline_fixed_gross_0.50"]["net_total_pct"] and
                            z[gate]["expectancy_pct"] > z["baseline_fixed_gross_0.50"]["expectancy_pct"])
            base_worst = abs(min(0.0, float(base_pool["worst_trade_pct"])))
            gate_worst = abs(min(0.0, float(pool["worst_trade_pct"])))
            tail_improvement = (1 - gate_worst / base_worst) * 100 if base_worst else 0.0
            profitable_pf = ((pool["profit_factor"] or 0) > 1 or
                             (pool["profit_factor"] is None and pool["positive"] > 0 and
                              pool["negative"] == 0))
            passed = (all(each) and pool["expectancy_pct"] > 0 and
                      profitable_pf and tail_improvement >= 40 and
                      (pool["preserved_target_ratio_pct"] or 0) >= 70 and
                      (pool["max_positive_concentration_pct"] or 100) <= 60)
            decisions[f"{cooldown}h:{gate}"] = {
                "passed": passed, "period_improvements": each,
                "worst_loss_improvement_pct": round(tail_improvement, 6),
                "pooled_metrics": pool,
            }
    passing = sorted(k for k, v in decisions.items() if v["passed"])
    return {"tests": decisions, "passing": passing,
            "decision": ("FREEZE_SIMPLEST_PASSING_GATE_FOR_2024_CALIBRATION" if passing
                         else "REJECT_PREREGISTERED_FOLLOWTHROUGH_GATES")}


def run(input_root: Path, outdir: Path) -> dict:
    started = time.perf_counter()
    prereg = preregistration()
    configure_fetch()
    manifests, files = engine.validate_manifest_root(input_root)
    raw15 = load_15m(files)
    period_results = {pid: period_replay(pid, input_root, outdir / pid, raw15) for pid in PERIODS}
    result = {
        "status": "PRESSURE_FOLLOWTHROUGH_CONFIRMATION_COMPLETE",
        "preregistration_status": prereg["status"],
        "periods": period_results,
        "decision_gate": decide(period_results),
        "round_trip_cost_pct": FEE_PCT,
        "expected_shards": sorted(dm.SHARDS), "completed_shards": sorted(manifests),
        "universe_contract": "Binance Spot USDT long; stable/fiat/leveraged bases excluded",
        "causality_contract": "scanner close_time < decision_time; gate uses only bars closed by gate time",
        "oos": "N/A: two independent 2023 Discovery replications; 2024+ unopened",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def self_test() -> None:
    x = preregistration()
    configure_fetch()
    assert len(engine.EXPECTED_SYMBOLS) == len(set(engine.EXPECTED_SYMBOLS)) == 24
    assert all(engine.allowed_symbol(s) for s in engine.EXPECTED_SYMBOLS)
    assert list(PERIODS) == ["D1", "D2"] and list(GATES) == [g["id"] for g in x["locked_gates"]]
    t = pd.Timestamp("2023-05-01T00:00:00Z")
    times = pd.date_range(t, periods=36, freq="5min")
    bars = pd.DataFrame({"open_time": times, "close_time": times + pd.Timedelta(minutes=5),
                         "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0,
                         "quote_volume": 1000.0, "taker_quote": 510.0})
    raw_times = pd.date_range(t - pd.Timedelta(hours=2), periods=16, freq="15min")
    raw = pd.DataFrame({"open_time": raw_times,
                        "close_time": raw_times + pd.Timedelta(minutes=15),
                        "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0,
                        "volume": 10.0, "quote_volume": 1000.0, "taker_quote": 510.0})
    baseline = path_exit.result("EXPIRED", -1.0, t + pd.Timedelta(hours=24))
    r, feat = gated_result("G30_CLOSE", {"decision_time": str(t), "entry": 100, "stop": 95}, bars, raw, baseline)
    assert r["outcome"] == "GATE_FAIL_EXIT" and r["net_pct"] == -.2 and feat["decision"] == "FAIL_EXIT"
    bars.loc[:5, "close"] = 100.2
    r, feat = gated_result("G30_CLOSE", {"decision_time": str(t), "entry": 100, "stop": 95}, bars, raw, baseline)
    assert r == baseline and feat["decision"] == "PASS"
    bars.loc[0, ["high", "low"]] = [100.6, 94.0]
    r, _ = gated_result("G60_MOTION_FLOW", {"decision_time": str(t), "entry": 100, "stop": 95}, bars, raw, baseline)
    assert r["outcome"] == "STOP_AMBIGUOUS" and r["same_bar_collision"]
    print(json.dumps({"self_test": "ok", "periods": list(PERIODS), "gates": list(GATES),
                      "symbols": len(engine.EXPECTED_SYMBOLS), "fee_pct": FEE_PCT}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--fetch-shard", choices=sorted(dm.SHARDS))
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--outdir", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    if a.outdir is None:
        ap.error("--outdir required")
    if a.fetch_shard:
        configure_fetch(); result = engine.fetch_shard(a.fetch_shard, a.outdir)
    elif a.input_root:
        result = run(a.input_root, a.outdir)
    else:
        ap.error("choose --fetch-shard or --input-root")
    print(json.dumps({k: result[k] for k in result if k in
                      {"status", "shard", "elapsed_seconds", "decision_gate"}}), flush=True)


if __name__ == "__main__":
    main()
