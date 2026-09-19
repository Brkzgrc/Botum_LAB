from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
EXT_DIR=HERE.parent/"frozen_candidate_outcome_extension"
sys.path.insert(0,str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

EXCLUDE={"btc1_tsi_d1","btc4_bb_width"}
OUTCOME_PREFIX=("net_","mfe_","mae_","t_","up3_","danger_")

def met(x):
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v):return {"n":0}
    return {"n":int(len(v)),"mean24":float(v.mean()),"median24":float(v.median()),
            "win24":float((v>0).mean()*100),"q10":float(v.quantile(.1)),
            "danger":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.dataset_dir/"r2_events.csv",low_memory=False);d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    masks=ext.split_masks(d);disc=masks["DISCOVERY"];cal=masks["CALIBRATION"]
    base={k:met(d[m]) for k,m in masks.items()}
    feats=[]
    for c in d.columns:
        if not (c.startswith("btc1_") or c.startswith("btc4_")) or c in EXCLUDE or c.startswith(OUTCOME_PREFIX):continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s[disc].notna().sum()>=20 and s.nunique(dropna=True)>=8:feats.append(c)

    rows=[];store={}
    for feat in feats:
        s=pd.to_numeric(d[feat],errors="coerce");sd=s[disc].dropna()
        for q in (.10,.20,.80,.90):
            th=float(sd.quantile(q))
            for side in ("KEEP_ABOVE","KEEP_BELOW"):
                keep=(s>th) if side=="KEEP_ABOVE" else (s<th)
                rec={"feature":feat,"q":q,"threshold":th,"side":side}
                ok=True;score=[]
                for k,m in masks.items():
                    mt=met(d[m&keep]);rec[k]=mt;rec[k+"_keep"]=mt["n"]/base[k]["n"] if base[k]["n"] else 0
                for k in ("DISCOVERY","CALIBRATION"):
                    if rec[k]["n"]<18 or not(.50<=rec[k+"_keep"]<=.90):ok=False
                    else:
                        imp=rec[k]["mean24"]-base[k]["mean24"];tail=rec[k]["q10"]-base[k]["q10"];danger=base[k]["danger"]-rec[k]["danger"]
                        score.append(imp+.20*tail+.015*danger)
                rec["stable_train_cal"]=ok and min(score)>0
                rec["train_score"]=min(score) if ok else -999
                name=f"{feat}:{side}:Q{int(q*100)}";store[name]=keep;rec["name"]=name;rows.append(rec)
    ranked=sorted(rows,key=lambda x:x["train_score"],reverse=True);stable=[r for r in ranked if r["stable_train_cal"]]
    champion=stable[0] if stable else None
    out={"purpose":"BTC-only regime gate discovery on frozen r2. Selection uses Discovery+Calibration; holdouts diagnostic only.",
         "features":len(feats),"rules":len(rows),"stable_rules":len(stable),"base":base,
         "champion_selected_without_holdouts":champion,"top20":ranked[:20]}
    (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{"name":r["name"],"feature":r["feature"],"side":r["side"],"q":r["q"],"threshold":r["threshold"],"stable":r["stable_train_cal"],"score":r["train_score"]} for r in ranked]).to_csv(args.outdir/"regime_rules.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 BTC Regime Filter\n\n"+json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
