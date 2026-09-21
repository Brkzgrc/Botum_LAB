from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
import frozen_candidate_outcome_extension_snapshot as ext

R2_BB=0.19233492
R2_DD=-7.3594696

def metrics(x):
    if len(x)==0:return {"n":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if len(v)==0:return {"n":0}
    gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
            "win24":float((v>0).mean()*100),"mean24":float(v.mean()),
            "median24":float(v.median()),"pf24":float(gp/gl) if gl>0 else None,
            "p10":float(v.quantile(.10))}

def load(indir):
    d=ext.load_frozen_candidate(indir)
    d=ext.add_causal_pullbacks(d,workers=12)
    return d[d.pullback_error.fillna("")==""].copy()

def usable_features(d):
    toks=("rsi","stoch","kdj","macd","ppo","tsi","mfi","cmf","obv","adx","di_",
          "atr","bb_","vwap","roc","cmo","donch","er10","chop","rvol","ret_","motion")
    out=[]
    for c in d.columns:
        lc=c.lower()
        if c.startswith(("net_","gross_","mfe_","mae_","t_","up3_","danger_","causal_")): continue
        if c in {"symbol","decision_time","entry_time","hash_mod"}: continue
        if not c.startswith(("m15_","h1_","h4_","btc1_","btc4_")): continue
        if not any(t in lc for t in toks): continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s.notna().sum()>=300 and s.nunique(dropna=True)>=20: out.append(c)
    return out

def robust_profile(d,train,r2,features):
    w=train&r2&(d.net_24h>0)
    l=train&r2&(d.net_24h<=0)
    rows=[]
    for c in features:
        sw=pd.to_numeric(d.loc[w,c],errors="coerce").dropna()
        sl=pd.to_numeric(d.loc[l,c],errors="coerce").dropna()
        if len(sw)<8 or len(sl)<3: continue
        allv=pd.concat([sw,sl]); scale=float(allv.quantile(.75)-allv.quantile(.25))
        if not np.isfinite(scale) or scale<=0: continue
        mw=float(sw.median()); ml=float(sl.median())
        sep=abs(mw-ml)/scale
        if sep<0.10: continue
        rows.append((c,mw,ml,scale,sep))
    rows=sorted(rows,key=lambda z:z[4],reverse=True)[:40]
    return rows

def prototype_score(d,profile):
    score=np.zeros(len(d),float); weight=0.0
    for c,mw,ml,scale,sep in profile:
        x=pd.to_numeric(d[c],errors="coerce")
        dw=((x-mw).abs()/scale).clip(upper=6)
        dl=((x-ml).abs()/scale).clip(upper=6)
        s=(dl-dw).fillna(-2.0)
        w=min(sep,2.0)
        score+=w*s.to_numpy(); weight+=w
    return pd.Series(score/max(weight,1e-9),index=d.index)

def main(indir,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    d=load(indir)
    t=d.decision_time
    disc=(d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC"))
    r2=(pd.to_numeric(d.h4_bb_width,errors="coerce")>=R2_BB)&(pd.to_numeric(d.causal_dd_high_48h,errors="coerce")<=R2_DD)

    feats=usable_features(d)
    profile=robust_profile(d,disc,r2,feats)
    d["winner_similarity"]=prototype_score(d,profile)

    pool=~r2
    # Thresholds are defined by DISCOVERY non-r2 score quantiles only.
    qs=[.50,.60,.70,.75,.80,.85,.90,.925,.95]
    rows=[]; masks={}
    sd=d.loc[disc&pool,"winner_similarity"].dropna()
    for q in qs:
        th=float(sd.quantile(q))
        m=pool&(d.winner_similarity>=th)
        md=metrics(d[disc&m]); mc=metrics(d[cal&m])
        if md.get("n",0)<10 or mc.get("n",0)<8: continue
        nm=f"NON_R2_R2WIN_SIM_Q{int(q*1000)}"
        rows.append({"name":nm,"q":q,"threshold":th,
                     "disc_n":md["n"],"cal_n":mc["n"],
                     "disc_win":md["win24"],"cal_win":mc["win24"],
                     "disc_mean":md["mean24"],"cal_mean":mc["mean24"],
                     "disc_pf":md["pf24"],"cal_pf":mc["pf24"]})
        masks[nm]=m
    tab=pd.DataFrame(rows)
    viable=pd.DataFrame()
    if len(tab):
        viable=tab[(tab.disc_win>=55)&(tab.cal_win>=55)&
                   (tab.disc_mean>0.5)&(tab.cal_mean>0.5)&
                   (tab.disc_pf>1.2)&(tab.cal_pf>1.2)].copy()
        if len(viable):
            viable["score"]=np.minimum(viable.disc_mean,viable.cal_mean)+0.04*np.minimum(viable.disc_win,viable.cal_win)+0.1*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))
            viable=viable.sort_values("score",ascending=False)
    tab.to_csv(outdir/"candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)
    pd.DataFrame(profile,columns=["feature","winner_median","loser_median","iqr","separation"]).to_csv(outdir/"r2_winner_profile.csv",index=False)

    weeks=(pd.Timestamp("2026-09-18",tz="UTC")-pd.Timestamp("2026-01-01",tz="UTC")).days/7
    top=[]
    for _,r in viable.head(8).iterrows():
        m=masks[r["name"]]; combo=r2|m
        top.append({"name":r["name"],
                    "second_family":{"discovery":metrics(d[disc&m]),"calibration":metrics(d[cal&m]),"cross_pre2026":metrics(d[cross&m]),"all_2026":metrics(d[hold&m])},
                    "combined":{"discovery":metrics(d[disc&combo]),"calibration":metrics(d[cal&combo]),"cross_pre2026":metrics(d[cross&combo]),"all_2026":metrics(d[hold&combo]),"signals_per_week_2026":metrics(d[hold&combo]).get("n",0)/weeks}})
    summary={"method":"R2 winner-vs-loser prototype similarity; discover non-r2 events matching winning movement profile",
             "selection_uses_2026":False,"features_considered":len(feats),"profile_features":len(profile),
             "r2":{"discovery":metrics(d[disc&r2]),"calibration":metrics(d[cal&r2]),"cross_pre2026":metrics(d[cross&r2]),"all_2026":metrics(d[hold&r2])},
             "thresholds_tested":len(tab),"viable_pre2026":len(viable),"top":top}
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (outdir/"REPORT.md").write_text("# Phase 5 R2 Winner Prototype Expansion\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--artifact-dir",type=Path,required=True); ap.add_argument("--outdir",type=Path,required=True)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir)
