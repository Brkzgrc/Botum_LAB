from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R2_DIR=HERE.parent/"r2_candidate"
sys.path.insert(0,str(R2_DIR))
import r2_candidate_scanner as sc  # noqa: E402

COST=0.20
HORIZONS=(12,24,72)


def open_at(symbol,t):
    ts=pd.Timestamp(t)
    ms=int(ts.timestamp()*1000)
    rows=sc.get_json("/api/v3/klines",{"symbol":symbol,"interval":"15m","startTime":ms,"limit":1})
    if not rows: return np.nan
    if int(rows[0][0])!=ms: return np.nan
    return float(rows[0][1])


def update_outcomes(hist,now):
    if not len(hist): return hist
    for i,r in hist.iterrows():
        entry_t=pd.Timestamp(r["tested_entry_not_before_utc"])
        if pd.isna(r.get("entry_price",np.nan)) and now>=entry_t:
            try: hist.at[i,"entry_price"]=open_at(r.symbol,entry_t)
            except Exception: pass
        ep=pd.to_numeric(pd.Series([hist.at[i,"entry_price"]]),errors="coerce").iloc[0]
        if not np.isfinite(ep) or ep<=0: continue
        for h in HORIZONS:
            c=f"net_{h}h"
            if c not in hist.columns: hist[c]=np.nan
            if pd.isna(hist.at[i,c]) and now>=entry_t+pd.Timedelta(hours=h):
                try:
                    xp=open_at(r.symbol,entry_t+pd.Timedelta(hours=h))
                    if np.isfinite(xp) and xp>0:
                        hist.at[i,c]=(xp/ep-1)*100-COST
                except Exception: pass
    return hist


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=6)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    history_path=args.outdir/"forward_signals.csv"
    if history_path.exists():
        hist=pd.read_csv(history_path)
    else:
        hist=pd.DataFrame()

    symbols=sc.spot_usdt_symbols()
    signals=sc.run_scan(symbols,workers=max(1,args.workers))
    if signals is None: signals=pd.DataFrame()
    if len(signals):
        signals=signals.copy()
        signals["entry_price"]=np.nan
        for h in HORIZONS: signals[f"net_{h}h"]=np.nan
        if len(hist):
            hist=pd.concat([hist,signals],ignore_index=True)
        else:
            hist=signals
        hist=hist.drop_duplicates(["symbol","decision_time_utc"],keep="first")

    now=pd.Timestamp.now(tz="UTC")
    hist=update_outcomes(hist,now)
    if len(hist):
        hist=hist.sort_values(["decision_time_utc","symbol"])
    hist.to_csv(history_path,index=False)

    summary={
        "candidate":sc.CANDIDATE_NAME,
        "version":sc.CANDIDATE_VERSION,
        "signals_recorded":int(len(hist)),
        "symbols_recorded":int(hist.symbol.nunique()) if len(hist) else 0,
        "resolved_12h":int(pd.to_numeric(hist.get("net_12h",pd.Series(dtype=float)),errors="coerce").notna().sum()) if len(hist) else 0,
        "resolved_24h":int(pd.to_numeric(hist.get("net_24h",pd.Series(dtype=float)),errors="coerce").notna().sum()) if len(hist) else 0,
        "resolved_72h":int(pd.to_numeric(hist.get("net_72h",pd.Series(dtype=float)),errors="coerce").notna().sum()) if len(hist) else 0,
    }
    for h in HORIZONS:
        if len(hist) and f"net_{h}h" in hist:
            v=pd.to_numeric(hist[f"net_{h}h"],errors="coerce").dropna()
            summary[f"net{h}_mean"]=float(v.mean()) if len(v) else None
            summary[f"net{h}_win"]=float((v>0).mean()*100) if len(v) else None

    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (args.outdir/"REPORT.md").write_text("# r2 Forward Shadow\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
