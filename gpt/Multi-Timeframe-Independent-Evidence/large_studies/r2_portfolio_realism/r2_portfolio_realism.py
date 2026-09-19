from __future__ import annotations

import argparse
import heapq
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R2_DIR=HERE.parent.parent/"r2_candidate"
sys.path.insert(0,str(R2_DIR))
import r2_common as rc  # noqa: E402


def simulate(d,max_slots=3,hold_h=24,per_symbol_lock=True,daily_entry_cap=None):
    x=d.sort_values(["entry_time","symbol"]).copy()
    equity=100.0
    cash=100.0
    active=[]  # (exit_ts, serial, symbol, notional, ret_pct)
    active_symbols=set()
    serial=0
    accepted=0; skipped_slots=0; skipped_symbol=0; skipped_daily=0
    curve=[]
    day_count={}

    def settle(until):
        nonlocal cash,equity
        while active and active[0][0] <= until:
            exit_ts,_,sym,notional,rp=heapq.heappop(active)
            cash += notional * (1.0 + rp/100.0)
            active_symbols.discard(sym)
            equity=cash+sum(p[3] for p in active)
            curve.append((exit_ts,equity))

    for r in x.itertuples(index=False):
        t=pd.Timestamp(r.entry_time)
        settle(t)
        day=str(t.date())
        if daily_entry_cap is not None and day_count.get(day,0)>=daily_entry_cap:
            skipped_daily+=1; continue
        if per_symbol_lock and r.symbol in active_symbols:
            skipped_symbol+=1; continue
        if len(active)>=max_slots:
            skipped_slots+=1; continue
        slot_fraction=1.0/max_slots
        notional=min(cash,equity*slot_fraction)
        if notional<=0: continue
        rp=float(getattr(r,f"net_{hold_h}h"))
        cash-=notional
        serial+=1
        exit_ts=t+pd.Timedelta(hours=hold_h)
        heapq.heappush(active,(exit_ts,serial,r.symbol,notional,rp))
        active_symbols.add(r.symbol)
        day_count[day]=day_count.get(day,0)+1
        accepted+=1
        equity=cash+sum(p[3] for p in active)

    settle(pd.Timestamp.max.tz_localize("UTC") if x.entry_time.dt.tz is not None else pd.Timestamp.max)
    if active:
        raise RuntimeError("unsettled positions")

    curve=pd.DataFrame(curve,columns=["time","equity"]).sort_values("time") if curve else pd.DataFrame(columns=["time","equity"])
    if len(curve):
        peak=curve.equity.cummax()
        dd=(curve.equity/peak-1)*100
        maxdd=float(dd.min())
    else: maxdd=np.nan
    total=(equity/100-1)*100
    return {"max_slots":max_slots,"hold_h":hold_h,"daily_entry_cap":daily_entry_cap,
            "accepted":accepted,"skipped_slots":skipped_slots,"skipped_symbol":skipped_symbol,
            "skipped_daily":skipped_daily,"final_equity":float(equity),"total_return_pct":float(total),
            "max_drawdown_pct":maxdd}


def period_stats(d):
    z=d.copy()
    z["day"]=z.entry_time.dt.floor("D")
    z["week"]=z.entry_time.dt.to_period("W").astype(str)
    z["month"]=z.entry_time.dt.to_period("M").astype(str)
    out={}
    for key in ("day","week","month"):
        g=z.groupby(key).agg(signals=("symbol","size"),coins=("symbol","nunique"),
                             mean24=("net_24h","mean"),sum24=("net_24h","sum"))
        out[key]={"periods":int(len(g)),"signals_median":float(g.signals.median()) if len(g) else np.nan,
                  "signals_p90":float(g.signals.quantile(.9)) if len(g) else np.nan,
                  "max_signals":int(g.signals.max()) if len(g) else 0,
                  "positive_period_pct":float((g.sum24>0).mean()*100) if len(g) else np.nan}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=12)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    d=rc.load_r2(args.artifact_dir,args.workers)
    masks=rc.split_masks(d)

    scenarios=[]
    for h in (12,24,72):
        for slots in (1,2,3,5,10):
            for cap in (None,1,3,5):
                scenarios.append(simulate(d,slots,h,True,cap))
    sdf=pd.DataFrame(scenarios).sort_values(["hold_h","max_slots","daily_entry_cap"],na_position="first")
    sdf.to_csv(args.outdir/"portfolio_scenarios.csv",index=False)

    split_results={}
    for k,m in masks.items():
        q=d[m].copy()
        split_results[k]={
            "events":int(len(q)),
            "period_stats":period_stats(q),
            "scenarios":[simulate(q,slots,24,True,cap) for slots in (1,2,3,5,10) for cap in (None,3)]
        }

    # Overlap diagnostics independent of a chosen capital model.
    xs=d.sort_values("entry_time")
    overlaps=[]
    for r in xs.itertuples(index=False):
        t=pd.Timestamp(r.entry_time)
        overlaps.append(int(((xs.entry_time<t)&(xs.entry_time+pd.Timedelta(hours=24)>t)).sum()))
    d["concurrent_before_entry_24h"]=overlaps
    conc={
        "median":float(d.concurrent_before_entry_24h.median()),
        "p90":float(d.concurrent_before_entry_24h.quantile(.9)),
        "max":int(d.concurrent_before_entry_24h.max()),
        "pct_entries_with_existing_position":float((d.concurrent_before_entry_24h>0).mean()*100),
        "pct_entries_with_3plus_existing":float((d.concurrent_before_entry_24h>=3).mean()*100),
    }

    summary={"purpose":"Translate frozen r2 event returns into constrained portfolio behavior without changing signal thresholds.",
             "events":int(len(d)),"symbols":int(d.symbol.nunique()),"overlap_24h":conc,
             "all_period_stats":period_stats(d),"split_results":split_results}
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (args.outdir/"REPORT.md").write_text("# r2 Portfolio Realism\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
