from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
EXT_DIR=HERE.parent/"frozen_candidate_outcome_extension"
sys.path.insert(0,str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402
COST=.20

def net(px,ep):return (px/ep-1)*100-COST
def met(v):
    v=pd.Series(v,dtype=float).dropna()
    if not len(v):return {"n":0}
    gp=v[v>0].sum();gl=-v[v<0].sum()
    return {"n":int(len(v)),"mean":float(v.mean()),"median":float(v.median()),"win":float((v>0).mean()*100),
            "pf":float(gp/gl) if gl>0 else np.nan,"q10":float(v.quantile(.1)),"q25":float(v.quantile(.25))}

def baseline(g):
    if len(g)<=96:return np.nan
    return net(float(g.open.iloc[96]),float(g.open.iloc[0]))

def checkpoint_exit(g,h,ret_thr):
    if len(g)<=96:return np.nan
    ep=float(g.open.iloc[0]);i=h*4
    if len(g)<=i:return np.nan
    r=net(float(g.close.iloc[i-1]),ep)
    if r<=ret_thr:return r
    return net(float(g.open.iloc[96]),ep)

def no_progress(g,h,mfe_thr):
    if len(g)<=96:return np.nan
    ep=float(g.open.iloc[0]);i=h*4
    sl=g.iloc[:i]
    mfe=(float(sl.high.max())/ep-1)*100
    r=net(float(sl.close.iloc[-1]),ep)
    if mfe<=mfe_thr and r<0:return r
    return net(float(g.open.iloc[96]),ep)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.dataset_dir/"r2_events.csv",low_memory=False);d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    p=pd.read_csv(args.dataset_dir/"r2_paths.csv",low_memory=False)
    P={int(eid):g.sort_values("bar_i").reset_index(drop=True) for eid,g in p.groupby("event_id")}
    if len(P)<150 or min(len(g) for g in P.values())<97:raise RuntimeError("path dataset insufficient for risk exit")
    policies=[("BASE_24H",lambda g:baseline(g))]
    for h in (3,6,9,12):
        for thr in (-.5,-1,-2,-3):
            policies.append((f"EXIT_{h}H_IF_RET_LE_{thr}",lambda g,hh=h,t=thr:checkpoint_exit(g,hh,t)))
    for h in (3,6,9,12):
        for mfe in (.25,.5,1.0):
            policies.append((f"EXIT_{h}H_IF_MFE_LE_{mfe}_AND_RED",lambda g,hh=h,m=mfe:no_progress(g,hh,m)))
    masks=ext.split_masks(d);rows=[]
    for name,fn in policies:
        vals=d.event_id.map(pd.Series({eid:fn(g) for eid,g in P.items()}))
        rec={"policy":name}
        for k,m in masks.items():rec[k]=met(vals[m])
        a=rec["DISCOVERY"];b=rec["CALIBRATION"]
        if min(a["n"],b["n"])>=20:
            rec["train_score"]=min(a["mean"],b["mean"])+.30*min(a["q10"],b["q10"])+.20*min(a["q25"],b["q25"])
        else:rec["train_score"]=-999
        rows.append(rec)
    ranked=sorted(rows,key=lambda x:x["train_score"],reverse=True);champ=ranked[0]
    out={"purpose":"Causal early-risk exits versus the frozen 24h exit. Selection uses Discovery+Calibration only.",
         "policies":len(rows),"champion_selected_without_holdouts":champ,"top15":ranked[:15]}
    (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{"policy":r["policy"],"score":r["train_score"],**{f"{k}_{m}":v for k in masks for m,v in r[k].items()}} for r in ranked]).to_csv(args.outdir/"policies.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 Early Risk Exit\n\n"+json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
