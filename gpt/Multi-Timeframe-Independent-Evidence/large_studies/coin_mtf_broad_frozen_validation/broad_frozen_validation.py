from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
CAUSAL_DIR = ROOT.parent / "coin_mtf_causal_validation"
sys.path.insert(0, str(CAUSAL_DIR))
import coin_mtf_causal_validation as core  # noqa: E402

UNIVERSE_PATH = PROJECT_ROOT / "frozen_universe.json"
PRIOR100_PATH = CAUSAL_DIR / "output" / "selected_universe.csv"

FETCH_START = pd.Timestamp("2022-11-01", tz="UTC")
START = pd.Timestamp("2023-01-01", tz="UTC")
END = pd.Timestamp("2026-09-18", tz="UTC")
WARMUP_DAYS = 45
COSTS = [0.20, 0.30, 0.40, 0.60]
FROZEN_RULE = "M15_ENGULF & M15_HL_HH & LEAD_GAP4"


def hmod(s: str) -> int:
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8], 16) % 100


def read_universe() -> list[str]:
    obj = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    return [s for s in obj["symbols"] if s != "BTCUSDT"]


def enrich_liquidity(base: pd.DataFrame) -> pd.DataFrame:
    x = base.copy()
    q = pd.to_numeric(x["quote_volume"], errors="coerce")
    x["qv_7d_daily"] = q.rolling(7 * 96, min_periods=96).sum() / 7.0
    x["qv_30d_daily"] = q.rolling(30 * 96, min_periods=7 * 96).sum() / 30.0
    return x


def btc_context() -> pd.DataFrame:
    b = core.fetch_15m("BTCUSDT", start=FETCH_START, end=END)
    t4 = core.indicators(core.resample(b, "4h"))
    g = t4[["motion_pos", "motion_net", "motion_rise"]].copy()
    g.index = g.index + pd.Timedelta(hours=4)
    return g.rename(columns={c: f"btc_h4_{c}" for c in g.columns})


def next_h1_confirm(t: pd.Timestamp, h1_events: pd.DatetimeIndex) -> pd.Timestamp:
    p = h1_events.searchsorted(t, side="right")
    if p >= len(h1_events):
        return pd.NaT
    q = h1_events[p]
    return q if q <= t + pd.Timedelta(hours=4) else pd.NaT


def process_symbol(symbol: str, btc_gate: pd.DataFrame, prior100: set[str]):
    try:
        base = core.fetch_15m(symbol, start=FETCH_START, end=END)
        if len(base) < 2500:
            return None, {"symbol": symbol, "error": f"too_short:{len(base)}"}

        base = enrich_liquidity(base)
        live_start = max(START, base.index.min() + pd.Timedelta(days=WARMUP_DAYS))

        t15 = core.indicators(base)
        d15 = t15.copy()
        d15.index = d15.index + pd.Timedelta(minutes=15)
        d15 = d15[~d15.index.duplicated(keep="last")]
        idx = d15.index

        t1 = core.indicators(core.resample(base, "1h"))
        t4 = core.indicators(core.resample(base, "4h"))
        a1 = core.to_decision_time(t1, pd.Timedelta(hours=1), idx, "h1")
        a4 = core.to_decision_time(t4, pd.Timedelta(hours=4), idx, "h4")

        z = d15.join(a1).join(a4)
        z = z.join(btc_gate.reindex(z.index, method="ffill"))
        z = z[(z.index >= live_start) & (z.index < END)].copy()
        if z.empty:
            return None, {"symbol": symbol, "error": "no_rows_after_warmup"}

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

        base_sig = core.compress(btc_ok & coin_h4_ok & trig & pat, core.COOLDOWN_BARS)
        times = base_sig[base_sig].index
        if not len(times):
            return pd.DataFrame(), None

        fm = core.forward_from_next_open(base, times)
        if fm.empty:
            return pd.DataFrame(), None

        h1_events = pd.DatetimeIndex(t1.index[t1.turn4.fillna(False)] + pd.Timedelta(hours=1))
        rows = []
        for t in fm.index:
            if t not in z.index:
                continue
            engulf = bool(z.at[t, "bull_engulf"])
            hl_hh = bool(z.at[t, "higher_low"]) and bool(z.at[t, "higher_high"])
            lead_gap = float(z.at[t, "motion_net"] - z.at[t, "h1_motion_net"])
            selected = engulf and hl_hh and lead_gap >= 4

            q7 = float(z.at[t, "qv_7d_daily"]) if "qv_7d_daily" in z.columns and pd.notna(z.at[t, "qv_7d_daily"]) else np.nan
            q30 = float(z.at[t, "qv_30d_daily"]) if "qv_30d_daily" in z.columns and pd.notna(z.at[t, "qv_30d_daily"]) else np.nan

            rec = {
                "symbol": symbol,
                "decision_time": t,
                "entry_time": fm.at[t, "entry_time"],
                "entry_open": fm.at[t, "entry_open"],
                "selected": int(selected),
                "rule": FROZEN_RULE,
                "prior_top100": int(symbol in prior100),
                "symbol_hash_mod": hmod(symbol),
                "stoch_pattern": z.at[t, "stoch_pattern"],
                "lead_gap": lead_gap,
                "m15_motion_net": float(z.at[t, "motion_net"]),
                "h1_motion_net": float(z.at[t, "h1_motion_net"]),
                "h4_motion_net": float(z.at[t, "h4_motion_net"]),
                "btc_h4_motion_net": float(z.at[t, "btc_h4_motion_net"]),
                "m15_bull_engulf": int(engulf),
                "m15_higher_low": int(bool(z.at[t, "higher_low"])),
                "m15_higher_high": int(bool(z.at[t, "higher_high"])),
                "qv_7d_daily": q7,
                "qv_30d_daily": q30,
            }
            for h in [3, 4, 6, 12, 24]:
                rec[f"gross_ret_{h}h"] = fm.at[t, f"gross_ret_{h}h"]
                rec[f"mfe_{h}h"] = fm.at[t, f"mfe_{h}h"]
                rec[f"mae_{h}h"] = fm.at[t, f"mae_{h}h"]
            h1t = next_h1_confirm(t, h1_events)
            rec["h1_confirm_within4h"] = int(pd.notna(h1t))
            rec["h1_confirm_time"] = h1t
            rows.append(rec)

        return pd.DataFrame(rows), None
    except Exception as e:
        return None, {"symbol": symbol, "error": repr(e)}


