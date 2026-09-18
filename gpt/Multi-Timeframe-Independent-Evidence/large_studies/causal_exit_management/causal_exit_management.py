from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
CAUSAL=PARENT/"coin_mtf_causal_validation"
sys.path.insert(0,str(CAUSAL))
import coin_mtf_causal_validation as core  # noqa: E402

EVENTS=PARENT/"coin_mtf_broad_frozen_validation"/"output"/"frozen_rule_events.csv"
FETCH_START=pd.Timestamp("2022-10-01",tz="UTC")
FETCH_END=pd.Timestamp("2026-09-18",tz="UTC")
COST=0.20
MAX_H=168

def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def atr14(x):
    pc=x.close.shift(1)
    tr=pd.concat([(x.high-x.low).abs(),(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()

def one_event_path(base, t, et):
    if et not in base.index: return None
    i=base.index.get_loc(et)
    if not isinstance(i,(int,np.integer)): return None
    ep=float(base.open.iloc[i])
    if not np.isfinite(ep) or ep<=0: return None
    end=min(i+MAX_H*4,len(base)-1)
    p=base.iloc[i:end+1].copy()
    if len(p)<8: return None
    return i,ep,p

def resolve_barrier(p, ep, stop_pct, target_pct, max_h):
    n=min(len(p)-1,max_h*4)
    if n<=0:return None
    for k in range(1,n+1):
        hi=(float(p.high.iloc[k])/ep-1)*100
        lo=(float(p.low.iloc[k])/ep-1)*100
        hit_t=hi>=target_pct
        hit_s=lo<=-stop_pct
        if hit_t and hit_s:
            # Conservative same-bar ambiguity: count stop first.
            return k/4.0, -stop_pct-COST, "SL_SAME_BAR"
        if hit_s:return k/4.0,-stop_pct-COST,"SL"
        if hit_t:return k/4.0,target_pct-COST,"TP"
    xp=float(p.open.iloc[n])
    return n/4.0,(xp/ep-1)*100-COST,"TIME"

def resolve_fixed(p,ep,h):
    k=h*4
    if k>=len(p):return None
    xp=float(p.open.iloc[k])
    return float(h),(xp/ep-1)*100-COST,"TIME"

def resolve_progress(p,ep,check_h,need_mfe,exit_h):
    ck=min(check_h*4,len(p)-1)
    if ck<=0:return None
    mfe=(float(p.high.iloc[:ck+1].max())/ep-1)*100
    if mfe<need_mfe:
        xp=float(p.open.iloc[ck])
        return ck/4.0,(xp/ep-1)*100-COST,"NO_PROGRESS"
    return resolve_fixed(p,ep,exit_h)

def resolve_breakeven(p,ep,activate_pct,stop_after_pct,target_pct,max_h):
    n=min(len(p)-1,max_h*4)
    activated=False
    for k in range(1,n+1):
        hi=(float(p.high.iloc[k])/ep-1)*100
        lo=(float(p.low.iloc[k])/ep-1)*100
        if not activated and hi>=activate_pct:
            activated=True
        current_stop=stop_after_pct if activated else -999.0
        hit_t=hi>=target_pct
        hit_s=activated and lo<=current_stop
        if hit_t and hit_s:
            return k/4.0,current_stop-COST,"BE_SAME_BAR"
        if hit_s:return k/4.0,current_stop-COST,"BE_STOP"
        if hit_t:return k/4.0,target_pct-COST,"TP"
    xp=float(p.open.iloc[n])
    return n/4.0,(xp/ep-1)*100-COST,"TIME"

def resolve_trailing_atr(base,i,p,ep,atr_mult,activate_pct,max_h):
    atr=atr14(base)
    n=min(len(p)-1,max_h*4)
    peak=ep
    active=False
    for k in range(1,n+1):
        global_i=i+k
        if global_i>=len(base):break
        hi=float(p.high.iloc[k]); lo=float(p.low.iloc[k])
        peak=max(peak,hi)
        mfe=(peak/ep-1)*100
        if mfe>=activate_pct: active=True
        if active:
            a=float(atr.iloc[global_i]) if pd.notna(atr.iloc[global_i]) else np.nan
            if np.isfinite(a):
                stop_price=peak-atr_mult*a
                if lo<=stop_price:
                    ret=(stop_price/ep-1)*100-COST
                    return k/4.0,ret,"ATR_TRAIL"
    xp=float(p.open.iloc[n])
    return n/4.0,(xp/ep-1)*100-COST,"TIME"

def process_symbol(symbol,ev):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=FETCH_END)
        rows=[]
        for _,e in ev.iterrows():
            r=one_event_path(base,e.decision_time,e.entry_time)
            if r is None:continue
            i,ep,p=r
            rec={"symbol":symbol,"decision_time":e.decision_time,"entry_time":e.entry_time,"year":int(e.decision_time.year),"hash_mod":hmod(symbol)}

            for h in [3,6,12,24,48,72,120,168]:
                z=resolve_fixed(p,ep,h)
                if z: rec[f"fixed_{h}h_ret"]=z[1]

            for sl in [0.75,1.0,1.5,2.0,2.5,3.0,4.0]:
                for tp in [1.0,1.5,2.0,3.0,4.0,5.0,6.0,8.0]:
                    if tp<=0 or sl<=0:continue
                    z=resolve_barrier(p,ep,sl,tp,72)
                    if z:
                        key=f"bar_sl{str(sl).replace('.','p')}_tp{str(tp).replace('.','p')}_72h"
                        rec[key+"_ret"]=z[1]; rec[key+"_hold_h"]=z[0]; rec[key+"_exit"]=z[2]

            for check_h in [3,6,12]:
                for need in [0.25,0.5,1.0]:
                    for exit_h in [24,48,72]:
                        if exit_h<=check_h:continue
                        z=resolve_progress(p,ep,check_h,need,exit_h)
                        if z:
                            key=f"progress_{check_h}h_mfe{str(need).replace('.','p')}_exit{exit_h}h"
                            rec[key+"_ret"]=z[1]; rec[key+"_hold_h"]=z[0]; rec[key+"_exit"]=z[2]

            for act in [0.75,1.0,1.5,2.0]:
                for stop_after in [0.0,0.25,0.5]:
                    for tp in [2.0,3.0,4.0,5.0,6.0]:
                        if tp<=act:continue
                        z=resolve_breakeven(p,ep,act,stop_after,tp,72)
                        if z:
                            key=f"be_act{str(act).replace('.','p')}_stop{str(stop_after).replace('.','p')}_tp{str(tp).replace('.','p')}"
                            rec[key+"_ret"]=z[1]; rec[key+"_hold_h"]=z[0]; rec[key+"_exit"]=z[2]

            for mult in [1.0,1.5,2.0,2.5,3.0]:
                for act in [0.5,1.0,1.5,2.0]:
                    z=resolve_trailing_atr(base,i,p,ep,mult,act,72)
                    if z:
                        key=f"trail_atr{str(mult).replace('.','p')}_act{str(act).replace('.','p')}"
                        rec[key+"_ret"]=z[1]; rec[key+"_hold_h"]=z[0]; rec[key+"_exit"]=z[2]

            rows.append(rec)
        return pd.DataFrame(rows),None
    except Exception as ex:
        return None,{"symbol":symbol,"error":repr(ex)}

def shard_main(shard,shards,outdir):
    d=pd.read_csv(EVENTS,low_memory=False)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    syms=sorted(d.symbol.astype(str).unique())
    mine=[s for i,s in enumerate(syms) if i%shards==shard]
    outdir.mkdir(parents=True,exist_ok=True)
    frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={}
        for s in mine:
            ev=d[d.symbol.astype(str)==s].copy()
            futs[ex.submit(process_symbol,s,ev)]=s
        for k,f in enumerate(as_completed(futs),1):
            x,e=f.result()
            if e:errs.append(e)
            elif x is not None and len(x):frames.append(x)
            if k%10==0 or k==len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"management.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"symbols":len(mine),"events":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def pf(v):
    wins=v[v>0].sum()
    losses=-v[v<0].sum()
    return float(wins/losses) if losses>0 else np.nan

def stats(v,hold=None):
    v=pd.to_numeric(v,errors="coerce").dropna()
    if len(v)==0:return {"n":0}
    out={"n":int(len(v)),"mean":float(v.mean()),"median":float(v.median()),"win_pct":float((v>0).mean()*100),
         "profit_factor":pf(v),"p10":float(v.quantile(.10)),"p90":float(v.quantile(.90))}
    if hold is not None:
        h=pd.to_numeric(hold,errors="coerce").reindex(v.index)
        out["mean_hold_h"]=float(h.mean());out["median_hold_h"]=float(h.median())
    return out

def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("management.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames:raise RuntimeError("no management files")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    outdir.mkdir(parents=True,exist_ok=True)

    discovery=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    calibration=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    final=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))

    ret_cols=[c for c in d.columns if c.endswith("_ret")]
    rows=[]
    for c in ret_cols:
        base=c[:-4]
        hc=base+"_hold_h" if base+"_hold_h" in d.columns else None
        sd=stats(d.loc[discovery,c],d.loc[discovery,hc] if hc else None)
        sc=stats(d.loc[calibration,c],d.loc[calibration,hc] if hc else None)
        if sd["n"]<150 or sc["n"]<100:continue
        # selection is about expectancy, not raw win-rate. Require both development periods positive,
        # plus PF>1, then rank by the weaker period to punish regime-specific overfit.
        stable=(sd["mean"]>0 and sc["mean"]>0 and sd["profit_factor"]>1 and sc["profit_factor"]>1)
        score=min(sd["mean"],sc["mean"])+0.15*min(sd["profit_factor"]-1,sc["profit_factor"]-1)
        rows.append({"policy":base,"stable_dev":stable,"score":score,
                     "disc_mean":sd["mean"],"disc_win":sd["win_pct"],"disc_pf":sd["profit_factor"],
                     "cal_mean":sc["mean"],"cal_win":sc["win_pct"],"cal_pf":sc["profit_factor"]})
    tab=pd.DataFrame(rows).sort_values(["stable_dev","score"],ascending=[False,False])
    tab.to_csv(outdir/"policy_ranking.csv",index=False)

    candidates=tab[tab.stable_dev].head(30)
    details=[]
    for _,r in candidates.iterrows():
        c=r.policy+"_ret"; hc=r.policy+"_hold_h" if r.policy+"_hold_h" in d.columns else None
        details.append({
            "policy":r.policy,
            "discovery":stats(d.loc[discovery,c],d.loc[discovery,hc] if hc else None),
            "calibration":stats(d.loc[calibration,c],d.loc[calibration,hc] if hc else None),
            "cross_holdout_pre2026":stats(d.loc[cross,c],d.loc[cross,hc] if hc else None),
            "final_holdout_2026":stats(d.loc[final,c],d.loc[final,hc] if hc else None),
        })

    champ=details[0] if details else None

    # Frequency / sparse quality perspective for the final champion.
    freq=None
    if champ:
        c=champ["policy"]+"_ret"
        x=d[final].copy()
        x["ret"]=pd.to_numeric(x[c],errors="coerce")
        x=x.dropna(subset=["ret"]).sort_values("decision_time")
        if len(x):
            days=max((x.decision_time.max()-x.decision_time.min()).days+1,1)
            freq={"trades":int(len(x)),"calendar_days":int(days),"trades_per_day":float(len(x)/days),
                  "positive_expectancy_per_trade_pct":float(x.ret.mean()),"profit_factor":pf(x.ret)}

    summary={
        "purpose":"Search causal trade-management policies so a valid entry is not judged only by arbitrary fixed holding horizons. Success is positive expectancy after 0.20% round-trip cost; high win-rate is not required.",
        "round_trip_cost_pct":COST,
        "lookahead":"none in policy execution; all barriers/trailing/progress exits are processed forward bar-by-bar; same-bar TP+SL ambiguity is resolved conservatively as stop first",
        "splits":{"discovery":"dev symbols 2023-2024","calibration":"dev symbols 2025","cross_holdout_pre2026":"holdout symbols 2023-2025","final_holdout_2026":"holdout symbols 2026"},
        "policies_tested":int(len(tab)),"stable_development_policies":int(tab.stable_dev.sum()),
        "champion_selected_without_holdouts":champ,
        "top_candidates":details,
        "final_champion_frequency":freq,
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Causal Exit & Trade Management Discovery","",
           f"Cost={COST:.2f}% | policies={len(tab)} | stable on discovery+calibration={int(tab.stable_dev.sum())}",
           "Selection uses positive expectancy + profit factor, not a required win-rate.","",
           "## Champion selected without holdouts",str(champ),"","## Final frequency",str(freq)]
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
        if args.shard is None:raise SystemExit("--shard required")
        shard_main(args.shard,args.shards,args.outdir or ROOT/f"shard_{args.shard}")

if __name__=="__main__":
    main()
