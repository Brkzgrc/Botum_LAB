from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R2_DIR=HERE.parent.parent/"r2_candidate"
sys.path.insert(0,str(R2_DIR))
import r2_common as rc  # noqa: E402

EXCLUDE_TOKENS=("net_","mfe_","mae_","up3","danger","entry_price","future","outcome","label","hash_mod")
QUANTS=(.10,.20,.30,.70,.80,.90)


def met(d):
    v=pd.to_numeric(d.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return {"n":int(len(v)),"symbols":int(d.loc[v.index,"symbol"].nunique()),
            "mean24":float(v.mean()),"median24":float(v.median()),
            "win24":float((v>0).mean()*100),"loss24":float((v<=0).mean()*100),
            "pf24":float(gp/gl) if gl>0 else np.nan,
            "q10":float(v.quantile(.10)),"q25":float(v.quantile(.25))}


def improve(base,sub):
    return {"mean24":sub["mean24"]-base["mean24"],"median24":sub["median24"]-base["median24"],
            "win24":sub["win24"]-base["win24"],"loss_reduction":base["loss24"]-sub["loss24"],
            "q10":sub["q10"]-base["q10"]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=12)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    d=rc.load_r2(args.artifact_dir,args.workers)
    masks=rc.split_masks(d)
    disc=masks["DISCOVERY"]; cal=masks["CALIBRATION"]
    base={k:met(d[m]) for k,m in masks.items()}

    numeric=[]
    for c in d.columns:
        if c in ("symbol","decision_time","entry_time","pullback_error","r2"): continue
        if any(t in c.lower() for t in EXCLUDE_TOKENS): continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s[disc].notna().sum()>=20 and s.nunique(dropna=True)>=8:
            numeric.append(c)

    singles=[]
    masks_by_name={}
    for feat in numeric:
        s=pd.to_numeric(d[feat],errors="coerce")
        sd=s[disc].dropna()
        for q in QUANTS:
            th=float(sd.quantile(q))
            # A veto means reject one tail; keep the complement.
            for side in ("veto_low","veto_high"):
                keep=(s>th) if side=="veto_low" else (s<th)
                md=met(d[disc & keep]); mc=met(d[cal & keep])
                if md.get("n",0)<20 or mc.get("n",0)<20: continue
                kd=md["n"]/base["DISCOVERY"]["n"]; kc=mc["n"]/base["CALIBRATION"]["n"]
                if min(kd,kc)<.55 or max(kd,kc)>.95: continue
                idd=improve(base["DISCOVERY"],md); ic=improve(base["CALIBRATION"],mc)
                stable=(idd["mean24"]>0 and ic["mean24"]>0 and idd["q10"]>=-0.5 and ic["q10"]>=-0.5)
                score=min(idd["mean24"],ic["mean24"])+.25*min(idd["q10"],ic["q10"])+.02*min(idd["loss_reduction"],ic["loss_reduction"])
                name=f"{feat}:{side}:Q{int(q*100)}:{th:.8g}"
                masks_by_name[name]=keep
                singles.append({"name":name,"feature":feat,"side":side,"q":q,"threshold":th,
                                "disc_n":md["n"],"cal_n":mc["n"],"disc_keep":kd,"cal_keep":kc,
                                "disc_imp":idd,"cal_imp":ic,"stable":stable,"score":score})

    singles=sorted(singles,key=lambda x:x["score"],reverse=True)
    stable=[x for x in singles if x["stable"]]

    pairs=[]
    top=stable[:12]
    for i,a in enumerate(top):
        for b in top[i+1:]:
            if a["feature"]==b["feature"]: continue
            keep=masks_by_name[a["name"]] & masks_by_name[b["name"]]
            md=met(d[disc&keep]); mc=met(d[cal&keep])
            if md.get("n",0)<18 or mc.get("n",0)<18: continue
            kd=md["n"]/base["DISCOVERY"]["n"]; kc=mc["n"]/base["CALIBRATION"]["n"]
            if min(kd,kc)<.50: continue
            idd=improve(base["DISCOVERY"],md); ic=improve(base["CALIBRATION"],mc)
            stable_pair=(idd["mean24"]>0 and ic["mean24"]>0 and idd["q10"]>=-0.5 and ic["q10"]>=-0.5)
            score=min(idd["mean24"],ic["mean24"])+.25*min(idd["q10"],ic["q10"])+.02*min(idd["loss_reduction"],ic["loss_reduction"])
            pairs.append({"name":a["name"]+" & "+b["name"],"a":a["name"],"b":b["name"],
                          "disc_n":md["n"],"cal_n":mc["n"],"disc_imp":idd,"cal_imp":ic,
                          "stable":stable_pair,"score":score})
            masks_by_name[a["name"]+" & "+b["name"]]=keep

    pairs=sorted(pairs,key=lambda x:x["score"],reverse=True)
    candidates=sorted([*stable,*[x for x in pairs if x["stable"]]],key=lambda x:x["score"],reverse=True)
    champion=candidates[0] if candidates else None

    diagnostics=None
    if champion:
        keep=masks_by_name[champion["name"]]
        diagnostics={"name":champion["name"],"splits":{}}
        for k,m in masks.items():
            sub=met(d[m&keep]); diagnostics["splits"][k]={"metrics":sub,"improvement":improve(base[k],sub),
                                                         "keep_pct":sub["n"]/base[k]["n"]*100}
        hold=masks["CROSS_HOLDOUT_PRE2026"]|masks["FINAL_HOLDOUT_2026"]
        q=d[hold&keep].copy()
        diagnostics["holdout_boot24"]=rc.cluster_bootstrap_mean(q,"net_24h",reps=10000)

    summary={"purpose":"Find a causal pre-entry veto on frozen r2. Selection uses Discovery+Calibration only; holdouts are diagnostics.",
             "features_scanned":len(numeric),"single_rules":len(singles),"stable_singles":len(stable),
             "pair_rules":len(pairs),"base":base,"champion_selected_without_holdouts":champion,
             "champion_diagnostics":diagnostics,"top10_singles":singles[:10],"top10_pairs":pairs[:10]}
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame(singles).to_csv(args.outdir/"single_vetos.csv",index=False)
    pd.DataFrame(pairs).to_csv(args.outdir/"pair_vetos.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 Loss Veto Research\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