def shard_main(shard: int, shards: int, outdir: Path):
    symbols = read_universe()
    symbols = [s for i, s in enumerate(symbols) if i % shards == shard]
    prior100 = set()
    if PRIOR100_PATH.exists():
        prior100 = set(pd.read_csv(PRIOR100_PATH)["symbol"].astype(str))

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"[SHARD] {shard}/{shards} symbols={len(symbols)} window={START}..{END}", flush=True)
    btc_gate = btc_context()

    frames = []
    errors = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(process_symbol, s, btc_gate, prior100): s for s in symbols}
        for i, fut in enumerate(as_completed(futs), 1):
            d, err = fut.result()
            if err:
                errors.append(err)
            elif d is not None and len(d):
                frames.append(d)
            if i % 10 == 0 or i == len(futs):
                print(f"[SHARD {shard}] {i}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errors)}", flush=True)

    ev = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    ev.to_csv(outdir / "events.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir / "errors.csv", index=False)
    meta = {
        "shard": shard, "shards": shards, "symbols_attempted": len(symbols),
        "symbols_with_events": int(ev.symbol.nunique()) if len(ev) else 0,
        "events": int(len(ev)), "selected_events": int(ev.selected.sum()) if len(ev) else 0,
        "errors": len(errors), "start": str(START), "end": str(END),
        "frozen_rule": FROZEN_RULE,
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2), flush=True)


def metric(d: pd.DataFrame, name: str, cost: float = 0.20) -> dict:
    d = d.dropna(subset=["gross_ret_12h"])
    if d.empty:
        return {"name": name, "n": 0}
    out = {
        "name": name,
        "n": int(len(d)),
        "symbols": int(d.symbol.nunique()),
        "h1_confirm_pct": float(d.h1_confirm_within4h.mean() * 100),
        "qv7_median_daily": float(d.qv_7d_daily.median()) if "qv_7d_daily" in d else np.nan,
    }
    for h in [3, 6, 12, 24]:
        g = d[f"gross_ret_{h}h"]
        out[f"gross_mean_{h}h"] = float(g.mean())
        out[f"gross_median_{h}h"] = float(g.median())
        out[f"net_mean_{h}h_cost{cost:.2f}"] = float((g - cost).mean())
        out[f"net_win_{h}h_cost{cost:.2f}"] = float(((g - cost) > 0).mean() * 100)
    out["mfe12_mean"] = float(d.mfe_12h.mean())
    out["mae12_mean"] = float(d.mae_12h.mean())
    out["mfe12_ge1"] = float((d.mfe_12h >= 1).mean() * 100)
    out["mfe12_ge2"] = float((d.mfe_12h >= 2).mean() * 100)
    out["mfe12_ge3"] = float((d.mfe_12h >= 3).mean() * 100)
    for c in COSTS:
        out[f"net12_mean_cost{c:.2f}"] = float((d.gross_ret_12h - c).mean())
        out[f"net12_win_cost{c:.2f}"] = float(((d.gross_ret_12h - c) > 0).mean() * 100)
    return out


