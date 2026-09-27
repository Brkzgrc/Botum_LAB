"""Causal 5m pre-exit diagnostic for the rejected 2024 RETRIGGER cohort.

This module never scans for new entries and never changes target/stop/cooldown.
It replays the archived events, verifies their locked exits, then measures only
closed 5m bars at or before the actual exit.  It is diagnostic-only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = HERE.parent
DISCOVERY = PARENT / "discovery_month"
sys.path[:0] = [str(PARENT), str(DISCOVERY)]

import pressure_discovery_month as dm  # type: ignore
import pressure_replay_preflight as helper  # type: ignore

PREREG_PATH = HERE / "preregistration.json"
THRESHOLDS = (0.10, 0.20, 0.30, 0.40, 0.50)


def prereg() -> dict:
    p = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert p["status"] == "PREREGISTERED_NOT_RUN"
    assert p["source"]["expected_events"] == 324
    assert p["immutable_contract"]["gross_target_pct"] == 0.5
    assert p["immutable_contract"]["fee_round_trip_pct"] == 0.2
    assert p["immutable_contract"]["closed_5m_candles_only"] is True
    assert p["immutable_contract"]["no_entry_rescan"] is True
    assert p["immutable_contract"]["no_threshold_optimization"] is True
    assert p["action_budget"]["hard_runner_minute_ceiling_from_job_timeouts"] == 64
    return p


def event_key(event: dict) -> tuple:
    return (
        event["symbol"], event["decision_time"],
        round(float(event["entry"]), 12), round(float(event["stop"]), 12),
        round(float(event["source_tp1"]), 12),
    )


def load_quarter(path: Path, quarter: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("quarter") != quarter:
        raise RuntimeError(f"QUARTER_MISMATCH:{payload.get('quarter')}:{quarter}")
    records = [r for r in payload["cooldowns"]["0"]["records"]
               if r["event"]["setup_kind"] == "RETRIGGER"]
    keys = [event_key(r["event"]) for r in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"DUPLICATE_EVENT:{quarter}")
    return records


def merge_intervals(spans: list[tuple[pd.Timestamp, pd.Timestamp]]):
    merged: list[list[pd.Timestamp]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(x[0], x[1]) for x in merged]


def fetch_paths(records: list[dict]) -> tuple[dict[str, pd.DataFrame], dict]:
    spans: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    for record in records:
        e = record["event"]
        start = pd.Timestamp(e["decision_time"])
        spans[e["symbol"]].append((start, start + pd.Timedelta(hours=24)))
    paths: dict[str, pd.DataFrame] = {}
    requests, total_rows = [], 0
    tasks = [(symbol, start, end) for symbol, intervals in sorted(spans.items())
             for start, end in merge_intervals(intervals)]

    def one(task):
        symbol, start, end = task
        bars = helper.fetch(symbol, "5m", start, end)
        expected = int((end - start).total_seconds() // 300)
        coverage = len(bars) / expected * 100 if expected else 0.0
        if coverage < 98.0 or bars.close_time.max() < end - pd.Timedelta(minutes=5):
            raise RuntimeError(f"PATH_INCOMPLETE:{symbol}:{coverage:.3f}")
        meta = {"symbol": symbol, "start": str(start), "end": str(end),
                "rows": len(bars), "coverage_pct": round(coverage, 4),
                "transports": bars.attrs.get("transports", [])}
        return symbol, bars, meta

    # Four bounded workers keep request weight far below Binance public limits
    # while avoiding the multi-minute serial latency observed in the Q1 probe.
    by_symbol: dict[str, list[pd.DataFrame]] = defaultdict(list)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, bars, meta in pool.map(one, tasks):
            by_symbol[symbol].append(bars)
            requests.append(meta)
            total_rows += len(bars)
    for symbol, parts in sorted(by_symbol.items()):
        paths[symbol] = (pd.concat(parts).drop_duplicates("open_time")
                         .sort_values("open_time").reset_index(drop=True))
    requests.sort(key=lambda x: (x["symbol"], x["start"]))
    return paths, {"request_count": len(requests), "rows": total_rows,
                   "symbols": len(paths), "requests": requests}


def minutes_since(start: pd.Timestamp, when: pd.Timestamp) -> int:
    # Binance close_time ends in :59.999; ceil maps a completed 5m bar to 5,
    # 10, 15... minutes instead of understating it by one minute.
    return int(math.ceil((when - start).total_seconds() / 60))


def first_minutes(frame: pd.DataFrame, mask: pd.Series, start: pd.Timestamp) -> int | None:
    hit = frame.loc[mask]
    return None if hit.empty else minutes_since(start, pd.Timestamp(hit.iloc[0].close_time))


def slope(values: pd.Series) -> float | None:
    z = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 3:
        return None
    y = z.to_numpy(dtype=float)
    scale = float(np.mean(np.abs(y))) or 1.0
    return round(float(np.polyfit(np.arange(len(y)), y / scale, 1)[0]), 8)


def max_lower_close_run(values: pd.Series) -> int:
    longest = current = 0
    a = values.to_numpy(dtype=float)
    for i in range(1, len(a)):
        current = current + 1 if a[i] < a[i - 1] else 0
        longest = max(longest, current)
    return int(longest)


def analyse_record(record: dict, bars5: pd.DataFrame) -> dict:
    e, expected = record["event"], record["result"]["fixed_gross_0.50"]
    start, entry, stop = pd.Timestamp(e["decision_time"]), float(e["entry"]), float(e["stop"])
    future = bars5[(bars5.open_time >= start) &
                   (bars5.open_time < start + pd.Timedelta(hours=24))].copy()
    if future.empty:
        raise RuntimeError(f"EMPTY_PATH:{e['symbol']}:{start}")
    reproduced = dm.fixed_target(bars5, start, entry, stop, target_pct=0.50)
    fields = ("outcome", "exit_time", "same_bar_collision")
    if any(reproduced.get(k) != expected.get(k) for k in fields):
        raise RuntimeError(f"EXIT_MISMATCH:{e['symbol']}:{start}:{expected}:{reproduced}")
    if not math.isclose(float(reproduced["net_pct"]), float(expected["net_pct"]), abs_tol=1e-6):
        raise RuntimeError(f"NET_MISMATCH:{e['symbol']}:{start}")

    exit_time = pd.Timestamp(expected["exit_time"])
    pre = future[future.close_time <= exit_time].copy()
    post_used = int((pre.close_time > exit_time).sum())
    if pre.empty or post_used:
        raise RuntimeError(f"CAUSAL_TRUNCATION_FAILED:{e['symbol']}:{start}")
    if pd.Timestamp(pre.iloc[-1].close_time) != exit_time:
        raise RuntimeError(f"EXIT_BAR_MISSING:{e['symbol']}:{start}")

    peak_pos = int(np.argmax(pre.high.to_numpy(dtype=float)))
    peak = pre.iloc[peak_pos]
    after_peak = pre.iloc[peak_pos:].copy()
    peak_high = float(peak.high)
    exit_execution = entry * (1 + float(expected["gross_pct"]) / 100)
    reaches = {}
    for threshold in THRESHOLDS:
        reaches[f"ge_{threshold:.2f}"] = first_minutes(
            pre, pre.high >= entry * (1 + threshold / 100), start)

    returns = after_peak.close.pct_change() * 100
    accel = returns.diff()
    taker_share = after_peak.taker_quote / after_peak.quote_volume.replace(0, np.nan)
    return {
        "quarter": record["quarter"], "event": e,
        "locked_exit": expected,
        "diagnostic": {
            "pre_exit_rows": len(pre), "post_exit_rows_used": post_used,
            "pre_exit_mfe_pct": round((float(pre.high.max()) / entry - 1) * 100, 6),
            "pre_exit_mae_pct": round((float(pre.low.min()) / entry - 1) * 100, 6),
            "minutes_to_first_positive_close": first_minutes(pre, pre.close > entry, start),
            "threshold_minutes": reaches,
            "minutes_to_pre_exit_peak": minutes_since(start, pd.Timestamp(peak.close_time)),
            "peak_to_exit_drawdown_pct": round((exit_execution / peak_high - 1) * 100, 6),
            "minutes_peak_to_exit": minutes_since(pd.Timestamp(peak.close_time), exit_time),
            "max_consecutive_lower_closes_after_peak": max_lower_close_run(after_peak.close),
            "post_peak_5m_return_acceleration": round(float(accel.mean()), 8)
                if accel.notna().any() else None,
            "post_peak_volume_direction": slope(after_peak.volume),
            "post_peak_taker_buy_share_direction": slope(taker_share),
        },
    }


def quarter_run(quarter: str, input_path: Path, output: Path) -> dict:
    p = prereg()
    records = load_quarter(input_path, quarter)
    paths, request_meta = fetch_paths(records)
    analysed = [analyse_record(r, paths[r["event"]["symbol"]]) for r in records]
    out = {
        "status": "RETRIGGER_PREEXIT_QUARTER_COMPLETE", "quarter": quarter,
        "source_run_id": p["source"]["workflow_run_id"], "events": len(analysed),
        "outcomes": dict(Counter(x["locked_exit"]["outcome"] for x in analysed)),
        "fetch": request_meta, "records": analysed,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def group_metrics(records: list[dict]) -> dict:
    if not records:
        return {"events": 0}
    mfe = [float(r["diagnostic"]["pre_exit_mfe_pct"]) for r in records]
    mae = [float(r["diagnostic"]["pre_exit_mae_pct"]) for r in records]
    return {
        "events": len(records), "mfe_mean_pct": round(float(np.mean(mfe)), 6),
        "mfe_median_pct": round(float(np.median(mfe)), 6),
        "mae_mean_pct": round(float(np.mean(mae)), 6),
        "reach_counts": {f"ge_{x:.2f}": sum(v >= x for v in mfe) for x in THRESHOLDS},
        "first_positive_close_count": sum(r["diagnostic"]["minutes_to_first_positive_close"] is not None
                                          for r in records),
    }


def aggregate(input_root: Path, output: Path) -> dict:
    p = prereg()
    files = sorted(input_root.glob("**/summary.json"))
    quarters: dict[str, dict] = {}
    for fp in files:
        x = json.loads(fp.read_text(encoding="utf-8"))
        if x.get("status") != "RETRIGGER_PREEXIT_QUARTER_COMPLETE":
            continue
        q = x["quarter"]
        if q in quarters:
            raise RuntimeError(f"DUPLICATE_QUARTER:{q}")
        quarters[q] = x
    required = set(p["integrity_gates"]["required_quarters"])
    if set(quarters) != required:
        raise RuntimeError(f"INCOMPLETE_QUARTERS:{sorted(quarters)}")
    records = [r for q in sorted(quarters) for r in quarters[q]["records"]]
    if len(records) != p["integrity_gates"]["exact_event_count"]:
        raise RuntimeError(f"EVENT_COUNT:{len(records)}")
    keys = [event_key(r["event"]) for r in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("DUPLICATE_EVENTS_ACROSS_QUARTERS")
    outcomes = Counter(r["locked_exit"]["outcome"] for r in records)
    if dict(outcomes) != p["integrity_gates"]["exact_outcome_counts"]:
        raise RuntimeError(f"OUTCOME_COUNTS:{dict(outcomes)}")
    if any(r["diagnostic"]["post_exit_rows_used"] for r in records):
        raise RuntimeError("POST_EXIT_LEAKAGE")
    losses = [r for r in records if float(r["locked_exit"]["net_pct"]) < 0]
    by_outcome = {name: group_metrics([r for r in records if r["locked_exit"]["outcome"] == name])
                  for name in sorted(outcomes)}
    out = {
        "status": "RETRIGGER_PREEXIT_DIAGNOSTIC_COMPLETE",
        "source_run_id": p["source"]["workflow_run_id"], "events": len(records),
        "outcomes": dict(outcomes), "round_trip_cost_pct": 0.2,
        "window": p["immutable_contract"]["event_window"],
        "all": group_metrics(records), "losses": group_metrics(losses),
        "by_outcome": by_outcome,
        "integrity": {"quarters": sorted(quarters), "duplicate_events": 0,
                      "post_exit_rows_used": 0, "exit_reproduction": "exact"},
        "decision_scope": "DIAGNOSTIC_ONLY_NO_PRODUCTION_PROMOTION",
        "oos": "N/A: 2025 and 2026 remain unopened",
        "production_effect": "None; Clear System.py unchanged.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def synthetic_bars() -> pd.DataFrame:
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    rows = []
    values = [
        (100.0, 100.20, 99.90, 100.10, 10, 1000, 520),
        (100.1, 100.35, 99.95, 100.20, 12, 1200, 650),
        (100.2, 100.60, 100.10, 100.55, 15, 1500, 900),
        (100.5, 120.00, 100.40, 119.00, 20, 2000, 1500),
    ]
    for i, (o, h, l, c, v, qv, tq) in enumerate(values):
        ot = start + pd.Timedelta(minutes=5 * i)
        rows.append({"open_time": ot, "close_time": ot + pd.Timedelta(minutes=5) - pd.Timedelta(milliseconds=1),
                     "open": o, "high": h, "low": l, "close": c, "volume": v,
                     "quote_volume": qv, "taker_quote": tq})
    return pd.DataFrame(rows)


def self_test() -> None:
    bars = synthetic_bars()
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    fixed = dm.fixed_target(bars, start, 100.0, 98.0, 0.50)
    record = {"quarter": "Q1", "event": {"symbol": "BTCUSDT", "decision_time": str(start),
              "setup_kind": "RETRIGGER", "entry": 100.0, "stop": 98.0, "source_tp1": 101.0},
              "result": {"fixed_gross_0.50": fixed}}
    got = analyse_record(record, bars)["diagnostic"]
    assert fixed["outcome"] == "TARGET_FIRST"
    assert got["pre_exit_rows"] == 3
    assert got["post_exit_rows_used"] == 0
    assert got["pre_exit_mfe_pct"] == 0.6
    assert got["threshold_minutes"]["ge_0.50"] == 15
    assert got["pre_exit_mfe_pct"] < 20.0  # post-exit 120 high is excluded
    assert max_lower_close_run(pd.Series([3.0, 2.0, 1.0, 2.0])) == 2
    print(json.dumps({"status": "SELF_TEST_OK", "fixed": fixed, "diagnostic": got}))


def smoke() -> None:
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    bars = helper.fetch("BTCUSDT", "5m", start, start + pd.Timedelta(hours=24))
    entry = float(bars.iloc[0].open)
    fixed = dm.fixed_target(bars, start, entry, entry * 0.90, 0.50)
    record = {"quarter": "Q1", "event": {"symbol": "BTCUSDT", "decision_time": str(start),
              "setup_kind": "RETRIGGER", "entry": entry, "stop": entry * 0.90,
              "source_tp1": entry * 1.01}, "result": {"fixed_gross_0.50": fixed}}
    got = analyse_record(record, bars)
    print(json.dumps({"status": "REAL_DATA_SMOKE_OK", "rows": len(bars),
                      "transport": bars.attrs.get("transports"), "result": got["locked_exit"],
                      "diagnostic": got["diagnostic"]}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--quarter", choices=("Q1", "Q2", "Q3", "Q4"))
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--input", type=Path)
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output"))
    a = ap.parse_args()
    prereg()
    if a.self_test:
        self_test()
    elif a.smoke:
        smoke()
    elif a.quarter:
        if not a.input:
            ap.error("--input is required with --quarter")
        out = quarter_run(a.quarter, a.input, a.output)
        print(json.dumps({"status": out["status"], "quarter": out["quarter"],
                          "events": out["events"], "outcomes": out["outcomes"],
                          "fetch": {k: out["fetch"][k]
                                    for k in ("request_count", "rows", "symbols")}}))
    elif a.aggregate:
        if not a.input_root:
            ap.error("--input-root is required with --aggregate")
        print(json.dumps(aggregate(a.input_root, a.output)))
    else:
        ap.error("select one mode")


if __name__ == "__main__":
    main()
