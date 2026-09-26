"""Read-only diagnostic of the archived Botum paper portfolio.

This reports observed subsets, not counterfactual fills or validated strategies.
No trading, network, or repository write occurs unless --output is supplied.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path


POLICIES = {
    "all_observed": lambda kind, regime: True,
    "pressure_observed": lambda kind, regime: kind == "PRESSURE",
    "pressure_plus_green_retrigger_observed":
        lambda kind, regime: kind == "PRESSURE" or (kind == "RETRIGGER" and regime == "GREEN"),
    "green_observed": lambda kind, regime: regime == "GREEN",
    "pressure_plus_other_green_observed":
        lambda kind, regime: kind == "PRESSURE" or regime == "GREEN",
}


def summarise(rows: list[dict], days: int) -> dict:
    returns = [float(r["close_pct"]) for r in rows]
    gains = sum(max(0.0, n) for n in returns)
    losses = sum(min(0.0, n) for n in returns)
    return {
        "signals": len(rows),
        "positive": sum(n > 0 for n in returns),
        "negative": sum(n < 0 for n in returns),
        "gross_winner_points": round(gains, 4),
        "gross_loser_points": round(losses, 4),
        "sum_net_trade_percentage_points": round(sum(returns), 4),
        "mean_net_pct_per_signal": round(sum(returns) / len(rows), 4) if rows else None,
        "profit_factor": round(gains / -losses, 4) if losses else None,
        "profit_factor_note": "undefined: no observed negative returns" if not losses else "",
        "worst_net_pct": min(returns) if returns else None,
        "signals_per_calendar_day": round(len(rows) / days, 4),
        "active_day_pct": round(100 * len({r["open_time"][:10] for r in rows}) / days, 4),
        "tp1_hit_count": sum(bool(r.get("tp1_hit")) for r in rows),
        "stop_exit_count": sum(r.get("close_reason") == "stop" for r in rows),
        "expired_count": sum(r.get("close_reason") == "expired" for r in rows),
        "mean_mfe_pct": round(sum(float(r["peak_pct"]) for r in rows) / len(rows), 4) if rows else None,
        "mean_mae_pct": round(sum(float(r["low_pct"]) for r in rows) / len(rows), 4) if rows else None,
    }


def audit(snapshot: dict) -> dict:
    records = snapshot["closed"]
    assert isinstance(records, list) and records, "no closed paper trades"
    assert not snapshot.get("open"), "open trades would require separate marking"
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)), "duplicate paper trade id"
    assert all(r["symbol"].endswith("/USDT") for r in records), "non-USDT record"
    assert all(abs(float(r["fee_pct"]) - 0.2) < 1e-8 for r in records), "fee differs from 0.20%"
    assert all(abs(float(r["gross_pct"]) - float(r["fee_pct"]) - float(r["close_pct"])) < .031
               for r in records), "gross/fee/net inconsistency"
    dates = [date.fromisoformat(r["open_time"][:10]) for r in records]
    days = (max(dates) - min(dates)).days + 1
    baseline = summarise(records, days)
    groups = {}
    for name, keep in POLICIES.items():
        chosen = [r for r in records if keep(r["extra"]["setup_kind"], r["extra"]["btc_regime"])]
        omitted = [r for r in records if r not in chosen]
        groups[name] = {
            **summarise(chosen, days),
            "omitted_positive": sum(float(r["close_pct"]) > 0 for r in omitted),
            "omitted_winner_points": round(sum(max(0.0, float(r["close_pct"])) for r in omitted), 4),
            "omitted_loser_points": round(sum(min(0.0, float(r["close_pct"])) for r in omitted), 4),
            "delta_points_vs_all_observed": round(sum(float(r["close_pct"]) for r in chosen)
                                                  - baseline["sum_net_trade_percentage_points"], 4),
            "by_open_day": {
                d: round(sum(float(r["close_pct"]) for r in chosen if r["open_time"][:10] == d), 4)
                for d in sorted({r["open_time"][:10] for r in chosen})
            },
        }
    by_kind_regime = defaultdict(list)
    for r in records:
        by_kind_regime[(r["extra"]["setup_kind"], r["extra"]["btc_regime"])].append(r)
    losses = sorted((r for r in records if float(r["close_pct"]) < 0),
                    key=lambda r: float(r["close_pct"]))
    target_ceiling = []
    for target in (.25, .35, .5, .8, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
        reached = [r for r in records if float(r["peak_pct"]) >= target]
        optimistic_points = sum(
            target - .2 if float(r["peak_pct"]) >= target else float(r["close_pct"])
            for r in records
        )
        target_ceiling.append({
            "gross_target_pct": target,
            "net_if_target_filled_pct": round(target - .2, 4),
            "observed_peak_reached_count": len(reached),
            "negative_trade_peaks_reached_count": sum(float(r["close_pct"]) < 0 for r in reached),
            "optimistic_sum_points": round(optimistic_points, 4),
            "interpretation": "optimistic peak ceiling only; NOT a first-passage or executable exit backtest",
        })
    return {
        "status": "PAPER_COHORT_DIAGNOSTIC_ONLY",
        "snapshot_time": snapshot.get("updated_at"),
        "period_open_dates": [str(min(dates)), str(max(dates))],
        "calendar_days": days,
        "cost_round_trip_pct": 0.2,
        "baseline": baseline,
        "observed_subsets": groups,
        "kind_regime_cells": {
            f"{kind}/{regime}": summarise(v, days)
            for (kind, regime), v in sorted(by_kind_regime.items())
        },
        "negative_trades": [
            {"symbol": r["symbol"], "open_time": r["open_time"],
             "kind": r["extra"]["setup_kind"], "btc_regime": r["extra"]["btc_regime"],
             "net_pct": r["close_pct"], "mfe_pct": r["peak_pct"],
             "mae_pct": r["low_pct"], "exit": r["close_reason"]}
            for r in losses
        ],
        "fixed_target_peak_ceiling_not_a_backtest": target_ceiling,
        "interpretation_limit": (
            "These are post-hoc subsets of emitted, closed paper trades. Removed signals can free daily "
            "quota and alter candidate selection; neither replacement signals nor new entry fills are "
            "recorded. MFE/MAE are post-entry observations and MUST NOT be used as pre-entry features. "
            "No OOS, historical expectancy, or real capital P&L can be inferred."
        ),
    }


def self_test() -> None:
    def row(name: str, kind: str, regime: str, net: float) -> dict:
        return {"id": name, "symbol": "TEST/USDT", "open_time": "2026-09-22T00:00:00+03:00",
                "gross_pct": net + .2, "fee_pct": .2, "close_pct": net,
                "peak_pct": max(net, 0), "low_pct": min(net, 0),
                "close_reason": "expired", "tp1_hit": False,
                "extra": {"setup_kind": kind, "btc_regime": regime}}
    sample = {"closed": [row("a", "PRESSURE", "YELLOW", 2),
                         row("b", "RETRIGGER", "GREEN", 1),
                         row("c", "RETRIGGER", "YELLOW", -3)], "open": []}
    s = audit(sample)
    assert s["baseline"]["sum_net_trade_percentage_points"] == 0
    assert s["baseline"]["expired_count"] == 3
    assert s["observed_subsets"]["pressure_plus_green_retrigger_observed"]["signals"] == 2
    assert s["observed_subsets"]["pressure_plus_green_retrigger_observed"]["omitted_loser_points"] == -3
    print("self-test ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.snapshot is None:
        parser.error("--snapshot required")
    report = audit(json.loads(args.snapshot.read_text(encoding="utf-8")))
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
