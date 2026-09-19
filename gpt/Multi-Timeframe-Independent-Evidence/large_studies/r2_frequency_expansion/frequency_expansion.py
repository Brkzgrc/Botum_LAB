from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

R1_TSI_MAX = -0.211069
R1_BTC4_BB_MIN = 0.0942267
COST = 0.20

META = {"symbol","decision_time","entry_time","hash_mod","year","r1","r2"}
OUTCOME_PREFIX = ("net_","mfe_","mae_","t_","up3_","danger_")
QUANTILES = (0.15,0.25,0.35,0.65,0.75,0.85)


def split_masks(d: pd.DataFrame) -> dict[str,pd.Series]:
    t=d["decision_time"]
    return {
        "DISCOVERY": (d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
        "CALIBRATION": (d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
        "CROSS_HOLDOUT_PRE2026": (d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
        "FINAL_SYMBOL_HOLDOUT_2026": (d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
        "ALL_2026": t>=pd.Timestamp("2026-01-01",tz="UTC"),
    }


def metrics(x: pd.DataFrame) -> dict:
    if len(x)==0:
        return {"n":0,"symbols":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v):
        return {"n":0,"symbols":0}
    q=x.loc[v.index]
    gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
    return {
        "n":int(len(v)),
        "symbols":int(q.symbol.nunique()),
        "mean24":float(v.mean()),
        "median24":float(v.median()),
        "win24":float((v>0).mean()*100.0),
        "pf24":gp/gl if gl>0 else None,
        "up3_before_dn2":float(pd.to_numeric(q.up3_before_dn2,errors="coerce").mean()*100.0),
        "danger_dn2_first":float(pd.to_numeric(q.danger_dn2_first,errors="coerce").mean()*100.0),
        "mean12":float(pd.to_numeric(q.net_12h,errors="coerce").mean()),
        "mean72":float(pd.to_numeric(q.net_72h,errors="coerce").mean()),
    }


def frequency_stats(x: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    if end<start:
        return {}
    days=max(1,(end.normalize()-start.normalize()).days+1)
    if len(x)==0:
        return {"calendar_days":days,"signals":0,"signals_per_day":0.0,"active_days":0,"median_on_active_day":0.0,"p90_on_active_day":0.0,"max_in_day":0}
    c=x.groupby(x.decision_time.dt.floor("D")).size()
    return {
        "calendar_days":int(days),
        "signals":int(len(x)),
        "signals_per_day":float(len(x)/days),
        "active_days":int(len(c)),
        "active_day_share_pct":float(len(c)/days*100.0),
        "median_on_active_day":float(c.median()),
        "p90_on_active_day":float(c.quantile(.90)),
        "max_in_day":int(c.max()),
    }


def family_of(c: str) -> str:
    s=c.lower()
    for fam in ("bb_","tsi","adx","di_spread","atr","mfi","cmf","vwap","roc","ppo","cmo","donch","er10","chop","rvol"):
        if fam in s: return fam
    return "other"


def timeframe_of(c: str) -> str:
    for p in ("m15_","h1_","h4_","btc1_","btc4_"):
        if c.startswith(p): return p.rstrip("_")
    return "other"


def load(indicator_dir: Path, r2_dataset_dir: Path) -> pd.DataFrame:
    fs=sorted(indicator_dir.rglob("features.csv"))
    if not fs: raise RuntimeError("no indicator artifact features.csv")
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames: raise RuntimeError("indicator artifact files are empty")
    d=pd.concat(frames,ignore_index=True)
    required={"symbol","decision_time","entry_time","hash_mod","btc1_tsi_d1","btc4_bb_width","net_12h","net_24h","net_72h","up3_before_dn2","danger_dn2_first"}
    miss=sorted(required-set(d.columns))
    if miss: raise RuntimeError(f"missing broad columns {miss}")
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    d["hash_mod"]=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
    d=d.drop_duplicates(["symbol","decision_time"],keep="last").reset_index(drop=True)

    r2=pd.read_csv(r2_dataset_dir/"r2_events.csv",usecols=["symbol","decision_time"],low_memory=False)
    r2["decision_time"]=pd.to_datetime(r2.decision_time,utc=True)
    r2keys=set(zip(r2.symbol.astype(str),r2.decision_time.astype(str)))
    keys=list(zip(d.symbol.astype(str),d.decision_time.astype(str)))
    d["r2"]=[k in r2keys for k in keys]
    d["r1"]=(pd.to_numeric(d.btc1_tsi_d1,errors="coerce")<=R1_TSI_MAX)&(pd.to_numeric(d.btc4_bb_width,errors="coerce")>=R1_BTC4_BB_MIN)
    return d


def feature_list(d: pd.DataFrame, study: str, disc_scope: pd.Series) -> list[str]:
    feats=[]
    for c in d.columns:
        if c in META or c.startswith(OUTCOME_PREFIX): continue
        if study=="local_non_r2" and not c.startswith(("m15_","h1_","h4_")): continue
        s=pd.to_numeric(d[c],errors="coerce")
        n=int(s[disc_scope].notna().sum())
        if n<max(30,int(disc_scope.sum()*.55)): continue
        if s[disc_scope].nunique(dropna=True)<12: continue
        feats.append(c)
    return feats


def scope_mask(d: pd.DataFrame, study: str) -> pd.Series:
    if study=="near_miss":
        return d.r1 & ~d.r2
    if study=="non_r1":
        return ~d.r1
    if study=="local_non_r2":
        return ~d.r2
    raise ValueError(study)


def apply_rule(d: pd.DataFrame, rule: dict) -> pd.Series:
    def one(r):
        s=pd.to_numeric(d[r["feature"]],errors="coerce")
        return s>=r["threshold"] if r["side"]=="GE" else s<=r["threshold"]
    if rule["type"]=="single":
        return one(rule)
    if rule["type"]=="or_pair":
        return one(rule["a"])|one(rule["b"])
    raise ValueError(rule["type"])


def quality_tier(md: dict, mc: dict) -> str|None:
    if min(md["n"],mc["n"])<10: return None
    strict=(min(md["mean24"],mc["mean24"])>=1.0 and min(md["win24"],mc["win24"])>=60.0 and
            min(md["up3_before_dn2"],mc["up3_before_dn2"])>=50.0 and max(md["danger_dn2_first"],mc["danger_dn2_first"])<=50.0)
    if strict: return "STRICT"
    acceptable=(min(md["mean24"],mc["mean24"])>=0.60 and min(md["win24"],mc["win24"])>=55.0 and
                min(md["up3_before_dn2"],mc["up3_before_dn2"])>=45.0 and max(md["danger_dn2_first"],mc["danger_dn2_first"])<=55.0)
    return "ACCEPTABLE" if acceptable else None


def score_rule(md: dict, mc: dict) -> float:
    return (
        min(md["mean24"],mc["mean24"]) +
        .018*min(md["win24"],mc["win24"]) +
        .010*min(md["up3_before_dn2"],mc["up3_before_dn2"]) -
        .008*max(md["danger_dn2_first"],mc["danger_dn2_first"]) +
        .10*math.log1p(min(md["n"],mc["n"]))
    )


def eval_candidate(d, scope, masks, rule):
    m=scope & apply_rule(d,rule)
    rec={"rule":rule}
    for k in ("DISCOVERY","CALIBRATION","CROSS_HOLDOUT_PRE2026","FINAL_SYMBOL_HOLDOUT_2026","ALL_2026"):
        rec[k]=metrics(d[m&masks[k]])
    rec["tier"]=quality_tier(rec["DISCOVERY"],rec["CALIBRATION"])
    rec["score"]=score_rule(rec["DISCOVERY"],rec["CALIBRATION"]) if rec["tier"] else -999.0
    return rec,m


def preflight(indicator_dir, r2_dataset_dir):
    d=load(indicator_dir,r2_dataset_dir)
    masks=split_masks(d)
    counts={k:int(v.sum()) for k,v in masks.items()}
    if len(d)<7000: raise RuntimeError(f"broad event count unexpectedly low {len(d)}")
    if int(d.r2.sum())!=225: raise RuntimeError(f"r2 key match expected 225 got {int(d.r2.sum())}")
    r1n=int(d.r1.sum())
    if r1n!=577: raise RuntimeError(f"r1 event count expected 577 got {r1n}")
    if counts["ALL_2026"]<1000: raise RuntimeError(f"all-2026 broad events unexpectedly low {counts['ALL_2026']}")
    return {"broad_events":int(len(d)),"symbols":int(d.symbol.nunique()),"r1_events":r1n,"r2_events":int(d.r2.sum()),"split_counts":counts}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indicator-dir",type=Path,required=True)
    ap.add_argument("--r2-dataset-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--study",choices=["near_miss","non_r1","local_non_r2"],required=True)
    ap.add_argument("--preflight",action="store_true")
    args=ap.parse_args()
    args.outdir.mkdir(parents=True,exist_ok=True)

    pf=preflight(args.indicator_dir,args.r2_dataset_dir)
    if args.preflight:
        (args.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
        print(json.dumps(pf),flush=True); return

    d=load(args.indicator_dir,args.r2_dataset_dir)
    masks=split_masks(d)
    scope=scope_mask(d,args.study)
    disc_scope=scope&masks["DISCOVERY"]
    cal_scope=scope&masks["CALIBRATION"]
    if disc_scope.sum()<40 or cal_scope.sum()<25:
        raise RuntimeError(f"scope too small study={args.study} D={disc_scope.sum()} C={cal_scope.sum()}")

    feats=feature_list(d,args.study,disc_scope)
    if len(feats)<40: raise RuntimeError(f"too few usable features: {len(feats)}")

    base_scope={k:metrics(d[scope&m]) for k,m in masks.items()}
    min_d=max(20,int(disc_scope.sum()*.10))
    min_c=max(15,int(cal_scope.sum()*.10))

    candidates=[]; rule_masks={}
    for c in feats:
        sdisc=pd.to_numeric(d.loc[disc_scope,c],errors="coerce").dropna()
        for q in QUANTILES:
            th=float(sdisc.quantile(q))
            if not np.isfinite(th): continue
            for side in ("GE","LE"):
                rule={"type":"single","feature":c,"side":side,"threshold":th,"q":q,"family":family_of(c),"timeframe":timeframe_of(c)}
                rec,m=eval_candidate(d,scope,masks,rule)
                if rec["DISCOVERY"]["n"]<min_d or rec["CALIBRATION"]["n"]<min_c: continue
                fracd=rec["DISCOVERY"]["n"]/max(1,int(disc_scope.sum()))
                fracc=rec["CALIBRATION"]["n"]/max(1,int(cal_scope.sum()))
                if not(.08<=fracd<=.80 and .08<=fracc<=.80): continue
                candidates.append(rec)
                rule_masks[json.dumps(rule,sort_keys=True)]=m

    singles=sorted(candidates,key=lambda r:r["score"],reverse=True)
    acceptable=[r for r in singles if r["tier"]]
    if not acceptable:
        out={"status":"NO_STABLE_SECOND_FAMILY","study":args.study,"preflight":pf,"scope_base":base_scope,"features":len(feats),"single_rules_tested":len(singles)}
        (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
        print(json.dumps(out),flush=True); return

    # Frequency-expansion search: OR two independently acceptable single rules.
    top=acceptable[:24]
    or_rows=[]
    for i,a in enumerate(top):
        for b in top[i+1:]:
            ra=a["rule"]; rb=b["rule"]
            if ra["family"]==rb["family"] and ra["timeframe"]==rb["timeframe"]: continue
            rule={"type":"or_pair","a":ra,"b":rb}
            rec,m=eval_candidate(d,scope,masks,rule)
            if rec["DISCOVERY"]["n"]<min_d or rec["CALIBRATION"]["n"]<min_c: continue
            if rec["tier"]:
                # Explicit bonus for more validated signals, not for holdout performance.
                rec["score"] += .12*math.log1p(min(rec["DISCOVERY"]["n"],rec["CALIBRATION"]["n"]))
                or_rows.append(rec)

    pool=acceptable+or_rows
    strict=[r for r in pool if r["tier"]=="STRICT"]
    chosen=max(strict if strict else pool,key=lambda r:r["score"])
    chosen_mask=scope & apply_rule(d,chosen["rule"])

    combined=d.r2 | chosen_mask
    combined_metrics={k:metrics(d[combined&m]) for k,m in masks.items()}
    r2_metrics={k:metrics(d[d.r2&m]) for k,m in masks.items()}

    all26=masks["ALL_2026"]
    t26=d.loc[all26,"decision_time"]
    start26=pd.Timestamp("2026-01-01",tz="UTC")
    end26=t26.max() if len(t26) else pd.Timestamp("2026-09-18",tz="UTC")
    freq={
        "r2_all_2026":frequency_stats(d[d.r2&all26],start26,end26),
        "second_family_all_2026":frequency_stats(d[chosen_mask&all26],start26,end26),
        "combined_all_2026":frequency_stats(d[combined&all26],start26,end26),
    }

    overlap=int((d.r2&chosen_mask).sum())
    summary={
        "status":"SUCCESS",
        "study":args.study,
        "purpose":"Find a second causal setup family that increases signal frequency without weakening the frozen r2 rule. Candidate selection uses Discovery+Calibration only; holdouts and all-2026 are diagnostics.",
        "preflight":pf,
        "scope":{
            "DISCOVERY":int(disc_scope.sum()),"CALIBRATION":int(cal_scope.sum()),
            "CROSS_HOLDOUT_PRE2026":int((scope&masks["CROSS_HOLDOUT_PRE2026"]).sum()),
            "FINAL_SYMBOL_HOLDOUT_2026":int((scope&masks["FINAL_SYMBOL_HOLDOUT_2026"]).sum()),
            "ALL_2026":int((scope&masks["ALL_2026"]).sum()),
        },
        "features":len(feats),
        "single_rules_tested":len(singles),
        "stable_singles":len(acceptable),
        "stable_or_pairs":len(or_rows),
        "selection_tiers":{"STRICT":"D+C mean24>=1.0, win24>=60, up3>=50, danger<=50","ACCEPTABLE":"D+C mean24>=0.60, win24>=55, up3>=45, danger<=55"},
        "champion_selected_without_holdouts":chosen,
        "r2_baseline":r2_metrics,
        "combined_r2_or_second_family":combined_metrics,
        "frequency":freq,
        "overlap_events":overlap,
        "top10_singles":acceptable[:10],
        "top10_or_pairs":sorted(or_rows,key=lambda r:r["score"],reverse=True)[:10],
    }
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    pd.DataFrame([{
        "rank":i+1,"tier":r["tier"],"score":r["score"],"rule":json.dumps(r["rule"],ensure_ascii=False),
        "disc_n":r["DISCOVERY"]["n"],"disc_mean24":r["DISCOVERY"]["mean24"],"disc_win24":r["DISCOVERY"]["win24"],
        "cal_n":r["CALIBRATION"]["n"],"cal_mean24":r["CALIBRATION"]["mean24"],"cal_win24":r["CALIBRATION"]["win24"],
        "hold_n":r["CROSS_HOLDOUT_PRE2026"]["n"],"hold_mean24":r["CROSS_HOLDOUT_PRE2026"].get("mean24"),
        "all2026_n":r["ALL_2026"]["n"],"all2026_mean24":r["ALL_2026"].get("mean24"),
    } for i,r in enumerate((acceptable+sorted(or_rows,key=lambda r:r["score"],reverse=True))[:100])]).to_csv(args.outdir/"candidate_table.csv",index=False)
    print(json.dumps({"study":args.study,"champion":chosen,"combined_all_2026":combined_metrics["ALL_2026"],"frequency":freq},ensure_ascii=False,allow_nan=False),flush=True)


if __name__=="__main__":
    main()
