"""Frozen D6 closed-candle movement-decay protection replay.

This module never rescans entries or tunes parameters.  It reuses the locked
2024 RETRIGGER cohort, reproduces the original stop/target/expiry path, and
adds exactly one preregistered causal close-exit rule.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PREEXIT = PARENT / "retrigger_preexit_path"
sys.path.insert(0, str(PREEXIT))

import retrigger_preexit_path as base  # type: ignore

PREREG_PATH = HERE / "preregistration.json"
FEE_PCT = 0.20
TARGET_PCT = 0.50


def prereg() -> dict:
    p = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert p["status"] == "PREREGISTERED_NOT_RUN"
    assert p["immutable_contract"]["one_frozen_variant"] is True
    assert p["immutable_contract"]["no_parameter_sweep"] is True
    assert p["immutable_contract"]["no_30_or_60_minute_forced_gate"] is True
    assert p["immutable_contract"]["no_post_exit_or_future_peak_features"] is True
    assert p["frozen_rule"]["name"] == "D6_RELATIVE_DECAY_2X"
    assert p["development_stage"]["expected_events"] == 324
    assert p["action_budget_for_2024_path_replay"]["hard_runner_minute_ceiling_from_job_timeouts"] == 64
    return p


def _ret(a: float, b: float) -> float:
    return a / b - 1.0


def d6_state(closes: np.ndarray, quote: np.ndarray, taker: np.ndarray, i: int) -> dict | None:
    """Return the causal D6 vote at closed bar i; no future row is accessed."""
    if i < 6:
        return None
    recent_close_return = _ret(float(closes[i]), float(closes[i - 3]))
    previous_close_return = _ret(float(closes[i - 3]), float(closes[i - 6]))
    price_structure_loss = (
        float(closes[i]) < float(np.min(closes[i - 3:i]))
        and recent_close_return < 0.0
    )
    momentum_decay = (
        recent_close_return < previous_close_return
        and _ret(float(closes[i]), float(closes[i - 1])) <= 0.0
        and _ret(float(closes[i - 1]), float(closes[i - 2])) <= 0.0
    )
    recent_quote = float(np.sum(quote[i - 2:i + 1]))
    previous_quote = float(np.sum(quote[i - 5:i - 2]))
    volume_fade = recent_quote < previous_quote
    recent_taker_share = float(np.sum(taker[i - 2:i + 1])) / recent_quote if recent_quote > 0 else math.nan
    previous_taker_share = float(np.sum(taker[i - 5:i - 2])) / previous_quote if previous_quote > 0 else math.nan
    taker_fade = (
        math.isfinite(recent_taker_share)
        and math.isfinite(previous_taker_share)
        and recent_taker_share < previous_taker_share
        and recent_taker_share < 0.50
    )
    confirmations = int(momentum_decay) + int(volume_fade) + int(taker_fade)
    return {
        "price_structure_loss": bool(price_structure_loss),
        "momentum_decay": bool(momentum_decay),
        "volume_fade": bool(volume_fade),
        "taker_fade": bool(taker_fade),
        "confirmations": confirmations,
        "decay_vote": bool(price_structure_loss and confirmations >= 2),
        "recent_three_bar_return_pct": round(recent_close_return * 100, 8),
        "previous_three_bar_return_pct": round(previous_close_return * 100, 8),
        "recent_taker_share": round(recent_taker_share, 8) if math.isfinite(recent_taker_share) else None,
        "previous_taker_share": round(previous_taker_share, 8) if math.isfinite(previous_taker_share) else None,
    }


def protected_exit(record: dict, bars5: pd.DataFrame) -> dict:
    event = record["event"]
    expected = record["result"]["fixed_gross_0.50"]
    start = pd.Timestamp(event["decision_time"])
    entry, stop = float(event["entry"]), float(event["stop"])
    future = bars5[(bars5.open_time >= start) &
                   (bars5.open_time < start + pd.Timedelta(hours=24))].copy()
    if future.empty:
        raise RuntimeError(f"EMPTY_PATH:{event['symbol']}:{start}")

    reproduced = base.dm.fixed_target(bars5, start, entry, stop, TARGET_PCT)
    for field in ("outcome", "exit_time", "same_bar_collision"):
        if reproduced.get(field) != expected.get(field):
            raise RuntimeError(f"BASELINE_MISMATCH:{event['symbol']}:{start}:{field}")
    if not math.isclose(float(reproduced["net_pct"]), float(expected["net_pct"]), abs_tol=1e-6):
        raise RuntimeError(f"BASELINE_NET_MISMATCH:{event['symbol']}:{start}")

    closes = future.close.to_numpy(dtype=float)
    quote = future.quote_volume.to_numpy(dtype=float)
    taker = future.taker_quote.to_numpy(dtype=float)
    target = entry * (1 + TARGET_PCT / 100)
    consecutive_votes = 0
    vote_count = 0
    protected = None
    exit_index = None
    exit_state = None

    for i, row in enumerate(future.itertuples(index=False)):
        stop_hit = float(row.low) <= stop
        target_hit = float(row.high) >= target
        if stop_hit:
            gross = (stop / entry - 1) * 100
            protected = {"outcome": "STOP_FIRST", "gross_pct": round(gross, 6),
                         "net_pct": round(gross - FEE_PCT, 6),
                         "exit_time": str(pd.Timestamp(row.close_time)),
                         "same_bar_collision": bool(target_hit)}
            exit_index = i
            break
        if target_hit:
            protected = {"outcome": "TARGET_FIRST", "gross_pct": TARGET_PCT,
                         "net_pct": round(TARGET_PCT - FEE_PCT, 6),
                         "exit_time": str(pd.Timestamp(row.close_time)),
                         "same_bar_collision": False}
            exit_index = i
            break

        state = d6_state(closes, quote, taker, i)
        vote = bool(state and state["decay_vote"])
        vote_count += int(vote)
        consecutive_votes = consecutive_votes + 1 if vote else 0
        if consecutive_votes >= 2:
            gross = (float(row.close) / entry - 1) * 100
            protected = {"outcome": "DECAY_EXIT", "gross_pct": round(gross, 6),
                         "net_pct": round(gross - FEE_PCT, 6),
                         "exit_time": str(pd.Timestamp(row.close_time)),
                         "same_bar_collision": False}
            exit_index, exit_state = i, state
            break

    if protected is None:
        protected = dict(expected)
        matches = future.index[future.close_time == pd.Timestamp(expected["exit_time"])]
        if len(matches) != 1:
            raise RuntimeError(f"BASELINE_EXIT_BAR_MISSING:{event['symbol']}:{start}")
        exit_index = int(future.index.get_loc(matches[0]))

    used = future.iloc[:exit_index + 1]
    exit_time = pd.Timestamp(protected["exit_time"])
    if used.empty or pd.Timestamp(used.iloc[-1].close_time) != exit_time:
        raise RuntimeError(f"CAUSAL_EXIT_SLICE_FAILED:{event['symbol']}:{start}")
    post_exit_rows_used = int((used.close_time > exit_time).sum())
    if post_exit_rows_used:
        raise RuntimeError(f"POST_EXIT_LEAKAGE:{event['symbol']}:{start}")
    return {
        "quarter": record["quarter"], "event": event, "baseline": expected,
        "protected": protected,
        "diagnostic": {
            "bars_used": len(used), "post_exit_rows_used": post_exit_rows_used,
            "mfe_to_protected_exit_pct": round((float(used.high.max()) / entry - 1) * 100, 6),
            "mae_to_protected_exit_pct": round((float(used.low.min()) / entry - 1) * 100, 6),
            "decay_vote_bars": vote_count,
            "exit_state": exit_state,
        },
    }


def quarter_run(quarter: str, input_path: Path, output: Path) -> dict:
    prereg()
    records = base.load_quarter(input_path, quarter)
    paths, fetch = base.fetch_paths(records)
    analysed = [protected_exit(r, paths[r["event"]["symbol"]]) for r in records]
    out = {"status": "D6_QUARTER_COMPLETE", "quarter": quarter, "events": len(analysed),
           "baseline_outcomes": dict(Counter(r["baseline"]["outcome"] for r in analysed)),
           "protected_outcomes": dict(Counter(r["protected"]["outcome"] for r in analysed)),
           "fetch": fetch, "records": analysed}
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def metrics(records: list[dict], key: str) -> dict:
    vals = np.array([float(r[key]["net_pct"]) for r in records], dtype=float)
    positives, negatives = vals[vals > 0], vals[vals < 0]
    pf = float(positives.sum() / -negatives.sum()) if len(negatives) else math.inf
    return {"events": len(records), "positive": int((vals > 0).sum()),
            "zero": int((vals == 0).sum()), "negative": int((vals < 0).sum()),
            "net_pct_points": round(float(vals.sum()), 6),
            "expectancy_pct": round(float(vals.mean()), 6),
            "profit_factor": round(pf, 6) if math.isfinite(pf) else "INF",
            "negative_pnl_sum": round(float(negatives.sum()), 6),
            "worst_trade_pct": round(float(vals.min()), 6),
            "outcomes": dict(Counter(r[key]["outcome"] for r in records))}


def aggregate(input_root: Path, output: Path) -> dict:
    p = prereg()
    quarters = {}
    for fp in sorted(input_root.glob("**/summary.json")):
        x = json.loads(fp.read_text(encoding="utf-8"))
        if x.get("status") != "D6_QUARTER_COMPLETE":
            continue
        if x["quarter"] in quarters:
            raise RuntimeError(f"DUPLICATE_QUARTER:{x['quarter']}")
        quarters[x["quarter"]] = x
    if set(quarters) != {"Q1", "Q2", "Q3", "Q4"}:
        raise RuntimeError(f"INCOMPLETE_QUARTERS:{sorted(quarters)}")
    records = [r for q in sorted(quarters) for r in quarters[q]["records"]]
    if len(records) != 324 or len({base.event_key(r["event"]) for r in records}) != 324:
        raise RuntimeError(f"EVENT_INTEGRITY:{len(records)}")
    expected = p["development_stage"]["baseline_outcomes"]
    baseline_counts = Counter(r["baseline"]["outcome"].lower() for r in records)
    if dict(baseline_counts) != expected:
        raise RuntimeError(f"BASELINE_OUTCOMES:{dict(baseline_counts)}")
    if any(r["diagnostic"]["post_exit_rows_used"] for r in records):
        raise RuntimeError("POST_EXIT_LEAKAGE")

    baseline, protected = metrics(records, "baseline"), metrics(records, "protected")
    target_preservation = protected["outcomes"].get("TARGET_FIRST", 0) / baseline["outcomes"]["TARGET_FIRST"]
    neg_reduction = 1 - abs(float(protected["negative_pnl_sum"])) / abs(float(baseline["negative_pnl_sum"]))
    worst_reduction = 1 - abs(float(protected["worst_trade_pct"])) / abs(float(baseline["worst_trade_pct"]))
    quarter_compare = {}
    for q in sorted(quarters):
        rs = quarters[q]["records"]
        b, d = metrics(rs, "baseline"), metrics(rs, "protected")
        quarter_compare[q] = {"baseline_net": b["net_pct_points"], "protected_net": d["net_pct_points"],
                              "improved": d["net_pct_points"] > b["net_pct_points"]}
    gate = p["development_stage"]["minimum_gate_to_open_2025"]
    checks = {
        "exact_baseline_reproduction": baseline["net_pct_points"] == -80.270038,
        "net_improvement": protected["net_pct_points"] - baseline["net_pct_points"] >= gate["net_pct_point_improvement_min"],
        "profit_factor": float(protected["profit_factor"]) >= gate["profit_factor_min"],
        "target_preservation": target_preservation >= gate["baseline_target_first_preservation_min_ratio"],
        "negative_pnl_reduction": neg_reduction >= gate["negative_pnl_sum_reduction_min_ratio"],
        "worst_loss_reduction": worst_reduction >= gate["worst_loss_magnitude_reduction_min_ratio"],
        "quarter_improvement": sum(x["improved"] for x in quarter_compare.values()) >= gate["quarters_with_net_improvement_min"],
        "post_exit_rows_zero": True,
    }
    mfes = [r["diagnostic"]["mfe_to_protected_exit_pct"] for r in records]
    maes = [r["diagnostic"]["mae_to_protected_exit_pct"] for r in records]
    out = {"status": "D6_DEVELOPMENT_COMPLETE", "rule": "D6_RELATIVE_DECAY_2X",
           "window": p["development_stage"]["period"], "round_trip_cost_pct": FEE_PCT,
           "events": len(records), "signals_per_day": round(len(records) / 366, 6),
           "active_days": len({pd.Timestamp(r["event"]["decision_time"]).date() for r in records}),
           "active_day_ratio_pct": round(len({pd.Timestamp(r["event"]["decision_time"]).date() for r in records}) / 366 * 100, 6),
           "baseline": baseline, "protected": protected,
           "target_first_preservation_ratio": round(target_preservation, 6),
           "negative_pnl_reduction_ratio": round(neg_reduction, 6),
           "worst_loss_magnitude_reduction_ratio": round(worst_reduction, 6),
           "protected_mfe_mean_pct": round(float(np.mean(mfes)), 6),
           "protected_mae_mean_pct": round(float(np.mean(maes)), 6),
           "quarters": quarter_compare, "gate_checks": checks,
           "decision": "OPEN_2025_FORWARD" if all(checks.values()) else "REJECT_D6_NO_2025",
           "integrity": {"quarters": sorted(quarters), "duplicate_events": 0,
                         "post_exit_rows_used": 0, "baseline_reproduction": "exact"},
           "oos": "N/A: 2025 opens only if all development gates pass; 2026 remains sealed",
           "production_effect": "None; Clear System.py unchanged."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def _bars(rows: list[tuple[float, float, float, float, float]]) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    out = []
    for i, (o, h, l, c, q) in enumerate(rows):
        ot = start + pd.Timedelta(minutes=5 * i)
        out.append({"open_time": ot, "close_time": ot + pd.Timedelta(minutes=5) - pd.Timedelta(milliseconds=1),
                    "open": o, "high": h, "low": l, "close": c, "volume": q / 100,
                    "quote_volume": q, "taker_quote": q * (0.60 if i < 4 else 0.35)})
    return pd.DataFrame(out)


def self_test() -> None:
    rows = [(100, 100.2, 99.9, 100.1, 2000), (100.1, 100.3, 100, 100.2, 1900),
            (100.2, 100.4, 100.1, 100.3, 1800), (100.3, 100.35, 100.1, 100.2, 1700),
            (100.2, 100.25, 99.9, 100.0, 1300), (100, 100.05, 99.7, 99.8, 1100),
            (99.8, 99.85, 99.5, 99.6, 900), (99.6, 99.65, 99.3, 99.4, 700),
            (99.4, 100.7, 99.3, 100.6, 800)]
    bars = _bars(rows)
    event = {"symbol": "BTCUSDT", "decision_time": str(bars.iloc[0].open_time),
             "setup_kind": "RETRIGGER", "entry": 100.0, "stop": 95.0, "source_tp1": 101.0}
    baseline = base.dm.fixed_target(bars, pd.Timestamp(event["decision_time"]), 100.0, 95.0, 0.50)
    got = protected_exit({"quarter": "Q1", "event": event,
                          "result": {"fixed_gross_0.50": baseline}}, bars)
    assert got["protected"]["outcome"] == "DECAY_EXIT"
    assert got["protected"]["exit_time"] == str(bars.iloc[7].close_time)
    assert got["diagnostic"]["post_exit_rows_used"] == 0
    assert got["diagnostic"]["exit_state"]["confirmations"] >= 2
    assert baseline["outcome"] == "TARGET_FIRST"  # later bar, proving causal early exit
    target_bars = _bars(rows[:3] + [(100.3, 100.7, 100.2, 100.6, 1700)])
    target_event = dict(event)
    target_baseline = base.dm.fixed_target(target_bars, pd.Timestamp(event["decision_time"]), 100.0, 95.0, 0.50)
    target_got = protected_exit({"quarter": "Q1", "event": target_event,
                                 "result": {"fixed_gross_0.50": target_baseline}}, target_bars)
    assert target_got["protected"]["outcome"] == "TARGET_FIRST"
    print(json.dumps({"status": "SELF_TEST_OK", "decay": got["protected"],
                      "target_priority": target_got["protected"]}))


def smoke() -> None:
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    bars = base.helper.fetch("BTCUSDT", "5m", start, start + pd.Timedelta(hours=24))
    entry = float(bars.iloc[0].open)
    event = {"symbol": "BTCUSDT", "decision_time": str(start), "setup_kind": "RETRIGGER",
             "entry": entry, "stop": entry * 0.90, "source_tp1": entry * 1.01}
    baseline = base.dm.fixed_target(bars, start, entry, entry * 0.90, 0.50)
    got = protected_exit({"quarter": "Q1", "event": event,
                          "result": {"fixed_gross_0.50": baseline}}, bars)
    print(json.dumps({"status": "REAL_DATA_SMOKE_OK", "rows": len(bars),
                      "transport": bars.attrs.get("transports"), "baseline": got["baseline"],
                      "protected": got["protected"], "diagnostic": got["diagnostic"]}))


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
            ap.error("--input required")
        out = quarter_run(a.quarter, a.input, a.output)
        print(json.dumps({"status": out["status"], "quarter": out["quarter"],
                          "events": out["events"],
                          "baseline_outcomes": out["baseline_outcomes"],
                          "protected_outcomes": out["protected_outcomes"],
                          "fetch": {k: out["fetch"][k]
                                    for k in ("request_count", "rows", "symbols")}}))
    elif a.aggregate:
        if not a.input_root:
            ap.error("--input-root required")
        print(json.dumps(aggregate(a.input_root, a.output)))
    else:
        ap.error("select one mode")


if __name__ == "__main__":
    main()
