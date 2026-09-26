"""Bounded historical replay preflight for the archived PRESSURE scanner.

This validates time ordering, watch state, ranking/quota and 5m first passage.
It is deliberately not a strategy selection or OOS performance test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources" / "botum_2026-09-26"
SOURCE_SHA = {
    "spot_opportunity_scanner.py": "f93655b474cdf2126bde8cc043689bbc5c270dac",
    "tsi_bb_frozen_candidate.py": "d98f9b164f1f7df10bd7f65f77e8267a451166ff",
}
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LINKUSDT", "AVAXUSDT")
APPROVED_SYMBOLS = SYMBOLS + ("BNBUSDT", "DOGEUSDT", "ADAUSDT", "TRXUSDT", "LTCUSDT", "SUIUSDT")
BASE_URLS = ("https://data-api.binance.vision", "https://api.binance.com")
RULES = {"source_tp1": None, "fixed_0.25": 0.25, "fixed_0.50": 0.50,
         "fixed_0.80": 0.80, "fixed_1.00": 1.00, "fixed_1.50": 1.50,
         "fixed_2.00": 2.00, "fixed_3.00": 3.00, "fixed_5.00": 5.00}
FEE_PCT = 0.20


def verify_sources() -> None:
    for name, expected in SOURCE_SHA.items():
        content = (SOURCE / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != expected:
            raise RuntimeError(f"archived source mismatch: {name}: {actual}")


def get_json(path: str, params: dict, tries: int = 3):
    import requests
    last = None
    for _ in range(tries):
        for base in BASE_URLS:
            try:
                r = requests.get(base + path, params=params, timeout=30)
                if r.status_code == 200:
                    return r.json(), base
                last = RuntimeError(f"{base} HTTP {r.status_code}")
            except Exception as exc:
                last = exc
        time.sleep(0.2)
    raise RuntimeError(f"all Binance transports failed: {last}")


def fetch(symbol: str, interval: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    step_ms = {"5m": 300_000, "15m": 900_000}[interval]
    rows, transports = [], set()
    cur, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000) - 1
    while cur <= end_ms:
        data, base = get_json("/api/v3/klines", {"symbol": symbol, "interval": interval,
                              "startTime": cur, "endTime": end_ms, "limit": 1000})
        transports.add(base)
        if not data:
            break
        rows.extend(data)
        nxt = int(data[-1][0]) + step_ms
        if nxt <= cur:
            raise RuntimeError(f"{symbol} {interval}: non-advancing pagination")
        cur = nxt
        if len(data) < 1000:
            break
        time.sleep(0.012)
    if not rows:
        raise RuntimeError(f"{symbol} {interval}: no data")
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
    d = pd.DataFrame(rows, columns=cols).drop_duplicates("open_time").sort_values("open_time")
    for c in ("open", "high", "low", "close", "volume", "quote_volume", "taker_quote"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["open_time"] = pd.to_datetime(d.open_time, unit="ms", utc=True)
    d["close_time"] = pd.to_datetime(d.close_time, unit="ms", utc=True)
    d = d.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
    d.attrs["transports"] = sorted(transports)
    return d


def build_frames(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    x = raw.set_index("open_time")
    out = {}
    for interval, freq, minutes in (("15m", "15min", 15), ("1h", "1h", 60),
                                    ("4h", "4h", 240), ("1d", "1D", 1440)):
        d = x.resample(freq, label="left", closed="left").agg({
            "open": "first", "high": "max", "low": "min", "close": "last",
            "volume": "sum", "quote_volume": "sum", "taker_quote": "sum",
        }).dropna(subset=["open", "high", "low", "close"])
        d["open_time"] = d.index
        d["close_time"] = d.index + pd.Timedelta(minutes=minutes) - pd.Timedelta(milliseconds=1)
        out[interval] = d.reset_index(drop=True)
    return out


def first_passage(bars: pd.DataFrame, entry_time: pd.Timestamp, entry: float,
                  stop: float, target: float, horizon_h: int = 24) -> dict:
    future = bars[(bars.open_time >= entry_time) &
                  (bars.open_time < entry_time + pd.Timedelta(hours=horizon_h))]
    if future.empty:
        raise RuntimeError("missing future 5m bars")
    for row in future.itertuples(index=False):
        hit_stop, hit_target = float(row.low) <= stop, float(row.high) >= target
        if hit_stop and hit_target:
            gross, outcome = (stop / entry - 1) * 100, "STOP_AMBIGUOUS"
            return {"outcome": outcome, "gross_pct": gross, "net_pct": gross - FEE_PCT,
                    "exit_time": str(row.close_time), "same_bar_collision": True}
        if hit_stop:
            gross = (stop / entry - 1) * 100
            return {"outcome": "STOP_FIRST", "gross_pct": gross, "net_pct": gross - FEE_PCT,
                    "exit_time": str(row.close_time), "same_bar_collision": False}
        if hit_target:
            gross = (target / entry - 1) * 100
            return {"outcome": "TARGET_FIRST", "gross_pct": gross, "net_pct": gross - FEE_PCT,
                    "exit_time": str(row.close_time), "same_bar_collision": False}
    last = future.iloc[-1]
    gross = (float(last.close) / entry - 1) * 100
    return {"outcome": "EXPIRED", "gross_pct": gross, "net_pct": gross - FEE_PCT,
            "exit_time": str(last.close_time), "same_bar_collision": False}


def self_test() -> None:
    verify_sources()
    t = pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC")
    bars = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(minutes=5),
                         "open": [100, 100, 100], "high": [101, 103, 100.5],
                         "low": [99.5, 97, 99.5], "close": [100, 101, 100]})
    a = first_passage(bars.iloc[:1], t[0], 100, 98, 101)
    b = first_passage(bars.iloc[1:2], t[1], 100, 98, 102)
    c = first_passage(bars.iloc[2:], t[2], 100, 98, 102)
    assert a["outcome"] == "TARGET_FIRST" and round(a["net_pct"], 6) == 0.8
    assert b["outcome"] == "STOP_AMBIGUOUS" and b["same_bar_collision"]
    assert c["outcome"] == "EXPIRED" and round(c["net_pct"], 6) == -0.2
    raw = pd.DataFrame({"open_time": pd.date_range("2025-01-01", periods=17, freq="15min", tz="UTC"),
                        "open": range(17), "high": range(17), "low": range(17),
                        "close": range(17), "volume": 1.0, "quote_volume": 100.0,
                        "taker_quote": 55.0})
    frames = build_frames(raw)
    assert len(frames["1h"]) == 5 and len(frames["4h"]) == 2
    print(json.dumps({"self_test": "ok", "source_sha_checked": len(SOURCE_SHA),
                      "same_bar_policy": "conservative_stop_first"}))


def replay(history_start: pd.Timestamp, replay_start: pd.Timestamp,
           replay_end: pd.Timestamp, symbols: tuple[str, ...],
           require_signal: bool = True, cooldown_hours: int = 0) -> dict:
    verify_sources()
    if replay_start.year != 2025 or replay_end.year != 2025:
        raise ValueError("bounded 2025 replay windows required")
    if replay_start - history_start < pd.Timedelta(days=100):
        raise ValueError("at least 100 closed daily bars of warmup required")
    if not history_start < replay_start < replay_end or replay_end - replay_start > pd.Timedelta(hours=48):
        raise ValueError("replay window must be positive and <=48h")
    if not 6 <= len(symbols) <= len(APPROVED_SYMBOLS) or len(set(symbols)) != len(symbols):
        raise ValueError("six-to-twelve unique symbols required")
    if not set(symbols).issubset(APPROVED_SYMBOLS):
        raise ValueError("unapproved symbol in bounded replay")
    if cooldown_hours not in {0, 6, 12, 24, 48}:
        raise ValueError("unapproved online cooldown")
    sys.path.insert(0, str(SOURCE))
    import spot_opportunity_scanner as scanner  # type: ignore

    raw15, raw5, frames, coverage = {}, {}, {}, []
    data_end = replay_end + pd.Timedelta(hours=24, minutes=15)
    for symbol in symbols:
        r15 = fetch(symbol, "15m", history_start, data_end)
        r5 = fetch(symbol, "5m", replay_start, replay_end + pd.Timedelta(hours=24))
        raw15[symbol], raw5[symbol], frames[symbol] = r15, r5, build_frames(r15)
        expected = int((data_end - history_start).total_seconds() // 900)
        cov = len(r15) / expected * 100
        if cov < 98:
            raise RuntimeError(f"{symbol}: 15m coverage {cov:.2f}%")
        coverage.append({"symbol": symbol, "rows_15m": len(r15), "coverage_pct": round(cov, 4),
                         "rows_5m": len(r5), "transports": r15.attrs.get("transports", [])})

    current = replay_start

    def historical_ohlcv(symbol: str, interval: str, limit: int = 240) -> pd.DataFrame:
        d = frames[symbol][interval]
        d = d[d.close_time < current].tail(limit).reset_index(drop=True)
        if len(d) < 80 or d.close_time.iloc[-1] >= current:
            raise RuntimeError(f"{symbol} {interval}: incomplete/insufficient historical bars")
        return d

    def historical_get(path: str, params: dict | None = None):
        if path != "/api/v3/ticker/price" or not params or params.get("symbol") not in symbols:
            raise RuntimeError("unexpected live API access")
        symbol = params["symbol"]
        return {"price": str(historical_ohlcv(symbol, "15m").close.iloc[-1])}

    scanner.ohlcv, scanner._get = historical_ohlcv, historical_get
    watch: dict[str, dict] = {}
    daily_count: dict[str, int] = {}
    last_signal_at: dict[str, pd.Timestamp] = {}
    signals, scan_count = [], 0
    final_candidates = cooldown_blocked = quota_blocked = 0
    while current <= replay_end:
        scan_count += 1
        day = current.strftime("%Y-%m-%d")
        dead = [s for s, rec in watch.items()
                if current - pd.Timestamp(rec["first_seen"]) > pd.Timedelta(hours=18)]
        for symbol in dead:
            watch.pop(symbol, None)
        regime = scanner.btc_regime()
        candidates = []
        for symbol in symbols:
            q = raw15[symbol]
            qv = float(q[(q.open_time >= current - pd.Timedelta(hours=24)) &
                         (q.close_time < current)].quote_volume.sum())
            pre = scanner._prefilter(symbol, qv)
            if pre is None:
                raise RuntimeError(f"{symbol}: historical prefilter failed")
            candidates.append(scanner.evaluate(symbol, qv, pre[2], regime, watch.get(symbol)))
        candidates.sort(key=lambda c: c.rank, reverse=True)
        waits = [c for c in candidates if c.decision["decision"] == "TETIK_BEKLE"]
        finals = [c for c in candidates if c.decision["decision"] == "ALIM_ADAYI"]
        final_candidates += len(finals)
        for c in waits:
            rec = watch.get(c.symbol) or {"first_seen": str(current),
                                          "first_price": c.snapshot["live_price"],
                                          "observations": 0, "last_bar_15m": 0}
            bar = c.snapshot["15m"]["bar_id"]
            if rec["last_bar_15m"] and bar > rec["last_bar_15m"]:
                rec["observations"] += 1
            rec.update({"phase": c.decision["state"], "setup_kind": c.decision["setup_kind"],
                        "last_bar_15m": bar, "updated_at": str(current)})
            watch[c.symbol] = rec
        room = max(0, 3 - daily_count.get(day, 0))
        eligible = []
        for c in finals:
            prior_signal = last_signal_at.get(c.symbol)
            if prior_signal is not None and current - prior_signal < pd.Timedelta(hours=cooldown_hours):
                cooldown_blocked += 1
                continue
            eligible.append(c)
        quota_blocked += max(0, len(eligible) - room)
        for c in eligible[:room]:
            lv = scanner.levels(c)
            event = {"symbol": c.symbol, "decision_time": str(current),
                     "setup_kind": c.decision["setup_kind"], "score": c.decision["confidence"],
                     "rank": c.rank, "btc_regime": regime, "entry": lv["price"],
                     "stop": lv["stop"], "source_tp1": lv["tp1"], "policies": {}}
            future = raw5[c.symbol][(raw5[c.symbol].open_time >= current) &
                                    (raw5[c.symbol].open_time < current + pd.Timedelta(hours=24))]
            event["mfe_pct_24h"] = round((float(future.high.max()) / lv["price"] - 1) * 100, 6)
            event["mae_pct_24h"] = round((float(future.low.min()) / lv["price"] - 1) * 100, 6)
            for name, fixed in RULES.items():
                target = lv["tp1"] if fixed is None else lv["price"] * (1 + fixed / 100)
                event["policies"][name] = first_passage(raw5[c.symbol], current, lv["price"],
                                                          lv["stop"], target)
            signals.append(event)
            last_signal_at[c.symbol] = current
            daily_count[day] = daily_count.get(day, 0) + 1
            watch.pop(c.symbol, None)
        current += pd.Timedelta(minutes=15)

    if scan_count < 100 or len(coverage) != len(symbols):
        raise RuntimeError("incomplete replay shard")
    if require_signal and not signals:
        raise RuntimeError("no historical signal; exit-order smoke not exercised")
    policy_summary = {}
    for name in RULES:
        vals = [e["policies"][name] for e in signals]
        policy_summary[name] = {
            "trades": len(vals), "target_first": sum(v["outcome"] == "TARGET_FIRST" for v in vals),
            "stop_first": sum(v["outcome"] in {"STOP_FIRST", "STOP_AMBIGUOUS"} for v in vals),
            "expired": sum(v["outcome"] == "EXPIRED" for v in vals),
            "same_bar_collisions": sum(v["same_bar_collision"] for v in vals),
            "net_pct_sum": round(sum(v["net_pct"] for v in vals), 6),
        }
    return {"status": "PRESSURE_REPLAY_PREFLIGHT_PASSED", "source_blob_shas": SOURCE_SHA,
            "history_start": str(history_start), "replay_window": [str(replay_start), str(replay_end)],
            "fee_pct": FEE_PCT, "same_bar_policy": "conservative_stop_first",
            "online_cooldown_hours": cooldown_hours,
            "expected_shards": 1, "completed_shards": 1,
            "expected_symbols": len(symbols), "completed_symbols": len(coverage), "coverage": coverage,
            "scan_count": scan_count, "signals": signals, "signal_count": len(signals),
            "final_candidates": final_candidates, "cooldown_blocked": cooldown_blocked,
            "quota_blocked": quota_blocked,
            "active_days": len({e["decision_time"][:10] for e in signals}),
            "policy_summary": policy_summary,
            "limitations": "Six-symbol <=48h mechanism preflight, not strategy selection, portfolio P&L or OOS. "
                           "Historical universe membership and full-market ranking are not reproduced."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--history-start", default="2025-01-01T00:00:00Z")
    ap.add_argument("--replay-start", default="2025-08-28T12:00:00Z")
    ap.add_argument("--replay-end", default="2025-08-30T00:00:00Z")
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--allow-zero-signals", action="store_true")
    ap.add_argument("--cooldown-hours", type=int, default=0)
    ap.add_argument("--outdir", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.outdir is None:
        ap.error("--outdir required")
    dates = [pd.Timestamp(x) for x in (a.history_start, a.replay_start, a.replay_end)]
    if any(x.tzinfo is None for x in dates):
        ap.error("all timestamps must be timezone-aware")
    result = replay(*dates, tuple(x.strip() for x in a.symbols.split(",") if x.strip()),
                    require_signal=not a.allow_zero_signals, cooldown_hours=a.cooldown_hours)
    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                             encoding="utf-8")
    print(json.dumps({"status": result["status"], "signals": result["signal_count"],
                      "scans": result["scan_count"]}), flush=True)


if __name__ == "__main__":
    main()
