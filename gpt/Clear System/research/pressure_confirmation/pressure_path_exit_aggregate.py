"""Aggregate four fixed-window PRESSURE path-exit mechanism shards."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from pressure_path_exit import PATH_POLICIES

EXPECTED_SHARDS = ("q1", "q2", "q3", "q4")


def profit_factor(values: list[float]) -> float | None:
    wins = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    return round(wins / losses, 6) if losses else None


def summarize(events: list[dict], policy: str) -> dict:
    rows = [e["path_policies"][policy] for e in events]
    values = [float(r["net_pct"]) for r in rows]
    closed = [float(r["net_pct"]) for r in rows if not r["outcome"].startswith("CENSORED")]
    outcomes = Counter(r["outcome"] for r in rows)
    return {
        "trades": len(rows), "closed": len(closed),
        "positive": sum(v > 0 for v in values), "negative": sum(v < 0 for v in values),
        "flat": sum(abs(v) < 1e-12 for v in values),
        "stop_first": sum(r["outcome"].startswith("STOP") for r in rows),
        "expired_or_time": sum(r["outcome"].startswith("EXPIRED") or r["outcome"] == "TIME_EXIT" for r in rows),
        "censored": sum(r["outcome"].startswith("CENSORED") for r in rows),
        "same_bar_collisions": sum(bool(r.get("same_bar_collision")) for r in rows),
        "outcomes": dict(sorted(outcomes.items())),
        "net_pct_sum_marked": round(sum(values), 6),
        "expectancy_pct_marked": round(float(np.mean(values)), 6) if values else None,
        "median_pct_marked": round(float(np.median(values)), 6) if values else None,
        "profit_factor_marked": profit_factor(values),
        "closed_net_pct_sum": round(sum(closed), 6),
        "closed_expectancy_pct": round(float(np.mean(closed)), 6) if closed else None,
        "worst_pct": round(min(values), 6) if values else None,
        "best_pct": round(max(values), 6) if values else None,
    }


def aggregate(root: Path) -> dict:
    shards, duplicates = {}, []
    for path in sorted(root.glob("**/summary.json")):
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
                "unexpected_shards": unexpected, "duplicates": duplicates}
    for name, x in shards.items():
        if x.get("status") != "PRESSURE_REPLAY_PREFLIGHT_PASSED":
            raise RuntimeError(f"{name}: invalid status")
        if x["expected_symbols"] != x["completed_symbols"] or x["completed_symbols"] != 12:
            raise RuntimeError(f"{name}: incomplete symbols")
        if min(r["coverage_pct"] for r in x["coverage"]) < 98 or x["scan_count"] < 100:
            raise RuntimeError(f"{name}: incomplete data/time scan")
    events = sorted([e | {"shard": name} for name, x in shards.items() for e in x["signals"]],
                    key=lambda e: e["decision_time"])
    if not events:
        raise RuntimeError("no path-exit events")
    for e in events:
        if set(e.get("path_policies", {})) != set(PATH_POLICIES):
            raise RuntimeError("missing or unexpected path policy")
    hours = sum((__import__("pandas").Timestamp(x["replay_window"][1]) -
                 __import__("pandas").Timestamp(x["replay_window"][0])).total_seconds() / 3600
                for x in shards.values())
    dates = sorted({d for x in shards.values() for d in
                    (x["replay_window"][0][:10], x["replay_window"][1][:10])})
    active = sorted({e["decision_time"][:10] for e in events})
    return {
        "status": "PRESSURE_PATH_EXIT_PREFLIGHT_PASSED",
        "expected_shards": list(EXPECTED_SHARDS), "completed_shards": sorted(shards),
        "fee_pct": 0.20, "same_bar_policy": "conservative_stop_first",
        "atr_contract": "ATR(14) from last fully closed 1H; x0.6; entry floor",
        "replay_hours": hours, "observed_days": hours / 24, "replay_dates": dates,
        "signals": len(events), "signals_per_observed_day": round(len(events) / (hours / 24), 6),
        "active_dates": active, "active_date_ratio_pct": round(len(active) / len(dates) * 100, 6),
        "symbols_with_signals": sorted({e["symbol"] for e in events}),
        "mfe_pct_24h": {"mean": round(float(np.mean([e["mfe_pct_24h"] for e in events])), 6),
                         "median": round(float(np.median([e["mfe_pct_24h"] for e in events])), 6)},
        "mae_pct_24h": {"mean": round(float(np.mean([e["mae_pct_24h"] for e in events])), 6),
                         "median": round(float(np.median([e["mae_pct_24h"] for e in events])), 6)},
        "policies": {p: summarize(events, p) for p in PATH_POLICIES},
        "per_shard": {n: {"window": x["replay_window"], "signals": x["signal_count"],
                            "scan_count": x["scan_count"]} for n, x in shards.items()},
        "events": events,
        "limitations": "12-symbol fixed-window mechanism sample; no full-market reranking, capital slots, threshold selection or OOS.",
        "decision": "Do not promote an exit from this smoke; use it only to decide which mechanisms deserve full research.",
        "oos": "N/A: four fixed 2025 diagnostic windows.",
    }


def self_test() -> None:
    assert profit_factor([1, 2, -1]) == 3
    assert profit_factor([1, 2]) is None
    assert len(PATH_POLICIES) == 10 and "source_atr_trail" in PATH_POLICIES
    print(json.dumps({"self_test": "ok", "policies": PATH_POLICIES}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    if a.input_root is None or a.output is None:
        ap.error("--input-root and --output required")
    out = aggregate(a.input_root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if out["status"] != "PRESSURE_PATH_EXIT_PREFLIGHT_PASSED":
        raise RuntimeError(json.dumps(out))
    print(json.dumps({"status": out["status"], "signals": out["signals"]}))


if __name__ == "__main__":
    main()
