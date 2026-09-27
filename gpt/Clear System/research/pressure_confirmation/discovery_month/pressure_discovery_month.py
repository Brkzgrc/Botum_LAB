"""Bounded 2023 Discovery-month candidate + selected-event exit benchmark.

This stage deliberately does not tune thresholds.  It validates that the exact
archived movement scanner can carry global watch/rank/quota/cooldown state over
a month, then downloads 5m paths only for globally selected events.  The only
exit families retained are the source ATR trail, a fixed gross +0.50% target,
and the already-promoted staged family.  Previously rejected time/fade sweeps
are not repeated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT.parents[1] / "sources" / "botum_2026-09-26"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(SOURCE))

import pressure_fullmarket_benchmark as engine  # type: ignore
import pressure_path_exit as path_exit  # type: ignore
import pressure_replay_preflight as helper  # type: ignore

HISTORY_START = pd.Timestamp("2023-04-20T00:00:00Z")
REPLAY_START = pd.Timestamp("2023-08-01T00:00:00Z")
REPLAY_END = pd.Timestamp("2023-08-31T00:00:00Z")
FUTURE_HOURS = 72
FEE_PCT = 0.20
POLICIES = ("source_atr_trail", "fixed_gross_0.50", "staged50_0.50_then_1.50_floor0.20")

# Point-in-time 2023 universe: MATIC was trading; SUI did not have the required
# 100-day warmup at the start of this Discovery window.
SHARDS = {
    "s0": ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"),
    "s1": ("ADAUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "MATICUSDT"),
    "s2": ("DOTUSDT", "BCHUSDT", "NEARUSDT", "UNIUSDT", "AAVEUSDT", "ETCUSDT"),
    "s3": ("XLMUSDT", "FILUSDT", "ATOMUSDT", "ALGOUSDT", "ICPUSDT", "VETUSDT"),
}


def configure_engine() -> None:
    engine.HISTORY_START = HISTORY_START
    engine.REPLAY_START = REPLAY_START
    engine.REPLAY_END = REPLAY_END
    engine.DATA_FUTURE_HOURS = FUTURE_HOURS
    engine.SHARDS = SHARDS
    engine.EXPECTED_SYMBOLS = tuple(s for values in SHARDS.values() for s in values)


def fixed_target(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float,
                 stop: float, target_pct: float = .50) -> dict:
    bars = path_exit.future_bars(bars5, entry_time, 24)
    target = entry * (1 + target_pct / 100)
    for row in bars.itertuples(index=False):
        hit_stop, hit_target = float(row.low) <= stop, float(row.high) >= target
        if hit_stop:
            return path_exit.result("STOP_AMBIGUOUS" if hit_target else "STOP_FIRST",
                                    (stop / entry - 1) * 100, row.close_time, hit_target)
        if hit_target:
            return path_exit.result("TARGET_FIRST", target_pct, row.close_time)
    last = bars.iloc[-1]
    return path_exit.result("EXPIRED", (float(last.close) / entry - 1) * 100,
                            last.close_time)


def merge_intervals(intervals: list[tuple[pd.Timestamp, pd.Timestamp]]):
    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(a, b) for a, b in merged]


def load_15m(files: dict[str, Path]) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol, fp in files.items():
        d = pd.read_csv(fp)
        d["open_time"] = pd.to_datetime(d.open_time, utc=True)
        d["close_time"] = pd.to_datetime(d.close_time, utc=True)
        for c in ("open", "high", "low", "close", "volume", "quote_volume", "taker_quote"):
            d[c] = pd.to_numeric(d[c], errors="raise")
        out[symbol] = d
    return out


def fetch_selected_paths(events: list[dict]) -> tuple[dict[str, pd.DataFrame], dict]:
    intervals = defaultdict(list)
    for e in events:
        t = pd.Timestamp(e["decision_time"])
        intervals[e["symbol"]].append((t, t + pd.Timedelta(hours=FUTURE_HOURS)))
    paths, requests, total_rows = {}, [], 0
    for symbol, spans in intervals.items():
        parts = []
        for start, end in merge_intervals(spans):
            d = helper.fetch(symbol, "5m", start, end)
            expected = int((end - start).total_seconds() // 300)
            coverage = len(d) / expected * 100 if expected else 0
            if coverage < 98 or d.close_time.max() < end - pd.Timedelta(minutes=5):
                raise RuntimeError(f"SELECTED_PATH_INCOMPLETE:{symbol}:{coverage:.3f}")
            parts.append(d)
            requests.append({"symbol": symbol, "start": str(start), "end": str(end),
                             "rows": len(d), "coverage_pct": round(coverage, 4),
                             "transports": d.attrs.get("transports", [])})
            total_rows += len(d)
        paths[symbol] = (pd.concat(parts).drop_duplicates("open_time")
                         .sort_values("open_time").reset_index(drop=True))
    return paths, {"request_count": len(requests), "rows": total_rows,
                   "symbols": len(paths), "requests": requests}


def event_key(e: dict) -> tuple:
    return (e["symbol"], e["decision_time"], round(float(e["entry"]), 12),
            round(float(e["stop"]), 12), round(float(e["source_tp1"]), 12))


def evaluate_event(e: dict, bars5: pd.DataFrame, raw15: pd.DataFrame) -> dict:
    t, entry, stop, tp1 = (pd.Timestamp(e["decision_time"]), float(e["entry"]),
                           float(e["stop"]), float(e["source_tp1"]))
    future24 = path_exit.future_bars(bars5, t, 24)
    mfe = (float(future24.high.max()) / entry - 1) * 100
    mae = (float(future24.low.min()) / entry - 1) * 100
    return {
        "mfe_pct": round(mfe, 6), "mae_pct": round(mae, 6),
        "policies": {
            "source_atr_trail": path_exit.source_atr_trail(bars5, raw15, t, entry, stop, tp1),
            "fixed_gross_0.50": fixed_target(bars5, t, entry, stop),
            "staged50_0.50_then_1.50_floor0.20": path_exit.staged(bars5, t, entry, stop),
        },
    }


def policy_metrics(records: list[dict], policy: str) -> dict:
    rows = [r["result"]["policies"][policy] for r in records]
    nets = [float(x["net_pct"]) for x in rows]
    gains, losses = sum(x for x in nets if x > 0), -sum(x for x in nets if x < 0)
    outcomes = Counter(x["outcome"] for x in rows)
    return {
        "events": len(rows), "positive": sum(x > 0 for x in nets),
        "negative": sum(x < 0 for x in nets), "flat": sum(x == 0 for x in nets),
        "net_total_pct": round(sum(nets), 6),
        "expectancy_pct": round(sum(nets) / len(nets), 6) if nets else None,
        "profit_factor": round(gains / losses, 6) if losses else None,
        "target_first": outcomes.get("TARGET_FIRST", 0) + outcomes.get("STAGED_FINAL", 0),
        "stop_first": sum(v for k, v in outcomes.items() if k.startswith("STOP")),
        "same_bar_collisions": sum(bool(x.get("same_bar_collision")) for x in rows),
        "outcomes": dict(sorted(outcomes.items())),
    }


def replay_with_paths(input_root: Path, outdir: Path) -> dict:
    configure_engine()
    started = time.perf_counter()
    candidate_dir = outdir / "candidate"
    base = engine.replay_central(input_root, candidate_dir)
    _, files = engine.validate_manifest_root(input_root)
    raw15 = load_15m(files)

    unique = {}
    for cooldown in ("0", "24", "48"):
        for e in base["comparison"][cooldown]["events"]:
            unique[event_key(e)] = e
    events = list(unique.values())
    if not events:
        raise RuntimeError("NO_SELECTED_EVENTS_FOR_5M_PATH_SMOKE")
    paths5, path_data = fetch_selected_paths(events) if events else ({}, {"request_count": 0,
                                                                         "rows": 0, "symbols": 0,
                                                                         "requests": []})
    evaluated = {event_key(e): evaluate_event(e, paths5[e["symbol"]], raw15[e["symbol"]])
                 for e in events}
    comparisons = {}
    for cooldown in ("0", "24", "48"):
        selected = base["comparison"][cooldown]["events"]
        records = [{"event": e, "result": evaluated[event_key(e)]} for e in selected]
        mfes = [r["result"]["mfe_pct"] for r in records]
        maes = [r["result"]["mae_pct"] for r in records]
        comparisons[cooldown] = {
            "signals": len(records),
            "signals_per_observed_day": round(len(records) / 30, 6),
            "active_days": len({e["decision_time"][:10] for e in selected}),
            "active_day_ratio_pct": round(len({e["decision_time"][:10] for e in selected}) / 30 * 100, 6),
            "mfe_mean_pct": round(sum(mfes) / len(mfes), 6) if mfes else None,
            "mae_mean_pct": round(sum(maes) / len(maes), 6) if maes else None,
            "policies": {p: policy_metrics(records, p) for p in POLICIES},
            "records": records,
        }
    handoff = json.dumps(base["state_end"], sort_keys=True, separators=(",", ":"))
    result = {
        "status": "PRESSURE_DISCOVERY_MONTH_BENCHMARK_PASSED",
        "research_role": "2023 Discovery infrastructure/capacity; no threshold selection",
        "history_start": str(HISTORY_START), "replay_window": [str(REPLAY_START), str(REPLAY_END)],
        "observed_days": 30, "symbols": len(engine.EXPECTED_SYMBOLS),
        "round_trip_cost_pct": FEE_PCT, "cooldowns": [0, 24, 48],
        "policies": list(POLICIES), "candidate_replay": base,
        "selected_path_data": path_data, "comparison": comparisons,
        "state_handoff": {"bytes": len(handoff.encode()),
                          "sha256": hashlib.sha256(handoff.encode()).hexdigest(),
                          "payload": base["state_end"]},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "oos": "N/A: Discovery infrastructure benchmark",
        "decision": "Use measured 15m/5m/state-handoff cost to budget year shards; do not promote an exit rule.",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def self_test() -> None:
    configure_engine()
    assert engine.DATA_FUTURE_HOURS == 72 and engine.REPLAY_START.year == 2023
    assert len(engine.EXPECTED_SYMBOLS) == len(set(engine.EXPECTED_SYMBOLS)) == 24
    assert "MATICUSDT" in engine.EXPECTED_SYMBOLS and "SUIUSDT" not in engine.EXPECTED_SYMBOLS
    assert all(engine.allowed_symbol(s) for s in engine.EXPECTED_SYMBOLS)
    t = pd.date_range("2023-01-01", periods=12, freq="5min", tz="UTC")
    bars = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(minutes=5),
                         "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0})
    bars.loc[1, ["high", "low", "close"]] = [100.6, 94.0, 95.0]
    collision = fixed_target(bars, t[0], 100, 95)
    assert collision["outcome"] == "STOP_AMBIGUOUS" and collision["same_bar_collision"]
    bars.loc[1, ["high", "low", "close"]] = [100.6, 99.9, 100.5]
    target = fixed_target(bars, t[0], 100, 95)
    assert target["outcome"] == "TARGET_FIRST" and target["net_pct"] == .30
    assert merge_intervals([(t[0], t[3]), (t[2], t[5]), (t[7], t[8])]) == [(t[0], t[5]), (t[7], t[8])]
    sample = [{"result": {"policies": {"p": target}}}]
    m = policy_metrics(sample, "p")
    assert m["positive"] == m["target_first"] == 1 and m["expectancy_pct"] == .30
    print(json.dumps({"self_test": "ok", "symbols": 24, "period_days": 30,
                      "fee_pct": FEE_PCT, "policies": POLICIES,
                      "rejected_retests": ["time_6h", "time_12h", "time_24h",
                                           "time_48h", "motion_fade_after0.50"]}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--fetch-shard", choices=sorted(SHARDS))
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--outdir", type=Path)
    a = ap.parse_args()
    configure_engine()
    if a.self_test:
        self_test(); return
    if a.outdir is None:
        ap.error("--outdir required")
    if a.fetch_shard:
        result = engine.fetch_shard(a.fetch_shard, a.outdir)
    elif a.input_root:
        result = replay_with_paths(a.input_root, a.outdir)
    else:
        ap.error("choose --fetch-shard or --input-root")
    print(json.dumps({k: result[k] for k in result if k in
                      {"status", "shard", "elapsed_seconds", "symbols"}}), flush=True)


if __name__ == "__main__":
    main()
