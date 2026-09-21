from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
import frozen_candidate_outcome_extension_snapshot as ext

COST=0.20
F1="btc1_tsi_d1"; F2="btc4_bb_width"
R1_TSI=-0.211069
R1_BB=0.0942267
R2_H4_BB=0.19233492
R2_DD=-7.3594696

OUTCOME_PREFIX=("net_","gross_","mfe_","mae_","t_","up3_","danger_")
META={"symbol","decision_time","entry_time","hash_mod","year"}

def metrics(x):
    if len(x)==0:return {"n":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return {
      "n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
      "win24":float((v>0).mean()*100),"mean24":float(v.mean()),
      "median24":float(v.median()),"pf24":float(gp/gl) if gl>0 else None,
      "p10":float(v.quantile(.10)),
      "up3_before_dn2":float(pd.to_numeric(x.loc[v.index,"up3_before_dn2"],errors="coerce").mean()*100),
      "danger_dn2_first":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100)
    }

def load(indir:Path):
    # Exact frozen TSI+BB base, then reconstruct the exact causal 48h pullback
    # used by the frozen r2 rule from only candles available before decision time.
    d=ext.load_frozen_candidate(indir)
    d=ext.add_causal_pullbacks(d,workers=12)
    d=d[d.pullback_error.fillna("")==""].copy()
    need=[F1,F2,"h4_bb_width","causal_dd_high_48h","net_24h","up3_before_dn2","danger_dn2_first"]
    miss=[c for c in need if c not in d.columns]
    if miss: raise RuntimeError("missing required columns after causal enrichment: "+str(miss))
    return d

def movement_columns(d):
    cols=[]
    include_tokens=("rsi","stoch","kdj","macd","ppo","tsi","mfi","cmf","obv","adx","di_spread","atr","bb_","vwap","roc","cmo","donch","er10","chop","rvol","ret_","dd_","motion")
    tf_prefix=("m15_","h1_","h4_","btc1_","btc4_")
    for c in d.columns:
        lc=c.lower()
        if c in META or c.startswith(OUTCOME_PREFIX): continue
        if not c.startswith(tf_prefix): continue
        if any(t in lc for t in include_tokens):
            s=pd.to_numeric(d[c],errors="coerce")
            if s.notna().sum()>=500 and s.nunique(dropna=True)>=20:
                cols.append(c)
    return cols

def robust_effect(a,b):
    a=pd.to_numeric(a,errors="coerce").dropna(); b=pd.to_numeric(b,errors="coerce").dropna()
    if len(a)<8 or len(b)<4:return np.nan
    scale=pd.concat([a,b]).quantile(.75)-pd.concat([a,b]).quantile(.25)
    if not np.isfinite(scale) or scale==0:return np.nan
    return float((a.median()-b.median())/scale)

def build_fingerprint(d,mask,features):
    win=mask&(d.net_24h>0)
    loss=mask&(d.net_24h<=0)
    rows=[]
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    for c in features:
        ed=robust_effect(d.loc[win&disc,c],d.loc[loss&disc,c])
        ec=robust_effect(d.loc[win&cal,c],d.loc[loss&cal,c])
        if not(np.isfinite(ed) and np.isfinite(ec)):continue
        if ed*ec<=0:continue
        strength=min(abs(ed),abs(ec))
        if strength<0.12:continue
        rows.append({"feature":c,"dir":1 if ed>0 else -1,"effect_disc":ed,"effect_cal":ec,"stable_strength":strength})
    return pd.DataFrame(rows).sort_values("stable_strength",ascending=False)

def score_by_winner_similarity(d,trainmask,fingerprint,topn=24):
    fp=fingerprint.head(topn)
    scores=np.zeros(len(d),float); used=0
    # use train-only winner medians and IQR; no holdout leakage
    winners=trainmask&(d.net_24h>0)
    for _,r in fp.iterrows():
        c=r.feature; direction=int(r["dir"])
        s=pd.to_numeric(d[c],errors="coerce")
        tr=pd.to_numeric(d.loc[winners,c],errors="coerce").dropna()
        if len(tr)<20:continue
        med=float(tr.median()); q1=float(tr.quantile(.25)); q3=float(tr.quantile(.75)); scale=max(q3-q1,1e-9)
        z=((s-med)/scale)*direction
        z=z.clip(-3,3).fillna(-3)
        scores+=z.to_numpy(); used+=1
    return pd.Series(scores/max(used,1),index=d.index),used

