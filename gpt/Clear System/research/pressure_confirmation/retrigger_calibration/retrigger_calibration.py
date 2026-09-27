"""Preregistered 2024 RETRIGGER-only calibration.

The archived causal movement scanner is replayed without threshold refitting.
Four quarter jobs reuse one hash-verified 15m data fetch.  Each quarter starts
48 hours early to reconstruct watch/cooldown state, but only in-quarter signals
enter metrics.  The rejected 30/60 minute gates are intentionally absent.
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

PREREG_PATH = HERE / "preregistration.json"
HISTORY_START = pd.Timestamp("2023-09-01T00:00:00Z")
CALIBRATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
CALIBRATION_END = pd.Timestamp("2025-01-01T00:00:00Z")
STATE_WARMUP_HOURS = 48
FUTURE_HOURS = 25
FEE_PCT = 0.20
QUARTERS = {
    "Q1": (pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2024-04-01T00:00:00Z")),
    "Q2": (pd.Timestamp("2024-04-01T00:00:00Z"), pd.Timestamp("2024-07-01T00:00:00Z")),
    "Q3": (pd.Timestamp("2024-07-01T00:00:00Z"), pd.Timestamp("2024-10-01T00:00:00Z")),
    "Q4": (pd.Timestamp("2024-10-01T00:00:00Z"), pd.Timestamp("2025-01-01T00:00:00Z")),
}
SETUPS = ("RETRIGGER", "PRESSURE")
COOLDOWNS = ("0", "24", "48")


def preregistration() -> dict:
    x = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert x["status"] == "PREREGISTERED_NOT_RUN"
    assert x["calibration_period"]["start"] == "2024-01-01T00:00:00Z"
    assert x["calibration_period"]["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert x["locked_candidate"]["setup_kind"] == "RETRIGGER"
    assert x["locked_candidate"]["cooldown_hours"] == 0
    assert x["locked_candidate"]["gross_target_pct"] == .5
    assert x["locked_candidate"]["round_trip_cost_pct"] == FEE_PCT
    assert x["locked_candidate"]["expiry_hours"] == 24
    assert x["locked_candidate"]["rejected_gates_disabled"] == [
        "G30_CLOSE", "G60_PRICE_VOLUME", "G60_MOTION_FLOW"
    ]
    assert x["action_budget"]["hard_runner_minute_ceiling_from_job_timeouts"] == 164
    return x


def configure(start: pd.Timestamp, end: pd.Timestamp) -> None:
    engine.HISTORY_START = HISTORY_START
    engine.REPLAY_START = start
    engine.REPLAY_END = end
    engine.DATA_FUTURE_HOURS = FUTURE_HOURS
    engine.ALLOW_TERMINATED_SYMBOLS = True
    engine.SHARDS = dm.SHARDS
    engine.EXPECTED_SYMBOLS = tuple(s for values in dm.SHARDS.values() for s in values)
    dm.FUTURE_HOURS = FUTURE_HOURS


def configure_fetch() -> None:
    configure(CALIBRATION_START - pd.Timedelta(hours=STATE_WARMUP_HOURS), CALIBRATION_END)


def event_key(event: dict) -> tuple:
    return dm.event_key(event)


def evaluate_event(event: dict, bars5: pd.DataFrame) -> dict:
    t = pd.Timestamp(event["decision_time"])
    entry, stop = float(event["entry"]), float(event["stop"])
    future = bars5[(bars5.open_time >= t) &
                   (bars5.open_time < t + pd.Timedelta(hours=24))]
    if future.empty or pd.Timestamp(future.close_time.iloc[-1]) < t + pd.Timedelta(hours=24) - pd.Timedelta(minutes=5):
        raise RuntimeError(f"CALIBRATION_PATH_INCOMPLETE:{event['symbol']}:{t}")
    fixed = dm.fixed_target(bars5, t, entry, stop, target_pct=.50)
    return {
        "mfe_pct": round((float(future.high.max()) / entry - 1) * 100, 6),
        "mae_pct": round((float(future.low.min()) / entry - 1) * 100, 6),
        "fixed_gross_0.50": fixed,
    }


def consecutive_losses(records: list[dict]) -> int:
    longest = current = 0
    ordered = sorted(records, key=lambda r: r["event"]["decision_time"])
    for record in ordered:
        if float(record["result"]["fixed_gross_0.50"]["net_pct"]) < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def metrics(records: list[dict], observed_days: float | None = None) -> dict:
    rows = [r["result"]["fixed_gross_0.50"] for r in records]
    nets = [float(r["net_pct"]) for r in rows]
    outcomes = Counter(r["outcome"] for r in rows)
    gains = sum(x for x in nets if x > 0)
    losses = -sum(x for x in nets if x < 0)
    active_days = len({r["event"]["decision_time"][:10] for r in records})
    result = {
        "events": len(records),
        "positive": sum(x > 0 for x in nets),
        "negative": sum(x < 0 for x in nets),
        "flat": sum(x == 0 for x in nets),
        "net_total_pct": round(sum(nets), 6),
        "expectancy_pct": round(sum(nets) / len(nets), 6) if nets else None,
        "profit_factor": round(gains / losses, 6) if losses else None,
        "target_first": outcomes.get("TARGET_FIRST", 0),
        "stop_first": sum(v for k, v in outcomes.items() if k.startswith("STOP")),
        "expired": outcomes.get("EXPIRED", 0),
        "worst_trade_pct": round(min(nets), 6) if nets else None,
        "maximum_consecutive_losses": consecutive_losses(records),
        "active_days": active_days,
        "mfe_mean_pct": round(sum(r["result"]["mfe_pct"] for r in records) / len(records), 6) if records else None,
        "mae_mean_pct": round(sum(r["result"]["mae_pct"] for r in records) / len(records), 6) if records else None,
        "outcomes": dict(sorted(outcomes.items())),
    }
    if observed_days is not None:
        result["signals_per_day"] = round(len(records) / observed_days, 6)
        result["active_day_ratio_pct"] = round(active_days / observed_days * 100, 6)
    return result


def quarter_replay(quarter: str, input_root: Path, outdir: Path) -> dict:
    if quarter not in QUARTERS:
        raise ValueError(quarter)
    started = time.perf_counter()
    qstart, qend = QUARTERS[quarter]
    replay_start = qstart - pd.Timedelta(hours=STATE_WARMUP_HOURS)
    configure(replay_start, qend)
    base = engine.replay_central(input_root, outdir / "candidate")
    _, files = engine.validate_manifest_root(input_root)
    raw15 = dm.load_15m(files)

    selected: dict[str, list[dict]] = {}
    unique: dict[tuple, dict] = {}
    for cooldown in COOLDOWNS:
        events = [e for e in base["comparison"][cooldown]["events"]
                  if qstart <= pd.Timestamp(e["decision_time"]) < qend]
        if any(pd.Timestamp(e["decision_time"]) < qstart for e in events):
            raise RuntimeError("WARMUP_EVENT_LEAK")
        selected[cooldown] = events
        for event in events:
            if event.get("setup_kind") not in SETUPS:
                raise RuntimeError(f"UNEXPECTED_SETUP_KIND:{event.get('setup_kind')}")
            unique[event_key(event)] = event
    if not unique:
        raise RuntimeError(f"NO_SELECTED_EVENTS:{quarter}")
    events = list(unique.values())
    paths5, path_data = dm.fetch_selected_paths(events)
    evaluated = {event_key(e): evaluate_event(e, paths5[e["symbol"]]) for e in events}
    days = (qend - qstart).total_seconds() / 86400
    cooldowns = {}
    for cooldown, events_for_cooldown in selected.items():
        records = [{"quarter": quarter, "event": e, "result": evaluated[event_key(e)]}
                   for e in events_for_cooldown]
        cooldowns[cooldown] = {
            "all": metrics(records, days),
            "setups": {
                setup: metrics([r for r in records if r["event"]["setup_kind"] == setup], days)
                for setup in SETUPS
            },
            "records": records,
        }
    result = {
        "status": "RETRIGGER_CALIBRATION_QUARTER_COMPLETE",
        "preregistration_status": preregistration()["status"],
        "quarter": quarter,
        "window": [str(qstart), str(qend)],
        "state_warmup_start": str(replay_start),
        "observed_days": days,
        "symbols": len(engine.EXPECTED_SYMBOLS),
        "round_trip_cost_pct": FEE_PCT,
        "candidate_replay": base,
        "selected_path_data": path_data,
        "cooldowns": cooldowns,
        "expected_shards": sorted(dm.SHARDS),
        "completed_shards": sorted(engine.validate_manifest_root(input_root, verify_files=False)[0]),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "oos": "N/A: 2024 Calibration quarter; 2025 and 2026 unopened",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def month_key(record: dict) -> str:
    return record["event"]["decision_time"][:7]


def positive_symbol_concentration(records: list[dict]) -> float | None:
    by_symbol: dict[str, float] = defaultdict(float)
    for record in records:
        net = float(record["result"]["fixed_gross_0.50"]["net_pct"])
        if net > 0:
            by_symbol[record["event"]["symbol"]] += net
    total = sum(by_symbol.values())
    return round(max(by_symbol.values(), default=0) / total * 100, 6) if total else None


def load_quarters(root: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in root.rglob("summary.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if data.get("status") != "RETRIGGER_CALIBRATION_QUARTER_COMPLETE":
            continue
        quarter = data.get("quarter")
        if quarter in found:
            raise RuntimeError(f"DUPLICATE_QUARTER:{quarter}")
        found[quarter] = data
    if set(found) != set(QUARTERS):
        raise RuntimeError(f"INCOMPLETE_QUARTERS:{sorted(found)}")
    return {q: found[q] for q in QUARTERS}


def aggregate(quarter_root: Path, outdir: Path) -> dict:
    started = time.perf_counter()
    prereg = preregistration()
    quarters = load_quarters(quarter_root)
    records_by_setup: dict[str, list[dict]] = {setup: [] for setup in SETUPS}
    for quarter in QUARTERS:
        for record in quarters[quarter]["cooldowns"]["0"]["records"]:
            records_by_setup[record["event"]["setup_kind"]].append(record)
    candidate = records_by_setup["RETRIGGER"]
    control = records_by_setup["PRESSURE"]
    observed_days = (CALIBRATION_END - CALIBRATION_START).total_seconds() / 86400
    candidate_metrics = metrics(candidate, observed_days)
    control_metrics = metrics(control, observed_days)

    months = {}
    for month in pd.period_range("2024-01", "2024-12", freq="M").astype(str):
        months[month] = metrics([r for r in candidate if month_key(r) == month])
    quarter_metrics = {
        q: metrics([r for r in candidate if r["quarter"] == q]) for q in QUARTERS
    }
    concentration = positive_symbol_concentration(candidate)
    negative_ratio = (candidate_metrics["negative"] / candidate_metrics["events"] * 100
                      if candidate_metrics["events"] else math.inf)
    positive_months = sum((m["net_total_pct"] or 0) > 0 for m in months.values())
    nonnegative_quarters = sum((m["net_total_pct"] is not None and m["net_total_pct"] >= 0)
                               for m in quarter_metrics.values())
    gate = prereg["pass_gate_all_required"]
    tests = {
        "minimum_events": candidate_metrics["events"] >= gate["minimum_events"],
        "minimum_signals_per_day": candidate_metrics["signals_per_day"] >= gate["minimum_signals_per_day"],
        "minimum_active_day_ratio_pct": candidate_metrics["active_day_ratio_pct"] >= gate["minimum_active_day_ratio_pct"],
        "minimum_expectancy_pct": (candidate_metrics["expectancy_pct"] is not None and
                                    candidate_metrics["expectancy_pct"] >= gate["minimum_expectancy_pct"]),
        "minimum_profit_factor": (candidate_metrics["profit_factor"] is not None and
                                  candidate_metrics["profit_factor"] >= gate["minimum_profit_factor"]),
        "minimum_positive_months": positive_months >= gate["minimum_positive_months"],
        "minimum_nonnegative_quarters": nonnegative_quarters >= gate["minimum_nonnegative_quarters"],
        "maximum_negative_event_ratio_pct": negative_ratio <= gate["maximum_negative_event_ratio_pct"],
        "minimum_worst_trade_pct": (candidate_metrics["worst_trade_pct"] is not None and
                                    candidate_metrics["worst_trade_pct"] >= gate["minimum_worst_trade_pct"]),
        "maximum_positive_pnl_symbol_concentration_pct": (concentration is not None and
            concentration <= gate["maximum_positive_pnl_symbol_concentration_pct"]),
    }
    passed = all(tests.values())
    result = {
        "status": "RETRIGGER_2024_CALIBRATION_COMPLETE",
        "preregistration_status": prereg["status"],
        "window": [str(CALIBRATION_START), str(CALIBRATION_END)],
        "observed_days": observed_days,
        "round_trip_cost_pct": FEE_PCT,
        "candidate": {"setup_kind": "RETRIGGER", "metrics": candidate_metrics,
                      "negative_event_ratio_pct": round(negative_ratio, 6),
                      "positive_pnl_symbol_concentration_pct": concentration,
                      "positive_months": positive_months,
                      "nonnegative_quarters": nonnegative_quarters,
                      "monthly": months, "quarterly": quarter_metrics},
        "control": {"setup_kind": "PRESSURE", "metrics": control_metrics},
        "decision_gate": {"tests": tests, "passed": passed,
                          "decision": ("ADVANCE_RETRIGGER_TO_2025_FORWARD_VALIDATION" if passed
                                       else "REJECT_RETRIGGER_SETUP_KIND_SEPARATION")},
        "quarters": {q: {"window": quarters[q]["window"],
                          "elapsed_seconds": quarters[q]["elapsed_seconds"],
                          "selected_path_data": quarters[q]["selected_path_data"],
                          "candidate": quarters[q]["cooldowns"]["0"]["setups"]["RETRIGGER"],
                          "control": quarters[q]["cooldowns"]["0"]["setups"]["PRESSURE"]}
                     for q in QUARTERS},
        "universe_contract": "Binance Spot USDT long; fixed historical 24-symbol set; stable/fiat/leveraged bases excluded",
        "causality_contract": "scanner close_time < decision_time; quarter warmup excluded from metrics; stop-first",
        "oos": "N/A: 2024 Calibration only; 2025 forward validation and 2026 final OOS unopened",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "production_effect": "None; Clear System.py remains unchanged.",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def self_test() -> None:
    prereg = preregistration()
    configure_fetch()
    assert len(engine.EXPECTED_SYMBOLS) == len(set(engine.EXPECTED_SYMBOLS)) == 24
    assert all(engine.allowed_symbol(symbol) for symbol in engine.EXPECTED_SYMBOLS)
    assert engine.ALLOW_TERMINATED_SYMBOLS is True
    assert list(QUARTERS) == ["Q1", "Q2", "Q3", "Q4"]
    assert QUARTERS["Q1"][0] == CALIBRATION_START and QUARTERS["Q4"][1] == CALIBRATION_END
    assert all(QUARTERS[a][1] == QUARTERS[b][0] for a, b in zip(list(QUARTERS)[:-1], list(QUARTERS)[1:]))
    assert prereg["locked_candidate"]["rejected_gates_disabled"] == [
        "G30_CLOSE", "G60_PRICE_VOLUME", "G60_MOTION_FLOW"
    ]

    t = pd.date_range("2024-01-01", periods=289, freq="5min", tz="UTC")
    bars = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(minutes=5),
                         "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0})
    bars.loc[1, ["high", "low", "close"]] = [100.6, 94.0, 95.0]
    event = {"symbol": "BTCUSDT", "decision_time": str(t[0]), "entry": 100.0,
             "stop": 95.0, "source_tp1": 103.5, "setup_kind": "RETRIGGER"}
    evaluated = evaluate_event(event, bars)
    fixed = evaluated["fixed_gross_0.50"]
    assert fixed["outcome"] == "STOP_AMBIGUOUS" and fixed["same_bar_collision"]
    assert fixed["net_pct"] == -5.2
    sample = [{"quarter": "Q1", "event": event, "result": evaluated}]
    m = metrics(sample, 1)
    assert m["events"] == m["negative"] == m["stop_first"] == 1
    assert m["maximum_consecutive_losses"] == 1 and m["signals_per_day"] == 1
    print(json.dumps({"self_test": "ok", "candidate": "RETRIGGER",
                      "quarters": list(QUARTERS), "symbols": 24,
                      "fee_pct": FEE_PCT, "state_warmup_hours": STATE_WARMUP_HOURS}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fetch-shard", choices=sorted(dm.SHARDS))
    parser.add_argument("--quarter", choices=sorted(QUARTERS))
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--aggregate-root", type=Path)
    parser.add_argument("--outdir", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.outdir is None:
        parser.error("--outdir required")
    if args.fetch_shard:
        configure_fetch()
        result = engine.fetch_shard(args.fetch_shard, args.outdir)
    elif args.quarter and args.input_root:
        result = quarter_replay(args.quarter, args.input_root, args.outdir)
    elif args.aggregate_root:
        result = aggregate(args.aggregate_root, args.outdir)
    else:
        parser.error("choose --fetch-shard, --quarter with --input-root, or --aggregate-root")
    print(json.dumps({k: result[k] for k in result if k in
                      {"status", "shard", "quarter", "elapsed_seconds", "decision_gate"}}), flush=True)


if __name__ == "__main__":
    main()
