from __future__ import annotations

"""
Standalone live scanner for the current research candidate.

Signal stack:
1) BTC 4H movement permission
2) Coin 4H movement permission
3) Coin 15M movement/structure trigger
4) StochRSI movement pattern: -0++ or -00+
5) Base-signal cooldown: 16 x 15M bars
6) Frozen lead-lag rule:
   - 15M bullish engulf
   - 15M higher-low
   - 15M higher-high
   - 15M motion_net - last completed 1H motion_net >= 4
7) BTC indicator filter:
   - BTC 1H TSI_d1 <= -0.211069
   - BTC 4H Bollinger Width >= 0.0942267
8) Frozen Outcome-First extension (r2):
   - Coin 4H Bollinger Width >= 0.19233492
   - Coin close is at least 7.3594696% below the highest high of the
     last 48 hours, using only 15M candles fully closed by decision time

Research cost assumption: 0.20% round-trip.
This file only emits signals. It does NOT place orders.

IMPORTANT:
Outcome-First research remains isolated except for the r2 extension above,
which was frozen from Discovery + Calibration and then checked on separate
pre-2026 and 2026 holdouts. No other Outcome-First rule is merged here.

Causality lock:
- Uses only CLOSED 15M / 1H / 4H candles.
- A signal known at decision time t is not modeled as filled at t.
- Earliest backtest-style entry time is t + 15 minutes.
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

CANDIDATE_NAME = "TSI_BB_FROZEN_CANDIDATE"
CANDIDATE_VERSION = "2026-09-19-r2"
ROBUSTNESS_STATUS = "R2_OUTCOME_EXTENSION_HOLDOUT_POSITIVE"

# Robustness audit summary (metadata only; not used as signal logic):
# - 577 / 8162 events selected across the full audit (7.07%)
# - 24h net mean after 0.20% cost: +1.6839%
# - 24h median: +2.0835%
# - 24h win rate: 67.24%
# - 24h profit factor: 2.398
# - 2026 final holdout: 51 events / 44 symbols
# - 2026 final holdout 24h net mean: +4.3419%
# - 2026 final holdout 24h median: +3.1898%
# - 2026 final holdout 24h win rate: 86.27%
#
# These thresholds are FROZEN. Do not re-optimize them from later holdouts.
TSI_D1_MAX = -0.211069
BTC4_BB_WIDTH_MIN = 0.0942267

# r2 Outcome-First extension, selected WITHOUT holdouts:
# - coin 4H BB Width >= 0.19233492
# - 48H causal drawdown from recent high <= -7.3594696%
# Separate diagnostics after freezing:
#   pre-2026 holdout: 24h mean +0.50% -> +2.76%
#   2026 holdout:     24h mean +4.34% -> +5.81%
#   holdout symbol-cluster bootstrap net24 delta: +2.73 pp
#   95% CI: +1.51 to +4.11 pp
COIN4_BB_WIDTH_MIN = 0.19233492
PULLBACK_48H_MAX_PCT = -7.3594696
PULLBACK_48H_BARS_15M = 48 * 4

COOLDOWN_BARS = 16
KLINE_LIMIT = 1000
DEFAULT_WORKERS = 6

# Universe rule:
# Binance SPOT, USDT-quoted pairs only.
# IMPORTANT: exclusions are EXACT base-asset matches. There is NO substring
# filtering such as "UP", "USD", etc.; therefore names like JUP/SYRUP are safe.
#
# Stable/fiat exclusions verified against the current Binance spot universe.
# FRAX is intentionally NOT excluded: Binance rebranded FXS Share to Frax (FRAX)
# in 2026; current FRAX is not treated here as the old FRAX stablecoin.
MIN_LISTING_AGE_DAYS = 45

STABLE_BASE_ASSETS = {
    # USD / EUR / national-currency stablecoins and legacy stablecoins
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD",
    "USDS", "USDE", "USD1", "USDJ", "PYUSD", "EURC", "AEUR",
    "EURI", "RLUSD", "XUSD", "U", "KGST", "USTC",
}

# Stable-value / cash-like Binance product. Binance itself says BFUSD is not a
# conventional stablecoin, but its purpose is stable-value/collateral behavior;
# it is excluded from directional coin scanning.
STABLE_LIKE_BASE_ASSETS = {
    "BFUSD",
}

FIAT_BASE_ASSETS = {
    "USD", "EUR", "TRY", "GBP", "JPY", "CHF", "AUD", "CAD",
    "BRL", "ARS", "MXN", "PLN", "RON", "RUB", "UAH", "ZAR",
    "NGN", "IDR", "BIDR", "KGS",
}

EXCLUDED_BASE_ASSETS = (
    STABLE_BASE_ASSETS
    | STABLE_LIKE_BASE_ASSETS
    | FIAT_BASE_ASSETS
)

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]


def get_json(path: str, params: dict | None = None, timeout: int = 20, tries: int = 3):
    last = None
    params = params or {}
    for _ in range(tries):
        for base in BASE_URLS:
            try:
                r = requests.get(base + path, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                last = RuntimeError(f"{base} HTTP {r.status_code}: {r.text[:120]}")
            except Exception as exc:
                last = exc
        time.sleep(0.20)
    raise RuntimeError(f"Binance public endpoints failed: {last}")


def server_time_ms() -> int:
    try:
        return int(get_json("/api/v3/time")["serverTime"])
    except Exception:
        return int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)


def spot_usdt_symbols(requested_symbols: list[str] | None = None) -> list[str]:
    """
    Build the live universe from Binance exchangeInfo on EVERY run.

    Rules:
    - active status must be TRADING
    - quote asset must be USDT
    - spot trading must be allowed
    - stable/fiat exclusions use exact BASE-ASSET equality only
    - optional manually requested symbols pass through the SAME filters

    An audit file is written so every included/excluded USDT symbol can be
    inspected after a run.
    """
    info = get_json("/api/v3/exchangeInfo")
    requested = (
        {str(s).strip().upper() for s in requested_symbols if str(s).strip()}
        if requested_symbols
        else None
    )

    allowed = []
    audit = []
    seen = set()

    for s in info.get("symbols", []):
        symbol = str(s.get("symbol", "")).upper()
        base_asset = str(s.get("baseAsset", "")).upper()
        quote_asset = str(s.get("quoteAsset", "")).upper()
        status = str(s.get("status", ""))
        spot_allowed = bool(s.get("isSpotTradingAllowed", True))

        # Audit is scoped to USDT-quoted pairs because that is the scanner universe.
        if quote_asset != "USDT":
            continue

        seen.add(symbol)

        if status != "TRADING":
            include = False
            reason = "NOT_TRADING"
        elif not spot_allowed:
            include = False
            reason = "SPOT_NOT_ALLOWED"
        elif base_asset in FIAT_BASE_ASSETS:
            include = False
            reason = "FIAT_BASE"
        elif base_asset in STABLE_BASE_ASSETS:
            include = False
            reason = "STABLE_BASE"
        elif base_asset in STABLE_LIKE_BASE_ASSETS:
            include = False
            reason = "STABLE_LIKE_BASE"
        else:
            include = True
            reason = "INCLUDED"

        # If the user manually passed --symbols, the same universe rules still apply.
        selected_by_request = requested is None or symbol in requested

        audit.append({
            "symbol": symbol,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "status": status,
            "spot_allowed": spot_allowed,
            "universe_allowed": include,
            "selected_by_request": selected_by_request,
            "reason": reason,
        })

        if include and selected_by_request:
            allowed.append(symbol)

    if requested is not None:
        for symbol in sorted(requested - seen):
            audit.append({
                "symbol": symbol,
                "base_asset": "",
                "quote_asset": "",
                "status": "",
                "spot_allowed": False,
                "universe_allowed": False,
                "selected_by_request": True,
                "reason": "NOT_A_BINANCE_USDT_SPOT_SYMBOL",
            })

    pd.DataFrame(audit).sort_values(
        ["universe_allowed", "reason", "symbol"],
        ascending=[False, True, True],
    ).to_csv("spot_universe_audit.csv", index=False)

    return sorted(set(allowed))


def has_min_listing_history(symbol: str, now_ms: int) -> bool:
    """
    Research-consistent listing warmup:
    require at least one Binance daily candle BEFORE the 45-day cutoff.

    This prevents brand-new listings from entering a rule that was researched
    with a 45-day warmup. Once the asset becomes old enough, it is automatically
    eligible on later runs.
    """
    cutoff_ms = now_ms - MIN_LISTING_AGE_DAYS * 24 * 60 * 60 * 1000
    rows = get_json(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": "1d",
            "endTime": cutoff_ms,
            "limit": 1,
        },
    )
    return bool(rows)


class WarmupPending(RuntimeError):
    pass

def fetch_15m(symbol: str, limit: int = KLINE_LIMIT, now_ms: int | None = None) -> pd.DataFrame:
    rows = get_json(
        "/api/v3/klines",
        {"symbol": symbol, "interval": "15m", "limit": limit},
    )
    if not rows:
        raise RuntimeError("no 15m data")

    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_base",
        "taker_quote", "ignore",
    ]
    d = pd.DataFrame(rows, columns=cols)
    for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    now_ms = server_time_ms() if now_ms is None else int(now_ms)
    d = d[pd.to_numeric(d["close_time"], errors="coerce") < now_ms].copy()
    d["time"] = pd.to_datetime(d["open_time"], unit="ms", utc=True)
    d = (
        d.drop_duplicates("open_time")
        .sort_values("open_time")
        .set_index("time")[["open", "high", "low", "close", "volume", "quote_volume"]]
        .dropna()
    )
    if len(d) < 400:
        raise RuntimeError(f"insufficient history: {len(d)} bars")
    return d


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(~((au == 0) & (ad == 0)), 50.0)


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["rsi"] = rsi(x.close)

    e12 = x.close.ewm(span=12, adjust=False).mean()
    e26 = x.close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    x["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()

    ll9 = x.low.rolling(9).min()
    hh9 = x.high.rolling(9).max()
    rsv = 100 * (x.close - ll9) / (hh9 - ll9).replace(0, np.nan)
    x["kdj_k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    x["kdj_d"] = x.kdj_k.ewm(alpha=1 / 3, adjust=False).mean()
    x["kdj_j"] = 3 * x.kdj_k - 2 * x.kdj_d
    x["kdj_spread"] = x.kdj_k - x.kdj_d

    ll14 = x.low.rolling(14).min()
    hh14 = x.high.rolling(14).max()
    x["wpr"] = -100 * (hh14 - x.close) / (hh14 - ll14).replace(0, np.nan)

    sign = np.sign(x.close.diff()).fillna(0)
    x["obv"] = (sign * x.volume).cumsum()

    rrmin = x.rsi.rolling(14).min()
    rrmax = x.rsi.rolling(14).max()
    x["stoch_raw"] = 100 * (x.rsi - rrmin) / (rrmax - rrmin).replace(0, np.nan)
    x["stoch_k"] = x.stoch_raw.rolling(3).mean()
    x["stoch_d"] = x.stoch_k.rolling(3).mean()
    x["stoch_spread"] = x.stoch_k - x.stoch_d

    for c in [
        "rsi", "macd_hist", "kdj_j", "kdj_spread",
        "wpr", "obv", "stoch_k", "stoch_spread",
    ]:
        x[c + "_d1"] = x[c].diff()
        x[c + "_d3"] = x[c].diff(3)

    rng = (x.high - x.low).replace(0, np.nan)
    body = (x.close - x.open).abs()
    x["body_frac"] = body / rng
    x["close_loc"] = (x.close - x.low) / rng
    x["lower_wick"] = (np.minimum(x.open, x.close) - x.low) / rng
    x["hammer"] = (
        (x.lower_wick >= 0.5)
        & (x.body_frac <= 0.4)
        & (x.close_loc >= 0.55)
    )

    prev_bear = x.close.shift(1) < x.open.shift(1)
    x["bull_engulf"] = (
        (x.close > x.open)
        & prev_bear
        & (x.open <= x.close.shift(1))
        & (x.close >= x.open.shift(1))
    )
    x["higher_low"] = x.low > x.low.shift(1)
    x["higher_high"] = x.high > x.high.shift(1)

    prev8 = x.low.shift(1).rolling(8).min()
    x["sweep_reclaim"] = (x.low < prev8) & (x.close > prev8)
    x["reclaim_prev_high"] = x.close > x.high.shift(1)
    x["structure"] = (
        x.hammer
        | x.bull_engulf
        | x.sweep_reclaim
        | x.reclaim_prev_high
        | (x.higher_low & x.higher_high)
    )

    fam = pd.DataFrame(index=x.index)
    fam["RSI"] = np.sign(x.rsi_d1.fillna(0)) + np.sign(x.rsi_d3.fillna(0))
    fam["MACD"] = np.sign(x.macd_hist_d1.fillna(0)) + np.sign(x.macd_hist_d3.fillna(0))
    fam["KDJ"] = np.sign(x.kdj_j_d1.fillna(0)) + np.sign(x.kdj_spread_d1.fillna(0))
    fam["WPR"] = np.sign(x.wpr_d1.fillna(0)) + np.sign(x.wpr_d3.fillna(0))
    fam["OBV"] = np.sign(x.obv_d1.fillna(0)) + np.sign(x.obv_d3.fillna(0))
    fam["STOCH"] = np.sign(x.stoch_k_d1.fillna(0)) + np.sign(x.stoch_spread_d1.fillna(0))

    x["motion_pos"] = (fam > 0).sum(axis=1)
    x["motion_neg"] = (fam < 0).sum(axis=1)
    x["motion_net"] = x.motion_pos - x.motion_neg
    x["motion_rise"] = x.motion_pos.diff()
    x["turn4"] = (
        (x.motion_pos >= 4)
        & ((x.motion_pos.shift(1) < 4) | (x.motion_rise >= 2))
    )
    return x


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def add_tsi_bb(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    mom = x.close.diff()
    a1 = ema(ema(mom, 25), 13)
    a2 = ema(ema(mom.abs(), 25), 13)
    x["tsi"] = 100 * a1 / a2.replace(0, np.nan)
    x["tsi_d1"] = x["tsi"].diff()

    mid = x.close.rolling(20).mean()
    sd = x.close.rolling(20).std(ddof=0)
    upper = mid + 2 * sd
    lower = mid - 2 * sd
    x["bb_width"] = (upper - lower) / mid.replace(0, np.nan)
    return x


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        df.resample(rule, origin="epoch", label="left", closed="left")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            quote_volume=("quote_volume", "sum"),
        )
        .dropna()
    )


def decision_15m(t15: pd.DataFrame) -> pd.DataFrame:
    z = t15.copy()
    z.index = z.index + pd.Timedelta(minutes=15)
    return z[~z.index.duplicated(keep="last")]


def align_motion(tf, close_delay, decision_index, prefix):
    cols = [
        "motion_pos", "motion_net", "motion_rise", "turn4", "structure",
        "higher_low", "higher_high", "sweep_reclaim", "reclaim_prev_high",
        "bull_engulf", "hammer",
    ]
    z = tf[[c for c in cols if c in tf.columns]].copy()
    z.index = z.index + close_delay
    z = z.rename(columns={c: f"{prefix}_{c}" for c in z.columns})
    return z.reindex(decision_index, method="ffill")


def align_columns(tf, cols, close_delay, decision_index, prefix):
    z = tf[cols].copy()
    z.index = z.index + close_delay
    z = z.rename(columns={c: f"{prefix}_{c}" for c in cols})
    return z.reindex(decision_index, method="ffill")


def stoch_pattern(t15_decision: pd.DataFrame) -> pd.Series:
    score = (
        np.sign(t15_decision.stoch_k_d1.fillna(0))
        + np.sign(t15_decision.stoch_spread_d1.fillna(0))
    )
    state = pd.Series(
        np.where(score > 0, "+", np.where(score < 0, "-", "0")),
        index=t15_decision.index,
    )
    return state.shift(3) + state.shift(2) + state.shift(1) + state


def compress(mask: pd.Series, cooldown_bars: int = COOLDOWN_BARS) -> pd.Series:
    arr = mask.fillna(False).to_numpy()
    out = np.zeros(len(arr), dtype=bool)
    last = -10**9
    for i, v in enumerate(arr):
        if v and i - last > cooldown_bars:
            out[i] = True
            last = i
    return pd.Series(out, index=mask.index)


def build_btc_context(btc15: pd.DataFrame, decision_index: pd.DatetimeIndex) -> pd.DataFrame:
    btc1 = add_tsi_bb(resample(btc15, "1h"))
    btc4_price = resample(btc15, "4h")
    btc4_motion = indicators(btc4_price)
    btc4_extra = add_tsi_bb(btc4_price)

    out = align_motion(
        btc4_motion, pd.Timedelta(hours=4), decision_index, "btc_h4"
    )
    out = out.join(
        align_columns(
            btc1, ["tsi_d1"], pd.Timedelta(hours=1), decision_index, "btc1"
        )
    )
    out = out.join(
        align_columns(
            btc4_extra, ["bb_width"], pd.Timedelta(hours=4), decision_index, "btc4"
        )
    )
    return out


def scan_symbol(symbol: str, btc15: pd.DataFrame, now_ms: int) -> dict | None:
    if not has_min_listing_history(symbol, now_ms):
        raise WarmupPending(
            f"{symbol}: listing history < {MIN_LISTING_AGE_DAYS} days"
        )

    base = fetch_15m(symbol, now_ms=now_ms)
    t15 = indicators(base)
    d15 = decision_15m(t15)
    decision_index = d15.index

    t1 = indicators(resample(base, "1h"))
    t4_price = resample(base, "4h")
    t4 = indicators(t4_price)
    t4_extra = add_tsi_bb(t4_price)

    a1 = align_motion(t1, pd.Timedelta(hours=1), decision_index, "h1")
    a4 = align_motion(t4, pd.Timedelta(hours=4), decision_index, "h4")
    coin4_extra = align_columns(
        t4_extra, ["bb_width"], pd.Timedelta(hours=4), decision_index, "coin4"
    )
    btc = build_btc_context(btc15, decision_index)

    # Corrected causal pullback measure used by the r2 research:
    # at each decision time, use only the 192 x 15M candles that have already
    # fully closed. This is exactly 48 hours of known information.
    d15["causal_dd_high_48h"] = 100.0 * (
        d15["close"]
        / d15["high"].rolling(
            PULLBACK_48H_BARS_15M, min_periods=PULLBACK_48H_BARS_15M
        ).max()
        - 1.0
    )

    z = d15.join(a1).join(a4).join(coin4_extra).join(btc)
    if z.empty:
        return None
    z["stoch_pattern"] = stoch_pattern(z)

    btc_ok = (
        (z.btc_h4_motion_pos >= 2)
        & (
            (z.btc_h4_motion_rise >= 0)
            | (z.btc_h4_motion_net > z.btc_h4_motion_net.shift(16))
        )
    )
    coin_h4_ok = (
        (z.h4_motion_pos >= 2)
        & (
            (z.h4_motion_rise >= 0)
            | (z.h4_motion_net > z.h4_motion_net.shift(16))
        )
    )
    trigger_15m = (
        (z.motion_pos >= 4)
        & (z.turn4 | (z.motion_rise >= 1))
        & z.structure
    )
    stoch_ok = z.stoch_pattern.isin(["-0++", "-00+"])

    raw_base = btc_ok & coin_h4_ok & trigger_15m & stoch_ok
    base_signal = compress(raw_base, COOLDOWN_BARS)

    lead_gap = z.motion_net - z.h1_motion_net
    frozen_lead_lag = (
        z.bull_engulf
        & z.higher_low
        & z.higher_high
        & (lead_gap >= 4)
    )

    indicator_filter = (
        (z.btc1_tsi_d1 <= TSI_D1_MAX)
        & (z.btc4_bb_width >= BTC4_BB_WIDTH_MIN)
    )

    outcome_extension_filter = (
        (z.coin4_bb_width >= COIN4_BB_WIDTH_MIN)
        & (z.causal_dd_high_48h <= PULLBACK_48H_MAX_PCT)
    )

    final_signal = (
        base_signal
        & frozen_lead_lag
        & indicator_filter
        & outcome_extension_filter
    )
    t = z.index[-1]
    if not bool(final_signal.loc[t]):
        return None

    row = z.loc[t]
    return {
        "candidate": CANDIDATE_NAME,
        "version": CANDIDATE_VERSION,
        "robustness_status": ROBUSTNESS_STATUS,
        "symbol": symbol,
        "decision_time_utc": t.isoformat(),
        "tested_entry_not_before_utc": (t + pd.Timedelta(minutes=15)).isoformat(),
        "last_closed_15m_price": float(row["close"]),
        "stoch_pattern": str(row["stoch_pattern"]),
        "m15_motion_pos": int(row["motion_pos"]),
        "m15_motion_net": int(row["motion_net"]),
        "h1_motion_net": int(row["h1_motion_net"]),
        "lead_gap": float(lead_gap.loc[t]),
        "h4_motion_pos": int(row["h4_motion_pos"]),
        "btc_h4_motion_pos": int(row["btc_h4_motion_pos"]),
        "btc1_tsi_d1": float(row["btc1_tsi_d1"]),
        "btc4_bb_width": float(row["btc4_bb_width"]),
        "coin4_bb_width": float(row["coin4_bb_width"]),
        "causal_dd_high_48h_pct": float(row["causal_dd_high_48h"]),
        "bull_engulf": bool(row["bull_engulf"]),
        "higher_low": bool(row["higher_low"]),
        "higher_high": bool(row["higher_high"]),
    }


def run_scan(symbols: list[str], workers: int = DEFAULT_WORKERS):
    print("=" * 78)
    print(f"{CANDIDATE_NAME} | {CANDIDATE_VERSION}")
    print(f"Robustness: {ROBUSTNESS_STATUS}")
    print("Binance SPOT / USDT | stable+fiat exact exclusions | no orders")
    print(f"Minimum listing history: {MIN_LISTING_AGE_DAYS} days")
    print(f"BTC 1H TSI_d1 <= {TSI_D1_MAX}")
    print(f"BTC 4H BB Width >= {BTC4_BB_WIDTH_MIN}")
    print(f"Coin 4H BB Width >= {COIN4_BB_WIDTH_MIN}")
    print(f"48H causal drawdown from high <= {PULLBACK_48H_MAX_PCT}%")
    print(f"Symbols after universe filter: {len(symbols)} | workers: {workers}")
    print("=" * 78)

    now_ms = server_time_ms()
    btc15 = fetch_15m("BTCUSDT", now_ms=now_ms)

    signals = []
    errors = []
    warmup_pending = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(scan_symbol, sym, btc15, now_ms): sym
            for sym in symbols
        }

        for i, fut in enumerate(as_completed(futs), 1):
            sym = futs[fut]

            try:
                rec = fut.result()
                if rec is not None:
                    signals.append(rec)
                    print(
                        f"\nSIGNAL {sym}"
                        f"\n  decision : {rec['decision_time_utc']}"
                        f"\n  entry >= : {rec['tested_entry_not_before_utc']}"
                        f"\n  price    : {rec['last_closed_15m_price']}"
                        f"\n  lead gap : {rec['lead_gap']:.1f}"
                        f"\n  BTC TSI d1 : {rec['btc1_tsi_d1']:.6f}"
                        f"\n  BTC4 BB    : {rec['btc4_bb_width']:.6f}"
                        f"\n  Coin4 BB   : {rec['coin4_bb_width']:.6f}"
                        f"\n  48H DD     : {rec['causal_dd_high_48h_pct']:.3f}%\n"
                    )
            except WarmupPending as exc:
                warmup_pending.append((sym, str(exc)))
            except Exception as exc:
                errors.append((sym, repr(exc)))

            if i % 25 == 0 or i == len(futs):
                print(
                    f"[{i}/{len(futs)}] "
                    f"signals={len(signals)} "
                    f"warmup={len(warmup_pending)} "
                    f"errors={len(errors)}",
                    flush=True,
                )

    out = pd.DataFrame(signals)

    if len(out):
        out = out.sort_values(["decision_time_utc", "symbol"])
        out.to_csv("tsi_bb_live_signals.csv", index=False)
        print("\nSignals saved: tsi_bb_live_signals.csv")
        print(out.to_string(index=False))
    else:
        print("\nNo current qualifying signal.")

    if warmup_pending:
        pd.DataFrame(
            warmup_pending,
            columns=["symbol", "reason"],
        ).to_csv("tsi_bb_warmup_pending.csv", index=False)
        print(
            f"Warmup pending: tsi_bb_warmup_pending.csv "
            f"({len(warmup_pending)})"
        )

    if errors:
        pd.DataFrame(errors, columns=["symbol", "error"]).to_csv(
            "tsi_bb_scan_errors.csv",
            index=False,
        )
        print(f"Errors saved: tsi_bb_scan_errors.csv ({len(errors)})")

    return out

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols. Manual symbols are still forced through the same Binance SPOT + stable/fiat filters.",
    )
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    return ap.parse_args()


def main():
    args = parse_args()

    requested = None
    if args.symbols.strip():
        requested = [
            s.strip().upper()
            for s in args.symbols.split(",")
            if s.strip()
        ]

    symbols = spot_usdt_symbols(requested_symbols=requested)

    if requested:
        accepted = set(symbols)
        rejected = sorted(set(requested) - accepted)
        if rejected:
            print(
                "Requested symbols rejected by SPOT/stable/fiat filter: "
                + ", ".join(rejected)
            )
            print("See spot_universe_audit.csv for exact reasons.")

    run_scan(symbols, workers=max(1, args.workers))


if __name__ == "__main__":
    main()