from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent
EXT_DIR=HERE.parent/"frozen_candidate_outcome_extension"
sys.path.insert(0,str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

OUTCOME_PREFIX=("net_","mfe_","mae_","t_","up3_","danger_")
META={"symbol","decision_time","entry_time","hash_mod","year","event_id","r2","pullback_error"}

def comp_groups(x):
    g=x.groupby("entry_time")
    return [q for _,q in g if len(q)>=2]

def eval_rank(x,feat,ascending):
    groups=comp_groups(x); sel=[]; base=[]
    for g in groups:
        s=pd.to_numeric(g[feat],errors="coerce")
        q=g[s.notna()]
        if len(q)<2:continue
        idx=pd.to_numeric(q[feat],errors="coerce").idxmin() if ascending else pd.to_numeric(q[feat],errors="coerce").idxmax()
        sel.append(float(q.loc[idx,"net_24h"]));base.extend(pd.to_numeric(q.net_24h,errors="coerce").dropna().tolist())
    if not sel:return None
    return {"groups":len(sel),"selected_mean":float(np.mean(sel)),"selected_median":float(np.median(sel)),
            "selected_win":float(np.mean(np.array(sel)>0)*100),"all_group_event_mean":float(np.mean(base)),
            "delta_mean":float(np.mean(sel)-np.mean(base))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.dataset_dir/"r2_events.csv",low_memory=False)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True);d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    masks=ext.split_masks(d)
    counts={k:len(comp_groups(d[m])) for k,m in masks.items()}
    if counts["DISCOVERY"]<3 or counts["CALIBRATION"]<3:
        out={"purpose":"Same-entry-time competition ranking","status":"INSUFFICIENT_COMPETITION_GROUPS","group_counts":counts}
        (args.outdir/"summary.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
        (args.outdir/"REPORT.md").write_text("# r2 Concurrent Ranking\n\n"+json.dumps(out,indent=2),encoding="utf-8")
        print(json.dumps(out));return

    feats=[]
    for c in d.columns:
        if c in META or c.startswith(OUTCOME_PREFIX):continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s.notna().sum()>=int(.7*len(d)) and s.nunique(dropna=True)>=10:feats.append(c)

    rows=[]
    for feat in feats:
        for side in ("HIGH","LOW"):
            asc=side=="LOW";rec={"feature":feat,"side":side}
            stable=True;score_parts=[]
            for k,m in masks.items():
                e=eval_rank(d[m],feat,asc);rec[k]=e
                if k in ("DISCOVERY","CALIBRATION"):
                    if not e or e["groups"]<3:stable=False
                    else:score_parts.append(e["delta_mean"])
            rec["stable_train_cal"]=stable and min(score_parts)>0
            rec["train_score"]=min(score_parts) if stable else -999
            rows.append(rec)
    ranked=sorted(rows,key=lambda x:x["train_score"],reverse=True)
    stable=[r for r in ranked if r["stable_train_cal"]]
    champion=stable[0] if stable else None
    out={"purpose":"Rank simultaneous frozen-r2 signals using only causal pre-entry features. Selection uses Discovery+Calibration.",
         "competition_group_counts":counts,"features":len(feats),"stable_rules":len(stable),
         "champion_selected_without_holdouts":champion,"top20":ranked[:20]}
    (args.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{"feature":r["feature"],"side":r["side"],"stable":r["stable_train_cal"],"score":r["train_score"]} for r in ranked]).to_csv(args.outdir/"ranking_rules.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 Concurrent Signal Ranking\n\n"+json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
