from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

BASE_URLS = [
    "https://data-api.binance.vision", "https://api.binance.com",
    "https://api1.binance.com", "https://api2.binance.com", "https://api3.binance.com",
]


def get_json(path: str, params: dict, tries: int = 3):
    import requests
    last = None
    for _ in range(tries):
        for base in BASE_URLS:
            try:
                r = requests.get(base + path, params=params, timeout=30)
                if r.status_code == 200:
                    return r.json(), base
                last = RuntimeError("{} HTTP {}".format(base, r.status_code))
            except Exception as ex:
                last = ex
        time.sleep(0.2)
    raise RuntimeError("all Binance transports failed: {}".format(last))


def fetch_15m(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows, transports = [], set()
    cur = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000) - 1
    while cur <= end_ms:
        data, base = get_json("/api/v3/klines", {
            "symbol": symbol, "interval": "15m", "startTime": cur,
            "endTime": end_ms, "limit": 1000,
        })
        transports.add(base)
        if not data:
            break
        rows.extend(data)
        nxt = int(data[-1][0]) + 15 * 60 * 1000
        if nxt <= cur:
            break
        cur = nxt
        if len(data) < 1000:
            break
        time.sleep(0.015)
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
    if not rows:
        raise RuntimeError(symbol + ": no data")
    d = pd.DataFrame(rows, columns=cols).drop_duplicates("open_time").sort_values("open_time")
    for c in ["open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d.open_time, unit="ms", utc=True)
    d = d.set_index("time")
    d.attrs["transports"] = sorted(transports)
    return d


def audit_symbol(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    d = fetch_15m(symbol, start, end)
    base_share = d.taker_base / d.volume.replace(0, np.nan)
    quote_share = d.taker_quote / d.quote_volume.replace(0, np.nan)
    imbalance = 2 * base_share - 1
    price_ret = d.close.pct_change(4) * 100
    flow_delta = imbalance.rolling(4).mean() - imbalance.shift(4).rolling(4).mean()
    absorption = (price_ret < 0) & (imbalance.rolling(4).mean() > 0) & (flow_delta > 0)
    release = (d.close > d.high.shift(1).rolling(8).max()) & (flow_delta > 0) & (base_share > 0.5)
    valid = base_share.between(0, 1) & quote_share.between(0, 1)
    expected = int((end - start).total_seconds() // 900)
    return {
        "symbol": symbol, "rows": int(len(d)), "expected_rows": expected,
        "coverage_pct": float(len(d) / max(1, expected) * 100),
        "valid_share_pct": float(valid.mean() * 100),
        "base_quote_share_mae": float((base_share - quote_share).abs().dropna().mean()),
        "buy_share_mean": float(base_share.mean()),
        "buy_share_std": float(base_share.std()),
        "absorption_events": int(absorption.sum()),
        "release_events": int(release.sum()),
        "transports": d.attrs.get("transports", []),
    }


def self_test() -> None:
    idx = pd.date_range("2026-01-01", periods=8, freq="15min", tz="UTC")
    d = pd.DataFrame({"volume": [100.0] * 8, "quote_volume": [10000.0] * 8,
                      "taker_base": [60.0] * 8, "taker_quote": [6000.0] * 8}, index=idx)
    b = d.taker_base / d.volume
    q = d.taker_quote / d.quote_volume
    assert np.allclose(b, 0.6) and np.allclose(q, 0.6)
    assert ((2 * b - 1) > 0).all()
    print(json.dumps({"self_test": "ok", "buy_share": 0.6}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,LINKUSDT,AVAXUSDT")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2026-09-18")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    start, end = pd.Timestamp(a.start, tz="UTC"), pd.Timestamp(a.end, tz="UTC")
    symbols = [x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    rows, errors = [], []
    for symbol in symbols:
        try:
            rec = audit_symbol(symbol, start, end)
            rows.append(rec)
            print(json.dumps(rec), flush=True)
        except Exception as ex:
            errors.append({"symbol": symbol, "error": type(ex).__name__ + ":" + str(ex)})
    if errors:
        raise RuntimeError(json.dumps(errors))
    if len(rows) != len(symbols):
        raise RuntimeError("symbol cardinality mismatch")
    if min(r["coverage_pct"] for r in rows) < 95:
        raise RuntimeError("historical coverage below 95%")
    if min(r["valid_share_pct"] for r in rows) < 99.9:
        raise RuntimeError("invalid taker-share values")
    if sum(r["absorption_events"] + r["release_events"] for r in rows) < 100:
        raise RuntimeError("insufficient movement events")
    summary = {
        "status": "TAKER_FLOW_DATA_READY", "window": [str(start), str(end)],
        "symbols": len(rows), "rows": rows,
        "decision": "Proceed to causal taker-flow absorption/release research only if this audit passes.",
    }
    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
