from __future__ import annotations

import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

PLANS=("TP3_SL2","TP4_SL2P5","TP5_SL3")
FAMILY_PREFIXES={"CB":"COMPRESSION_BREAKOUT","PB":"PULLBACK_REACCEL","RC":"RECLAIM_BEAR_TRAP","ER":"EARLY_REVERSAL"}
END_2026=pd.Timestamp("2026-09-18",tz="UTC")

def split_masks(d):
    t=d.decision_time
    return {
      "DISCOVERY":(d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
      "CALIBRATION":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "CROSS_HOLDOUT_PRE2026":(d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "FINAL_HOLDOUT_2026":(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
      "ALL_2026":t>=pd.Timestamp("2026-01-01",tz="UTC"),
    }

def days(split):
    return {"DISCOVERY":731,"CALIBRATION":365,"CROSS_HOLDOUT_PRE2026":1096,
            "FINAL_HOLDOUT_2026":260,"ALL_2026":260}[split]

def metrics(x):
    if len(x)==0:return {"n":0,"symbols":0}
    v=pd.to_numeric(x.net24,errors="coerce").dropna()
    z=x.loc[v.index]
    gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
    out={
      "n":int(len(v)),"symbols":int(z.symbol.nunique()),
      "mean24":float(v.mean()),"median24":float(v.median()),
      "win24":float((v>0).mean()*100),
      "pf24":float(gp/gl) if gl>0 else None,
      "mfe24":float(pd.to_numeric(z.mfe24,errors="coerce").mean()),
      "mae24":float(pd.to_numeric(z.mae24,errors="coerce").mean()),
    }
    for p in PLANS:
      q=pd.to_numeric(z[f"ret_{p}"],errors="coerce").dropna()
      g=float(q[q>0].sum()); l=float(-q[q<0].sum())
      out[p]={
        "mean":float(q.mean()),"win":float((q>0).mean()*100),
        "pf":float(g/l) if l>0 else None,
        "target_first":float(pd.to_numeric(z.loc[q.index,f"win_{p}"],errors="coerce").mean()*100),
        "stop_first":float(pd.to_numeric(z.loc[q.index,f"loss_{p}"],errors="coerce").mean()*100),
      }
    return out

def frequency(x,split):
    n=len(x); nd=days(split)
    if not n:return {"signals":0,"signals_per_day":0.0,"active_days":0,"active_day_share_pct":0.0}
    c=x.groupby(x.decision_time.dt.floor("D")).size()
    return {"signals":int(n),"signals_per_day":float(n/nd),"active_days":int(len(c)),
            "active_day_share_pct":float(len(c)/nd*100),
            "median_on_active_day":float(c.median()),"p90_on_active_day":float(c.quantile(.90)),
            "max_in_day":int(c.max())}

def load_events(indir):
    fs=sorted(indir.rglob("events.csv"))
    if len(fs)!=64: raise RuntimeError(f"expected 64 events.csv files, found {len(fs)}")
    frames=[]
    for f in fs:
      try:q=pd.read_csv(f,low_memory=False)
      except pd.errors.EmptyDataError:continue
      if len(q):frames.append(q)
    if not frames:raise RuntimeError("no event rows")
    d=pd.concat(frames,ignore_index=True)
    req={"symbol","hash_mod","decision_time","rules","net24","mfe24","mae24"}
    for p in PLANS:req|={f"ret_{p}",f"win_{p}",f"loss_{p}"}
    miss=sorted(req-set(d.columns))
    if miss:raise RuntimeError(f"missing columns {miss}")
    d.decision_time=pd.to_datetime(d.decision_time,utc=True)
    d.hash_mod=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
    d=d.drop_duplicates(["symbol","decision_time"]).sort_values(["decision_time","symbol"]).reset_index(drop=True)
    if len(d)<1_000_000 or d.symbol.nunique()<450:
      raise RuntimeError(f"unexpected population rows={len(d)} symbols={d.symbol.nunique()}")
    return d

def bucket(n):
    n=int(n)
    if n==0:return "0"
    if n<=2:return "1-2"
    if n<=5:return "3-5"
    if n<=8:return "6-8"
    return "9+"

def signatures(d):
    counts={p:[] for p in FAMILY_PREFIXES}
    total=[]; fams=[]; sig=[]
    for s in d.rules.astype(str):
      ids=[x for x in s.split(";") if x]
      cc={p:sum(x.startswith(p+"_") for x in ids) for p in FAMILY_PREFIXES}
      for p in FAMILY_PREFIXES:counts[p].append(cc[p])
      total.append(len(ids)); fams.append(sum(v>0 for v in cc.values()))
      sig.append("|".join(f"{p}:{bucket(cc[p])}" for p in FAMILY_PREFIXES))
    for p in FAMILY_PREFIXES:d[p.lower()+"_n"]=counts[p]
    d["rule_n"]=total;d["family_n"]=fams;d["signature"]=sig
    return d

def wilson_lower(wins,n,z=1.96):
    if n<=0:return 0.0
    p=wins/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def load_r2_reference(path):
    s=json.loads(path.read_text(encoding="utf-8"))
    D=s["sections"]["DISCOVERY"]["r2"];C=s["sections"]["CALIBRATION"]["r2"]
    return {
      "min_mean24":min(D["net24_mean"],C["net24_mean"]),
      "min_win24":min(D["win24"],C["win24"]),
      "min_up3":min(D["up3_before_dn2"],C["up3_before_dn2"]),
      "min_pf24":min(D["pf24"],C["pf24"]),
    }

def group_table(d,sm):
    rows=[]
    for sig,z in d.groupby("signature",sort=False):
      rec={"signature":sig}
      ok=True
      for sp in ("DISCOVERY","CALIBRATION"):
        q=z[sm[sp].loc[z.index]]
        m=metrics(q); f=frequency(q,sp)
        rec[sp]={"metrics":m,"frequency":f}
        if m["n"]<50:ok=False
      if not ok:continue
      D=rec["DISCOVERY"]["metrics"];C=rec["CALIBRATION"]["metrics"]
      # conservative success estimate based on +3/-2 first touch
      for sp in ("DISCOVERY","CALIBRATION"):
        m=rec[sp]["metrics"];n=m["n"];wins=round(m["TP3_SL2"]["target_first"]/100*n)
        rec[sp]["tp3_wilson_low"]=wilson_lower(wins,n)*100
      rec["score"]=min(D["mean24"],C["mean24"])+.03*min(D["win24"],C["win24"])+.02*min(D["TP3_SL2"]["target_first"],C["TP3_SL2"]["target_first"])+.25*math.log1p(min(D["n"],C["n"]))
      rows.append(rec)
    rows.sort(key=lambda r:r["score"],reverse=True)
    return rows

def union_metrics(d,sm,sigs):
    mask=d.signature.isin(sigs)
    return {sp:{"metrics":metrics(d[mask&m]),"frequency":frequency(d[mask&m],sp)} for sp,m in sm.items()},mask

def parity_ok(u,ref):
    for sp in ("DISCOVERY","CALIBRATION"):
      m=u[sp]["metrics"]
      if m["n"]<100:return False
      if m["mean24"]<ref["min_mean24"]:return False
      if m["win24"]<ref["min_win24"]:return False
      if m["TP3_SL2"]["target_first"]<ref["min_up3"]:return False
      if (m["pf24"] or 0)<ref["min_pf24"]:return False
    return True

def strong_ok(u):
    for sp in ("DISCOVERY","CALIBRATION"):
      m=u[sp]["metrics"]
      if m["n"]<150:return False
      if m["mean24"]<1.5 or m["win24"]<70:return False
      if m["TP3_SL2"]["target_first"]<60:return False
      if (m["pf24"] or 0)<2:return False
    return True

def projected_rate(u):
    # D/C use ~70% symbol bucket. Scale only for selection-frequency targeting.
    D=u["DISCOVERY"]["frequency"]["signals_per_day"]/0.70
    C=u["CALIBRATION"]["frequency"]["signals_per_day"]/0.70
    return min(D,C)

def greedy(d,sm,groups,ref,mode):
    selected=[];best=None
    # prefilter individual structural states
    cand=[]
    for g in groups:
      D=g["DISCOVERY"]["metrics"];C=g["CALIBRATION"]["metrics"]
      if mode=="PARITY":
        cond=(min(D["mean24"],C["mean24"])>=ref["min_mean24"] and
              min(D["win24"],C["win24"])>=ref["min_win24"] and
              min(D["TP3_SL2"]["target_first"],C["TP3_SL2"]["target_first"])>=ref["min_up3"])
      else:
        cond=(min(D["mean24"],C["mean24"])>=1.0 and min(D["win24"],C["win24"])>=65 and
              min(D["TP3_SL2"]["target_first"],C["TP3_SL2"]["target_first"])>=55)
      if cond:cand.append(g)
    for g in cand:
      trial=selected+[g["signature"]]
      u,_=union_metrics(d,sm,trial)
      ok=parity_ok(u,ref) if mode=="PARITY" else strong_ok(u)
      if not ok:continue
      selected=trial
      rate=projected_rate(u)
      best={"signatures":selected.copy(),"evaluation":u,"projected_all_symbol_dev_rate":rate}
      if rate>=2.0:break
      if len(selected)>=120:break
    return best, len(cand)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--movement-dir",type=Path,required=True)
    ap.add_argument("--r2-summary",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--preflight",action="store_true")
    a=ap.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
    d=signatures(load_events(a.movement_dir));sm=split_masks(d);ref=load_r2_reference(a.r2_summary)
    pf={"events":int(len(d)),"symbols":int(d.symbol.nunique()),"signatures":int(d.signature.nunique()),
        "split_counts":{k:int(v.sum()) for k,v in sm.items()},"r2_reference":ref}
    if a.preflight:
      (a.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
      print(json.dumps(pf));return
    groups=group_table(d,sm)
    parity,parity_n=greedy(d,sm,groups,ref,"PARITY")
    strong,strong_n=greedy(d,sm,groups,ref,"STRONG")
    chosen=parity if parity and parity["projected_all_symbol_dev_rate"]>=2 else strong
    tier="R2_PARITY" if chosen is parity and chosen is not None else ("STRONG_QUALITY" if chosen is not None else None)
    status="NO_STABLE_SIGNATURE_FAMILY_SET"
    if chosen:
      # Holdouts were not consulted until after the signature set was locked.
      all26=chosen["evaluation"]["ALL_2026"]
      rate=all26["frequency"]["signals_per_day"]
      m=all26["metrics"]
      status="DEV_STABLE_SIGNATURE_SET_HOLDOUT_EVALUATED"
      if rate>=2 and m["mean24"]>0 and (m["pf24"] or 0)>1:
        status="OOS_POSITIVE_2PLUS_PER_DAY"
      if tier=="R2_PARITY" and rate>=2 and m["win24"]>=ref["min_win24"] and m["mean24"]>=ref["min_mean24"]:
        status="R2_PARITY_TARGET_FREQUENCY"
    out={
      "status":status,
      "purpose":"Discover independent price-movement setup states from the 48-rule movement-family membership signature, not by loosening r2 filters.",
      "causality":"All source events were formed from closed 15M/1H/4H bars; entry is next 15M open. Signature selection uses Discovery+Calibration only.",
      "preflight":pf,"r2_reference_floor":ref,
      "signature_groups_evaluated":len(groups),
      "parity_individual_candidates":parity_n,"strong_individual_candidates":strong_n,
      "selected_tier":tier,"selected":chosen,
      "top30_structural_signatures":groups[:30],
    }
    (a.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    pd.DataFrame([{
      "rank":i+1,"signature":g["signature"],"score":g["score"],
      "disc_n":g["DISCOVERY"]["metrics"]["n"],"disc_mean24":g["DISCOVERY"]["metrics"]["mean24"],"disc_win24":g["DISCOVERY"]["metrics"]["win24"],"disc_tp3":g["DISCOVERY"]["metrics"]["TP3_SL2"]["target_first"],
      "cal_n":g["CALIBRATION"]["metrics"]["n"],"cal_mean24":g["CALIBRATION"]["metrics"]["mean24"],"cal_win24":g["CALIBRATION"]["metrics"]["win24"],"cal_tp3":g["CALIBRATION"]["metrics"]["TP3_SL2"]["target_first"],
    } for i,g in enumerate(groups)]).to_csv(a.outdir/"signature_table.csv",index=False)
    print(json.dumps({"status":status,"selected_tier":tier,"selected":chosen,"groups":len(groups)},ensure_ascii=False,allow_nan=False))

if __name__=="__main__":main()
