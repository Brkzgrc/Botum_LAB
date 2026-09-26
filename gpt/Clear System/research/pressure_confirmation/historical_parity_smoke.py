"""Bounded closed-candle replay smoke for the archived Botum scanner.

This is a causality and data-feasibility check, NOT a strategy backtest.
Only historical 2025 15m Binance Spot candles are fetched. No order or POST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources" / "botum_2026-09-26"
RESEARCH = ROOT / "research"
SOURCE_SHA = {
    "spot_opportunity_scanner.py": "f93655b474cdf2126bde8cc043689bbc5c270dac",
    "tsi_bb_frozen_candidate.py": "d98f9b164f1f7df10bd7f65f77e8267a451166ff",
}
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LINKUSDT", "AVAXUSDT")
INTERVALS = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def verify_sources() -> None:
    for name, expected in SOURCE_SHA.items():
        content = (SOURCE / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != expected:
            raise RuntimeError(f"archived source mismatch: {name}: {actual}")


def closed_ohlcv(raw: pd.DataFrame, interval: str, decision: pd.Timestamp) -> pd.DataFrame:
    """Build completed bars from historical 15m opens, never from future data."""
    if interval not in INTERVALS or decision.tzinfo is None:
        raise ValueError("invalid interval or timezone-naive decision")
    minutes = MINUTES[interval]
    complete = raw[raw.index + pd.Timedelta(minutes=15) <= decision]
    if complete.empty:
        return pd.DataFrame()
    frame = complete.resample(INTERVALS[interval], label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "quote_volume": "sum", "taker_quote": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    frame = frame[frame.index + pd.Timedelta(minutes=minutes) <= decision]
    frame["open_time"] = frame.index
    frame["close_time"] = frame.index + pd.Timedelta(minutes=minutes) - pd.Timedelta(milliseconds=1)
    return frame.reset_index(drop=True)


def self_test() -> None:
    verify_sources()
    idx = pd.date_range("2025-01-01", periods=17, freq="15min", tz="UTC")
    raw = pd.DataFrame({"open": range(17), "high": range(17), "low": range(17),
                        "close": range(17), "volume": 1.0,
                        "quote_volume": 100.0, "taker_quote": 55.0}, index=idx)
    at = pd.Timestamp("2025-01-01 04:00", tz="UTC")
    assert len(closed_ohlcv(raw, "15m", at)) == 16
    assert len(closed_ohlcv(raw, "1h", at)) == 4
    assert len(closed_ohlcv(raw, "4h", at)) == 1
    assert len(closed_ohlcv(raw, "1d", at)) == 0
    assert closed_ohlcv(raw, "1h", at).iloc[-1].close == 15
    assert closed_ohlcv(raw, "15m", at).iloc[-1].close_time < at
    print(json.dumps({"self_test": "ok", "source_sha_checked": len(SOURCE_SHA)}))


def audit(start: pd.Timestamp, decision: pd.Timestamp, symbols: tuple[str, ...]) -> dict:
    verify_sources()
    if start.year != 2025 or decision.year != 2025 or decision - start < pd.Timedelta(days=210):
        raise ValueError("bounded 2025-only smoke requires >=210 historical days")
    if len(symbols) != len(set(symbols)) or not set(symbols).issubset(SYMBOLS):
        raise ValueError("unapproved or duplicate symbol")
    sys.path.insert(0, str(SOURCE))
    sys.path.insert(0, str(RESEARCH))
    import spot_opportunity_scanner as scanner  # type: ignore
    import taker_flow_preflight as data  # type: ignore

    results = []
    for symbol in symbols:
        raw = data.fetch_15m(symbol, start, decision + pd.Timedelta(minutes=30))
        expected = int((decision - start).total_seconds() // 900)
        coverage = len(raw[raw.index < decision]) / expected * 100
        if coverage < 98.0:
            raise RuntimeError(f"{symbol}: 15m coverage {coverage:.2f}% below 98%")
        current = decision

        def historical_ohlcv(requested: str, interval: str, limit: int = 240) -> pd.DataFrame:
            if requested != symbol:
                raise RuntimeError("unexpected symbol in historical scanner")
            frame = closed_ohlcv(raw, interval, current).tail(limit).reset_index(drop=True)
            if len(frame) < 80 or frame.close_time.iloc[-1] >= current:
                raise RuntimeError(f"open/incomplete historical {interval} candles")
            return frame

        def historical_get(path: str, params: dict | None = None) -> dict:
            if path != "/api/v3/ticker/price" or params != {"symbol": symbol}:
                raise RuntimeError("scanner attempted unexpected live API access")
            # Closed 15m price substitutes live ticker ONLY for diagnostic smoke.
            return {"price": str(historical_ohlcv(symbol, "15m").close.iloc[-1])}

        scanner.ohlcv = historical_ohlcv
        scanner._get = historical_get
        first = scanner.evaluate(symbol, 1e7, 100.0, "GREEN", None)
        if first.decision["decision"] == "ALIM_ADAYI":
            raise RuntimeError("first-scan entry forbidden")
        prior = {"phase": first.decision["state"],
                 "first_price": first.snapshot["live_price"],
                 "last_bar_15m": first.snapshot["15m"]["bar_id"]}
        current = decision + pd.Timedelta(minutes=15)
        second = scanner.evaluate(symbol, 1e7, 100.0, "GREEN", prior)
        if second.snapshot["15m"]["bar_id"] <= prior["last_bar_15m"]:
            raise RuntimeError("missing next closed 15m bar")
        result = {"symbol": symbol, "15m_rows": int(len(raw)), "coverage_pct": round(coverage, 4),
                  "first_phase": first.decision["state"], "next_phase": second.decision["state"],
                  "first_kind": first.decision["setup_kind"],
                  "next_kind": second.decision["setup_kind"],
                  "first_15m_bar": prior["last_bar_15m"],
                  "next_15m_bar": second.snapshot["15m"]["bar_id"],
                  "transports": raw.attrs.get("transports", [])}
        results.append(result)
        print(json.dumps(result), flush=True)
    if len(results) != len(symbols):
        raise RuntimeError("missing single-shard symbol output")
    return {
        "status": "HISTORICAL_SOURCE_PARITY_SMOKE_PASSED",
        "source_blob_shas": SOURCE_SHA,
        "period": [str(start), str(decision)],
        "expected_symbols": len(symbols), "completed_symbols": len(results),
        "expected_shards": 1, "completed_shards": 1,
        "fee_pct_for_next_outcome_study": .2,
        "symbols": results,
        "limitations": "Source decisions checked at two 2025 closed bars; not a historical trade or exit simulation. "
                       "Closed 15m price replaces unavailable historical live ticker, which requires future fill modeling.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--decision", default="2025-08-29T00:00:00Z")
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--outdir", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.outdir is None:
        ap.error("--outdir required")
    start = pd.Timestamp(a.start)
    decision = pd.Timestamp(a.decision)
    if start.tzinfo is None or decision.tzinfo is None:
        ap.error("start/decision must be timezone-aware")
    result = audit(start, decision, tuple(s.strip() for s in a.symbols.split(",") if s.strip()))
    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "completed_symbols": result["completed_symbols"]}), flush=True)


if __name__ == "__main__":
    main()
