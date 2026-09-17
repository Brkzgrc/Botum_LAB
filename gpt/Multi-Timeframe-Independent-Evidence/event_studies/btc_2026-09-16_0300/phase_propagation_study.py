from __future__ import annotations

import json
import math
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

SYMBOL = "BTCUSDT"
TR = timezone(timedelta(hours=3))
TARGET_TR = datetime(2026, 9, 16, 3, 0, tzinfo=TR)
TARGET_UTC = TARGET_TR.astimezone(timezone.utc)

# Enough warm-up for RSI/MACD/KDJ/OBV plus 60x15m pre-window and long post-window.
FETCH_START = TARGET_UTC - timedelta(days=24)
FETCH_END = TARGET_UTC + timedelta(days=3)

BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://data-api.binance.vision",
]


def get_json(path: str, params: dict, timeout: int = 25):
    last = None
    for base in BASE_URLS:
        try:
            r = requests.get(base + path, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json(), base
            last = RuntimeError(f"{base} HTTP {r.status_code}: {r.text[:160]}")
        except Exception as e:
            last = e
    raise RuntimeError(f"All Binance transports failed: {last}")


def fetch_15m(start: datetime, end: datetime) -> pd.DataFrame:
    rows = []
    cur = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    used = set()
    while cur < end_ms:
        data, base = get_json(
            "/api/v3/klines",
            {"symbol": SYMBOL, "interval": "15m", "startTime": cur, "endTime": end_ms, "limit": 1000},
        )
        used.add(base)
        if not data:
            break
        rows.extend(data)
        nxt = int(data[-1][0]) + 15 * 60 * 1000
        if nxt <= cur:
            break
        cur = nxt
        if len(data) < 1000:
            break
        time.sleep(0.05)
    if not rows:
        raise RuntimeError("No 15m data")
    cols = ["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
    df = pd.DataFrame(rows, columns=cols)
    df = df.drop_duplicates("open_time").sort_values("open_time")
    for c in ["open","high","low","close","volume","quote_volume","taker_base","taker_quote"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("time")[["open","high","low","close","volume"]]
    df.attrs["transports"] = sorted(used)
    return df


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(~((au == 0) & (ad == 0)), 50.0)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["rsi"] = rsi(x.close, 14)
    ema12 = x.close.ewm(span=12, adjust=False).mean()
    ema26 = x.close.ewm(span=26, adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["macd_signal"] = x.macd.ewm(span=9, adjust=False).mean()
    x["macd_hist"] = x.macd - x.macd_signal

    ll9 = x.low.rolling(9).min()
    hh9 = x.high.rolling(9).max()
    rsv = 100 * (x.close - ll9) / (hh9 - ll9).replace(0, np.nan)
    x["kdj_k"] = rsv.ewm(alpha=1/3, adjust=False).mean()
    x["kdj_d"] = x.kdj_k.ewm(alpha=1/3, adjust=False).mean()
    x["kdj_j"] = 3 * x.kdj_k - 2 * x.kdj_d
    x["kdj_spread"] = x.kdj_k - x.kdj_d

    ll14 = x.low.rolling(14).min()
    hh14 = x.high.rolling(14).max()
    x["wpr"] = -100 * (hh14 - x.close) / (hh14 - ll14).replace(0, np.nan)

    sign = np.sign(x.close.diff()).fillna(0)
    x["obv"] = (sign * x.volume).cumsum()
    x["obv_delta"] = x.obv.diff()
    x["obv_slope3"] = x.obv.diff(3) / x.volume.rolling(20).mean().replace(0, np.nan)

    rr = x.rsi
    rr_min = rr.rolling(14).min()
    rr_max = rr.rolling(14).max()
    x["stochrsi_raw"] = 100 * (rr - rr_min) / (rr_max - rr_min).replace(0, np.nan)
    x["stochrsi_k"] = x.stochrsi_raw.rolling(3).mean()
    x["stochrsi_d"] = x.stochrsi_k.rolling(3).mean()
    x["stoch_spread"] = x.stochrsi_k - x.stochrsi_d

    # Movement features: deliberately no absolute RSI/W%R/KDJ/StochRSI threshold gates.
    for c in ["rsi","macd","macd_hist","kdj_k","kdj_d","kdj_j","kdj_spread","wpr","obv","stochrsi_k","stochrsi_d","stoch_spread"]:
        x[c + "_d1"] = x[c].diff()
        x[c + "_d3"] = x[c].diff(3)

    # Candle/price-action descriptors.
    rng = (x.high - x.low).replace(0, np.nan)
    body = x.close - x.open
    x["body_frac"] = body.abs() / rng
    x["close_location"] = (x.close - x.low) / rng
    x["lower_wick_frac"] = (np.minimum(x.open, x.close) - x.low) / rng
    x["upper_wick_frac"] = (x.high - np.maximum(x.open, x.close)) / rng
    x["bull"] = x.close > x.open
    x["hammer_like"] = (x.lower_wick_frac >= 0.5) & (x.body_frac <= 0.4) & (x.close_location >= 0.55)
    prev_bear = x.close.shift(1) < x.open.shift(1)
    x["bull_engulf"] = x.bull & prev_bear & (x.open <= x.close.shift(1)) & (x.close >= x.open.shift(1))

    # Local structural clues, dynamic and relative only.
    x["higher_low"] = x.low > x.low.shift(1)
    x["higher_high"] = x.high > x.high.shift(1)
    x["sweep8_reclaim"] = (x.low < x.low.shift(1).rolling(8).min()) & (x.close > x.low.shift(1).rolling(8).min())
    x["reclaim_prev_high"] = x.close > x.high.shift(1)
    x["range_expansion"] = rng / rng.rolling(20).median()
    x["volume_expansion"] = x.volume / x.volume.rolling(20).median()
    return x


def resample_ohlcv(base: pd.DataFrame, rule: str) -> pd.DataFrame:
    # UTC anchoring matches Binance exchange candles; displaying +03 later yields 4H opens 03/07/11/15/19/23 TR.
    return base.resample(rule, origin="epoch", label="left", closed="left").agg(
        open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last"), volume=("volume","sum")
    ).dropna()


def partial_resample(base_until: pd.DataFrame, rule: str) -> pd.DataFrame:
    return resample_ohlcv(base_until, rule)


def movement_votes(row: pd.Series) -> dict:
    votes = {}
    # Each family is independent. Positive means improving/upward movement, negative means deteriorating.
    votes["RSI"] = np.sign(row.get("rsi_d1", np.nan)) if pd.notna(row.get("rsi_d1", np.nan)) else 0
    votes["MACD"] = np.sign(row.get("macd_hist_d1", np.nan)) if pd.notna(row.get("macd_hist_d1", np.nan)) else 0
    # KDJ: prioritize J turn + K-D spread change, not level.
    a = row.get("kdj_j_d1", np.nan); b = row.get("kdj_spread_d1", np.nan)
    vals = [v for v in [a,b] if pd.notna(v)]
    votes["KDJ"] = np.sign(np.nansum(vals)) if vals else 0
    votes["W%R"] = np.sign(row.get("wpr_d1", np.nan)) if pd.notna(row.get("wpr_d1", np.nan)) else 0
    votes["OBV"] = np.sign(row.get("obv_slope3", np.nan)) if pd.notna(row.get("obv_slope3", np.nan)) else 0
    a = row.get("stochrsi_k_d1", np.nan); b = row.get("stoch_spread_d1", np.nan)
    vals = [v for v in [a,b] if pd.notna(v)]
    votes["STOCHRSI"] = np.sign(np.nansum(vals)) if vals else 0
    return {k:int(v) for k,v in votes.items()}


def evidence(row: pd.Series) -> dict:
    v = movement_votes(row)
    pos = sum(1 for z in v.values() if z > 0)
    neg = sum(1 for z in v.values() if z < 0)
    # This is descriptive, not a trading gate.
    return {"votes":v, "positive":pos, "negative":neg, "net":pos-neg}


def first_sustained_turn(timeline: pd.DataFrame, col: str, after: pd.Timestamp, min_positive_families=4):
    z = timeline[timeline.index >= after].copy()
    # First point where >=4/6 independent families improve for 3 consecutive 15m snapshots.
    good = z[col] >= min_positive_families
    run = good & good.shift(1, fill_value=False) & good.shift(2, fill_value=False)
    if run.any():
        return run[run].index[0]
    return None


def fmt_tr(ts):
    if ts is None or pd.isna(ts):
        return "—"
    return pd.Timestamp(ts).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d %H:%M")


def make_snapshot_timeline(base15: pd.DataFrame) -> pd.DataFrame:
    start = TARGET_UTC - timedelta(hours=10)
    end = TARGET_UTC + timedelta(hours=18)
    snaps = base15[(base15.index >= start) & (base15.index <= end)].index
    rows = []
    for ts in snaps:
        b = base15.loc[:ts]
        tf15 = add_indicators(b)
        tf1 = add_indicators(partial_resample(b, "1h"))
        tf4 = add_indicators(partial_resample(b, "4h"))
        r15 = tf15.iloc[-1]; r1 = tf1.iloc[-1]; r4 = tf4.iloc[-1]
        e15 = evidence(r15); e1 = evidence(r1); e4 = evidence(r4)
        rows.append({
            "time_utc":ts,
            "price":float(r15.close),
            "15m_pos":e15["positive"], "15m_neg":e15["negative"], "15m_net":e15["net"],
            "1h_pos":e1["positive"], "1h_neg":e1["negative"], "1h_net":e1["net"],
            "4h_pos":e4["positive"], "4h_neg":e4["negative"], "4h_net":e4["net"],
            "15m_votes":json.dumps(e15["votes"], ensure_ascii=False),
            "1h_votes":json.dumps(e1["votes"], ensure_ascii=False),
            "4h_votes":json.dumps(e4["votes"], ensure_ascii=False),
            "15m_hammer":bool(r15.get("hammer_like",False)), "15m_engulf":bool(r15.get("bull_engulf",False)),
            "15m_sweep_reclaim":bool(r15.get("sweep8_reclaim",False)), "15m_reclaim_prev_high":bool(r15.get("reclaim_prev_high",False)),
            "1h_hammer":bool(r1.get("hammer_like",False)), "1h_engulf":bool(r1.get("bull_engulf",False)),
            "1h_sweep_reclaim":bool(r1.get("sweep8_reclaim",False)), "1h_reclaim_prev_high":bool(r1.get("reclaim_prev_high",False)),
            "4h_hammer":bool(r4.get("hammer_like",False)), "4h_engulf":bool(r4.get("bull_engulf",False)),
            "4h_sweep_reclaim":bool(r4.get("sweep8_reclaim",False)), "4h_reclaim_prev_high":bool(r4.get("reclaim_prev_high",False)),
        })
    out = pd.DataFrame(rows).set_index("time_utc")
    out.index = pd.to_datetime(out.index, utc=True)
    return out


def closed_bar_tables(base15: pd.DataFrame):
    tf15 = add_indicators(base15)
    tf1 = add_indicators(resample_ohlcv(base15, "1h"))
    tf4 = add_indicators(resample_ohlcv(base15, "4h"))
    return tf15, tf1, tf4


def select_window(df: pd.DataFrame, center: pd.Timestamp, pre: int, post: int) -> pd.DataFrame:
    idx = df.index.searchsorted(center)
    a = max(0, idx-pre)
    b = min(len(df), idx+post+1)
    return df.iloc[a:b].copy()


def summarize_indicator_motion(df: pd.DataFrame, center: pd.Timestamp, pre: int, post: int):
    w = select_window(df, center, pre, post)
    cols = ["open","high","low","close","volume","rsi","macd","macd_signal","macd_hist","kdj_k","kdj_d","kdj_j","wpr","obv","stochrsi_k","stochrsi_d","hammer_like","bull_engulf","higher_low","higher_high","sweep8_reclaim","reclaim_prev_high","volume_expansion","range_expansion"]
    return w[[c for c in cols if c in w.columns]]


def detect_price_structure(df: pd.DataFrame, center: pd.Timestamp, lookback=12, lookforward=12):
    w = select_window(df, center, lookback, lookforward)
    lows = w.low.values; highs = w.high.values
    swings_low=[]; swings_high=[]
    for i in range(2,len(w)-2):
        if lows[i] <= min(lows[i-2:i]) and lows[i] <= min(lows[i+1:i+3]):
            swings_low.append((w.index[i], float(lows[i])))
        if highs[i] >= max(highs[i-2:i]) and highs[i] >= max(highs[i+1:i+3]):
            swings_high.append((w.index[i], float(highs[i])))
    return swings_low, swings_high


def main():
    base15 = fetch_15m(FETCH_START, FETCH_END)
    tf15, tf1, tf4 = closed_bar_tables(base15)
    timeline = make_snapshot_timeline(base15)

    # Full requested windows around target: 4H +/-12 bars, 1H -8/+48, 15M -60/+64.
    w4 = summarize_indicator_motion(tf4, pd.Timestamp(TARGET_UTC), 12, 12)
    w1 = summarize_indicator_motion(tf1, pd.Timestamp(TARGET_UTC), 8, 48)
    w15 = summarize_indicator_motion(tf15, pd.Timestamp(TARGET_UTC), 60, 64)

    for name, df in [("4h_window.csv",w4),("1h_window.csv",w1),("15m_window.csv",w15),("15m_snapshot_timeline.csv",timeline)]:
        z=df.copy(); z.index = z.index.tz_convert("Europe/Istanbul"); z.index.name="time_TR"; z.to_csv(OUT/name)

    first15 = first_sustained_turn(timeline, "15m_pos", pd.Timestamp(TARGET_UTC)-timedelta(hours=4))
    first1 = first_sustained_turn(timeline, "1h_pos", pd.Timestamp(TARGET_UTC)-timedelta(hours=4))
    first4 = first_sustained_turn(timeline, "4h_pos", pd.Timestamp(TARGET_UTC)-timedelta(hours=4))

    # Stronger confirmation: net evidence positive and prior-bar-high reclaim / structural event nearby.
    def first_combo(tf: str):
        z=timeline[timeline.index >= pd.Timestamp(TARGET_UTC)-timedelta(hours=4)].copy()
        cond=(z[f"{tf}_net"]>=2)
        struct=(z[f"{tf}_reclaim_prev_high"] | z[f"{tf}_sweep_reclaim"] | z[f"{tf}_hammer"] | z[f"{tf}_engulf"])
        hit=z[cond & struct]
        return hit.index[0] if len(hit) else None
    combo15, combo1, combo4 = first_combo("15m"), first_combo("1h"), first_combo("4h")

    lows15, highs15 = detect_price_structure(tf15, pd.Timestamp(TARGET_UTC), 60, 64)
    lows1, highs1 = detect_price_structure(tf1, pd.Timestamp(TARGET_UTC), 12, 48)
    lows4, highs4 = detect_price_structure(tf4, pd.Timestamp(TARGET_UTC), 8, 12)

    # Price outcome from potential trigger times.
    def outcome(ts):
        if ts is None: return None
        p0=float(base15.loc[:ts].iloc[-1].close)
        ret={}
        for h in [1,2,4,8,12,24]:
            tgt=ts+timedelta(hours=h)
            q=base15[base15.index>=tgt]
            ret[str(h)+"h"]=(float(q.iloc[0].close)/p0-1)*100 if len(q) else None
        q=base15[(base15.index>ts)&(base15.index<=ts+timedelta(hours=24))]
        ret["MFE24h"]=(float(q.high.max())/p0-1)*100 if len(q) else None
        ret["MAE24h"]=(float(q.low.min())/p0-1)*100 if len(q) else None
        ret["entry_price"]=p0
        return ret

    result={
        "target_TR":TARGET_TR.isoformat(),
        "transports":base15.attrs.get("transports",[]),
        "first_sustained_motion_turn_TR":{"15m":fmt_tr(first15),"1h":fmt_tr(first1),"4h_intrabar":fmt_tr(first4)},
        "first_motion_plus_price_structure_TR":{"15m":fmt_tr(combo15),"1h":fmt_tr(combo1),"4h_intrabar":fmt_tr(combo4)},
        "outcomes":{"15m_combo":outcome(combo15),"1h_combo":outcome(combo1),"4h_combo":outcome(combo4)},
    }
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")

    # Build report with motion, not static levels, as the core interpretation.
    lines=[]
    lines.append("# BTC 16-09-2026 03:00 TR — 4H → 1H → 15M Hareket Yayılımı Olay Çalışması\n")
    lines.append("Bu çalışma sabit RSI/KDJ/W%R/StochRSI eşiklerini **setup kuralı olarak kullanmaz**. Seviyeler yalnızca bağlamdır; tespit yön değişimi, eğim, spread değişimi, OBV akışı ve fiyat yapısına dayanır.\n")
    lines.append("## En önemli metodoloji notu\n")
    lines.append("TradingView'da `03:00` etiketli 4H mum 03:00 TR'de açılır ve 07:00 TR'de kapanır. Bu yüzden iki şeyi ayırdık: **kapanmış-mum analizi** ve 15 dakikalık veriden yeniden oluşturulan **canlı/intrabar 4H durumu**. Böylece geleceği görme (look-ahead) yok.\n")
    lines.append("## İlk hareket dönüşleri\n")
    lines.append(f"- 15M: hareket ailesinden en az 4/6'sının 3 ardışık snapshot iyileşmesi: **{fmt_tr(first15)} TR**")
    lines.append(f"- 1H (canlı/intrabar): aynı tanım: **{fmt_tr(first1)} TR**")
    lines.append(f"- 4H (canlı/intrabar): aynı tanım: **{fmt_tr(first4)} TR**\n")
    lines.append("## Hareket + fiyat yapısı birlikte ilk belirme\n")
    lines.append(f"- 15M: **{fmt_tr(combo15)} TR**")
    lines.append(f"- 1H: **{fmt_tr(combo1)} TR**")
    lines.append(f"- 4H intrabar: **{fmt_tr(combo4)} TR**\n")

    def add_out(label, ts):
        o=outcome(ts)
        if not o: return
        lines.append(f"### {label} — {fmt_tr(ts)} TR")
        lines.append(f"Giriş referansı {o['entry_price']:.2f}. Sonraki 24 saatte MFE **{o['MFE24h']:+.2f}%**, MAE **{o['MAE24h']:+.2f}%**. 4s/8s/12s/24s getiriler: {o['4h']:+.2f}% / {o['8h']:+.2f}% / {o['12h']:+.2f}% / {o['24h']:+.2f}%.\n")
    add_out("15M ilk yapı destekli dönüş", combo15)
    add_out("1H ilk yapı destekli dönüş", combo1)
    add_out("4H intrabar ilk yapı destekli dönüş", combo4)

    lines.append("## Mum ve grafik yapısı araştırması\n")
    lines.append("Otomatik olarak hammer-benzeri mum, bullish engulfing, önceki tepe reclaim, 8-mum dip süpürme/reclaim, higher-low/higher-high ve yerel swing dizileri tarandı. Bunlar tek başına şart değildir; göstergelerin hareket yönüyle birlikte zamanlanır.\n")

    def swing_text(title, lows, highs, n=8):
        lines.append(f"### {title}")
        if lows:
            lines.append("Son yerel dipler: " + ", ".join(f"{fmt_tr(t)}={p:.0f}" for t,p in lows[-n:]))
        if highs:
            lines.append("Son yerel tepeler: " + ", ".join(f"{fmt_tr(t)}={p:.0f}" for t,p in highs[-n:]))
        lines.append("")
    swing_text("15M swing yapısı", lows15, highs15)
    swing_text("1H swing yapısı", lows1, highs1)
    swing_text("4H swing yapısı", lows4, highs4)

    lines.append("## Çalışmanın sınadığı asıl hipotez\n")
    lines.append("Tek bir zaman diliminde 'RSI kaç?' sorusu yerine şu zincir test edilir: **4H'ta satış baskısının zayıflaması / dönüşe izin veren zemin → 1H'ta yön değişiminin oluşması → 15M'de fiyat-yapısı ile giriş tetiği**. Ters yönden bakıldığında ise gerçek dönüş çoğu kez **15M → 1H → 4H** şeklinde teyit yayılımı gösterebilir. İki sıra birbirine zıt değildir: biri üstten-aşağı bağlam/karar akışı, diğeri alttan-yukarı gerçekleşen teyit yayılımıdır.\n")
    lines.append("## Sonraki araştırma önerisi\n")
    lines.append("Bu tek olaydan kural çıkarılmamalı. Aynı hareket-imzasını BTC'nin yüzlerce yükseliş/dönüş episode'unda tarayıp zaman gecikmesi dağılımı çıkarılmalı: 4H baskı-zayıflama anı, 1H dönüş anı, 15M tetik anı; ayrıca yanlış tetiklerde aynı dizinin ne kadar görüldüğü ölçülmeli. Sabit seviyeler sadece açıklayıcı bağlam olarak raporlanmalı, seçim filtresi yapılmamalı.\n")

    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print(f"Report: {OUT/'REPORT.md'}")


if __name__ == "__main__":
    main()
