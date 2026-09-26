"""Aggregate fixed-calendar PRESSURE replay preflight shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

EXPECTED_SHARDS = ("q1", "q2", "q3", "q4")
POLICIES = ("source_tp1", "fixed_0.25", "fixed_0.50", "fixed_0.80", "fixed_1.00",
            "fixed_1.50", "fixed_2.00", "fixed_3.00", "fixed_5.00")
COOLDOWNS_H = (0, 6, 12, 24, 48)


def profit_factor(values: list[float]) -> float | None:
    wins = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    return round(wins / losses, 6) if losses else None


def cooldown(events: list[dict], hours: int) -> list[dict]:
    if hours == 0:
        return list(events)
    from pandas import Timestamp, Timedelta
    out, last = [], {}
    for event in sorted(events, key=lambda x: x["decision_time"]):
        at, symbol = Timestamp(event["decision_time"]), event["symbol"]
        if symbol in last and at - last[symbol] < Timedelta(hours=hours):
            continue
        out.append(event)
        last[symbol] = at
    return out


def summarize_policy(events: list[dict], policy: str) -> dict:
    rows = [e["policies"][policy] for e in events]
    values = [float(x["net_pct"]) for x in rows]
    return {
        "trades": len(rows),
        "target_first": sum(x["outcome"] == "TARGET_FIRST" for x in rows),
        "stop_first": sum(x["outcome"] in {"STOP_FIRST", "STOP_AMBIGUOUS"} for x in rows),
        "expired": sum(x["outcome"] == "EXPIRED" for x in rows),
        "same_bar_collisions": sum(bool(x["same_bar_collision"]) for x in rows),
        "net_pct_sum": round(sum(values), 6),
        "expectancy_pct": round(float(np.mean(values)), 6) if values else None,
        "median_pct": round(float(np.median(values)), 6) if values else None,
        "profit_factor": profit_factor(values),
    }


def aggregate(root: Path) -> dict:
    files = sorted(root.glob("**/summary.json"))
    shards, duplicates = {}, []
    for path in files:
        x = json.loads(path.read_text())
        shard = x.get("shard") or path.parent.name.rsplit("-", 1)[-1]
        if shard in shards:
            duplicates.append(shard)
        shards[shard] = x
    missing = sorted(set(EXPECTED_SHARDS) - set(shards))
    unexpected = sorted(set(shards) - set(EXPECTED_SHARDS))
    if missing or unexpected or duplicates:
        return {"status": "INCOMPLETE_SHARDS", "expected_shards": list(EXPECTED_SHARDS),
                "completed_shards": sorted(shards), "missing_shards": missing,
                "unexpected_shards": unexpected, "duplicate_shards": duplicates}
    for name, x in shards.items():
        if x.get("status") != "PRESSURE_REPLAY_PREFLIGHT_PASSED":
            raise RuntimeError(f"{name}: invalid shard status")
        if x["expected_symbols"] != x["completed_symbols"] or x["completed_symbols"] != 12:
            raise RuntimeError(f"{name}: incomplete symbol cardinality")
        if min(r["coverage_pct"] for r in x["coverage"]) < 98:
            raise RuntimeError(f"{name}: insufficient coverage")
    events = sorted([e | {"shard": name} for name, x in shards.items() for e in x["signals"]],
                    key=lambda x: x["decision_time"])
    replay_hours = sum((__import__("pandas").Timestamp(x["replay_window"][1]) -
                        __import__("pandas").Timestamp(x["replay_window"][0])).total_seconds() / 3600
                       for x in shards.values())
    replay_dates = sorted({d for x in shards.values() for d in
                           (x["replay_window"][0][:10], x["replay_window"][1][:10])})
    active_dates = sorted({e["decision_time"][:10] for e in events})
    by_cooldown = {}
    for hours in COOLDOWNS_H:
        kept = cooldown(events, hours)
        by_cooldown[str(hours)] = {
            "signals": len(kept),
            "removed": len(events) - len(kept),
            "symbols": len({e["symbol"] for e in kept}),
            "policies": {p: summarize_policy(kept, p) for p in POLICIES},
        }
    return {
        "status": "PRESSURE_MULTIPERIOD_PREFLIGHT_PASSED",
        "expected_shards": list(EXPECTED_SHARDS), "completed_shards": sorted(shards),
        "fee_pct": 0.20, "same_bar_policy": "conservative_stop_first",
        "replay_hours": replay_hours, "observed_days": replay_hours / 24,
        "replay_dates": replay_dates, "signals": len(events),
        "signals_per_observed_day": round(len(events) / (replay_hours / 24), 6),
        "active_dates": active_dates,
        "active_date_ratio_pct": round(len(active_dates) / len(replay_dates) * 100, 6),
        "symbols_with_signals": sorted({e["symbol"] for e in events}),
        "mfe_pct_24h": {
            "mean": round(float(np.mean([e["mfe_pct_24h"] for e in events])), 6) if events else None,
            "median": round(float(np.median([e["mfe_pct_24h"] for e in events])), 6) if events else None,
        },
        "mae_pct_24h": {
            "mean": round(float(np.mean([e["mae_pct_24h"] for e in events])), 6) if events else None,
            "median": round(float(np.median([e["mae_pct_24h"] for e in events])), 6) if events else None,
        },
        "per_shard": {name: {"window": x["replay_window"], "signals": x["signal_count"],
                              "scan_count": x["scan_count"]} for name, x in shards.items()},
        "cooldown_ablation": by_cooldown,
        "events": events,
        "decision": "Mechanism/event-density preflight only; do not select an exit threshold or change production.",
        "oos": "N/A: fixed 2025 diagnostic windows, not a held-out promotion test.",
    }


def self_test() -> None:
    events = [
        {"symbol": "AAAUSDT", "decision_time": "2025-01-01T00:00:00Z"},
        {"symbol": "AAAUSDT", "decision_time": "2025-01-01T05:00:00Z"},
        {"symbol": "AAAUSDT", "decision_time": "2025-01-01T13:00:00Z"},
        {"symbol": "BBBUSDT", "decision_time": "2025-01-01T05:00:00Z"},
    ]
    assert len(cooldown(events, 0)) == 4
    assert len(cooldown(events, 6)) == 3
    assert len(cooldown(events, 12)) == 3
    assert profit_factor([1, 2, -1]) == 3.0
    assert profit_factor([1, 2]) is None
    print(json.dumps({"self_test": "ok", "cooldowns": COOLDOWNS_H}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.input_root is None or a.output is None:
        ap.error("--input-root and --output required")
    result = aggregate(a.input_root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if result["status"] != "PRESSURE_MULTIPERIOD_PREFLIGHT_PASSED":
        raise RuntimeError(json.dumps(result))
    print(json.dumps({"status": result["status"], "signals": result["signals"]}), flush=True)


if __name__ == "__main__":
    main()
