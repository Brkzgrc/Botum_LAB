from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ATR_BASE=1.58953710752988
COST=0.20

def metrics(x):
    if len(x)==0:return {"n":0,"symbols":0}
    v=pd.to_numeric(x.net24,errors="coerce").dropna(); z=x.loc[v.index]
    gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
    return {"n":int(len(v)),"symbols":int(z.symbol.nunique()),"mean24":float(v.mean()),"median24":float(v.median()),"win24":float((v>0).mean()*100),"pf24":gp/gl if gl>0 else None,"up3":float(pd.to_numeric(z.up3_before_dn2,errors="coerce").mean()*100),"danger":float(pd.to_numeric(z.danger_dn2_first,errors="coerce").mean()*100)}

def frequency(x,start,end):
    days=max(1,(end.normalize()-start.normalize()).days+1)
    return {"signals":int(len(x)),"days":int(days),"signals_per_day":float(len(x)/days)}

def load(path):
    d=pd.read_csv(path,low_memory=False)
    need={"symbol","decision_time","h1_atr_pct","hash_mod","net24","up3_before_dn2","danger_dn2_first"}
    miss=sorted(need-set(d.columns))
    if miss:raise RuntimeError(f"missing columns {miss}")
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["hash_mod"]=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
    d["h1_atr_pct"]=pd.to_numeric(d.h1_atr_pct,errors="coerce")
    d=d.sort_values(["symbol","decision_time"]).reset_index(drop=True)
    g=d.groupby("symbol",sort=False)
    d["prev_time"]=g.decision_time.shift(1)
    d["prev_atr"]=g.h1_atr_pct.shift(1)
    d["gap_h"]=(d.decision_time-d.prev_time).dt.total_seconds()/3600.0
    d["atr_d1"]=d.h1_atr_pct-d.prev_atr
    newrun=d.gap_h.isna()|(d.gap_h>1.5)
    d["run_id"]=newrun.groupby(d.symbol).cumsum()
    d["run_age"]=d.groupby(["symbol","run_id"]).cumcount()
    return d

def splits(d):
    t=d.decision_time
    return {
      "DISCOVERY":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2025-07-01",tz="UTC")),
      "CALIBRATION":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-07-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "CROSS_HOLDOUT_2025":(d.hash_mod<30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "FINAL_HOLDOUT_2026":(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
      "ALL_2026":t>=pd.Timestamp("2026-01-01",tz="UTC"),
    }

def candidate_rules():
    out=[]
    uppers=[2.0,2.5,3.0,4.0,5.0,7.0,10.0,None]
    lowers=[ATR_BASE,1.75,2.0,2.5,3.0,4.0]
    for lo in lowers:
        for hi in uppers:
            if hi is not None and hi<=lo:continue
            out.append({"family":"RUN_START_BAND","run_age_max":0,"atr_lo":lo,"atr_hi":hi})
    for gap in [2,4,8,12,24,48,72]:
        for hi in [2.5,3.0,4.0,5.0,7.0,None]:
            out.append({"family":"QUIET_GAP","gap_min":gap,"atr_lo":ATR_BASE,"atr_hi":hi})
    for age in [0,1,2,3,6,12]:
        for hi in [2.5,3.0,4.0,5.0,None]:
            out.append({"family":"EARLY_RUN","run_age_max":age,"atr_lo":ATR_BASE,"atr_hi":hi})
    for side in ["UP","DOWN"]:
        for age in [1,2,3,6]:
            for hi in [2.5,3.0,4.0,5.0,None]:
                out.append({"family":"ATR_DIRECTION","run_age_max":age,"atr_d1":side,"atr_lo":ATR_BASE,"atr_hi":hi})
    return out

def apply(d,r):
    m=d.h1_atr_pct>=r.get("atr_lo",ATR_BASE)
    hi=r.get("atr_hi")
    if hi is not None:m&=d.h1_atr_pct<hi
    if "run_age_max" in r:m&=d.run_age<=r["run_age_max"]
    if "gap_min" in r:m&=(d.gap_h.isna()|(d.gap_h>=r["gap_min"]))
    side=r.get("atr_d1")
    if side=="UP":m&=d.atr_d1>0
    elif side=="DOWN":m&=d.atr_d1<0
    return m.fillna(False)

def eval_rule(d,sp,r):
    m=apply(d,r); rec={"rule":r}
    for k,sm in sp.items(): rec[k]=metrics(d[m&sm])
    return rec,m

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--events",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True);ap.add_argument("--preflight",action="store_true");a=ap.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
    d=load(a.events);sp=splits(d)
    pf={"rows":int(len(d)),"symbols":int(d.symbol.nunique()),"min_time":str(d.decision_time.min()),"max_time":str(d.decision_time.max()),"split_counts":{k:int(v.sum()) for k,v in sp.items()},"rules":len(candidate_rules())}
    if len(d)<1500000 or d.symbol.nunique()<400 or min(pf["split_counts"]["DISCOVERY"],pf["split_counts"]["CALIBRATION"])<100000:raise RuntimeError(f"unexpected cohort {pf}")
    if a.preflight:
        print(json.dumps(pf));(a.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8");return
    rows=[]
    for r in candidate_rules():
        rec,m=eval_rule(d,sp,r);D=rec["DISCOVERY"];C=rec["CALIBRATION"]
        if min(D["n"],C["n"])<100:continue
        fd=frequency(d[m&sp["DISCOVERY"]],pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-06-30",tz="UTC"))["signals_per_day"]
        fc=frequency(d[m&sp["CALIBRATION"]],pd.Timestamp("2025-07-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC"))["signals_per_day"]
        rec["train_frequency"]={"discovery_per_day":fd,"calibration_per_day":fc}
        stable=(min(D["mean24"],C["mean24"])>0 and min(D["win24"],C["win24"])>=50 and (D["pf24"] or 0)>1 and (C["pf24"] or 0)>1)
        rec["stable_train"]=stable
        freq_pen=abs(math.log((min(fd,fc)+0.25)/2.75))
        rec["score"]=min(D["mean24"],C["mean24"])+0.01*min(D["win24"],C["win24"])-0.15*freq_pen
        rows.append(rec)
    stable=[x for x in rows if x["stable_train"]]
    stable=sorted(stable,key=lambda x:x["score"],reverse=True)
    champ=stable[0] if stable else None
    if champ:
        m=apply(d,champ["rule"])
        champ["frequency"]={
          "CROSS_HOLDOUT_2025":frequency(d[m&sp["CROSS_HOLDOUT_2025"]],pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
          "FINAL_HOLDOUT_2026":frequency(d[m&sp["FINAL_HOLDOUT_2026"]],pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-18",tz="UTC")),
          "ALL_2026":frequency(d[m&sp["ALL_2026"]],pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-18",tz="UTC")),
        }
    out={"status":"SUCCESS","purpose":"Audit whether the failed broad ATR screen contains a causal sparse transition state (first-cross/quiet-gap/early-run/ATR-direction) with positive real 24h expectancy. Candidate choice uses only 2025 DEV-symbol Discovery+Calibration; holdouts are diagnostic.","preflight":pf,"stable_train_rules":len(stable),"champion_selected_without_holdouts":champ,"top20":stable[:20]}
    (a.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":out["status"],"stable":len(stable),"champion":champ},ensure_ascii=False,allow_nan=False))
if __name__=="__main__":main()
