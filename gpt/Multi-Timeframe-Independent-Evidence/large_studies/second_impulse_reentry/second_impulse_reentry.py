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
SEARCH_H=36
HORIZONS=[12,24,48,72]

def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def build_decision_15m(base):
    t=core.indicators(base)
    d=t.copy()
    d.index=d.index+pd.Timedelta(minutes=15)
    return d[~d.index.duplicated(keep="last")]

TRIGGERS={
    "STRUCT_M4": lambda z: z.structure.fillna(False)&(z.motion_pos>=4)&(z.motion_net>0),
    "HLHH_M3": lambda z: z.higher_low.fillna(False)&z.higher_high.fillna(False)&(z.motion_pos>=3)&(z.motion_net>0),
    "RECLAIM_M3": lambda z: z.reclaim_prev_high.fillna(False)&(z.motion_pos>=3)&(z.motion_net>0),
    "TURN4": lambda z: z.turn4.fillna(False)&(z.motion_net>=0),
    "STOCH_MULTI": lambda z: (z.stoch_spread_d1>0)&(z.stoch_k_d1>0)&(z.kdj_spread_d1>0)&(z.rsi_d1>0)&(z.motion_pos>=3),
}

def eval_entry(base, fill):
    if fill not in base.index:return None
    i=base.index.get_loc(fill)
    if not isinstance(i,(int,np.integer)):return None
    ep=float(base.open.iloc[i])
    if not np.isfinite(ep) or ep<=0:return None
    out={"entry_price":ep}
    for h in HORIZONS:
        j=i+h*4
        if j>=len(base):
            out[f"net_{h}h"]=np.nan;out[f"mfe_{h}h"]=np.nan;out[f"mae_{h}h"]=np.nan
            continue
        xp=float(base.open.iloc[j])
        sl=base.iloc[i:j+1]
        out[f"net_{h}h"]=(xp/ep-1)*100-COST
        out[f"mfe_{h}h"]=(float(sl.high.max())/ep-1)*100
        out[f"mae_{h}h"]=(float(sl.low.min())/ep-1)*100
    return out

def first_trigger_after(mask, times, armed, min_time=None):
    m=mask & armed
    if min_time is not None:
        m=m & (times>=min_time)
    idx=np.flatnonzero(m)
    return int(idx[0]) if len(idx) else None

def process_event(base,d15,e):
    t=e.decision_time
    et=e.entry_time
    if et not in base.index:return []
    i=base.index.get_loc(et)
    if not isinstance(i,(int,np.integer)):return []
    ep=float(base.open.iloc[i])
    if not np.isfinite(ep) or ep<=0:return []

    # scan only data that would become known after the original setup
    start=t
    end=t+pd.Timedelta(hours=SEARCH_H)
    z=d15[(d15.index>start)&(d15.index<=end)].copy()
    if len(z)<4:return []
    times=z.index
    close_ret=(z.close/ep-1)*100
    high_ret=(z.high/ep-1)*100
    low_ret=(z.low/ep-1)*100
    cum_peak=high_ret.cummax()
    cum_trough=low_ret.cummin()

    trig_masks={k:fn(z).fillna(False).to_numpy(bool) for k,fn in TRIGGERS.items()}
    rows=[]

    # 1) First impulse -> meaningful giveback -> bullish re-trigger.
    for imp in [0.5,1.0,1.5,2.0]:
        reached=(cum_peak>=imp)
        for gb in [0.30,0.50,0.70,1.00]:
            # giveback is fraction of the best excursion that has been surrendered.
            giveback=((cum_peak-close_ret)/cum_peak.replace(0,np.nan))>=gb
            armed=(reached & giveback).fillna(False).to_numpy(bool)
            for tn,tm in trig_masks.items():
                k=first_trigger_after(tm,times,armed)
                if k is None:continue
                decision=times[k];fill=decision+pd.Timedelta(minutes=15)
                ev=eval_entry(base,fill)
                if ev is None:continue
                rows.append({"policy":f"IMP{imp:g}_GB{gb:g}_{tn}","mode":"IMPULSE_GIVEBACK",
                             "trigger_decision":decision,"fill":fill,
                             "wait_h":(fill-et).total_seconds()/3600,
                             "price_vs_early_pct":(ev["entry_price"]/ep-1)*100,**ev})

    # 2) Initial failed attempt / deeper sweep -> recovery trigger.
    for dip in [0.5,1.0,1.5,2.0,3.0]:
        armed=(cum_trough<=-dip).to_numpy(bool)
        for tn,tm in trig_masks.items():
            k=first_trigger_after(tm,times,armed)
            if k is None:continue
            decision=times[k];fill=decision+pd.Timedelta(minutes=15)
            ev=eval_entry(base,fill)
            if ev is None:continue
            rows.append({"policy":f"DIP{dip:g}_{tn}","mode":"DIP_RECLAIM",
                         "trigger_decision":decision,"fill":fill,
                         "wait_h":(fill-et).total_seconds()/3600,
                         "price_vs_early_pct":(ev["entry_price"]/ep-1)*100,**ev})

    # 3) Do not force an early trade: wait, then take first fresh bullish state.
    alltrue=np.ones(len(z),dtype=bool)
    for wait in [2,4,8,12,18,24]:
        min_time=et+pd.Timedelta(hours=wait)
        for tn,tm in trig_masks.items():
            k=first_trigger_after(tm,times,alltrue,min_time)
            if k is None:continue
            decision=times[k];fill=decision+pd.Timedelta(minutes=15)
            ev=eval_entry(base,fill)
            if ev is None:continue
            rows.append({"policy":f"WAIT{wait}H_{tn}","mode":"DELAYED_CONFIRM",
                         "trigger_decision":decision,"fill":fill,
                         "wait_h":(fill-et).total_seconds()/3600,
                         "price_vs_early_pct":(ev["entry_price"]/ep-1)*100,**ev})
    return rows

