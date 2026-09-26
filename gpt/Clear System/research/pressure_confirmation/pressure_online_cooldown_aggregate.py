"""Aggregate online cooldown/quota replacement smoke shards."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

EXPECTED = (0, 6, 24, 48)


def identity(event: dict) -> tuple[str, str]:
    return event["symbol"], event["decision_time"]


def aggregate(root: Path) -> dict:
    shards = {}
    duplicates = []
    for path in sorted(root.glob("**/summary.json")):
        x = json.loads(path.read_text())
        hours = int(x.get("online_cooldown_hours", -1))
        if hours in shards:
            duplicates.append(hours)
        shards[hours] = x
    missing = sorted(set(EXPECTED) - set(shards))
    unexpected = sorted(set(shards) - set(EXPECTED))
    if missing or unexpected or duplicates:
        return {"status": "INCOMPLETE_SHARDS", "expected_cooldowns": list(EXPECTED),
                "completed_cooldowns": sorted(shards), "missing": missing,
                "unexpected": unexpected, "duplicates": duplicates}
    windows = {tuple(x["replay_window"]) for x in shards.values()}
    if len(windows) != 1:
        raise RuntimeError("cooldown shards used different replay windows")
    for hours, x in shards.items():
        if x["status"] != "PRESSURE_REPLAY_PREFLIGHT_PASSED":
            raise RuntimeError(f"cooldown {hours}: invalid status")
        if x["expected_symbols"] != x["completed_symbols"] or x["completed_symbols"] != 12:
            raise RuntimeError(f"cooldown {hours}: incomplete symbols")
        if min(r["coverage_pct"] for r in x["coverage"]) < 98 or x["scan_count"] < 100:
            raise RuntimeError(f"cooldown {hours}: incomplete data/time scan")
    baseline = {identity(e) for e in shards[0]["signals"]}
    comparison = {}
    for hours in EXPECTED:
        x = shards[hours]
        ids = {identity(e) for e in x["signals"]}
        events = x["signals"]
        dates = {e["decision_time"][:10] for e in events}
        comparison[str(hours)] = {
            "signals": len(events),
            "signals_per_observed_day": round(len(events) / 1.5, 6),
            "active_dates": sorted(dates),
            "active_date_ratio_pct": round(len(dates) / 2 * 100, 6),
            "symbols": dict(sorted(Counter(e["symbol"] for e in events).items())),
            "setups": dict(sorted(Counter(e["setup_kind"] for e in events).items())),
            "final_candidates": x["final_candidates"],
            "cooldown_blocked_observations": x["cooldown_blocked"],
            "quota_blocked_observations": x["quota_blocked"],
            "removed_vs_baseline": sorted([list(v) for v in baseline - ids]),
            "replacement_vs_baseline": sorted([list(v) for v in ids - baseline]),
            "mfe_pct_24h_mean": round(float(np.mean([e["mfe_pct_24h"] for e in events])), 6) if events else None,
            "mae_pct_24h_mean": round(float(np.mean([e["mae_pct_24h"] for e in events])), 6) if events else None,
            "policy_summary": x["policy_summary"],
            "events": events,
        }
    return {
        "status": "PRESSURE_ONLINE_COOLDOWN_PREFLIGHT_PASSED",
        "expected_cooldowns": list(EXPECTED), "completed_cooldowns": sorted(shards),
        "replay_window": list(next(iter(windows))), "observed_days": 1.5,
        "symbols_per_shard": 12, "fee_pct": 0.20,
        "same_bar_policy": "conservative_stop_first",
        "comparison": comparison,
        "limitations": "Online daily quota and candidate replacement are replayed inside the 12-symbol set. "
                       "Open-position capital slots, full-market universe replacement and 2026 OOS are not modeled.",
        "decision": "Mechanism smoke only; do not select cooldown/exit thresholds or change production.",
        "oos": "N/A: one fixed 2025 mechanism window.",
    }


def self_test() -> None:
    a = {"symbol": "AAAUSDT", "decision_time": "2025-01-01T00:00:00Z"}
    b = {"symbol": "AAAUSDT", "decision_time": "2025-01-01T01:00:00Z"}
    c = {"symbol": "BBBUSDT", "decision_time": "2025-01-01T01:00:00Z"}
    base, changed = {identity(x) for x in (a, b)}, {identity(x) for x in (a, c)}
    assert base - changed == {identity(b)}
    assert changed - base == {identity(c)}
    assert len(EXPECTED) == 4 and 0 in EXPECTED
    print(json.dumps({"self_test": "ok", "cooldowns": EXPECTED}))


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
    if result["status"] != "PRESSURE_ONLINE_COOLDOWN_PREFLIGHT_PASSED":
        raise RuntimeError(json.dumps(result))
    print(json.dumps({"status": result["status"],
                      "signals": {k: v["signals"] for k, v in result["comparison"].items()}}))


if __name__ == "__main__":
    main()
