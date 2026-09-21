from __future__ import annotations

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

F1="btc1_tsi_d1"
F2="btc4_bb_width"
F1_FROZEN=-0.211069
F2_FROZEN=0.0942267
COST=0.20

def pf(v):
    v=pd.to_numeric(v,errors="coerce").dropna()
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return float(gp/gl) if gl>0 else np.nan

def metrics(x):
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    return {
      "n":int(len(v)),
      "symbols":int(x.loc[v.index,"symbol"].nunique()),
      "win24":float((v>0).mean()*100),
      "mean24":float(v.mean()),
      "median24":float(v.median()),
      "pf24":pf(v),
      "p10_24":float(v.quantile(.10)),
      "up3_before_dn2":float(pd.to_numeric(x.loc[v.index,"up3_before_dn2"],errors="coerce").mean()*100),
      "danger_dn2_first":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100),
    }

def weeks_between(a,b):
    return (pd.Timestamp(b,tz="UTC")-pd.Timestamp(a,tz="UTC")).total_seconds()/604800.0

def load(indir:Path):
    fs=sorted(indir.rglob("features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames: raise RuntimeError("no features.csv artifacts")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [F1,F2,"net_24h","up3_before_dn2","danger_dn2_first"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    return d.dropna(subset=[F1,F2,"net_24h"]).copy()

def mask_feature(d,name,side,th):
    s=pd.to_numeric(d[name],errors="coerce")
    return s>=th if side=="GE" else s<=th

def main(indir:Path,outdir:Path):
    d=load(indir); outdir.mkdir(parents=True,exist_ok=True)
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))

    # Frozen baseline
    frozen=(d[F1]<=F1_FROZEN)&(d[F2]>=F2_FROZEN)

    # Controlled relaxation grid. Selection NEVER uses 2026.
    f1_grid=[-0.211069,-0.15,-0.10,-0.05,0.00,0.05,0.10]
    f2_grid=[0.0942267,0.085,0.075,0.065,0.055,0.045]

    # Video-rule-derived measurable proxy families available in the frozen artifacts.
    # A: momentum slowing / recovery (PPO histogram derivatives)
    # C: bearish pressure veto proxies (DI spread / ADX context)
    # Additional location/energy proxies: VWAP, BB position, relative volume.
    candidate_features=[
      "m15_ppo_hist_d1","m15_ppo_hist_acc","h1_ppo_hist_d1","h1_ppo_hist_acc",
      "h4_ppo_hist_d1","h4_ppo_hist_acc",
      "m15_di_spread","h1_di_spread","h4_di_spread",
      "m15_vwap_dist","h1_vwap_dist",
      "m15_bb_pctb","h1_bb_pctb",
      "m15_rvol20","h1_rvol20",
      "m15_er10","h1_er10"
    ]
    candidate_features=[c for c in candidate_features if c in d.columns]

    # thresholds learned on DISCOVERY only, fixed before calibration/holdout
    filters=[]
    for c in candidate_features:
        s=pd.to_numeric(d.loc[disc,c],errors="coerce").dropna()
        if len(s)<500: continue
        for q in [.30,.40,.50,.60,.70]:
            th=float(s.quantile(q))
            for side in ["GE","LE"]:
                filters.append((c,side,q,th))

    w_disc=weeks_between("2023-01-01","2025-01-01")
    w_cal=weeks_between("2025-01-01","2026-01-01")
    rows=[]; masks={}
    for a in f1_grid:
      for b in f2_grid:
        base=(d[F1]<=a)&(d[F2]>=b)
        md=metrics(d[disc&base]); mc=metrics(d[cal&base])
        if md["n"]<50 or mc["n"]<25: continue
        freq_d=md["n"]/w_disc; freq_c=mc["n"]/w_cal
        nm=f"TSI<={a:.6f}&BTC4BB>={b:.7f}"
        rows.append({"kind":"relaxed","name":nm,"f1":a,"f2":b,"filter_feature":"","filter_side":"","filter_threshold":np.nan,
                     "disc_freq":freq_d,"cal_freq":freq_c,
                     "disc_win":md["win24"],"cal_win":mc["win24"],
                     "disc_mean":md["mean24"],"cal_mean":mc["mean24"],
                     "disc_pf":md["pf24"],"cal_pf":mc["pf24"]})
        masks[nm]=base

        for c,side,q,th in filters:
            fm=mask_feature(d,c,side,th)
            m=base&fm
            xd=metrics(d[disc&m]); xc=metrics(d[cal&m])
            if xd["n"]<40 or xc["n"]<20: continue
            fd=xd["n"]/w_disc; fc=xc["n"]/w_cal
            name=f"{nm} + {c} {side} Q{int(q*100)}({th:.6g})"
            rows.append({"kind":"relaxed+filter","name":name,"f1":a,"f2":b,"filter_feature":c,"filter_side":side,"filter_threshold":th,
                         "disc_freq":fd,"cal_freq":fc,
                         "disc_win":xd["win24"],"cal_win":xc["win24"],
                         "disc_mean":xd["mean24"],"cal_mean":xc["mean24"],
                         "disc_pf":xd["pf24"],"cal_pf":xc["pf24"]})
            masks[name]=m

    tab=pd.DataFrame(rows)
    # Operational target: at least ~5/week in both dev splits, preferably <=15/week;
    # quality must remain economically meaningful in both.
    viable=tab[
      (tab.disc_freq>=5)&(tab.cal_freq>=5)&
      (tab.disc_freq<=15)&(tab.cal_freq<=15)&
      (tab.disc_mean>1.0)&(tab.cal_mean>1.0)&
      (tab.disc_pf>1.5)&(tab.cal_pf>1.5)&
      (tab.disc_win>=60)&(tab.cal_win>=60)
    ].copy()
    if len(viable):
        viable["score"]=(
          np.minimum(viable.disc_mean,viable.cal_mean)
          +0.06*np.minimum(viable.disc_win,viable.cal_win)
          +0.15*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))
          -0.08*(np.abs(viable.disc_freq-8)+np.abs(viable.cal_freq-8))
        )
        viable=viable.sort_values("score",ascending=False)
    tab.to_csv(outdir/"all_candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)

    chosen=[]
    for _,r in viable.head(12).iterrows():
        m=masks[r["name"]]
        chosen.append({
          "name":r["name"],"kind":r["kind"],
          "discovery":metrics(d[disc&m]),"calibration":metrics(d[cal&m]),
          "cross_holdout_pre2026":metrics(d[cross&m]),
          "holdout_2026":metrics(d[hold&m]),
          "holdout_2026_signals_per_week":metrics(d[hold&m]).get("n",0)/weeks_between("2026-01-01","2026-09-18")
        })

    base={
      "frozen_tsi_bb":{
        "discovery":metrics(d[disc&frozen]),"calibration":metrics(d[cal&frozen]),
        "cross_holdout_pre2026":metrics(d[cross&frozen]),"holdout_2026":metrics(d[hold&frozen]),
      }
    }
    summary={
      "purpose":"Phase 1: widen frozen TSI+BB pre-2026, then test measurable momentum/pressure/location filters inspired by SPOT_STRATEJI_KURALLARI. 2026 is evaluation only.",
      "cost_pct":COST,
      "selection_uses_2026":False,
      "candidate_features":candidate_features,
      "candidate_count":int(len(tab)),
      "viable_pre2026_count":int(len(viable)),
      "base":base,
      "top_candidates":chosen
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# TSI+BB Extension Research — Phase 1","",
      "Selection: Discovery 2023-24 + Calibration 2025 only. 2026 never selects thresholds.",
      "Target: 5-15 signals/week in both dev splits; win>=60%, mean24>1%, PF>1.5.",
      f"Candidates={len(tab)} | viable pre2026={len(viable)}","",
      "## Frozen baseline",json.dumps(base,ensure_ascii=False),"","## Top candidates"]
    for x in chosen: lines.append("- "+json.dumps(x,ensure_ascii=False))
    (outdir/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir)
