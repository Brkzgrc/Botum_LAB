"""Bounded full-universe architecture benchmark for archived PRESSURE logic.

Symbol shards fetch only closed 15m candles.  A single central replay then owns
global ranking, watch state, daily quota and online cooldown replacement.  This
separation is required because selection mutates watch state and therefore
changes later PRESSURE/RETRIGGER decisions.

This benchmark measures capacity.  It does not select an exit or report P&L.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

import pressure_vector_snapshots as vector_snap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources" / "botum_2026-09-26"
HISTORY_START = pd.Timestamp("2024-10-01T00:00:00Z")
REPLAY_START = pd.Timestamp("2025-02-15T00:00:00Z")
REPLAY_END = pd.Timestamp("2025-02-22T00:00:00Z")
COOLDOWNS = (0, 24, 48)
MAX_DAILY = 3
DATA_FUTURE_HOURS = 0

SHARDS = {
    "s0": ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"),
    "s1": ("ADAUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "SUIUSDT"),
    "s2": ("DOTUSDT", "BCHUSDT", "NEARUSDT", "UNIUSDT", "AAVEUSDT", "ETCUSDT"),
    "s3": ("XLMUSDT", "FILUSDT", "ATOMUSDT", "ALGOUSDT", "ICPUSDT", "VETUSDT"),
}
EXPECTED_SYMBOLS = tuple(x for shard in SHARDS.values() for x in shard)
STABLE_FIAT_BASES = {
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "BUSD", "DAI", "EUR", "TRY",
    "GBP", "BRL", "AUD", "RUB", "UAH", "BIDR", "IDRT", "NGN", "PLN", "RON",
    "ARS", "AEUR", "EURI", "JPY", "MXN", "ZAR", "CZK", "CHF",
}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def allowed_symbol(symbol: str) -> bool:
    if not symbol.endswith("USDT") or symbol.count("USDT") != 1:
        return False
    base = symbol[:-4]
    return bool(base) and base not in STABLE_FIAT_BASES and not base.endswith(LEVERAGED_SUFFIXES)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest_root(root: Path, verify_files: bool = True) -> tuple[dict, dict[str, Path]]:
    manifests = {}
    files: dict[str, Path] = {}
    for p in root.rglob("manifest.json"):
        x = json.loads(p.read_text(encoding="utf-8"))
        shard = x.get("shard")
        if shard in manifests:
            raise RuntimeError(f"DUPLICATE_SHARD:{shard}")
        manifests[shard] = x
        if shard not in SHARDS or tuple(x.get("symbols", [])) != SHARDS[shard]:
            raise RuntimeError(f"SHARD_CONTRACT_MISMATCH:{shard}")
        for rec in x.get("files", []):
            symbol = rec["symbol"]
            fp = p.parent / rec["file"]
            if symbol in files:
                raise RuntimeError(f"DUPLICATE_SYMBOL:{symbol}")
            if verify_files and (not fp.is_file() or file_sha256(fp) != rec["sha256"]):
                raise RuntimeError(f"FILE_HASH_MISMATCH:{symbol}")
            files[symbol] = fp
    if set(manifests) != set(SHARDS):
        raise RuntimeError(f"INCOMPLETE_SHARDS:{sorted(manifests)}")
    if set(files) != set(EXPECTED_SYMBOLS):
        raise RuntimeError(f"INCOMPLETE_SYMBOLS:{sorted(files)}")
    return manifests, files


def fetch_shard(shard: str, outdir: Path) -> dict:
    if shard not in SHARDS:
        raise ValueError("unknown shard")
    if not all(allowed_symbol(s) for s in SHARDS[shard]):
        raise RuntimeError("stable/fiat/leveraged symbol leaked into benchmark")
    sys.path.insert(0, str(HERE))
    import pressure_replay_preflight as replay  # type: ignore

    replay.verify_sources()
    outdir.mkdir(parents=True, exist_ok=True)
    records = []
    started = time.perf_counter()
    data_end = REPLAY_END + pd.Timedelta(hours=DATA_FUTURE_HOURS, minutes=15)
    expected_rows = int((data_end - HISTORY_START).total_seconds() // 900)
    for symbol in SHARDS[shard]:
        d = replay.fetch(symbol, "15m", HISTORY_START, data_end)
        coverage = len(d) / expected_rows * 100
        if coverage < 98.0 or d.close_time.max() < REPLAY_END:
            raise RuntimeError(f"{symbol}: incomplete 15m coverage {coverage:.3f}%")
        keep = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                "quote_volume", "taker_quote"]
        fp = outdir / f"{symbol}.csv.gz"
        d[keep].to_csv(fp, index=False, compression="gzip")
        records.append({"symbol": symbol, "file": fp.name, "rows": len(d),
                        "coverage_pct": round(coverage, 4), "sha256": file_sha256(fp),
                        "transports": d.attrs.get("transports", [])})
    result = {
        "status": "PRESSURE_DATA_SHARD_PASSED", "shard": shard,
        "symbols": list(SHARDS[shard]), "history_start": str(HISTORY_START),
        "replay_window": [str(REPLAY_START), str(REPLAY_END)], "files": records,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (outdir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def select_finals(finals, current: pd.Timestamp, state: dict, cooldown_h: int):
    day = current.strftime("%Y-%m-%d")
    room = max(0, MAX_DAILY - state["daily_count"].get(day, 0))
    eligible = []
    for c in finals:
        prior = state["last_signal_at"].get(c.symbol)
        if prior is not None and current - prior < pd.Timedelta(hours=cooldown_h):
            state["cooldown_blocked"] += 1
            continue
        eligible.append(c)
    state["quota_blocked"] += max(0, len(eligible) - room)
    return eligible[:room]


def update_waits(waits, current: pd.Timestamp, watch: dict) -> None:
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


def vector_prefilter(symbol: str, qv: float, s: dict):
    """Archived ``_prefilter`` formula evaluated from an exact vector snapshot."""
    p, r, sk, sd = s["price"], s["rsi"], s["stoch_k"], s["stoch_d"]
    sk0, mh, mh0 = s["stoch_k_prev"], s["macd_hist"], s["macd_hist_prev"]
    e20, e50, vr = s["ema20"], s["ema50"], s["vol_ratio"]
    ret3, ret6, obv = s["ret3"], s["ret6"], s["obv_up"]
    near, taker = s["near_high20_pct"], s["taker_buy_ratio"]
    hc, hl = s["higher_closes6"], s["higher_lows6"]
    reset = sk <= 75 or s["stoch_min3"] <= 30
    turn = sk > sd and sk > sk0
    score = ((18 if p >= e50 else 0) + (12 if p >= e20 else 5) +
             (12 if 45 <= r <= 88 else 5 if 38 <= r <= 92 else 0) +
             (13 if reset else 8 if turn else 0) +
             (10 if mh > mh0 else 5 if mh > 0 else 0) + (10 if obv else 0) +
             (7 if vr >= .8 else 3) + (7 if near <= 7 else 3 if near <= 12 else 0) +
             (5 if taker >= .50 else 0) + (4 if ret6 > 3 else 0))
    retrigger_seed = p >= e50 and 38 <= r <= 90 and (reset or turn) and -7 <= ret3 <= 10
    pressure_seed = (p >= e20 and 45 <= r <= 88 and hc >= 3 and hl >= 3 and
                     near <= 6 and -1 <= ret3 <= 9 and (taker >= .50 or obv))
    seed = "RETRIGGER" if retrigger_seed else "PRESSURE" if pressure_seed else ""
    if ret3 > 14 and sk > 85 and s["dist_ema20"] > 15:
        score -= 18
    return symbol, qv, round(score, 2), seed


def replay_central(input_root: Path, outdir: Path) -> dict:
    manifests, files = validate_manifest_root(input_root)
    sys.path.insert(0, str(SOURCE))
    sys.path.insert(0, str(HERE))
    import spot_opportunity_scanner as scanner  # type: ignore
    import pressure_replay_preflight as helper  # type: ignore

    helper.verify_sources()
    raw, frames = {}, {}
    for symbol, fp in files.items():
        d = pd.read_csv(fp)
        for col in ("open_time", "close_time"):
            d[col] = pd.to_datetime(d[col], utc=True)
        for col in ("open", "high", "low", "close", "volume", "quote_volume", "taker_quote"):
            d[col] = pd.to_numeric(d[col], errors="raise")
        raw[symbol] = d
        frames[symbol] = helper.build_frames(d)

    decision_times = pd.date_range(REPLAY_START, REPLAY_END, freq="15min", inclusive="left")
    labels = {"15m": "15M", "1h": "1H", "4h": "4H", "1d": "1D"}
    vector_cache: dict[tuple, dict] = {}
    vector_started = time.perf_counter()
    for symbol in EXPECTED_SYMBOLS:
        for interval, label in labels.items():
            snapshots = vector_snap.build_snapshots(frames[symbol][interval], label, decision_times)
            for value in snapshots.values():
                vector_cache[(symbol, interval, value["bar_id"])] = value
    vector_build_seconds = time.perf_counter() - vector_started

    current = REPLAY_START
    history_cache: dict[tuple, pd.DataFrame] = {}
    snapshot_cache: dict[tuple, dict] = {}
    snapshot_stats = {"computed": 0, "cache_hits": 0}

    def historical_ohlcv(symbol: str, interval: str, limit: int = 240) -> pd.DataFrame:
        key = (symbol, interval, limit)
        if key in history_cache:
            return history_cache[key]
        d = frames[symbol][interval]
        z = d[d.close_time < current].tail(limit).reset_index(drop=True)
        if len(z) < 80 or z.close_time.iloc[-1] >= current:
            raise RuntimeError(f"{symbol} {interval}: incomplete/future history")
        z.attrs.update({"symbol": symbol, "interval": interval})
        history_cache[key] = z
        return z

    def historical_get(path: str, params: dict | None = None):
        if path != "/api/v3/ticker/price" or not params or params.get("symbol") not in frames:
            raise RuntimeError("unexpected live API access")
        symbol = params["symbol"]
        return {"price": str(historical_ohlcv(symbol, "15m").close.iloc[-1])}

    def cached_snap(frame: pd.DataFrame, label: str) -> dict:
        key = (id(frame), label)
        if key in snapshot_cache:
            snapshot_stats["cache_hits"] += 1
            return snapshot_cache[key]
        symbol, interval = frame.attrs["symbol"], frame.attrs["interval"]
        bar_id = int(pd.Timestamp(frame.open_time.iloc[-1]).timestamp())
        value = vector_cache[(symbol, interval, bar_id)]
        snapshot_cache[key] = value
        snapshot_stats["computed"] += 1
        return value

    def cached_prefilter(symbol: str, qv: float):
        frame = historical_ohlcv(symbol, "1h", 220)
        return vector_prefilter(symbol, qv, cached_snap(frame, "1H"))

    scanner.ohlcv, scanner._get, scanner.snap = historical_ohlcv, historical_get, cached_snap
    scanner._prefilter = cached_prefilter
    states = {h: {"watch": {}, "daily_count": {}, "last_signal_at": {}, "signals": [],
                  "final_candidates": 0, "cooldown_blocked": 0, "quota_blocked": 0}
              for h in COOLDOWNS}
    scan_count = evaluations = 0
    started = time.perf_counter()
    while current < REPLAY_END:
        scan_count += 1
        history_cache.clear()
        snapshot_cache.clear()
        regime = scanner.btc_regime()
        # Prefilter and volume are independent of cooldown/watch state.  Compute
        # them once per decision time, then reuse across the three state paths.
        prefiltered = {}
        for symbol in EXPECTED_SYMBOLS:
            q = raw[symbol]
            qv = float(q[(q.open_time >= current - pd.Timedelta(hours=24)) &
                         (q.close_time < current)].quote_volume.sum())
            pre = scanner._prefilter(symbol, qv)
            if pre is not None:
                prefiltered[symbol] = (qv, pre[2])
        for cooldown_h, state in states.items():
            dead = [s for s, rec in state["watch"].items()
                    if current - pd.Timestamp(rec["first_seen"]) > pd.Timedelta(hours=18)]
            for symbol in dead:
                state["watch"].pop(symbol, None)
            candidates = []
            for symbol, (qv, pre_rank) in prefiltered.items():
                candidates.append(scanner.evaluate(symbol, qv, pre_rank, regime,
                                                   state["watch"].get(symbol)))
                evaluations += 1
            candidates.sort(key=lambda c: c.rank, reverse=True)
            waits = [c for c in candidates if c.decision["decision"] == "TETIK_BEKLE"]
            finals = [c for c in candidates if c.decision["decision"] == "ALIM_ADAYI"]
            state["final_candidates"] += len(finals)
            update_waits(waits, current, state["watch"])
            for c in select_finals(finals, current, state, cooldown_h):
                lv = scanner.levels(c)
                state["signals"].append({"symbol": c.symbol, "decision_time": str(current),
                                         "setup_kind": c.decision["setup_kind"],
                                         "score": c.decision["confidence"], "rank": c.rank,
                                         "btc_regime": regime, "entry": lv["price"],
                                         "stop": lv["stop"], "source_tp1": lv["tp1"]})
                state["last_signal_at"][c.symbol] = current
                day = current.strftime("%Y-%m-%d")
                state["daily_count"][day] = state["daily_count"].get(day, 0) + 1
                state["watch"].pop(c.symbol, None)
        if scan_count % 96 == 0:
            print(json.dumps({"checkpoint_scans": scan_count,
                              "elapsed_seconds": round(time.perf_counter() - started, 3),
                              "evaluations": evaluations,
                              "snapshots_computed": snapshot_stats["computed"],
                              "snapshot_cache_hits": snapshot_stats["cache_hits"]}), flush=True)
        current += pd.Timedelta(minutes=15)
    elapsed = time.perf_counter() - started
    observed_days = (REPLAY_END - REPLAY_START).total_seconds() / 86400
    comparison = {}
    state_end = {}
    for h, state in states.items():
        active = sorted({x["decision_time"][:10] for x in state["signals"]})
        comparison[str(h)] = {"signals": len(state["signals"]),
                              "signals_per_observed_day": round(len(state["signals"]) / observed_days, 6),
                              "active_days": len(active),
                              "active_day_ratio_pct": round(len(active) / observed_days * 100, 6),
                              "final_candidates": state["final_candidates"],
                              "cooldown_blocked": state["cooldown_blocked"],
                              "quota_blocked": state["quota_blocked"],
                              "events": state["signals"]}
        state_end[str(h)] = {
            "watch": state["watch"],
            "daily_count": state["daily_count"],
            "last_signal_at": {k: str(v) for k, v in state["last_signal_at"].items()},
        }
    result = {
        "status": "PRESSURE_FULLMARKET_BENCHMARK_PASSED",
        "expected_shards": sorted(SHARDS), "completed_shards": sorted(manifests),
        "symbols": len(EXPECTED_SYMBOLS), "symbol_days": len(EXPECTED_SYMBOLS) * observed_days,
        "replay_window": [str(REPLAY_START), str(REPLAY_END)], "observed_days": observed_days,
        "scan_count": scan_count, "evaluations": evaluations,
        "elapsed_seconds": round(elapsed, 3),
        "vector_build_seconds": round(vector_build_seconds, 3),
        "evaluations_per_second": round(evaluations / elapsed, 3),
        "snapshots_computed": snapshot_stats["computed"],
        "snapshot_cache_hits": snapshot_stats["cache_hits"],
        "cooldowns": list(COOLDOWNS), "comparison": comparison,
        "state_end": state_end,
        "universe_contract": "Binance Spot USDT long; stable/fiat/leveraged bases excluded",
        "causality_contract": "only frames with close_time < decision_time",
        "pnl_metrics": "N/A: capacity/state benchmark; no 5m exit path in this stage",
        "oos": "N/A: fixed 2025 infrastructure benchmark, not strategy selection",
        "decision": "Use measured throughput to budget the staged 2023-2025 research; do not promote a rule.",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                          encoding="utf-8")
    return result


def self_test() -> None:
    assert all(allowed_symbol(s) for s in EXPECTED_SYMBOLS)
    for bad in ("USDCUSDT", "EURUSDT", "BTCUPUSDT", "ETHBEARUSDT", "BTCFDUSD"):
        assert not allowed_symbol(bad)
    assert len(EXPECTED_SYMBOLS) == len(set(EXPECTED_SYMBOLS)) == 24

    class C:
        def __init__(self, symbol): self.symbol = symbol
    now = pd.Timestamp("2025-01-01T00:00:00Z")
    state = {"daily_count": {}, "last_signal_at": {"AUSDT": now - pd.Timedelta(hours=2)},
             "cooldown_blocked": 0, "quota_blocked": 0}
    chosen = select_finals([C("AUSDT"), C("BUSDT"), C("CUSDT"), C("DUSDT")], now, state, 24)
    assert [x.symbol for x in chosen] == ["BUSDT", "CUSDT", "DUSDT"]
    assert state["cooldown_blocked"] == 1 and state["quota_blocked"] == 0

    # Exact parity against the archived scanner, including its reset-on-each-
    # window EMA/RSI semantics and a short (<240) daily-style history.
    sys.path.insert(0, str(SOURCE))
    import spot_opportunity_scanner as scanner  # type: ignore
    n = 330
    t = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    wave = pd.Series(range(n), dtype=float)
    close = 100 + wave * .031 + (wave % 17 - 8) * .19
    test = pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(hours=1) - pd.Timedelta(milliseconds=1),
                         "open": close - .07, "high": close + .41 + (wave % 5) * .01,
                         "low": close - .37 - (wave % 3) * .01, "close": close,
                         "volume": 1000 + (wave % 23) * 31,
                         "quote_volume": (1000 + (wave % 23) * 31) * close,
                         "taker_quote": (1000 + (wave % 23) * 31) * close * (.47 + (wave % 7) * .01)})
    decisions = [test.close_time.iloc[i] + pd.Timedelta(milliseconds=1) for i in (100, 238, 239, 275, 329)]
    got = vector_snap.build_snapshots(test, "1H", decisions)
    assert len(got) == len(decisions) == 5
    for end, actual in got.items():
        expected = scanner.snap(test.iloc[max(0, end - 239):end + 1].reset_index(drop=True), "1H")
        vector_snap.assert_snapshot_equal(expected, actual)
        qv = 1234567.0
        a = scanner._prefilter
        # Compare the replicated prefilter formula through a patched one-symbol
        # history adapter; this guards rank/seed as well as snapshot fields.
        old_ohlcv = scanner.ohlcv
        scanner.ohlcv = lambda symbol, interval, limit=240, end=end: test.iloc[max(0, end-limit+1):end+1].reset_index(drop=True)
        try:
            assert a("TESTUSDT", qv) == vector_prefilter("TESTUSDT", qv, actual)
        finally:
            scanner.ohlcv = old_ohlcv

    print(json.dumps({"self_test": "ok", "symbols": len(EXPECTED_SYMBOLS),
                      "cooldowns": COOLDOWNS, "central_state_owner": True,
                      "vector_snapshot_parity_cases": len(got)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--fetch-shard", choices=sorted(SHARDS))
    ap.add_argument("--input-root", type=Path)
    ap.add_argument("--outdir", type=Path)
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    if a.outdir is None:
        ap.error("--outdir required")
    if a.fetch_shard:
        result = fetch_shard(a.fetch_shard, a.outdir)
    elif a.input_root:
        result = replay_central(a.input_root, a.outdir)
    else:
        ap.error("choose --fetch-shard or --input-root")
    print(json.dumps({k: result[k] for k in result if k in
                      {"status", "shard", "elapsed_seconds", "symbols", "evaluations"}}), flush=True)


if __name__ == "__main__":
    main()
