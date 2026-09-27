"""Exact-window batch implementation of the archived scanner ``snap`` function.

The production scanner intentionally rebuilds indicators from its last (up to)
240 closed candles.  Computing indicators once over the entire history changes
EMA/RSI initialization and is therefore not equivalent.  This module batches
many independent 240-candle windows as DataFrame columns: pandas still applies
the archived formulas down each window, but does the expensive work in C.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable

import numpy as np
import pandas as pd


def _sf(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _pct(new, old):
    return (new / old - 1) * 100 if old else 0.0


def _matrix(frame: pd.DataFrame, column: str, ends: list[int], width: int) -> pd.DataFrame:
    a = frame[column].to_numpy(dtype=float)
    return pd.DataFrame(np.column_stack([a[e - width + 1:e + 1] for e in ends]))


def _ema(x: pd.DataFrame, *, span=None, alpha=None, min_periods=0) -> pd.DataFrame:
    return x.ewm(span=span, alpha=alpha, adjust=False, min_periods=min_periods).mean()


def _rsi(close: pd.DataFrame, n=14) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = _ema(gain, alpha=1 / n, min_periods=n)
    al = _ema(loss, alpha=1 / n, min_periods=n)
    rs = ag / al.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _last(df: pd.DataFrame, offset=0) -> np.ndarray:
    return df.iloc[-1 - offset].to_numpy(dtype=float)


def _batch_same_width(frame: pd.DataFrame, label: str, ends: list[int], width: int) -> dict[int, dict]:
    close = _matrix(frame, "close", ends, width)
    opn = _matrix(frame, "open", ends, width)
    high = _matrix(frame, "high", ends, width)
    low = _matrix(frame, "low", ends, width)
    volume = _matrix(frame, "volume", ends, width)
    quote_volume = _matrix(frame, "quote_volume", ends, width)
    taker_quote = _matrix(frame, "taker_quote", ends, width)

    ema20 = _ema(close, span=20)
    ema50 = _ema(close, span=50)
    ema200 = _ema(close, span=200)
    rsi = _rsi(close)
    lo_rsi = rsi.rolling(14).min()
    hi_rsi = rsi.rolling(14).max()
    raw = 100 * (rsi - lo_rsi) / (hi_rsi - lo_rsi).replace(0, np.nan)
    stoch_k = raw.rolling(3).mean().fillna(50)
    stoch_d = stoch_k.rolling(3).mean().fillna(50)
    e12 = _ema(close, span=12)
    e26 = _ema(close, span=26)
    macd = e12 - e26
    macd_hist = macd - _ema(macd, span=9)
    pc = close.shift(1)
    # ``pd.concat(...).max(axis=1)`` in the source skips the first-row NaNs.
    tr = pd.DataFrame(np.nanmax(np.stack(((high - low).to_numpy(),
                                          (high - pc).abs().to_numpy(),
                                          (low - pc).abs().to_numpy())), axis=0))
    atr = _ema(tr, alpha=1 / 14, min_periods=14)
    vol_ratio = volume / volume.rolling(20).mean().replace(0, np.nan)
    obv = (np.sign(close.diff()).fillna(0) * volume).cumsum()
    taker = (taker_quote / quote_volume.replace(0, np.nan)).clip(0, 1).fillna(.5)

    arrays = {name: df.to_numpy(dtype=float) for name, df in {
        "close": close, "open": opn, "high": high, "low": low,
        "ema20": ema20, "ema50": ema50, "ema200": ema200, "rsi": rsi,
        "stoch_k": stoch_k, "stoch_d": stoch_d, "macd_hist": macd_hist,
        "atr": atr, "vol_ratio": vol_ratio, "obv": obv, "taker": taker,
    }.items()}
    out = {}
    for j, end in enumerate(ends):
        def v(name, offset=0, default=0.0):
            return _sf(arrays[name][-1 - offset, j], default)

        p = v("close")
        rg = max(0.0, v("high") - v("low"))
        upper = (v("high") - max(v("open"), p)) / rg if rg else 0.0
        lower = (min(v("open"), p) - v("low")) / rg if rg else 0.0
        c6 = arrays["close"][-6:, j]
        l6 = arrays["low"][-6:, j]

        hs, ls = [], []
        h = arrays["high"][-80:, j]
        l = arrays["low"][-80:, j]
        for i in range(2, len(h) - 2):
            if h[i] >= h[i - 2:i + 3].max():
                hs.append(float(h[i]))
            if l[i] <= l[i - 2:i + 3].min():
                ls.append(float(l[i]))
        hs, ls = hs[-8:], ls[-8:]

        a20, a50 = v("ema20"), v("ema50")
        atr_v = v("atr")
        out[end] = {
            "tf": label, "price": p,
            "bar_id": int(pd.Timestamp(frame.open_time.iloc[end]).timestamp()),
            "ret3": _pct(p, v("close", 3)), "ret6": _pct(p, v("close", 6)),
            "ret24": _pct(p, v("close", 24)),
            "ema20": a20, "ema50": a50, "ema200": v("ema200"),
            "ema20_slope": _pct(a20, v("ema20", 3)),
            "ema50_slope": _pct(a50, v("ema50", 3)),
            "dist_ema20": _pct(p, a20), "dist_ema50": _pct(p, a50),
            "rsi": v("rsi"), "stoch_k": v("stoch_k"), "stoch_d": v("stoch_d"),
            "stoch_k_prev": v("stoch_k", 1),
            "stoch_min3": _sf(np.nanmin(arrays["stoch_k"][-3:, j])),
            "macd_hist": v("macd_hist"), "macd_hist_prev": v("macd_hist", 1),
            "vol_ratio": v("vol_ratio", default=1),
            "obv_up": v("obv") >= v("obv", 5),
            "obv_fast_up": v("obv") >= v("obv", 2),
            "taker_buy_ratio": _sf(np.nanmean(arrays["taker"][-3:, j]), .5),
            "higher_closes6": int(sum(c6[i] > c6[i - 1] for i in range(1, len(c6)))),
            "higher_lows6": int(sum(l6[i] >= l6[i - 1] for i in range(1, len(l6)))),
            "near_high20_pct": max(0.0, -_pct(p, _sf(np.nanmax(arrays["high"][-20:, j])))),
            "prev_high6": _sf(np.nanmax(arrays["high"][-7:-1, j])),
            "atr_pct": 100 * atr_v / p if p else 0.0,
            "upper_wick": upper, "lower_wick": lower,
            "supports": sorted([x for x in ls if x < p], reverse=True)[:4],
            "resistances": sorted([x for x in hs if x > p])[:4],
        }
    return out


def build_snapshots(frame: pd.DataFrame, label: str, decision_times: Iterable[pd.Timestamp]) -> dict[int, dict]:
    """Return snapshots keyed by the source-frame end-row index."""
    # pandas 3 may preserve a microsecond datetime dtype; ``Timestamp.value``
    # is always nanoseconds.  Normalize explicitly so searchsorted cannot
    # silently collapse every requested time onto the final row.
    close_ns = (pd.to_datetime(frame.close_time, utc=True)
                .to_numpy(dtype="datetime64[ns]").astype("int64"))
    ends = sorted({int(np.searchsorted(close_ns, pd.Timestamp(t).value, side="left") - 1)
                   for t in decision_times})
    if not ends or ends[0] < 79:
        raise RuntimeError(f"{label}: insufficient closed history")
    groups = defaultdict(list)
    for end in ends:
        groups[min(240, end + 1)].append(end)
    out = {}
    for width, members in groups.items():
        out.update(_batch_same_width(frame, label, members, width))
    return out


def assert_snapshot_equal(expected: dict, actual: dict, *, atol=2e-10) -> None:
    if expected.keys() != actual.keys():
        raise AssertionError((expected.keys(), actual.keys()))
    exact = {"tf", "bar_id", "obv_up", "obv_fast_up", "higher_closes6", "higher_lows6"}
    for key in expected:
        a, b = expected[key], actual[key]
        if key in exact:
            if a != b: raise AssertionError(f"{key}: {a!r} != {b!r}")
        elif isinstance(a, list):
            if len(a) != len(b) or not np.allclose(a, b, rtol=0, atol=atol):
                raise AssertionError(f"{key}: {a!r} != {b!r}")
        elif not math.isclose(float(a), float(b), rel_tol=0, abs_tol=atol):
            raise AssertionError(f"{key}: {a!r} != {b!r}")
