#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC OI/Funding causal enrichment + veto research layer.

Input: baseline_signals.json produced by the live-parity replay.
This script DOES NOT generate signals and DOES NOT alter the baseline.
It attaches only BTC futures information known at/before signal_time, then
evaluates pre-declared veto families on development/validation/final holdout.

Expected signal fields:
  signal_time, symbol, setup_kind, close_pct, close_reason
Optional: entry_time is accepted as alias for signal_time.

Binance public USD-M endpoints are used; no paid API.
"""
from __future__ import annotations
import argparse, json, math, time
from pathlib import Path
from datetime import timezone
import numpy as np
import pandas as pd
import requests

BASE="https://fapi.binance.com"
S=requests.Session()
S.headers.update({"User-Agent":"Botum-OI-Funding-Audit/1.0"})
COST_PCT=0.20

def get(path, params=None, tries=5):
    last=None
    for i in range(tries):
        try:
            r=S.get(BASE+path,params=params or {},timeout=30)
            if r.status_code in (418,429):
                time.sleep(1.5*(2**i)); continue
            r.raise_for_status(); return r.json()
        except Exception as e:
            last=e; time.sleep(.5*(2**i))
    raise RuntimeError(f"{path}: {last}")

def ms(ts): return int(pd.Timestamp(ts).timestamp()*1000)

def fetch_funding(start,end):
    rows=[]; cur=ms(start); stop=ms(end)
    while cur<stop:
        x=get("/fapi/v1/fundingRate",{"symbol":"BTCUSDT","startTime":cur,"endTime":stop,"limit":1000})
        if not x: break
        rows.extend(x); nxt=int(x[-1]["fundingTime"])+1
        if nxt<=cur: break
        cur=nxt; time.sleep(.04)
    d=pd.DataFrame(rows)
    if d.empty: return d
    d["time"]=pd.to_datetime(d.fundingTime.astype("int64"),unit="ms",utc=True)
    d["funding"]=pd.to_numeric(d.fundingRate,errors="coerce")
    return d[["time","funding"]].dropna().drop_duplicates("time").sort_values("time")

def fetch_oi_hist(start,end,period="5m"):
    """Binance OI history. Endpoint retention can be limited; caller records coverage."""
    rows=[]; cur=ms(start); stop=ms(end)
    while cur<stop:
        x=get("/futures/data/openInterestHist",{"symbol":"BTCUSDT","period":period,"startTime":cur,"endTime":stop,"limit":500})
        if not x: break
        rows.extend(x); nxt=int(x[-1]["timestamp"])+1
        if nxt<=cur: break
        cur=nxt; time.sleep(.04)
    d=pd.DataFrame(rows)
    if d.empty: return d
    d["time"]=pd.to_datetime(d.timestamp.astype("int64"),unit="ms",utc=True)
    d["oi_usdt"]=pd.to_numeric(d.sumOpenInterestValue,errors="coerce")
    return d[["time","oi_usdt"]].dropna().drop_duplicates("time").sort_values("time")

def backward_join(sig, data, cols):
    if data.empty:
        for c in cols: sig[c]=np.nan
        return sig
    return pd.merge_asof(sig.sort_values("signal_time"),data.sort_values("time"),
                         left_on="signal_time",right_on="time",direction="backward").drop(columns=["time"])

def add_features(sig,oi,funding):
    if not oi.empty:
        o=oi.copy().set_index("time").sort_index()
        # causal features: pct changes and trailing z/percentile use only current/past observations
        o["oi_chg_1h"]=o.oi_usdt.pct_change(12)*100
        o["oi_chg_4h"]=o.oi_usdt.pct_change(48)*100
        roll=o.oi_usdt.rolling(12*24*7,min_periods=12*24)
        o["oi_z_7d"]=(o.oi_usdt-roll.mean())/roll.std().replace(0,np.nan)
        # 7d rolling percentile, causal
        o["oi_pctile_7d"]=o.oi_usdt.rolling(12*24*7,min_periods=12*24).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1],raw=False)
        oi=o.reset_index()
    sig=backward_join(sig,oi,["oi_usdt","oi_chg_1h","oi_chg_4h","oi_z_7d","oi_pctile_7d"])
    sig=backward_join(sig,funding,["funding"])
    sig["funding_bps"]=sig.funding*10000
    return sig

def metrics(d):
    if d.empty: return {"n":0}
    p=pd.to_numeric(d.close_pct,errors="coerce").dropna()
    wins=p[p>0]; losses=p[p<0]
    eq=p.cumsum(); dd=eq-eq.cummax()
    return {
      "n":int(len(p)),"win_rate_pct":round(float((p>0).mean()*100),2),
      "net_pct_sum":round(float(p.sum()),2),"expectancy_pct":round(float(p.mean()),4),
      "profit_factor":round(float(wins.sum()/abs(losses.sum())),3) if len(losses) and losses.sum()!=0 else None,
      "max_drawdown_pct_sum":round(float(dd.min()),2) if len(dd) else 0.0,
    }

def split(df):
    # chronological 60/20/20; thresholds are not fitted on final holdout
    d=df.sort_values("signal_time").reset_index(drop=True); n=len(d)
    a=int(n*.60); b=int(n*.80)
    d["sample"]="development"; d.loc[a:b-1,"sample"]="validation"; d.loc[b:,"sample"]="final_holdout"
    return d

def veto_specs():
    # Predeclared coarse families; no full-sample optimization.
    return {
      "OI_1H_RISE_1": lambda x: x.oi_chg_1h>=1.0,
      "OI_1H_RISE_2": lambda x: x.oi_chg_1h>=2.0,
      "OI_Z7D_1_5": lambda x: x.oi_z_7d>=1.5,
      "FUNDING_POS_1BP": lambda x: x.funding_bps>=1.0,
      "FUNDING_POS_2BP": lambda x: x.funding_bps>=2.0,
      "OI1H1_AND_FUND1BP": lambda x: (x.oi_chg_1h>=1.0)&(x.funding_bps>=1.0),
      "OI_Z1_5_AND_FUND1BP": lambda x: (x.oi_z_7d>=1.5)&(x.funding_bps>=1.0),
    }

def evaluate(df):
    out=[]
    families=["ALL"]+sorted(df.setup_kind.fillna("UNKNOWN").unique().tolist())
    for sample in ["development","validation","final_holdout"]:
      z=df[df["sample"]==sample]
      for fam in families:
        q=z if fam=="ALL" else z[z.setup_kind.fillna("UNKNOWN")==fam]
        base=metrics(q)
        for name,fn in veto_specs().items():
          mask=fn(q).fillna(False)
          kept=q[~mask]; blocked=q[mask]
          m=metrics(kept)
          out.append({
            "sample":sample,"family":fam,"veto":name,"baseline":base,"after_veto":m,
            "blocked_n":int(mask.sum()),
            "blocked_losses":int((pd.to_numeric(blocked.close_pct,errors="coerce")<0).sum()),
            "blocked_wins":int((pd.to_numeric(blocked.close_pct,errors="coerce")>0).sum()),
            "net_delta_pct_sum":round(float(m.get("net_pct_sum",0)-base.get("net_pct_sum",0)),2)
          })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="baseline_signals.json")
    ap.add_argument("--output",default="oi_funding_audit.json")
    ap.add_argument("--enriched",default="baseline_signals_oi_funding.json")
    args=ap.parse_args()
    raw=json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows=raw["trades"] if isinstance(raw,dict) and "trades" in raw else raw
    df=pd.DataFrame(rows)
    if "signal_time" not in df and "entry_time" in df: df["signal_time"]=df.entry_time
    need={"signal_time","setup_kind","close_pct"}
    miss=need-set(df.columns)
    if miss: raise SystemExit(f"Eksik alanlar: {sorted(miss)}")
    df["signal_time"]=pd.to_datetime(df.signal_time,utc=True)
    df=split(df)
    start=df.signal_time.min()-pd.Timedelta(days=8); end=df.signal_time.max()+pd.Timedelta(hours=1)
    funding=fetch_funding(start,end)
    try: oi=fetch_oi_hist(start,end)
    except Exception as e:
        print("[OI COVERAGE ERROR]",e); oi=pd.DataFrame()
    enriched=add_features(df,oi,funding)
    coverage={
      "signals":len(enriched),
      "funding_pct":round(float(enriched.funding.notna().mean()*100),2),
      "oi_pct":round(float(enriched.oi_usdt.notna().mean()*100),2),
      "oi_first":oi.time.min().isoformat() if not oi.empty else None,
      "oi_last":oi.time.max().isoformat() if not oi.empty else None,
      "funding_first":funding.time.min().isoformat() if not funding.empty else None,
      "funding_last":funding.time.max().isoformat() if not funding.empty else None,
    }
    Path(args.enriched).write_text(enriched.to_json(orient="records",date_format="iso",indent=2),encoding="utf-8")
    result={"coverage":coverage,"baseline_by_sample":{s:metrics(enriched[enriched["sample"]==s]) for s in enriched["sample"].unique()},"veto_results":evaluate(enriched),
            "notes":["Funding join is backward-only.","OI join is backward-only.","Final holdout is never used to choose thresholds.","If Binance OI-history retention does not cover the baseline, OI conclusions are invalid until an archive/source fills the gap."]}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(coverage,ensure_ascii=False)); print("OUT",args.output)

if __name__=="__main__": main()