def cluster_boot(selected: pd.DataFrame, base: pd.DataFrame, n=4000, seed=20260918):
    syms = sorted(set(base.symbol.astype(str)))
    if not syms or selected.empty:
        return None
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        draw = rng.choice(syms, size=len(syms), replace=True)
        aa, bb = [], []
        for s in draw:
            a = selected.loc[selected.symbol == s, "gross_ret_12h"].dropna().to_numpy() - 0.20
            b = base.loc[base.symbol == s, "gross_ret_12h"].dropna().to_numpy() - 0.20
            if len(a):
                aa.append(a)
            if len(b):
                bb.append(b)
        if aa and bb:
            vals.append(np.concatenate(aa).mean() - np.concatenate(bb).mean())
    if not vals:
        return None
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return {"mean": float(np.mean(vals)), "ci_low": float(lo), "ci_high": float(hi)}


def aggregate_main(indir: Path, outdir: Path):
    files = sorted(indir.rglob("events.csv"))
    frames = []
    for f in files:
        try:
            x = pd.read_csv(f, low_memory=False)
            if len(x):
                frames.append(x)
        except Exception as e:
            print(f"[AGG] skip {f}: {e}")
    if not frames:
        raise RuntimeError("No shard events found")

    d = pd.concat(frames, ignore_index=True)
    d["decision_time"] = pd.to_datetime(d.decision_time, utc=True)
    d["entry_time"] = pd.to_datetime(d.entry_time, utc=True)
    d = d.sort_values(["decision_time", "symbol"]).reset_index(drop=True)
    d["year"] = d.decision_time.dt.year
    d["selected"] = pd.to_numeric(d.selected, errors="coerce").fillna(0).astype(int)

    outdir.mkdir(parents=True, exist_ok=True)
    d.to_csv(outdir / "all_events.csv", index=False)
    sel = d[d.selected == 1].copy()
    sel.to_csv(outdir / "frozen_rule_events.csv", index=False)

    q = pd.to_numeric(d.qv_7d_daily, errors="coerce")
    d["liq_bucket"] = pd.cut(
        q,
        bins=[-np.inf, 1e6, 5e6, 20e6, np.inf],
        labels=["<1M/day", "1-5M/day", "5-20M/day", ">=20M/day"],
    )
    sel = d[d.selected == 1].copy()

    sections = {}
    sections["ALL_BASE"] = metric(d, "ALL_BASE")
    sections["ALL_SELECTED"] = metric(sel, "ALL_SELECTED")

    for y in sorted(d.year.dropna().unique()):
        yy = d[d.year == y]
        sections[f"Y{int(y)}_BASE"] = metric(yy, f"Y{int(y)}_BASE")
        sections[f"Y{int(y)}_SELECTED"] = metric(yy[yy.selected == 1], f"Y{int(y)}_SELECTED")

    pre2026 = d[d.decision_time < pd.Timestamp("2026-01-01", tz="UTC")]
    sections["PRE2026_BASE"] = metric(pre2026, "PRE2026_BASE")
    sections["PRE2026_SELECTED"] = metric(pre2026[pre2026.selected == 1], "PRE2026_SELECTED")

    new_symbols = d[d.prior_top100 == 0]
    sections["NEW_SYMBOLS_BASE"] = metric(new_symbols, "NEW_SYMBOLS_BASE")
    sections["NEW_SYMBOLS_SELECTED"] = metric(new_symbols[new_symbols.selected == 1], "NEW_SYMBOLS_SELECTED")

    new_2026 = d[(d.prior_top100 == 0) & (d.decision_time >= pd.Timestamp("2026-01-01", tz="UTC"))]
    sections["NEW_SYMBOLS_2026_BASE"] = metric(new_2026, "NEW_SYMBOLS_2026_BASE")
    sections["NEW_SYMBOLS_2026_SELECTED"] = metric(new_2026[new_2026.selected == 1], "NEW_SYMBOLS_2026_SELECTED")

    fresh = d[(d.decision_time < pd.Timestamp("2026-01-01", tz="UTC")) | (d.prior_top100 == 0)]
    sections["FRESH_EVIDENCE_BASE"] = metric(fresh, "FRESH_EVIDENCE_BASE")
    sections["FRESH_EVIDENCE_SELECTED"] = metric(fresh[fresh.selected == 1], "FRESH_EVIDENCE_SELECTED")

    liquidity = {}
    for b in ["<1M/day", "1-5M/day", "5-20M/day", ">=20M/day"]:
        x = d[d.liq_bucket.astype(str) == b]
        liquidity[b] = {
            "base": metric(x, f"{b}_BASE"),
            "selected": metric(x[x.selected == 1], f"{b}_SELECTED"),
        }

    boot = cluster_boot(sel, d)
    boot_fresh = cluster_boot(fresh[fresh.selected == 1], fresh)

    summary = {
        "frozen_rule": FROZEN_RULE,
        "rule_was_reoptimized": False,
        "absolute_oscillator_levels_used_as_rule": False,
        "future_features_used": False,
        "entry_model": "closed 15m decision; completed 1h/4h/BTC4h only; one extra 15m safety delay; fill at next open",
        "window": [str(START), str(END)],
        "frozen_universe_size": len(read_universe()),
        "events": int(len(d)),
        "selected_events": int(d.selected.sum()),
        "symbols_with_events": int(d.symbol.nunique()),
        "selected_symbols": int(sel.symbol.nunique()),
        "sections": sections,
        "liquidity_buckets_descriptive_only": liquidity,
        "selected_minus_base_net12_cost0p20_symbol_cluster_bootstrap": boot,
        "fresh_selected_minus_base_net12_cost0p20_symbol_cluster_bootstrap": boot_fresh,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frozen MTF Lead-Lag Rule — Broad Historical Validation",
        "",
        f"Frozen rule: {FROZEN_RULE}",
        "",
        "Bu çalışma kuralı yeniden seçmez/değiştirmez. Sabit osilatör seviyesi setup şartı değildir.",
        "15M karar yalnız kapanmış mumdan gelir; 1H/4H/BTC4H yalnız tamamen kapanmış mumdan gelir.",
        "Giriş karar anında değil, ek 15 dakika güvenlik gecikmesi sonrası bir sonraki 15M açılışındadır.",
        "",
        f"Window: {START.date()}..{END.date()} | universe={len(read_universe())} | events={len(d)} | selected={int(d.selected.sum())} | selected symbols={sel.symbol.nunique()}",
        "",
    ]
    order = ["ALL", "PRE2026", "NEW_SYMBOLS", "NEW_SYMBOLS_2026", "FRESH_EVIDENCE"] + [f"Y{y}" for y in sorted(d.year.unique())]
    for key in order:
        b = sections.get(f"{key}_BASE", {})
        s = sections.get(f"{key}_SELECTED", {})
        if not b or not s:
            continue
        lines += [
            f"## {key}",
            f"Base: n={b.get('n',0)} net12@0.20={b.get('net12_mean_cost0.20',np.nan):.3f}% win={b.get('net12_win_cost0.20',np.nan):.1f}%",
            f"Selected: n={s.get('n',0)} net12@0.20={s.get('net12_mean_cost0.20',np.nan):.3f}% win={s.get('net12_win_cost0.20',np.nan):.1f}% H1<=4h={s.get('h1_confirm_pct',np.nan):.1f}% MFE12={s.get('mfe12_mean',np.nan):.2f}% MAE12={s.get('mae12_mean',np.nan):.2f}%",
            "",
        ]
    lines += [
        "## Bootstrap",
        f"All selected-base: {boot}",
        f"Fresh evidence selected-base: {boot_fresh}",
        "",
        "## Liquidity (descriptive; NOT a selection gate)",
    ]
    for b, obj in liquidity.items():
        s = obj["selected"]
        lines.append(f"- {b}: n={s.get('n',0)} net12@0.20={s.get('net12_mean_cost0.20',np.nan):.3f}% win={s.get('net12_win_cost0.20',np.nan):.1f}%")
    (outdir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int)
    ap.add_argument("--shards", type=int, default=8)
    ap.add_argument("--outdir", type=Path)
    ap.add_argument("--aggregate-dir", type=Path)
    args = ap.parse_args()
    if args.aggregate_dir is not None:
        aggregate_main(args.aggregate_dir, args.outdir or (ROOT / "output"))
    else:
        if args.shard is None:
            raise SystemExit("--shard required unless --aggregate-dir is used")
        shard_main(args.shard, args.shards, args.outdir or (ROOT / f"shard_{args.shard}"))


if __name__ == "__main__":
    main()
