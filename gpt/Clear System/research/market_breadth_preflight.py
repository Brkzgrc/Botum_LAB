from __future__ import annotations

"""Bounded historical audit for a closed-candle market-breadth context."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REFERENCES = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")
data = None


def load_data_dependency() -> None:
    global data
    if data is None:
        import taker_flow_preflight as _data
        data = _data


def closed_frame(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    load_data_dependency()
    raw = data.fetch_15m(symbol, start, end)
    expected = int((end - start).total_seconds() // 900)
    x = raw[["close", "volume"]].copy()
    x.index = x.index + pd.Timedelta(minutes=15)
    x = x[~x.index.duplicated(keep="last")]
    return x, {
        "symbol": symbol,
        "rows": int(len(x)),
        "expected_rows": expected,
        "coverage_pct": float(len(x) / max(1, expected) * 100),
        "first_decision_time": str(x.index.min()),
        "last_decision_time": str(x.index.max()),
        "transports": raw.attrs.get("transports", []),
    }


def build_breadth(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    common = None
    for x in frames.values():
        common = x.index if common is None else common.intersection(x.index)
    if common is None or len(common) == 0:
        raise RuntimeError("no common closed-candle timeline")
    parts = []
    for symbol in REFERENCES:
        x = frames[symbol].reindex(common)
        ret1h = x.close.pct_change(4) * 100
        ret4h = x.close.pct_change(16) * 100
        prior_high16 = x.close.shift(1).rolling(16, min_periods=16).max()
        vol_ref = x.volume.shift(1).rolling(32, min_periods=16).mean()
        q = pd.DataFrame({
            (symbol, "pos1h"): (ret1h > 0).astype(float),
            (symbol, "pos4h"): (ret4h > 0).astype(float),
            (symbol, "high16"): (x.close > prior_high16).astype(float),
            (symbol, "vol_expand"): (x.volume > 1.20 * vol_ref).astype(float),
        }, index=common)
        parts.append(q)
    wide = pd.concat(parts, axis=1)
    out = pd.DataFrame(index=common)
    for feature in ("pos1h", "pos4h", "high16", "vol_expand"):
        out["breadth_" + feature] = wide.xs(feature, axis=1, level=1).mean(axis=1)
    out["breadth_accel"] = out.breadth_pos1h - out.breadth_pos1h.shift(4)
    state = (
        (out.breadth_pos1h >= 4 / 6)
        & (out.breadth_pos4h >= 3 / 6)
        & (out.breadth_accel >= 2 / 6)
        & ((out.breadth_high16 >= 2 / 6) | (out.breadth_vol_expand >= 3 / 6))
    )
    out["ignition"] = state & ~state.shift(1, fill_value=False)
    return out


def audit(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    frames, rows = {}, []
    for symbol in REFERENCES:
        frame, rec = closed_frame(symbol, start, end)
        frames[symbol] = frame
        rows.append(rec)
        print(json.dumps(rec), flush=True)
    breadth = build_breadth(frames)
    expected = int((end - start).total_seconds() // 900)
    valid = breadth[["breadth_pos1h", "breadth_pos4h", "breadth_high16",
                     "breadth_vol_expand", "breadth_accel"]].dropna()
    summary = {
        "status": "BREADTH_DATA_READY",
        "window": [str(start), str(end)],
        "references": list(REFERENCES),
        "reference_count": len(REFERENCES),
        "rows": rows,
        "common_rows": int(len(breadth)),
        "common_coverage_pct": float(len(breadth) / max(1, expected) * 100),
        "valid_feature_rows": int(len(valid)),
        "ignition_events": int(breadth.ignition.sum()),
        "ignition_active_days": int(breadth.index[breadth.ignition].floor("D").nunique()),
        "closed_candle_contract": "Raw open_time is shifted +15m; decision_time therefore sees only a closed 15m candle.",
        "decision": "Proceed only if coverage, closed-candle alignment, and ignition density pass.",
    }
    if len(rows) != len(REFERENCES):
        raise RuntimeError("reference cardinality mismatch")
    if min(r["coverage_pct"] for r in rows) < 95 or summary["common_coverage_pct"] < 95:
        raise RuntimeError("breadth historical coverage below 95%")
    if summary["ignition_events"] < 50 or summary["ignition_active_days"] < 30:
        raise RuntimeError("insufficient independent breadth ignitions")
    return summary


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=80, freq="15min", tz="UTC")
    frames = {}
    for n, symbol in enumerate(REFERENCES):
        close = 100 * np.cumprod(1 + np.where((np.arange(80) + n) % 12 < 7, 0.002, -0.001))
        frames[symbol] = pd.DataFrame({"close": close, "volume": 1000 + 100 * n}, index=idx)
    out = build_breadth(frames)
    assert len(out) == len(idx)
    assert out.breadth_pos1h.between(0, 1).all()
    assert out.breadth_pos4h.between(0, 1).all()
    assert int(out.ignition.sum()) > 0
    raw = pd.DataFrame({"close": [1.0], "volume": [1.0]}, index=pd.DatetimeIndex([idx[0]]))
    raw.index = raw.index + pd.Timedelta(minutes=15)
    assert raw.index[0] == idx[0] + pd.Timedelta(minutes=15)
    print(json.dumps({"self_test": "ok", "references": len(REFERENCES)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2026-09-18")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    start, end = pd.Timestamp(a.start, tz="UTC"), pd.Timestamp(a.end, tz="UTC")
    summary = audit(start, end)
    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "status", "reference_count", "common_rows", "common_coverage_pct",
        "ignition_events", "ignition_active_days")}), flush=True)


if __name__ == "__main__":
    main()
