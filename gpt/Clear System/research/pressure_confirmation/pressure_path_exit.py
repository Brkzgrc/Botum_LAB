"""Causal path-dependent exits for archived PRESSURE replay events.

All decisions use completed 5m/15m bars after entry.  The source policy mirrors
the paper tracker: structural stop before TP1, then ATR(14, closed 1H) x 0.6
trailing with an entry floor.  Research cost is always 0.20% round trip.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import numpy as np
import pandas as pd

FEE_PCT = 0.20
PATH_POLICIES = (
    "source_atr_trail",
    "protect_0.50_floor_0.20",
    "protect_0.80_floor_0.20",
    "mfe1_giveback0.50_floor0.20",
    "staged50_0.50_then_1.50_floor0.20",
    "motion_fade_after0.50",
    "time_6h", "time_12h", "time_24h", "time_48h",
)


def result(outcome: str, gross: float, when, collision: bool = False, **extra) -> dict:
    return {"outcome": outcome, "gross_pct": round(float(gross), 6),
            "net_pct": round(float(gross) - FEE_PCT, 6),
            "exit_time": str(when), "same_bar_collision": bool(collision), **extra}


def future_bars(bars: pd.DataFrame, entry_time: pd.Timestamp, hours: int = 72) -> pd.DataFrame:
    out = bars[(bars.open_time >= entry_time) &
               (bars.open_time < entry_time + pd.Timedelta(hours=hours))]
    if out.empty:
        raise RuntimeError("missing future 5m bars for path exit")
    return out


def closed_hour_atr(raw15: pd.DataFrame) -> pd.Series:
    x = raw15.set_index("open_time").resample("1h", label="left", closed="left").agg(
        {"high": "max", "low": "min", "close": "last"}).dropna()
    prev = x.close.shift(1)
    tr = pd.concat((x.high - x.low, (x.high - prev).abs(), (x.low - prev).abs()), axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    atr.index = atr.index + pd.Timedelta(hours=1)
    return atr.dropna()


def atr_at(atr: pd.Series, when: pd.Timestamp) -> float | None:
    z = atr[atr.index <= when]
    return float(z.iloc[-1]) if len(z) and np.isfinite(z.iloc[-1]) else None


def source_atr_trail(bars5: pd.DataFrame, raw15: pd.DataFrame, entry_time: pd.Timestamp,
                     entry: float, stop: float, tp1: float) -> dict:
    """Paper-tracker semantics, with closed-1H ATR instead of its open-1H API bar."""
    bars = future_bars(bars5, entry_time)
    atrs = closed_hour_atr(raw15)
    armed, peak = False, entry
    for row in bars.itertuples(index=False):
        high, low, close = float(row.high), float(row.low), float(row.close)
        peak = max(peak, high)
        if not armed:
            if low <= stop:
                collision = high >= tp1
                gross = (min(close, stop) / entry - 1) * 100
                return result("STOP_AMBIGUOUS" if collision else "STOP_FIRST", gross,
                              row.close_time, collision)
            if high >= tp1:
                armed = True
        if armed:
            atr = atr_at(atrs, pd.Timestamp(row.open_time))
            trail = max(entry, peak - 0.6 * atr) if atr else max(entry, peak * (1 - 0.0184))
            if close <= trail:
                gross = (min(close, trail) / entry - 1) * 100
                return result("TRAIL", gross, row.close_time, trail_level=trail)
        elif pd.Timestamp(row.close_time) >= entry_time + pd.Timedelta(hours=24):
            return result("EXPIRED", (close / entry - 1) * 100, row.close_time)
    last = bars.iloc[-1]
    return result("CENSORED_AFTER_TP1" if armed else "CENSORED", (float(last.close) / entry - 1) * 100,
                  last.close_time)


def protected_floor(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float, stop: float,
                    arm_pct: float, floor_pct: float) -> dict:
    bars = future_bars(bars5, entry_time, 24)
    target, floor = entry * (1 + arm_pct / 100), entry * (1 + floor_pct / 100)
    armed = False
    for row in bars.itertuples(index=False):
        high, low = float(row.high), float(row.low)
        if not armed and low <= stop:
            collision = high >= target
            gross = (stop / entry - 1) * 100
            return result("STOP_AMBIGUOUS" if collision else "STOP_FIRST", gross,
                          row.close_time, collision)
        if not armed and high >= target:
            armed = True
            if low <= floor:
                return result("PROTECTED_AMBIGUOUS", floor_pct, row.close_time, True)
        elif armed and low <= floor:
            return result("PROTECTED_FLOOR", floor_pct, row.close_time)
    last = bars.iloc[-1]
    return result("EXPIRED", (float(last.close) / entry - 1) * 100, last.close_time)


def mfe_giveback(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float, stop: float) -> dict:
    bars = future_bars(bars5, entry_time, 24)
    arm, floor = entry * 1.01, entry * 1.002
    armed, peak = False, entry
    for row in bars.itertuples(index=False):
        high, low = float(row.high), float(row.low)
        if not armed and low <= stop:
            collision = high >= arm
            return result("STOP_AMBIGUOUS" if collision else "STOP_FIRST",
                          (stop / entry - 1) * 100, row.close_time, collision)
        if not armed and high >= arm:
            armed = True
            peak = high
            if low <= floor:
                return result("GIVEBACK_AMBIGUOUS", 0.20, row.close_time, True)
            continue
        if armed:
            trail = max(floor, peak - entry * 0.005)
            if low <= trail:
                return result("MFE_GIVEBACK", (trail / entry - 1) * 100, row.close_time,
                              trail_level=trail)
            peak = max(peak, high)
    last = bars.iloc[-1]
    return result("EXPIRED", (float(last.close) / entry - 1) * 100, last.close_time)


def staged(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float, stop: float) -> dict:
    bars = future_bars(bars5, entry_time, 24)
    first, final, floor = entry * 1.005, entry * 1.015, entry * 1.002
    partial = False
    for row in bars.itertuples(index=False):
        high, low = float(row.high), float(row.low)
        if not partial and low <= stop:
            collision = high >= first
            return result("STOP_AMBIGUOUS" if collision else "STOP_FIRST",
                          (stop / entry - 1) * 100, row.close_time, collision, partial=False)
        if not partial and high >= first:
            partial = True
            if low <= floor:
                gross = 0.5 * 0.50 + 0.5 * 0.20
                return result("STAGED_FLOOR_AMBIGUOUS", gross, row.close_time, True, partial=True)
        if partial:
            hit_floor, hit_final = low <= floor, high >= final
            if hit_floor and hit_final:
                gross = 0.5 * 0.50 + 0.5 * 0.20
                return result("STAGED_AMBIGUOUS", gross, row.close_time, True, partial=True)
            if hit_floor:
                gross = 0.5 * 0.50 + 0.5 * 0.20
                return result("STAGED_FLOOR", gross, row.close_time, partial=True)
            if hit_final:
                gross = 0.5 * 0.50 + 0.5 * 1.50
                return result("STAGED_FINAL", gross, row.close_time, partial=True)
    last = bars.iloc[-1]
    last_gross = (float(last.close) / entry - 1) * 100
    gross = 0.5 * 0.50 + 0.5 * last_gross if partial else last_gross
    return result("EXPIRED_PARTIAL" if partial else "EXPIRED", gross, last.close_time, partial=partial)


def fade_times(raw15: pd.DataFrame) -> set[pd.Timestamp]:
    x = raw15.copy().sort_values("open_time")
    e12 = x.close.ewm(span=12, adjust=False).mean()
    e26 = x.close.ewm(span=26, adjust=False).mean()
    hist = (e12 - e26) - (e12 - e26).ewm(span=9, adjust=False).mean()
    obv = (np.sign(x.close.diff()).fillna(0) * x.volume).cumsum()
    price_down = (x.close < x.close.shift(1)) & (x.close.shift(1) < x.close.shift(2))
    momentum_down = (hist < hist.shift(1)) & (hist.shift(1) < hist.shift(2))
    volume_weak = (x.volume < x.volume.shift(1).rolling(20, min_periods=10).mean()) | (obv < obv.shift(2))
    return set(pd.to_datetime(x.loc[price_down & momentum_down & volume_weak, "close_time"], utc=True))


def motion_fade(bars5: pd.DataFrame, raw15: pd.DataFrame, entry_time: pd.Timestamp,
                entry: float, stop: float) -> dict:
    bars = future_bars(bars5, entry_time, 24)
    fades, arm = fade_times(raw15), entry * 1.005
    armed = False
    for row in bars.itertuples(index=False):
        high, low, close = float(row.high), float(row.low), float(row.close)
        if not armed and low <= stop:
            collision = high >= arm
            return result("STOP_AMBIGUOUS" if collision else "STOP_FIRST",
                          (stop / entry - 1) * 100, row.close_time, collision)
        if high >= arm:
            armed = True
        if armed and pd.Timestamp(row.close_time) in fades:
            return result("MOTION_FADE", (close / entry - 1) * 100, row.close_time)
    last = bars.iloc[-1]
    return result("EXPIRED", (float(last.close) / entry - 1) * 100, last.close_time)


def time_exit(bars5: pd.DataFrame, entry_time: pd.Timestamp, entry: float,
              stop: float, hours: int) -> dict:
    bars = future_bars(bars5, entry_time, hours)
    for row in bars.itertuples(index=False):
        if float(row.low) <= stop:
            return result("STOP_FIRST", (stop / entry - 1) * 100, row.close_time)
    last = bars.iloc[-1]
    return result("TIME_EXIT", (float(last.close) / entry - 1) * 100, last.close_time)


def evaluate_all(bars5: pd.DataFrame, raw15: pd.DataFrame, entry_time: pd.Timestamp,
                 entry: float, stop: float, tp1: float) -> dict[str, dict]:
    return {
        "source_atr_trail": source_atr_trail(bars5, raw15, entry_time, entry, stop, tp1),
        "protect_0.50_floor_0.20": protected_floor(bars5, entry_time, entry, stop, .50, .20),
        "protect_0.80_floor_0.20": protected_floor(bars5, entry_time, entry, stop, .80, .20),
        "mfe1_giveback0.50_floor0.20": mfe_giveback(bars5, entry_time, entry, stop),
        "staged50_0.50_then_1.50_floor0.20": staged(bars5, entry_time, entry, stop),
        "motion_fade_after0.50": motion_fade(bars5, raw15, entry_time, entry, stop),
        "time_6h": time_exit(bars5, entry_time, entry, stop, 6),
        "time_12h": time_exit(bars5, entry_time, entry, stop, 12),
        "time_24h": time_exit(bars5, entry_time, entry, stop, 24),
        "time_48h": time_exit(bars5, entry_time, entry, stop, 48),
    }


def self_test() -> None:
    t = pd.date_range("2025-01-01", periods=36, freq="5min", tz="UTC")
    bars = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(minutes=5),
                         "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0})
    bars.loc[1, ["high", "low", "close"]] = [100.6, 100.3, 100.5]
    bars.loc[2, ["low", "close"]] = [100.1, 100.2]
    p = protected_floor(bars, t[0], 100, 95, .5, .2)
    assert p["outcome"] == "PROTECTED_FLOOR" and p["net_pct"] == 0
    q = staged(bars, t[0], 100, 95)
    assert q["partial"] and q["net_pct"] == 0.15
    s = time_exit(bars, t[0], 100, 95, 6)
    assert s["outcome"] == "TIME_EXIT"
    assert set(evaluate_all.__annotations__) >= {"bars5", "raw15", "entry_time"}
    print(json.dumps({"self_test": "ok", "policies": PATH_POLICIES,
                      "fee_pct": FEE_PCT, "closed_candle_only": True}))


if __name__ == "__main__":
    self_test()
