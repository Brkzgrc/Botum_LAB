from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
CAUSAL_DIR = PARENT / "coin_mtf_causal_validation"
sys.path.insert(0, str(CAUSAL_DIR))
import coin_mtf_causal_validation as core  # noqa: E402

EVENTS_PATH = PARENT / "coin_mtf_broad_frozen_validation" / "output" / "frozen_rule_events.csv"
FETCH_START = pd.Timestamp("2022-10-15", tz="UTC")
FETCH_END = pd.Timestamp("2026-09-18", tz="UTC")
ROUND_TRIP_COST = 0.20
FWD_HOURS = [1,2,3,4,6,8,12,18,24,36,48,72,96,120,168]
BACK_HOURS = [1,2,4,8,12,24,48]
UP_LEVELS = [0.5,1.0,2.0,3.0,5.0,8.0]
DOWN_LEVELS = [0.5,1.0,2.0,3.0,5.0]
MAX_FWD_H = max(FWD_HOURS)


def load_events() -> pd.DataFrame:
    d = pd.read_csv(EVENTS_PATH, low_memory=False)
    d["decision_time"] = pd.to_datetime(d["decision_time"], utc=True)
    d["entry_time"] = pd.to_datetime(d["entry_time"], utc=True)
    d = d.sort_values(["symbol","decision_time"]).reset_index(drop=True)
    return d


def first_hit(rel_hi: np.ndarray, rel_lo: np.ndarray, level: float, up: bool) -> int | None:
    a = rel_hi if up else rel_lo
    if up:
        idx = np.flatnonzero(a >= level)
    else:
        idx = np.flatnonzero(a <= -level)
    return int(idx[0]) if len(idx) else None


def first_confirm_after(t: pd.Timestamp, h1: pd.DataFrame, mode: str, max_h: int = 12):
    close_times = h1.index + pd.Timedelta(hours=1)
    z = h1.copy()
    z.index = close_times
    z = z[(z.index > t) & (z.index <= t + pd.Timedelta(hours=max_h))]
    if z.empty:
        return pd.NaT
    if mode == "turn4":
        m = z["turn4"].fillna(False)
    elif mode == "momentum":
        m = (z["motion_pos"] >= 4) & (z["motion_net"] > 0) & ((z["motion_rise"] >= 1) | z["turn4"].fillna(False))
    elif mode == "structure":
        struct = (
            z["bull_engulf"].fillna(False) |
            (z["higher_low"].fillna(False) & z["higher_high"].fillna(False)) |
            z["reclaim_prev_high"].fillna(False) |
            z["sweep_reclaim"].fillna(False)
        )
        m = struct & (z["motion_pos"] >= 3)
    elif mode == "combined":
        struct = (
            z["bull_engulf"].fillna(False) |
            (z["higher_low"].fillna(False) & z["higher_high"].fillna(False)) |
            z["reclaim_prev_high"].fillna(False) |
            z["sweep_reclaim"].fillna(False)
        )
        mom = (z["motion_pos"] >= 4) & (z["motion_net"] > 0)
        m = struct & mom
    else:
        raise ValueError(mode)
    hit = z.index[m.fillna(False)]
    return hit[0] if len(hit) else pd.NaT


