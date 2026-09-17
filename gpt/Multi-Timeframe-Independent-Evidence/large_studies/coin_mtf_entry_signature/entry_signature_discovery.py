from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

CAUSAL_DIR = ROOT.parent / "coin_mtf_causal_validation"
sys.path.insert(0, str(CAUSAL_DIR))
import coin_mtf_causal_validation as core  # noqa: E402

UNIVERSE_CSV = CAUSAL_DIR / "output" / "selected_universe.csv"
TRAIN_END = pd.Timestamp("2026-05-01", tz="UTC")
CAL_END = pd.Timestamp("2026-07-01", tz="UTC")
COST = 0.20
MIN_CAL_SELECTED = 100

INDICATORS = ["rsi", "macd_hist", "kdj_j", "kdj_spread", "wpr", "obv", "stoch_k", "stoch_spread"]


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Build movement-only features. No absolute oscillator level is exposed."""
    x = core.indicators(df)

    # Normalize indicator changes by their own recent movement scale so that
    # cross-coin comparisons do not depend on price/OBV units.
    for c in INDICATORS:
        d1 = x[c].diff()
        d3 = x[c].diff(3)
        scale1 = d1.abs().rolling(48, min_periods=12).median().replace(0, np.nan)
        scale3 = d3.abs().rolling(48, min_periods=12).median().replace(0, np.nan)
        x[f"{c}_d1n"] = d1 / scale1
        x[f"{c}_d3n"] = d3 / scale3
        x[f"{c}_accn"] = (d1 - d1.shift(1)) / scale1
        s = np.sign(d1.fillna(0))
        x[f"{c}_sign4"] = s + s.shift(1).fillna(0) + s.shift(2).fillna(0) + s.shift(3).fillna(0)

    for k in [1, 2, 4, 8]:
        x[f"price_ret_{k}"] = x.close.pct_change(k) * 100
    x["price_accel_1"] = x["price_ret_1"] - x["price_ret_1"].shift(1)
    x["price_accel_4"] = x["price_ret_4"] - x["price_ret_4"].shift(1)

    rng = (x.high - x.low).replace(0, np.nan)
    x["range_pct"] = rng / x.close.shift(1) * 100
    x["body_signed_pct"] = (x.close - x.open) / x.open.replace(0, np.nan) * 100
    x["upper_wick_frac"] = (x.high - np.maximum(x.open, x.close)) / rng
    x["volume_log_ratio"] = np.log((x.volume / x.volume.rolling(20, min_periods=8).median()).replace(0, np.nan))
    x["range_log_ratio"] = np.log((rng / rng.rolling(20, min_periods=8).median()).replace(0, np.nan))
    return x


def feature_columns(x: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for c in INDICATORS:
        cols += [f"{c}_d1n", f"{c}_d3n", f"{c}_accn", f"{c}_sign4"]
    cols += [
        "motion_pos", "motion_neg", "motion_net", "motion_rise",
        "price_ret_1", "price_ret_2", "price_ret_4", "price_ret_8",
        "price_accel_1", "price_accel_4", "range_pct", "body_signed_pct",
        "close_loc", "lower_wick", "upper_wick_frac", "volume_log_ratio", "range_log_ratio",
        "hammer", "bull_engulf", "higher_low", "higher_high", "sweep_reclaim",
        "reclaim_prev_high", "structure",
    ]
    return [c for c in cols if c in x.columns]


def align_closed(tf: pd.DataFrame, delta: pd.Timedelta, decision_index: pd.DatetimeIndex, prefix: str) -> pd.DataFrame:
    z = tf.copy()
    z.index = z.index + delta  # feature becomes knowable only when the TF candle has closed
    cols = feature_columns(z)
    z = z[cols].rename(columns={c: f"{prefix}_{c}" for c in cols})
    return z.reindex(decision_index, method="ffill")


def decision_15m(tf15: pd.DataFrame) -> pd.DataFrame:
    z = tf15.copy()
    z.index = z.index + pd.Timedelta(minutes=15)  # closed 15m candle becomes knowable here
    z = z[~z.index.duplicated(keep="last")]
    return z


def btc_context() -> tuple[pd.DataFrame, pd.DataFrame]:
    base = core.fetch_15m("BTCUSDT")
    t4 = enrich(core.resample(base, "4h"))
    # Exact setup gate needs these summary fields. Rich BTC features are aligned separately per coin.
    gate = t4[["motion_pos", "motion_net", "motion_rise"]].copy()
    gate.index = gate.index + pd.Timedelta(hours=4)
    gate = gate.rename(columns={c: f"btc_h4_{c}" for c in gate.columns})
    return t4, gate


def next_h1_confirm(t: pd.Timestamp, h1_events: pd.DatetimeIndex) -> pd.Timestamp:
    p = h1_events.searchsorted(t, side="right")
    if p >= len(h1_events):
        return pd.NaT
    q = h1_events[p]
    return q if q <= t + pd.Timedelta(hours=4) else pd.NaT


def process_symbol(symbol: str, rank_qv: float, btc4: pd.DataFrame, btc_gate: pd.DataFrame):
    try:
        base = core.fetch_15m(symbol)
        if len(base) < 2000 or base.index.min() > core.FETCH_START + pd.Timedelta(days=5):
            return symbol, None, "insufficient_history"

        t15 = enrich(base)
        d15 = decision_15m(t15)
        idx = d15.index
        t1 = enrich(core.resample(base, "1h"))
        t4 = enrich(core.resample(base, "4h"))

        h1 = align_closed(t1, pd.Timedelta(hours=1), idx, "h1")
        h4 = align_closed(t4, pd.Timedelta(hours=4), idx, "h4")
        b4 = align_closed(btc4, pd.Timedelta(hours=4), idx, "btc4")
        z = d15.join(h1).join(h4).join(b4)
        z = z.join(btc_gate.reindex(idx, method="ffill"))
        z = z[(z.index >= core.START) & (z.index < core.END)].copy()
        z["stoch_pattern"] = core.stoch_pattern(z)

        btc_ok = (z.btc_h4_motion_pos >= 2) & (
            (z.btc_h4_motion_rise >= 0) |
            (z.btc_h4_motion_net > z.btc_h4_motion_net.shift(16))
        )
        coin_h4_ok = (z.h4_motion_pos >= 2) & (
            (z.h4_motion_rise >= 0) |
            (z.h4_motion_net > z.h4_motion_net.shift(16))
        )
        trig = (z.motion_pos >= 4) & ((z.turn4) | (z.motion_rise >= 1)) & z.structure
        pat = z.stoch_pattern.isin(["-0++", "-00+"])
        sig = core.compress(btc_ok & coin_h4_ok & trig & pat, core.COOLDOWN_BARS)
        times = sig[sig].index
        if not len(times):
            return symbol, pd.DataFrame(), None

        fm = core.forward_from_next_open(base, times)
        if fm.empty:
            return symbol, pd.DataFrame(), None

        # Completed 1H turn events become knowable at candle close only.
        h1_event_mask = t1.turn4.fillna(False)
        h1_events = pd.DatetimeIndex(t1.index[h1_event_mask] + pd.Timedelta(hours=1))

        f15 = feature_columns(d15)
        rows = []
        for t in fm.index:
            if t not in z.index:
                continue
            h1t = next_h1_confirm(t, h1_events)
            r = {
                "symbol": symbol,
                "decision_time": t,
                "entry_time": fm.at[t, "entry_time"],
                "symbol_bucket": core.symbol_bucket(symbol),
                "period_bucket": "LATE_HOLDOUT" if t >= core.LATE_SPLIT else "EARLY",
                "rank_quote_volume": rank_qv,
                "h1_confirm_within4h": int(pd.notna(h1t)),
                "h1_confirm_time": h1t,
                "gross_ret_12h": fm.at[t, "gross_ret_12h"],
                "net_ret_12h_cost0p2": fm.at[t, "gross_ret_12h"] - COST,
                "mfe_12h": fm.at[t, "mfe_12h"],
                "mae_12h": fm.at[t, "mae_12h"],
                "stoch_pattern": z.at[t, "stoch_pattern"],
            }
            # Current closed 15m features.
            for c in f15:
                r[f"m15_{c}"] = d15.at[t, c] if t in d15.index else np.nan
            # Already-aligned completed 1H / 4H / BTC4 features.
            for c in h1.columns:
                r[c] = z.at[t, c]
            for c in h4.columns:
                r[c] = z.at[t, c]
            for c in b4.columns:
                r[c] = z.at[t, c]
            rows.append(r)
        return symbol, pd.DataFrame(rows), None
    except Exception as e:
        return symbol, None, repr(e)


def model_features(df: pd.DataFrame) -> list[str]:
    prefixes = ("m15_", "h1_", "h4_", "btc4_")
    exclude = {
        "h1_confirm_within4h", "h1_confirm_time", "gross_ret_12h", "net_ret_12h_cost0p2",
        "mfe_12h", "mae_12h", "rank_quote_volume",
    }
    cols = []
    for c in df.columns:
        if c in exclude or not c.startswith(prefixes):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c]):
            cols.append(c)
    return cols


def metrics(d: pd.DataFrame, name: str) -> dict:
    d = d.dropna(subset=["net_ret_12h_cost0p2"])
    if not len(d):
        return {"name": name, "n": 0}
    return {
        "name": name,
        "n": int(len(d)),
        "symbols": int(d.symbol.nunique()),
        "h1_confirm_pct": float(d.h1_confirm_within4h.mean() * 100),
        "net12_mean": float(d.net_ret_12h_cost0p2.mean()),
        "net12_median": float(d.net_ret_12h_cost0p2.median()),
        "net12_win_pct": float((d.net_ret_12h_cost0p2 > 0).mean() * 100),
        "mfe12_mean": float(d.mfe_12h.mean()),
        "mae12_mean": float(d.mae_12h.mean()),
    }


def cluster_bootstrap(selected: pd.DataFrame, broad: pd.DataFrame, n=3000, seed=20260917):
    syms = sorted(set(broad.symbol.unique()))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        draw = rng.choice(syms, size=len(syms), replace=True)
        a_parts = []
        b_parts = []
        for s in draw:
            aa = selected.loc[selected.symbol == s, "net_ret_12h_cost0p2"].dropna().to_numpy()
            bb = broad.loc[broad.symbol == s, "net_ret_12h_cost0p2"].dropna().to_numpy()
            if len(aa): a_parts.append(aa)
            if len(bb): b_parts.append(bb)
        if a_parts and b_parts:
            vals.append(np.concatenate(a_parts).mean() - np.concatenate(b_parts).mean())
    if not vals:
        return {"mean": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return {"mean": float(np.mean(vals)), "ci_low": float(lo), "ci_high": float(hi)}


def robust_effects(df: pd.DataFrame, features: list[str], subsets: dict[str, pd.Series]) -> list[dict]:
    out = []
    for c in features:
        rec = {"feature": c}
        signs = []
        ok = True
        mags = []
        for name, mask in subsets.items():
            q = df.loc[mask, [c, "h1_confirm_within4h"]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(q) < 50:
                ok = False; break
            a = q.loc[q.h1_confirm_within4h == 1, c]
            b = q.loc[q.h1_confirm_within4h == 0, c]
            if len(a) < 15 or len(b) < 15:
                ok = False; break
            iqr = q[c].quantile(.75) - q[c].quantile(.25)
            if not np.isfinite(iqr) or iqr == 0:
                ok = False; break
            eff = float((a.median() - b.median()) / iqr)
            rec[f"{name}_effect_iqr"] = eff
            signs.append(np.sign(eff)); mags.append(abs(eff))
        if ok:
            rec["same_direction_all"] = bool(len(set(int(s) for s in signs if s != 0)) <= 1)
            rec["min_abs_effect"] = float(min(mags))
            out.append(rec)
    out.sort(key=lambda r: (r["same_direction_all"], r["min_abs_effect"]), reverse=True)
    return out[:25]


def main():
    uni = pd.read_csv(UNIVERSE_CSV)
    uni = uni.head(100)
    btc4, btc_gate = btc_context()

    frames = []
    errors = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {
            ex.submit(process_symbol, r.symbol, float(r.median_daily_quote_volume), btc4, btc_gate): r.symbol
            for r in uni.itertuples(index=False)
        }
        for i, fut in enumerate(as_completed(futs), 1):
            sym, d, err = fut.result()
            if err:
                errors.append({"symbol": sym, "error": err})
            elif d is not None and len(d):
                frames.append(d)
            if i % 10 == 0:
                print(f"processed {i}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errors)}", flush=True)

    if not frames:
        raise RuntimeError("No events produced")
    ev = pd.concat(frames, ignore_index=True)
    ev["decision_time"] = pd.to_datetime(ev.decision_time, utc=True)
    ev["entry_time"] = pd.to_datetime(ev.entry_time, utc=True)
    ev = ev.sort_values(["decision_time", "symbol"]).reset_index(drop=True)
    ev.to_csv(OUT / "entry_signature_events.csv", index=False)
    pd.DataFrame(errors).to_csv(OUT / "errors.csv", index=False)

    feats = model_features(ev)
    X = ev[feats].replace([np.inf, -np.inf], np.nan)
    y = ev.h1_confirm_within4h.astype(int)

    train = (ev.symbol_bucket == "DEV_SYMBOL") & (ev.decision_time < TRAIN_END)
    calib = (ev.symbol_bucket == "DEV_SYMBOL") & (ev.decision_time >= TRAIN_END) & (ev.decision_time < CAL_END)
    final = (ev.symbol_bucket == "HOLDOUT_SYMBOL") & (ev.decision_time >= CAL_END)
    late_all = ev.decision_time >= CAL_END
    holdout_early = (ev.symbol_bucket == "HOLDOUT_SYMBOL") & (ev.decision_time < CAL_END)

    models = {
        "LOGISTIC": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1500, class_weight="balanced", C=0.5)),
        ]),
        "RANDOM_FOREST": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=500, max_depth=8, min_samples_leaf=30,
                max_features="sqrt", class_weight="balanced_subsample",
                n_jobs=-1, random_state=42,
            )),
        ]),
    }

    candidates = []
    fitted = {}
    for name, model in models.items():
        model.fit(X.loc[train], y.loc[train])
        fitted[name] = model
        p_train = model.predict_proba(X.loc[train])[:, 1]
        p_cal = model.predict_proba(X.loc[calib])[:, 1]
        for q in [0.50, 0.60, 0.70, 0.80, 0.90]:
            thr = float(np.quantile(p_train, q))
            sel_mask = p_cal >= thr
            idx = X.loc[calib].index[sel_mask]
            d = ev.loc[idx]
            if len(d) < MIN_CAL_SELECTED:
                continue
            m = metrics(d, f"{name}_q{int(q*100)}")
            m.update({"model": name, "quantile": q, "threshold": thr, "cal_selected_frac": float(sel_mask.mean())})
            # Calibration-only choice: favor tradable net return; confirmation precision breaks near ties.
            m["selection_score"] = m["net12_mean"] + 0.002 * m["h1_confirm_pct"]
            candidates.append(m)

    if not candidates:
        raise RuntimeError("No model/threshold candidate met minimum calibration sample")
    candidates.sort(key=lambda r: r["selection_score"], reverse=True)
    champion = candidates[0]
    model = fitted[champion["model"]]
    thr = champion["threshold"]

    def apply(mask: pd.Series, name: str):
        p = model.predict_proba(X.loc[mask])[:, 1]
        idx = X.loc[mask].index[p >= thr]
        return ev.loc[idx].copy(), metrics(ev.loc[idx], name), float((p >= thr).mean())

    final_sel, final_m, final_frac = apply(final, "FINAL_DOUBLE_HOLDOUT_SELECTED")
    late_sel, late_m, late_frac = apply(late_all, "LATE_ALL_SELECTED")
    he_sel, he_m, he_frac = apply(holdout_early, "HOLDOUT_SYMBOLS_EARLY_SELECTED")

    base_train = metrics(ev.loc[train], "TRAIN_BASE")
    base_cal = metrics(ev.loc[calib], "CALIB_BASE")
    base_final = metrics(ev.loc[final], "FINAL_DOUBLE_HOLDOUT_BASE")
    base_late = metrics(ev.loc[late_all], "LATE_ALL_BASE")
    base_he = metrics(ev.loc[holdout_early], "HOLDOUT_SYMBOLS_EARLY_BASE")

    boot = cluster_bootstrap(final_sel, ev.loc[final]) if len(final_sel) else {"mean": np.nan, "ci_low": np.nan, "ci_high": np.nan}

    # Explain the mechanism, but do not use final-period effects for model/threshold selection.
    effects = robust_effects(ev, feats, {"train": train, "calib": calib, "final": final})

    # Model importance for interpretation.
    importance = []
    if champion["model"] == "RANDOM_FOREST":
        imp = model.named_steps["model"].feature_importances_
        importance = sorted([{"feature": f, "importance": float(v)} for f, v in zip(feats, imp)], key=lambda r: r["importance"], reverse=True)[:25]
    else:
        coef = np.abs(model.named_steps["model"].coef_[0])
        importance = sorted([{"feature": f, "importance": float(v)} for f, v in zip(feats, coef)], key=lambda r: r["importance"], reverse=True)[:25]

    final_sel.to_csv(OUT / "final_selected_events.csv", index=False)
    pd.DataFrame(candidates).to_csv(OUT / "calibration_candidates.csv", index=False)
    pd.DataFrame(effects).to_csv(OUT / "stable_feature_effects.csv", index=False)

    summary = {
        "purpose": "Predict, using only information known at the closed-15m decision time, which 15m setups will receive completed-1H confirmation within 4h; then test whether that distinction improves real next-open trading outcomes.",
        "lookahead_lock": {
            "absolute_oscillator_levels_used": False,
            "15m_features": "closed candle only",
            "1h_features": "completed 1H candles only",
            "4h_features": "completed 4H candles only",
            "btc_features": "completed BTC 4H candles only",
            "entry": "signal decision t, one full 15m safety delay, fill at open t+15m",
            "future_1h_confirmation_used_as_feature": False,
        },
        "splits": {
            "train": "DEV_SYMBOL, 2026-01-15 <= t < 2026-05-01",
            "calibration": "DEV_SYMBOL, 2026-05-01 <= t < 2026-07-01",
            "final_double_holdout": "HOLDOUT_SYMBOL, t >= 2026-07-01",
        },
        "event_count": int(len(ev)),
        "feature_count": int(len(feats)),
        "errors": int(len(errors)),
        "champion_selected_on_calibration_only": champion,
        "baselines": {"train": base_train, "calibration": base_cal, "final": base_final, "late_all": base_late, "holdout_early": base_he},
        "selected": {
            "final": {**final_m, "selected_fraction": final_frac},
            "late_all": {**late_m, "selected_fraction": late_frac},
            "holdout_early": {**he_m, "selected_fraction": he_frac},
        },
        "final_selected_minus_base_net12_symbol_cluster_bootstrap": boot,
        "top_model_features": importance,
        "stable_confirm_vs_no_confirm_entry_time_effects": effects,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [
        "# Coin MTF Entry-Time Signature Discovery — Strictly Causal",
        "",
        "Amaç: 15M sinyali çıktığı anda, gelecekteki 1H mumunu görmeden, 1H'ın 4 saat içinde teyit verip vermeyeceğini giriş anındaki hareket geometrisinden ayırmak.",
        "",
        "## Look-ahead kilidi",
        "- Sabit RSI/KDJ/W%R/StochRSI seviyesi feature değildir.",
        "- 15M feature yalnızca kapanmış 15M mumdan gelir.",
        "- 1H/4H/BTC4H feature yalnızca tamamen kapanmış üst-zaman mumu kapandıktan sonra kullanılabilir.",
        "- Giriş karar anında değil; ek 15 dakika güvenlik gecikmesi sonrası bir sonraki açılıştadır.",
        "- Gelecekteki 1H teyidi sadece hedef/etikettir, feature değildir.",
        "- Model ve eşik yalnız TRAIN+CALIBRATION tarafında seçilir; FINAL double-holdout seçim sürecine hiç girmez.",
        "",
        f"Olay={len(ev)} | feature={len(feats)} | hata={len(errors)}",
        f"Seçilen model={champion['model']} | train-prob quantile={champion['quantile']:.2f} | threshold={champion['threshold']:.4f}",
        f"Calibration seçili: n={champion['n']} | H1 teyit={champion['h1_confirm_pct']:.1f}% | net12=%{champion['net12_mean']:.3f}",
        "",
        "## FINAL double-holdout",
        f"BASE: n={base_final.get('n',0)} | H1 teyit={base_final.get('h1_confirm_pct',np.nan):.1f}% | net12=%{base_final.get('net12_mean',np.nan):.3f} | win={base_final.get('net12_win_pct',np.nan):.1f}%",
        f"SELECTED: n={final_m.get('n',0)} | H1 teyit={final_m.get('h1_confirm_pct',np.nan):.1f}% | net12=%{final_m.get('net12_mean',np.nan):.3f} | win={final_m.get('net12_win_pct',np.nan):.1f}% | selected={final_frac*100:.1f}%",
        f"Selected - base net12 cluster-bootstrap: %{boot['mean']:.3f} [%95 GA {boot['ci_low']:.3f}, {boot['ci_high']:.3f}]",
        "",
        "## En etkili giriş-anı hareket feature'ları",
    ]
    for r in importance[:15]:
        lines.append(f"- {r['feature']}: {r['importance']:.4f}")
    lines += ["", "## Confirm / no-confirm ayrımında üç bölümde de aynı yönü koruyan feature'lar"]
    for r in effects[:15]:
        lines.append(f"- {r['feature']}: train={r['train_effect_iqr']:.3f}, calib={r['calib_effect_iqr']:.3f}, final={r['final_effect_iqr']:.3f}")
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