def main(indir:Path,outdir:Path):
    d=load(indir); outdir.mkdir(parents=True,exist_ok=True)
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))
    dev=disc|cal

    r1=(pd.to_numeric(d[F1],errors="coerce")<=R1_TSI)&(pd.to_numeric(d[F2],errors="coerce")>=R1_BB)
    r2=r1&(pd.to_numeric(d.h4_bb_width,errors="coerce")>=R2_H4_BB)&(pd.to_numeric(d.causal_dd_high_48h,errors="coerce")<=R2_DD)

    feats=movement_columns(d)
    fp=build_fingerprint(d,r2,feats)
    fp.to_csv(outdir/"r2_winner_vs_loser_movement_effects.csv",index=False)

    # Reverse-engineering target: learn WHAT r2 winners look like pre-entry, then
    # search broad NON-r2 events that resemble that path. Threshold selection uses dev only.
    score,used=score_by_winner_similarity(d,dev&r2,fp,topn=24)
    d["reverse_score"]=score

    # Candidate pool excludes existing r2, to measure true frequency expansion.
    pool=~r2
    rows=[]; masks={}
    dev_scores=d.loc[dev&pool,"reverse_score"].dropna()
    for q in [.80,.85,.90,.925,.95,.965,.975,.985]:
        th=float(dev_scores.quantile(q))
        m=pool&(d.reverse_score>=th)
        md=metrics(d[disc&m]); mc=metrics(d[cal&m])
        if md.get("n",0)<20 or mc.get("n",0)<12:continue
        name=f"NON_R2_WINNER_PATH_SCORE_GE_Q{q:.3f}_{th:.5f}"
        rows.append({"name":name,"q":q,"threshold":th,
                     "disc_n":md["n"],"cal_n":mc["n"],
                     "disc_win":md["win24"],"cal_win":mc["win24"],
                     "disc_mean":md["mean24"],"cal_mean":mc["mean24"],
                     "disc_pf":md["pf24"],"cal_pf":mc["pf24"]})
        masks[name]=m
    tab=pd.DataFrame(rows)
    if len(tab):
        viable=tab[(tab.disc_win>=55)&(tab.cal_win>=55)&(tab.disc_mean>=0.75)&(tab.cal_mean>=0.75)&(tab.disc_pf>=1.4)&(tab.cal_pf>=1.4)].copy()
        if len(viable):
            viable["score"]=np.minimum(viable.disc_mean,viable.cal_mean)+0.04*np.minimum(viable.disc_win,viable.cal_win)+0.12*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))
            viable=viable.sort_values("score",ascending=False)
    else: viable=pd.DataFrame()

    tab.to_csv(outdir/"reverse_engineered_candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)

    top=[]
    weeks_2026=(pd.Timestamp("2026-09-18",tz="UTC")-pd.Timestamp("2026-01-01",tz="UTC")).days/7
    for _,r in viable.head(10).iterrows():
        m=masks[r["name"]]
        combo=r2|m
        top.append({
          "name":r["name"],
          "second_family":{"discovery":metrics(d[disc&m]),"calibration":metrics(d[cal&m]),"cross_holdout_pre2026":metrics(d[cross&m]),"all_2026":metrics(d[hold&m])},
          "combined_r2_or_second":{"discovery":metrics(d[disc&combo]),"calibration":metrics(d[cal&combo]),"cross_holdout_pre2026":metrics(d[cross&combo]),"all_2026":metrics(d[hold&combo]),
                                   "signals_per_week_2026":metrics(d[hold&combo]).get("n",0)/weeks_2026}
        })

    summary={
      "method":"Reverse engineer pre-entry movement fingerprint from existing r2 WINNERS versus r2 LOSERS, then find non-r2 events that resemble the winner path.",
      "selection_uses_2026":False,
      "movement_features_considered":len(feats),
      "stable_winner_loser_features":int(len(fp)),
      "fingerprint_features_used":used,
      "r2_baseline":{"discovery":metrics(d[disc&r2]),"calibration":metrics(d[cal&r2]),"cross_holdout_pre2026":metrics(d[cross&r2]),"all_2026":metrics(d[hold&r2])},
      "candidate_thresholds_tested":int(len(tab)),
      "viable_pre2026":int(len(viable)),
      "top":top
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Phase 4 — Winner Movement Reverse Engineering","",
           "Bu faz filtre uydurmuyor: mevcut r2 kazananlarının giriş ÖNCESİ hareket profilini r2 kaybedenlerinden çıkarır, sonra r2 dışındaki olaylarda aynı profile benzeyenleri arar.","",
           json.dumps(summary,indent=2,ensure_ascii=False)]
    (outdir/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir)
