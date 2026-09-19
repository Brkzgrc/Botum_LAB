from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

COST = 0.20
DIP_PCT = 0.50
WINDOW_BARS = 8   # 2h
EXIT_BARS = 96    # 24h after each actual fill

REQUIRED_EVENT_COLS = {"event_id","symbol","decision_time","entry_time","hash_mod","net_24h"}
REQUIRED_PATH_COLS = {"event_id","bar_i","open","high","low","close"}


def split_masks(d):
    t=d["decision_time"]
    return {
        "DISCOVERY": (d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
        "CALIBRATION": (d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
        "FINAL_HOLDOUT_2026": (d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
    }


def net_ret(exit_px,entry_px):
    return (exit_px/entry_px-1.0)*100.0-COST


def metrics(v):
    x=pd.to_numeric(v,errors="coerce").dropna()
    if not len(x): return {"n":0}
    gp=float(x[x>0].sum()); gl=float(-x[x<0].sum())
    return {
        "n":int(len(x)),"mean":float(x.mean()),"median":float(x.median()),
        "win":float((x>0).mean()*100.0),"pf":gp/gl if gl>0 else None,
        "q10":float(x.quantile(.10)),"q25":float(x.quantile(.25)),
    }


def load_dataset(dataset_dir):
    ev=pd.read_csv(dataset_dir/"r2_events.csv",low_memory=False)
    pa=pd.read_csv(dataset_dir/"r2_paths.csv",low_memory=False)
    me=sorted(REQUIRED_EVENT_COLS-set(ev.columns)); mp=sorted(REQUIRED_PATH_COLS-set(pa.columns))
    if me or mp: raise RuntimeError(f"missing columns events={me} paths={mp}")
    ev["decision_time"]=pd.to_datetime(ev.decision_time,utc=True)
    ev["entry_time"]=pd.to_datetime(ev.entry_time,utc=True)
    ev["event_id"]=pd.to_numeric(ev.event_id,errors="raise").astype(int)
    ev["hash_mod"]=pd.to_numeric(ev.hash_mod,errors="raise").astype(int)
    ev["net_24h"]=pd.to_numeric(ev.net_24h,errors="coerce")
    for c in ["event_id","bar_i"]: pa[c]=pd.to_numeric(pa[c],errors="raise").astype(int)
    for c in ["open","high","low","close"]: pa[c]=pd.to_numeric(pa[c],errors="coerce")
    paths={int(eid):g.sort_values("bar_i").reset_index(drop=True) for eid,g in pa.groupby("event_id")}
    return ev,paths


def preflight(dataset_dir):
    ev,paths=load_dataset(dataset_dir)
    masks=split_masks(ev); counts={k:int(v.sum()) for k,v in masks.items()}
    if len(ev)<150 or min(counts.values())<20: raise RuntimeError(f"bad cohort/splits rows={len(ev)} counts={counts}")
    if len(paths)!=ev.event_id.nunique(): raise RuntimeError("path/event mismatch")
    minbars=min(len(g) for g in paths.values())
    if minbars<110: raise RuntimeError(f"insufficient path bars: {minbars}")
    diffs=[]
    for r in ev.itertuples(index=False):
        g=paths[int(r.event_id)]
        calc=net_ret(float(g.open.iloc[EXIT_BARS]),float(g.open.iloc[0]))
        diffs.append(abs(calc-float(r.net_24h)))
    md=float(max(diffs))
    if md>1e-8: raise RuntimeError(f"baseline mismatch max_diff={md}")
    return {"events":int(len(ev)),"symbols":int(ev.symbol.nunique()),"split_counts":counts,"min_path_bars":int(minbars),"baseline_max_abs_diff":md}


def find_dip(g):
    base=float(g.open.iloc[0]); trigger=base*(1-DIP_PCT/100.0)
    for i in range(min(WINDOW_BARS,len(g)-EXIT_BARS-2)):
        if float(g.close.iloc[i])<=trigger:
            j=i+1; x=j+EXIT_BARS
            if x<len(g):
                return {"entry_i":j,"return":net_ret(float(g.open.iloc[x]),float(g.open.iloc[j]))}
    return None


def event_policy(g, immediate_weight, no_dip_mode):
    base_ret=net_ret(float(g.open.iloc[EXIT_BARS]),float(g.open.iloc[0]))
    dip=find_dip(g)
    w0=float(immediate_weight); w1=1.0-w0
    if dip is not None:
        return w0*base_ret+w1*float(dip["return"]), "DIP", int(dip["entry_i"])
    if no_dip_mode=="CASH":
        return w0*base_ret, "NO_DIP_CASH", None
    if no_dip_mode=="FALLBACK_2H":
        j=WINDOW_BARS; x=j+EXIT_BARS
        if x>=len(g): return np.nan,"ERROR",None
        late=net_ret(float(g.open.iloc[x]),float(g.open.iloc[j]))
        return w0*base_ret+w1*late, "NO_DIP_FALLBACK", j
    raise ValueError(no_dip_mode)


def boot_delta(z,reps=10000,seed=260919):
    q=z[["symbol","delta"]].dropna().copy()
    g=q.groupby("symbol").delta.agg(["sum","count"])
    if len(g)<8:return None
    sums=g["sum"].to_numpy(float); counts=g["count"].to_numpy(float); n=len(g)
    rng=np.random.default_rng(seed); vals=np.empty(reps)
    for i in range(reps):
        idx=rng.integers(0,n,n)
        vals[i]=sums[idx].sum()/counts[idx].sum()
    return {"mean_delta":float(vals.mean()),"ci_low":float(np.quantile(vals,.025)),"ci_high":float(np.quantile(vals,.975)),"p_gt_0":float((vals>0).mean())}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--preflight",action="store_true")
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    pf=preflight(args.dataset_dir)
    if args.preflight:
        (args.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
        print(json.dumps(pf)); return

    ev,paths=load_dataset(args.dataset_dir)
    masks=split_masks(ev)

    policies=[]
    # Capital-neutral staged entries. Baseline is 100% immediate.
    for w0 in (1.00,.75,.50,.25):
        modes=("CASH","FALLBACK_2H") if w0<1 else ("CASH",)
        for mode in modes:
            name="BASE_100_IMMEDIATE" if w0==1 else f"STAGED_{int(w0*100)}I_{int((1-w0)*100)}D_{mode}"
            vals=[]; states=[]
            for r in ev.itertuples(index=False):
                v,state,_=event_policy(paths[int(r.event_id)],w0,mode)
                vals.append(v); states.append(state)
            s=pd.Series(vals,index=ev.index,dtype=float)
            rec={"policy":name,"immediate_weight":w0,"dip_weight":1-w0,"no_dip_mode":mode}
            for k,m in masks.items():
                rec[k]=metrics(s[m])
            a=rec["DISCOVERY"]; b=rec["CALIBRATION"]
            rec["train_score"]=min(a["mean"],b["mean"])+.25*min(a["median"],b["median"])+.20*min(a["q10"],b["q10"])
            rec["_returns"]=s
            rec["_states"]=states
            policies.append(rec)

    ranked=sorted(policies,key=lambda r:r["train_score"],reverse=True)
    champ=ranked[0]
    base=next(r for r in policies if r["policy"]=="BASE_100_IMMEDIATE")

    # Holdouts are diagnostics only; champion already fixed by Discovery+Calibration.
    ret=champ["_returns"]; base_ret=base["_returns"]
    audit=ev[["event_id","symbol","decision_time","hash_mod"]].copy()
    audit["champion_return"]=ret
    audit["baseline_return"]=base_ret
    audit["delta"]=ret-base_ret
    audit["state"]=champ["_states"]

    hold=masks["CROSS_HOLDOUT_PRE2026"]|masks["FINAL_HOLDOUT_2026"]
    hold_boot=boot_delta(audit[hold])

    split_diag={}
    for k,m in masks.items():
        q=audit[m]
        split_diag[k]={
            "champion":metrics(q.champion_return),
            "baseline":metrics(q.baseline_return),
            "delta":metrics(q.delta),
            "dip_state_pct":float((q.state=="DIP").mean()*100.0),
        }

    yearly=[]
    audit["year"]=pd.to_datetime(audit.decision_time,utc=True).dt.year
    for y,q in audit.groupby("year"):
        yearly.append({"year":int(y),"champion":metrics(q.champion_return),"baseline":metrics(q.baseline_return),"delta":metrics(q.delta),"dip_state_pct":float((q.state=="DIP").mean()*100.0)})

    clean_rank=[]
    for r in ranked:
        clean_rank.append({k:v for k,v in r.items() if not k.startswith("_")})

    summary={
        "purpose":"Capital-neutral staged-entry audit using the already frozen -0.5%/2h dip trigger. Policy selection uses Discovery+Calibration only.",
        "preflight":pf,
        "dip_trigger":{"dip_pct":DIP_PCT,"window_hours":2,"fill":"next 15m open","exit":"24h after each tranche fill"},
        "candidate_policies":clean_rank,
        "champion_selected_without_holdouts":{k:v for k,v in champ.items() if not k.startswith("_")},
        "champion_vs_baseline_by_split":split_diag,
        "holdout_symbol_cluster_bootstrap_delta":hold_boot,
        "yearly":yearly,
    }
    audit.to_csv(args.outdir/"event_audit.csv",index=False)
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    (args.outdir/"REPORT.md").write_text("# r2 Staged Entry Audit\n\n"+json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"champion":summary["champion_selected_without_holdouts"],"split_diag":split_diag,"bootstrap":hold_boot},ensure_ascii=False,allow_nan=False),flush=True)


if __name__=="__main__":
    main()
