from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    d = close.diff().fillna(0.0)
    gain = d.clip(lower=0.0)
    loss = (-d).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.mask((avg_loss == 0) & avg_gain.notna(), 100.0)
    return out


def causal_percentile_prev(x: pd.Series, lookback: int = 500) -> pd.Series:
    vals = x.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    for i in range(lookback, len(vals)):
        cur = vals[i]
        hist = vals[i - lookback : i]
        hist = hist[np.isfinite(hist)]
        if not np.isfinite(cur) or len(hist) < int(0.8 * lookback):
            continue
        out[i] = 100.0 * np.mean(hist <= cur)
    return pd.Series(out, index=x.index)


def reconstruct_4h_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.sort_index().copy()
    rolling_low_100 = x["low"].rolling(100, min_periods=100).min()
    x["dip100_uzaklik"] = 100.0 * (x["close"] / rolling_low_100 - 1.0)
    x["dip100_uzaklik_d3_raw"] = x["dip100_uzaklik"].diff(3)
    x["dip100_uzaklik_d3"] = causal_percentile_prev(x["dip100_uzaklik_d3_raw"], 500)

    x["RSI2"] = wilder_rsi(x["close"], 2)
    rsi_diff = x["RSI2"].diff()
    scale = rsi_diff.abs().rolling(20, min_periods=20).mean()
    x["RSI2_hiz"] = rsi_diff / scale.replace(0.0, np.nan)
    x["RSI2_ivme_raw"] = x["RSI2_hiz"] - x["RSI2_hiz"].shift(1)
    x["RSI2_ivme"] = causal_percentile_prev(x["RSI2_ivme_raw"], 500)
    return x


def window_mean(series: pd.Series, event_time: pd.Timestamp, far_hours: int, near_hours: int) -> float:
    lo = event_time - pd.Timedelta(hours=far_hours)
    hi = event_time - pd.Timedelta(hours=near_hours)
    z = series[(series.index >= lo) & (series.index < hi)].dropna()
    return float(z.mean()) if len(z) else float("nan")


def frozen_rule_values(features: pd.DataFrame, event_time: pd.Timestamp) -> dict:
    a = window_mean(features["dip100_uzaklik_d3"], event_time, 24, 12)
    b = window_mean(features["RSI2_ivme"], event_time, 48, 24)
    return {
        "dip100_uzaklik_d3_24_12_mean": a,
        "RSI2_ivme_48_24_mean": b,
        "fires": bool(np.isfinite(a) and np.isfinite(b) and a <= 36.6 and b >= 48.4),
    }
