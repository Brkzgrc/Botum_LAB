from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np,pandas as pd

POS_ARCH={"IMMEDIATE_CLEAN_3PCT_12H","TREND_CLEAN_5PCT_24H","IMPULSE_8PCT_72H"}
META={"symbol","decision_time","entry_time","label","archetype","year","hash_mod"}
OUTCOME={"ret12","mfe12","mae12","ret24","mfe24","mae24","ret72","mfe72","mae72"}
QSET=(.10,.20,.30,.70,.80,.90)

def split_masks(d):
    t=d.decision_time
    return {
      "DISCOVERY":(d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
      "CALIBRATION":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "CROSS_HOLDOUT_PRE2026":(d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "FINAL_HOLDOUT_2026":(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
    }

def load(indir):
    fs=sorted(indir.rglob("episodes.csv"))
    if not fs: raise RuntimeError("no outcome-first episodes artifacts")
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["hash_mod"]=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
    d=d[(d.label=="CONTROL")|((d.label=="RISE")&d.archetype.isin(POS_ARCH))].copy()
    d["y"]=((d.label=="RISE")&d.archetype.isin(POS_ARCH)).astype(int)
    return d

def met(d,m):
    z=d[m]
    if not len(z): return {"n":0}
    n=int(len(z)); pos=int(z.y.sum())
    return {"n":n,"symbols":int(z.symbol.nunique()),"pos":pos,"pos_rate":float(pos/n*100)}

def fam(c):
    s=c.lower()
    for x in ("bb_","tsi","adx","di_spread","atr","mfi","cmf","vwap","roc","ppo","cmo","donch","er10","chop","rvol","stoch","kdj","rsi","wpr","motion","macd","obv"):
        if x in s:return x
    return "other"

def tf(c):
    for p in ("m15_","h1_","h4_","btc1_","btc4_"):
        if c.startswith(p):return p[:-1]
    return "other"

def apply(d,r):
    if r["type"]=="single":
        s=pd.to_numeric(d[r["feature"]],errors="coerce")
        return s>=r["threshold"] if r["side"]=="GE" else s<=r["threshold"]
    return apply(d,r["a"])&apply(d,r["b"])

def score(base_d,base_c,md,mc):
    ld=md["pos_rate"]-base_d["pos_rate"]; lc=mc["pos_rate"]-base_c["pos_rate"]
    return min(ld,lc)+.4*min(math.log1p(md["n"]),math.log1p(mc["n"]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--preflight",action="store_true")
    a=ap.parse_args(); a.outdir.mkdir(parents=True,exist_ok=True)
    d=load(a.artifact_dir); masks=split_masks(d)
    pf={"rows":int(len(d)),"symbols":int(d.symbol.nunique()),"positive":int(d.y.sum()),
        "controls":int((d.y==0).sum()),"splits":{k:int(v.sum()) for k,v in masks.items()}}
    if pf["rows"]<200000 or pf["symbols"]<400 or min(pf["splits"].values())<10000:
        raise RuntimeError(f"unexpected cohort {pf}")
    if a.preflight:
        (a.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
        print(json.dumps(pf));return

    disc=masks["DISCOVERY"]; cal=masks["CALIBRATION"]
    base={k:met(d,m) for k,m in masks.items()}
    feats=[]
    for c in d.columns:
        if c in META|OUTCOME|{"y"} or c.startswith("pre_"): continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s[disc].notna().sum()>=10000 and s[disc].nunique(dropna=True)>=20: feats.append(c)

    rows=[]
    for c in feats:
        sd=pd.to_numeric(d.loc[disc,c],errors="coerce").dropna()
        for q in QSET:
            th=float(sd.quantile(q))
            for side in ("GE","LE"):
                r={"type":"single","feature":c,"side":side,"threshold":th,"q":q,"family":fam(c),"timeframe":tf(c)}
                m=apply(d,r)
                md=met(d,disc&m); mc=met(d,cal&m)
                if md["n"]<2500 or mc["n"]<1500:continue
                ld=md["pos_rate"]-base["DISCOVERY"]["pos_rate"];lc=mc["pos_rate"]-base["CALIBRATION"]["pos_rate"]
                if min(ld,lc)<4.0:continue
                rec={"rule":r,"DISCOVERY":md,"CALIBRATION":mc,
                     "CROSS_HOLDOUT_PRE2026":met(d,masks["CROSS_HOLDOUT_PRE2026"]&m),
                     "FINAL_HOLDOUT_2026":met(d,masks["FINAL_HOLDOUT_2026"]&m)}
                rec["score"]=score(base["DISCOVERY"],base["CALIBRATION"],md,mc)
                rows.append(rec)
    singles=sorted(rows,key=lambda x:x["score"],reverse=True)

    pairs=[]
    top=singles[:24]
    for i,x in enumerate(top):
        for y in top[i+1:]:
            if x["rule"]["family"]==y["rule"]["family"] and x["rule"]["timeframe"]==y["rule"]["timeframe"]:continue
            r={"type":"and_pair","a":x["rule"],"b":y["rule"]}
            m=apply(d,r);md=met(d,disc&m);mc=met(d,cal&m)
            if md["n"]<1200 or mc["n"]<800:continue
            ld=md["pos_rate"]-base["DISCOVERY"]["pos_rate"];lc=mc["pos_rate"]-base["CALIBRATION"]["pos_rate"]
            if min(ld,lc)<6.0:continue
            rec={"rule":r,"DISCOVERY":md,"CALIBRATION":mc,
                 "CROSS_HOLDOUT_PRE2026":met(d,masks["CROSS_HOLDOUT_PRE2026"]&m),
                 "FINAL_HOLDOUT_2026":met(d,masks["FINAL_HOLDOUT_2026"]&m)}
            rec["score"]=score(base["DISCOVERY"],base["CALIBRATION"],md,mc)
            pairs.append(rec)
    pairs=sorted(pairs,key=lambda x:x["score"],reverse=True)
    pool=pairs+singles
    champ=max(pool,key=lambda x:x["score"]) if pool else None
    out={"status":"SUCCESS" if champ else "NO_CANDIDATE","purpose":"Screen a genuinely independent second setup family from outcome-first rise/control episodes, without conditioning on r1/r2. All pre_* fields are excluded because the original pre-path implementation touched the entry candle. Selection uses Discovery+Calibration only.",
         "preflight":pf,"base":base,"features":len(feats),"stable_singles":len(singles),"stable_pairs":len(pairs),
         "champion_selected_without_holdouts":champ,"top10_singles":singles[:10],"top10_pairs":pairs[:10],
         "next_required_validation":"Run the frozen champion over the complete hourly Binance Spot USDT population for 2025 calibration and 2026 untouched population to measure real net24 and signals/day."}
    (a.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":out["status"],"features":len(feats),"singles":len(singles),"pairs":len(pairs),"champion":champ},ensure_ascii=False,allow_nan=False),flush=True)
if __name__=="__main__":main()
