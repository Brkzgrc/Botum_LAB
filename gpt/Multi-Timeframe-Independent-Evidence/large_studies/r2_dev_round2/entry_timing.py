from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
EXT_DIR=HERE.parent/"frozen_candidate_outcome_extension"
sys.path.insert(0,str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402
COST=.20

def ret(exit_px,entry_px): return (exit_px/entry_px-1)*100-COST

def metrics(v):
    v=pd.Series(v,dtype=float).dropna()
    if not len(v):return {"n":0}
    gp=v[v>0].sum();gl=-v[v<0].sum()
    return {"n":int(len(v)),"mean":float(v.mean()),"median":float(v.median()),"win":float((v>0).mean()*100),
            "pf":float(gp/gl) if gl>0 else np.nan,"q10":float(v.quantile(.1))}

def build_paths(events,paths):
    return {int(eid):g.sort_values("bar_i").reset_index(drop=True) for eid,g in paths.groupby("event_id")}

def fixed_delay(g,bars):
    if len(g)<=bars+96:return np.nan
    ep=float(g.open.iloc[bars]); xp=float(g.open.iloc[bars+96])
    return ret(xp,ep)

def dip_entry(g,dip,max_wait=8):
    base=float(g.open.iloc[0]); trigger=base*(1-dip/100)
    for i in range(min(max_wait,len(g)-97)):
        # Decision uses the just-closed candle; fill next candle open.
        if float(g.close.iloc[i])<=trigger:
            j=i+1
            if j+96<len(g):return ret(float(g.open.iloc[j+96]),float(g.open.iloc[j]))
    return np.nan

def reclaim_entry(g,dip=.5,max_wait=12):
    base=float(g.open.iloc[0]); trigger=base*(1-dip/100); armed=False
    for i in range(min(max_wait,len(g)-97)):
        c=float(g.close.iloc[i])
        if c<=trigger: armed=True
        elif armed and i>=1 and c>float(g.close.iloc[i-1]):
            j=i+1
            if j+96<len(g):return ret(float(g.open.iloc[j+96]),float(g.open.iloc[j]))
    return np.nan

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.dataset_dir/"r2_events.csv",low_memory=False);d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    p=pd.read_csv(args.dataset_dir/"r2_paths.csv",low_memory=False)
    P=build_paths(d,p)
    if len(P)<150 or min(len(g) for g in P.values())<193: raise RuntimeError("path dataset insufficient for timing study")
    policies=[]
    for mins in (0,15,30,45,60,90,120):
        policies.append((f"DELAY_{mins}M",lambda g,b=mins//15:fixed_delay(g,b),1.0))
    for dip in (.5,1.0,1.5,2.0):
        policies.append((f"DIP_{dip:.1f}_2H",lambda g,x=dip:dip_entry(g,x,8),.55))
    for dip in (.5,1.0):
        policies.append((f"RECLAIM_{dip:.1f}_3H",lambda g,x=dip:reclaim_entry(g,x,12),.45))

    masks=ext.split_masks(d); rows=[]; returns={}
    for name,fn,min_cov in policies:
        s=pd.Series({int(eid):fn(g) for eid,g in P.items()})
        vals=d.event_id.map(s);returns[name]=vals
        rec={"policy":name}
        for k,m in masks.items():
            v=vals[m];mt=metrics(v);mt["coverage_pct"]=float(v.notna().mean()*100);rec[k]=mt
        a=rec["DISCOVERY"];b=rec["CALIBRATION"]
        if a["coverage_pct"]>=min_cov*100 and b["coverage_pct"]>=min_cov*100 and min(a["n"],b["n"])>=15:
            rec["train_score"]=min(a["mean"],b["mean"])+.25*min(a["median"],b["median"])+.015*min(a["win"],b["win"])
        else:rec["train_score"]=-999
        rows.append(rec)
    ranked=sorted(rows,key=lambda x:x["train_score"],reverse=True)
    champion=ranked[0] if ranked else None
    out={"purpose":"Causal entry timing refinement on frozen r2; policy selected with Discovery+Calibration only.",
         "policies":len(rows),"champion_selected_without_holdouts":champion,"ranking":ranked}
    (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{"policy":r["policy"],"train_score":r["train_score"],**{f"{k}_{m}":v for k in ext.split_masks(d) for m,v in r[k].items()}} for r in ranked]).to_csv(args.outdir/"policies.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 Entry Timing\n\n"+json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