def process_symbol(symbol,ev):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=FETCH_END)
        d15=build_decision_15m(base)
        out=[]
        for _,e in ev.iterrows():
            rows=process_event(base,d15,e)
            for r in rows:
                r.update({"symbol":symbol,"original_decision":e.decision_time,"original_entry":e.entry_time,
                          "year":int(e.decision_time.year),"hash_mod":hmod(symbol)})
                out.append(r)
        return pd.DataFrame(out),None
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
                print(f"[SHARD {shard}] {k}/{len(futs)} rows={sum(len(x) for x in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"reentries.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"symbols":len(mine),"rows":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def pf(v):
    v=pd.to_numeric(v,errors="coerce").dropna()
    gp=v[v>0].sum();gl=-v[v<0].sum()
    return float(gp/gl) if gl>0 else np.nan

def metrics(x):
    if len(x)==0:return {"n":0}
    out={"n":int(len(x)),"events":int(x.original_decision.nunique()),"symbols":int(x.symbol.nunique()),
         "mean_wait_h":float(x.wait_h.mean()),"median_wait_h":float(x.wait_h.median()),
         "median_price_vs_early_pct":float(x.price_vs_early_pct.median())}
    for h in HORIZONS:
        v=pd.to_numeric(x[f"net_{h}h"],errors="coerce").dropna()
        out[f"net{h}_mean"]=float(v.mean());out[f"net{h}_median"]=float(v.median())
        out[f"win{h}"]=float((v>0).mean()*100);out[f"pf{h}"]=pf(v)
    return out

def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("reentries.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames:raise RuntimeError("no reentry files")
    d=pd.concat(frames,ignore_index=True)
    for c in ["original_decision","original_entry","trigger_decision","fill"]:
        d[c]=pd.to_datetime(d[c],utc=True)
    outdir.mkdir(parents=True,exist_ok=True)

    disc=(d.hash_mod>=30)&(d.original_decision<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.original_decision>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.original_decision<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.original_decision<pd.Timestamp("2026-01-01",tz="UTC"))
    final=(d.hash_mod<30)&(d.original_decision>=pd.Timestamp("2026-01-01",tz="UTC"))

    rows=[]
    for p,g in d.groupby("policy"):
        md=metrics(g[disc.loc[g.index]]);mc=metrics(g[cal.loc[g.index]])
        if md["n"]<120 or mc["n"]<80:continue
        # choose by expectancy, PF and stability; no minimum win rate.
        stable=(md["net24_mean"]>0 and mc["net24_mean"]>0 and md["net48_mean"]>0 and mc["net48_mean"]>0
                and md["pf24"]>1 and mc["pf24"]>1)
        score=min(md["net24_mean"],mc["net24_mean"])+min(md["net48_mean"],mc["net48_mean"])+0.1*min(md["pf24"]-1,mc["pf24"]-1)
        rows.append({"policy":p,"mode":g["mode"].iloc[0],"stable_dev":stable,"score":score,
                     "disc_n":md["n"],"cal_n":mc["n"],"disc_net24":md["net24_mean"],"cal_net24":mc["net24_mean"],
                     "disc_net48":md["net48_mean"],"cal_net48":mc["net48_mean"],"disc_pf24":md["pf24"],"cal_pf24":mc["pf24"]})
    rank=pd.DataFrame(rows).sort_values(["stable_dev","score"],ascending=[False,False])
    rank.to_csv(outdir/"policy_ranking.csv",index=False)

    details=[]
    for _,r in rank[rank.stable_dev].head(30).iterrows():
        g=d[d.policy==r.policy]
        details.append({"policy":r.policy,"mode":r["mode"],
                        "discovery":metrics(g[disc.loc[g.index]]),
                        "calibration":metrics(g[cal.loc[g.index]]),
                        "cross_holdout_pre2026":metrics(g[cross.loc[g.index]]),
                        "final_holdout_2026":metrics(g[final.loc[g.index]])})
    champion=details[0] if details else None
    summary={
        "purpose":"Test the user's concrete hypothesis that an early rise can retrace and the real tradable move may begin later; search causal second-entry/re-entry timing rather than judging only the first signal.",
        "round_trip_cost_pct":COST,
        "causality":"all re-entry triggers use only states already observed after the original setup; entry is one additional 15m after the trigger candle closes",
        "same_original_setup_pool":8174,
        "policies_tested":int(len(rank)),"stable_dev_policies":int(rank.stable_dev.sum()),
        "champion_selected_without_holdouts":champion,
        "top_candidates":details
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Second Impulse / Re-entry Discovery","",
           "Amaç: İlk sinyal sonrası yükseliş -> geri çekilme -> asıl yükseliş veya ilk başarısız deneme -> dip/reclaim gibi ikinci girişleri nedensel biçimde test etmek.",
           "",f"Cost={COST:.2f}% | policies={len(rank)} | stable dev={int(rank.stable_dev.sum())}","",
           "## Champion selected without holdouts",str(champion)]
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