def add_path_stats(rec: dict, base: pd.DataFrame, entry_time: pd.Timestamp, prefix: str):
    idx = base.index
    if entry_time not in idx:
        return
    i = idx.get_loc(entry_time)
    if not isinstance(i, (int, np.integer)):
        return
    entry = float(base.open.iloc[i])
    if not np.isfinite(entry) or entry <= 0:
        return
    rec[f"{prefix}_entry_time"] = entry_time
    rec[f"{prefix}_entry_price"] = entry

    for h in FWD_HOURS:
        j = i + h*4
        if j >= len(base):
            rec[f"{prefix}_ret_{h}h"] = np.nan
            rec[f"{prefix}_net_{h}h"] = np.nan
            rec[f"{prefix}_mfe_{h}h"] = np.nan
            rec[f"{prefix}_mae_{h}h"] = np.nan
            continue
        exitp = float(base.open.iloc[j])
        rec[f"{prefix}_ret_{h}h"] = (exitp/entry - 1)*100
        rec[f"{prefix}_net_{h}h"] = rec[f"{prefix}_ret_{h}h"] - ROUND_TRIP_COST
        sl = base.iloc[i:min(j, len(base)-1)+1]
        rec[f"{prefix}_mfe_{h}h"] = (float(sl.high.max())/entry - 1)*100
        rec[f"{prefix}_mae_{h}h"] = (float(sl.low.min())/entry - 1)*100

    endj = min(i + MAX_FWD_H*4, len(base)-1)
    path = base.iloc[i:endj+1]
    rel_hi = (path.high.to_numpy(float)/entry - 1)*100
    rel_lo = (path.low.to_numpy(float)/entry - 1)*100

    for lvl in UP_LEVELS:
        k = first_hit(rel_hi, rel_lo, lvl, True)
        rec[f"{prefix}_t_up_{str(lvl).replace('.','p')}h"] = np.nan if k is None else k/4.0
    for lvl in DOWN_LEVELS:
        k = first_hit(rel_hi, rel_lo, lvl, False)
        rec[f"{prefix}_t_dn_{str(lvl).replace('.','p')}h"] = np.nan if k is None else k/4.0

    # Full 7-day peak/trough timing.
    kh = int(np.nanargmax(rel_hi)) if len(rel_hi) else 0
    kl = int(np.nanargmin(rel_lo)) if len(rel_lo) else 0
    rec[f"{prefix}_mfe_168h"] = float(np.nanmax(rel_hi)) if len(rel_hi) else np.nan
    rec[f"{prefix}_mae_168h"] = float(np.nanmin(rel_lo)) if len(rel_lo) else np.nan
    rec[f"{prefix}_t_mfe_168h"] = kh/4.0
    rec[f"{prefix}_t_mae_168h"] = kl/4.0

    # Outcome morphology. These labels are descriptive only, never used as entry features.
    t1 = rec.get(f"{prefix}_t_up_1p0h", np.nan)
    t3 = rec.get(f"{prefix}_t_up_3p0h", np.nan)
    t5 = rec.get(f"{prefix}_t_up_5p0h", np.nan)
    td2 = rec.get(f"{prefix}_t_dn_2p0h", np.nan)

    cls = "NO_3PCT_7D"
    if pd.notna(t3):
        if t3 <= 12:
            cls = "IMMEDIATE_3PCT"
        elif t3 <= 72:
            cls = "DELAYED_3PCT_12_72H"
        else:
            cls = "LATE_3PCT_72_168H"

    # Rise -> retrace -> later real rise:
    # first +1% occurs, then price trades back to entry or below after that,
    # and only later reaches +3%, all within 72h.
    rec[f"{prefix}_rise_retrace_then_3pct"] = 0
    if pd.notna(t1) and pd.notna(t3) and t1 < t3 <= 72:
        k1 = int(round(t1*4))
        k3 = int(round(t3*4))
        if k3 > k1:
            interim_low = float(rel_lo[k1:k3+1].min())
            if interim_low <= 0:
                rec[f"{prefix}_rise_retrace_then_3pct"] = 1
                cls = "RISE_RETRACE_THEN_3PCT"

    rec[f"{prefix}_path_class"] = cls
    rec[f"{prefix}_up3_before_dn2"] = int(pd.notna(t3) and (pd.isna(td2) or t3 < td2))
    rec[f"{prefix}_up5_within_72h"] = int(pd.notna(t5) and t5 <= 72)


