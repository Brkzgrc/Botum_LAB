from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
EXT_DIR=HERE.parent/"frozen_candidate_outcome_extension"
sys.path.insert(0,str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

A="h1_rvol20_d1"; B="h1_donch_pos_d3"
A_FIXED=0.002034226506109368
B_FIXED=-0.18543143174956295

def met(x):
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    gp=v[v>0].sum();gl=-v[v<0].sum()
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
            "mean24":float(v.mean()),"median24":float(v.median()),"win24":float((v>0).mean()*100),
            "pf24":float(gp/gl) if gl>0 else np.nan,"q10":float(v.quantile(.1)),
            "danger":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100)}

def delta(base,sub):
    return {"mean24":sub["mean24"]-base["mean24"],"median24":sub["median24"]-base["median24"],
            "win24":sub["win24"]-base["win24"],"q10":sub["q10"]-base["q10"],
            "danger_reduction":base["danger"]-sub["danger"]}

def boot_delta(base,mask,reps=10000,seed=260920):
    z=base[["symbol","net_24h"]].copy();z["keep"]=mask.reindex(z.index).fillna(False)
    syms=z.symbol.unique(); by={s:z[z.symbol==s] for s in syms}
    if len(syms)<8:return None
    rng=np.random.default_rng(seed); vals=[]
    for _ in range(reps):
        q=pd.concat([by[s] for s in rng.choice(syms,len(syms),replace=True)],ignore_index=True)
        a=q.loc[q.keep,"net_24h"]; b=q.net_24h
        if len(a): vals.append(float(a.mean()-b.mean()))
    a=np.array(vals,float)
    return {"mean_delta":float(a.mean()),"ci_low":float(np.quantile(a,.025)),
            "ci_high":float(np.quantile(a,.975)),"p_gt_0":float((a>0).mean())}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.dataset_dir/"r2_events.csv",low_memory=False)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [A,B,"net_24h","danger_dn2_first"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    if int(d[[A,B]].notna().sum().min())<150: raise RuntimeError("veto features unexpectedly sparse")
    masks=ext.split_masks(d); disc=masks["DISCOVERY"]
    base={k:met(d[m]) for k,m in masks.items()}
    fixed=(d[A]>A_FIXED)&(d[B]>B_FIXED)
    primary={}
    for k,m in masks.items():
        s=met(d[m&fixed]);primary[k]={"metrics":s,"delta":delta(base[k],s),"keep_pct":s["n"]/base[k]["n"]*100}
    hold=masks["CROSS_HOLDOUT_PRE2026"]|masks["FINAL_HOLDOUT_2026"]
    primary["holdout_bootstrap_delta"]=boot_delta(d[hold],fixed[hold])

    # Robustness neighborhood only; primary thresholds remain frozen.
    qa={q:float(d.loc[disc,A].quantile(q)) for q in (.15,.20,.25)}
    qb={q:float(d.loc[disc,B].quantile(q)) for q in (.15,.20,.25)}
    neigh=[]
    for a_q,a_t in qa.items():
        for b_q,b_t in qb.items():
            keep=(d[A]>a_t)&(d[B]>b_t)
            rec={"a_q":a_q,"a_t":a_t,"b_q":b_q,"b_t":b_t}
            for k,m in masks.items(): rec[k]=met(d[m&keep])
            neigh.append(rec)

    y=[]
    for year,g in d[fixed].groupby(d.loc[fixed,"decision_time"].dt.year):
        y.append({"year":int(year),**met(g)})
    out={"purpose":"Robustness-only audit of the already selected r2 veto pair. No new veto selection.",
         "fixed_rule":f"{A} > {A_FIXED} AND {B} > {B_FIXED}","base":base,
         "primary":primary,"threshold_neighborhood":neigh,"yearly":y}
    (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    (args.outdir/"REPORT.md").write_text("# r2 Veto Robustness\n\n"+json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