def process_symbol(symbol: str, ev: pd.DataFrame):
    try:
        base = core.fetch_15m(symbol, start=FETCH_START, end=FETCH_END)
        t15 = core.indicators(base)
        h1 = core.indicators(core.resample(base, "1h"))
        idx = base.index
        rows = []

        for _, e in ev.iterrows():
            t = e.decision_time
            entry_time = e.entry_time
            if entry_time not in idx:
                continue
            i = idx.get_loc(entry_time)
            if not isinstance(i, (int, np.integer)):
                continue

            rec = {
                "symbol": symbol,
                "decision_time": t,
                "original_entry_time": entry_time,
                "original_entry_price": float(base.open.iloc[i]),
                "year": int(t.year),
            }

            # Backward path: what actually happened before the signal.
            ref = float(base.open.iloc[i])
            for h in BACK_HOURS:
                j = i - h*4
                if j >= 0:
                    old = float(base.open.iloc[j])
                    rec[f"back_ret_{h}h"] = (ref/old - 1)*100
                    sl = base.iloc[j:i+1]
                    rec[f"back_drawdown_{h}h"] = (ref/float(sl.high.max()) - 1)*100
                    rec[f"back_bounce_from_low_{h}h"] = (ref/float(sl.low.min()) - 1)*100
                else:
                    rec[f"back_ret_{h}h"] = np.nan
                    rec[f"back_drawdown_{h}h"] = np.nan
                    rec[f"back_bounce_from_low_{h}h"] = np.nan

            # Original early entry path.
            add_path_stats(rec, base, entry_time, "early")

            # Multiple causal 1H confirmation definitions. The confirmation candle must close first.
            for mode in ["turn4","momentum","structure","combined"]:
                ct = first_confirm_after(t, h1, mode, max_h=12)
                rec[f"{mode}_confirm_time"] = ct
                rec[f"{mode}_confirm_wait_h"] = np.nan if pd.isna(ct) else (ct-t).total_seconds()/3600
                if pd.notna(ct):
                    # One extra 15m safety delay after the CLOSED 1H confirmation.
                    fill = ct + pd.Timedelta(minutes=15)
                    if fill in idx:
                        rec[f"{mode}_delay_vs_early_pct"] = (float(base.open.loc[fill])/ref - 1)*100
                        add_path_stats(rec, base, fill, mode)

            rows.append(rec)

        return pd.DataFrame(rows), None
    except Exception as ex:
        return None, {"symbol": symbol, "error": repr(ex)}


def shard_main(shard: int, shards: int, outdir: Path):
    all_ev = load_events()
    syms = sorted(all_ev.symbol.astype(str).unique())
    mine = [s for i,s in enumerate(syms) if i % shards == shard]
    outdir.mkdir(parents=True, exist_ok=True)
    frames=[]; errors=[]

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {}
        for s in mine:
            ev = all_ev[all_ev.symbol.astype(str) == s].copy()
            futs[ex.submit(process_symbol, s, ev)] = s
        for k,f in enumerate(as_completed(futs),1):
            d,err=f.result()
            if err:
                errors.append(err)
            elif d is not None and len(d):
                frames.append(d)
            if k % 10 == 0 or k == len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errors)}", flush=True)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"paths.csv", index=False)
    pd.DataFrame(errors).to_csv(outdir/"errors.csv", index=False)
    meta={"shard":shard,"symbols":len(mine),"events":int(len(out)),"errors":len(errors)}
    (outdir/"meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta), flush=True)


def summarize_group(d: pd.DataFrame, prefix: str):
    x = d[pd.notna(d.get(f"{prefix}_entry_price"))].copy()
    if x.empty:
        return {"n":0}
    out={"n":int(len(x)),"symbols":int(x.symbol.nunique())}
    for h in FWD_HOURS:
        c=f"{prefix}_net_{h}h"
        if c in x:
            v=pd.to_numeric(x[c],errors="coerce")
            out[f"net_{h}h_mean"]=float(v.mean())
            out[f"net_{h}h_median"]=float(v.median())
            out[f"net_{h}h_win_pct"]=float((v>0).mean()*100)
    for target in ["1p0","2p0","3p0","5p0"]:
        c=f"{prefix}_t_up_{target}h"
        if c in x:
            v=pd.to_numeric(x[c],errors="coerce")
            out[f"hit_{target}_within12h_pct"]=float((v<=12).mean()*100)
            out[f"hit_{target}_within24h_pct"]=float((v<=24).mean()*100)
            out[f"hit_{target}_within72h_pct"]=float((v<=72).mean()*100)
            out[f"hit_{target}_within168h_pct"]=float((v<=168).mean()*100)
            out[f"median_time_to_{target}_h"]=float(v.median()) if v.notna().any() else np.nan
    out["up3_before_dn2_pct"]=float(pd.to_numeric(x.get(f"{prefix}_up3_before_dn2"),errors="coerce").mean()*100)
    out["rise_retrace_then_3pct_pct"]=float(pd.to_numeric(x.get(f"{prefix}_rise_retrace_then_3pct"),errors="coerce").mean()*100)
    out["up5_within72h_pct"]=float(pd.to_numeric(x.get(f"{prefix}_up5_within_72h"),errors="coerce").mean()*100)
    tmfe=pd.to_numeric(x.get(f"{prefix}_t_mfe_168h"),errors="coerce")
    out["median_time_to_7d_mfe_h"]=float(tmfe.median())
    out["p25_time_to_7d_mfe_h"]=float(tmfe.quantile(.25))
    out["p75_time_to_7d_mfe_h"]=float(tmfe.quantile(.75))
    out["mfe_7d_mean"]=float(pd.to_numeric(x.get(f"{prefix}_mfe_168h"),errors="coerce").mean())
    out["mae_7d_mean"]=float(pd.to_numeric(x.get(f"{prefix}_mae_168h"),errors="coerce").mean())
    cls=x.get(f"{prefix}_path_class")
    if cls is not None:
        out["path_classes"]={str(k):int(v) for k,v in cls.value_counts(dropna=False).to_dict().items()}
    return out


def aggregate_main(indir: Path, outdir: Path):
    files=sorted(indir.rglob("paths.csv"))
    frames=[]
    for f in files:
        x=pd.read_csv(f,low_memory=False)
        if len(x): frames.append(x)
    if not frames:
        raise RuntimeError("no path files")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    outdir.mkdir(parents=True,exist_ok=True)
    d.to_csv(outdir/"all_event_paths.csv",index=False)

    summary={
        "purpose":"Describe the full pre/post path and causal confirmation-entry behavior instead of judging signals only at a fixed 12h close.",
        "round_trip_cost_pct":ROUND_TRIP_COST,
        "lookahead_policy":{
            "strategy_entries":"strictly causal; closed 15m/1h only; confirmation entry waits an extra 15m after the closed 1h confirmation",
            "future_path_labels":"descriptive outcome labels only; never used as entry features"
        },
        "events":int(len(d)),
        "symbols":int(d.symbol.nunique()),
        "early_all":summarize_group(d,"early"),
        "confirmations":{
            m:summarize_group(d,m) for m in ["turn4","momentum","structure","combined"]
        },
        "years":{},
        "confirmation_wait_buckets":{},
        "back_path_success_comparison":{},
    }

    for y in sorted(pd.to_numeric(d.year,errors="coerce").dropna().astype(int).unique()):
        yy=d[pd.to_numeric(d.year,errors="coerce")==y]
        summary["years"][str(y)]={
            "early":summarize_group(yy,"early"),
            **{m:summarize_group(yy,m) for m in ["turn4","momentum","structure","combined"]}
        }

    # Does "confirmation soon" matter, and how much move is already lost by waiting?
    for m in ["turn4","momentum","structure","combined"]:
        wait=pd.to_numeric(d.get(f"{m}_confirm_wait_h"),errors="coerce")
        buckets={}
        for lo,hi,label in [(0,1,"0-1h"),(1,2,"1-2h"),(2,4,"2-4h"),(4,8,"4-8h"),(8,12,"8-12h")]:
            z=d[(wait>lo)&(wait<=hi)]
            if len(z):
                s=summarize_group(z,m)
                delay=pd.to_numeric(z.get(f"{m}_delay_vs_early_pct"),errors="coerce")
                s["median_price_delay_vs_early_pct"]=float(delay.median())
                s["mean_price_delay_vs_early_pct"]=float(delay.mean())
                buckets[label]=s
        summary["confirmation_wait_buckets"][m]=buckets

    # Compare what happened BEFORE events that later truly trend vs those that do not.
    success=pd.to_numeric(d.get("early_t_up_3p0h"),errors="coerce")<=72
    for c in [x for x in d.columns if x.startswith("back_ret_") or x.startswith("back_drawdown_") or x.startswith("back_bounce_")]:
        a=pd.to_numeric(d.loc[success,c],errors="coerce")
        b=pd.to_numeric(d.loc[~success,c],errors="coerce")
        summary["back_path_success_comparison"][c]={
            "success_median":float(a.median()),
            "fail_median":float(b.median()),
            "success_mean":float(a.mean()),
            "fail_mean":float(b.mean()),
        }

    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")

    ea=summary["early_all"]
    lines=[
        "# Event Path Morphology — Full Horizon / Causal Confirmation Study",
        "",
        f"Events={summary['events']} | symbols={summary['symbols']} | round-trip cost={ROUND_TRIP_COST:.2f}%",
        "",
        "Bu çalışma sinyali yalnız 12 saat kapanışına bakarak yargılamaz. 1 saatten 7 güne kadar tüm yolu, ilk hedefe ulaşma zamanını, geri çekilme-sonra-yükseliş dizisini ve kapanmış 1H teyidinden sonra gerçekçi girişi ölçer.",
        "",
        "## Early 15M entry — horizon curve",
    ]
    for h in FWD_HOURS:
        lines.append(f"- {h}h: net mean={ea.get(f'net_{h}h_mean',np.nan):.3f}% | median={ea.get(f'net_{h}h_median',np.nan):.3f}% | win={ea.get(f'net_{h}h_win_pct',np.nan):.1f}%")
    lines += [
        "",
        "## Early-entry path morphology",
        f"- +3% within 12h: {ea.get('hit_3p0_within12h_pct',np.nan):.1f}%",
        f"- +3% within 24h: {ea.get('hit_3p0_within24h_pct',np.nan):.1f}%",
        f"- +3% within 72h: {ea.get('hit_3p0_within72h_pct',np.nan):.1f}%",
        f"- +3% within 7d: {ea.get('hit_3p0_within168h_pct',np.nan):.1f}%",
        f"- Rise -> retrace -> later +3% within 72h: {ea.get('rise_retrace_then_3pct_pct',np.nan):.1f}%",
        f"- +3% before -2%: {ea.get('up3_before_dn2_pct',np.nan):.1f}%",
        f"- Median time to 7d MFE: {ea.get('median_time_to_7d_mfe_h',np.nan):.1f}h (P25={ea.get('p25_time_to_7d_mfe_h',np.nan):.1f}h, P75={ea.get('p75_time_to_7d_mfe_h',np.nan):.1f}h)",
        "",
        "## Causal 1H confirmation entries",
    ]
    for m,s in summary["confirmations"].items():
        lines.append(f"- {m}: n={s.get('n',0)} | net12={s.get('net_12h_mean',np.nan):.3f}% | net24={s.get('net_24h_mean',np.nan):.3f}% | net72={s.get('net_72h_mean',np.nan):.3f}% | +3%<=72h={s.get('hit_3p0_within72h_pct',np.nan):.1f}%")
    (outdir/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard",type=int)
    ap.add_argument("--shards",type=int,default=8)
    ap.add_argument("--outdir",type=Path)
    ap.add_argument("--aggregate-dir",type=Path)
    args=ap.parse_args()
    if args.aggregate_dir:
        aggregate_main(args.aggregate_dir,args.outdir or ROOT/"output")
    else:
        if args.shard is None:
            raise SystemExit("--shard required")
        shard_main(args.shard,args.shards,args.outdir or ROOT/f"shard_{args.shard}")


if __name__=="__main__":
    main()
