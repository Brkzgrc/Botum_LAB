from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np,pandas as pd

PLANS=("TP3_SL2","TP4_SL2P5","TP5_SL3")
CATS=("h4_trend_score",)
FOCUS=[
"h4_trend_score","mom_accel_15m","h4_rsi","h4_ema50_dist_pct","h4_ema50_d1",
"h4_di_spread","h4_ema20_dist_pct","h4_ema20_d1","mom_accel_4h","h1_di_spread",
"stoch_spread_d3","dd_12h_prev","h1_rsi","h1_macd_hist_d1","h1_rsi_d3",
"h1_bb_width_ratio","rvol20","ret_6p","ret_3p","break_strength_pct"
]

def split_masks(d):
 t=d.decision_time
 return {
 "DISCOVERY":(d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
 "CALIBRATION":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
 "CROSS_HOLDOUT_PRE2026":(d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
 "FINAL_HOLDOUT_2026":(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
 "ALL_2026":t>=pd.Timestamp("2026-01-01",tz="UTC"),
 }

def period_days(s):return {"DISCOVERY":731,"CALIBRATION":365,"CROSS_HOLDOUT_PRE2026":1096,"FINAL_HOLDOUT_2026":260,"ALL_2026":260}[s]

def metrics(x,plan):
 if len(x)==0:return {"n":0}
 q=pd.to_numeric(x[f"ret_{plan}"],errors="coerce").dropna();z=x.loc[q.index]
 if not len(q):return {"n":0}
 g=float(q[q>0].sum());l=float(-q[q<0].sum())
 return {"n":int(len(q)),"mean":float(q.mean()),"median":float(q.median()),"win":float((q>0).mean()*100),
 "pf":float(g/l) if l>0 else None,
 "target_first":float(pd.to_numeric(z[f"win_{plan}"],errors="coerce").mean()*100),
 "stop_first":float(pd.to_numeric(z[f"loss_{plan}"],errors="coerce").mean()*100)}

def freq(x,sp):
 nd=period_days(sp)
 if len(x)==0:return {"signals":0,"signals_per_day":0.0,"active_days":0,"active_day_share_pct":0.0}
 c=x.groupby(x.decision_time.dt.floor("D")).size()
 return {"signals":int(len(x)),"signals_per_day":float(len(x)/nd),"active_days":int(len(c)),
 "active_day_share_pct":float(len(c)/nd*100),"max_in_day":int(c.max())}

def load(indir):
 fs=sorted(indir.rglob("events.csv"))
 if len(fs)!=64:raise RuntimeError(f"expected 64 events files got {len(fs)}")
 frames=[]
 for p in fs:
  try:q=pd.read_csv(p,low_memory=False)
  except pd.errors.EmptyDataError:continue
  if len(q):frames.append(q)
 if not frames:raise RuntimeError("no events")
 d=pd.concat(frames,ignore_index=True)
 d.decision_time=pd.to_datetime(d.decision_time,utc=True)
 d.hash_mod=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
 d=d.drop_duplicates(["symbol","decision_time"]).reset_index(drop=True)
 if len(d)<2500 or d.symbol.nunique()<350:raise RuntimeError(f"unexpected coverage {len(d)} {d.symbol.nunique()}")
 miss=[c for c in FOCUS if c not in d.columns]
 if miss:raise RuntimeError(f"missing focus features {miss}")
 return d

def audit_errors(indir):
 benign=[];hard=[]
 for p in indir.rglob("errors.csv"):
  try:e=pd.read_csv(p)
  except pd.errors.EmptyDataError:continue
  for _,r in e.iterrows():
   rec={"symbol":str(r.get("symbol","")),"error":str(r.get("error",""))}
   if rec["error"].startswith(("too_short:","study_too_short:")):benign.append(rec)
   else:hard.append(rec)
 return benign,hard

def gates(d,dev):
 out=[]
 # Explicit categorical gates missed by v1 because of low cardinality.
 out += [
  {"feature":"h4_trend_score","op":"<=","threshold":0.0,"kind":"categorical"},
  {"feature":"h4_trend_score","op":"<=","threshold":1.0,"kind":"categorical"},
  {"feature":"h4_trend_score","op":"<=","threshold":2.0,"kind":"categorical"},
  {"feature":"h4_trend_score","op":">=","threshold":1.0,"kind":"categorical"},
  {"feature":"h4_trend_score","op":">=","threshold":2.0,"kind":"categorical"},
 ]
 for f in FOCUS:
  if f in CATS:continue
  x=pd.to_numeric(d.loc[dev,f],errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
  if len(x)<500 or x.nunique()<8:continue
  for q in (.15,.25,.35,.65,.75,.85):
   th=float(x.quantile(q))
   op=">=" if q<.5 else "<="
   out.append({"feature":f,"op":op,"threshold":th,"q":q,"kind":"quantile"})
 # de-dup semantically
 seen=set();ans=[]
 for g in out:
  k=(g["feature"],g["op"],round(g["threshold"],12))
  if k not in seen:seen.add(k);ans.append(g)
 return ans

def apply(d,g):
 x=pd.to_numeric(d[g["feature"]],errors="coerce")
 return (x>=g["threshold"]).fillna(False) if g["op"]==">=" else (x<=g["threshold"]).fillna(False)

def evaluate(d,mask,plan):
 sm=split_masks(d);out={}
 for sp,m in sm.items():
  z=d[mask&m];out[sp]={"metrics":metrics(z,plan),"frequency":freq(z,sp)}
 return out

def dev_score(d,mask,plan,min_keep):
 sm=split_masks(d);D0=d[sm["DISCOVERY"]];C0=d[sm["CALIBRATION"]]
 D=d[sm["DISCOVERY"]&mask];C=d[sm["CALIBRATION"]&mask]
 kd=len(D)/len(D0);kc=len(C)/len(C0)
 if min(kd,kc)<min_keep or min(len(D),len(C))<250:return None
 dm=metrics(D,plan);cm=metrics(C,plan)
 if min(dm["mean"],cm["mean"])<=0 or min(dm["pf"] or 0,cm["pf"] or 0)<=1:return None
 # require improvement over base in both chronological DEV sections
 bd=metrics(D0,plan);bc=metrics(C0,plan)
 id_=dm["mean"]-bd["mean"];ic=cm["mean"]-bc["mean"]
 if min(id_,ic)<=0:return None
 return {"score":min(dm["mean"],cm["mean"])+.25*min(id_,ic)+.006*min(dm["target_first"],cm["target_first"])+.20*min(kd,kc),
 "keep_discovery":kd,"keep_calibration":kc,"discovery":dm,"calibration":cm,"improvement_discovery":id_,"improvement_calibration":ic}

def keyg(g):return f'{g["feature"]}{g["op"]}{g["threshold"]:.8g}'

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--input-dir",type=Path,required=True);ap.add_argument("--outdir",type=Path,required=True);ap.add_argument("--preflight",action="store_true")
 a=ap.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
 benign,hard=audit_errors(a.input_dir)
 if hard:raise RuntimeError(f"hard errors {hard[:20]}")
 d=load(a.input_dir);sm=split_masks(d);dev=sm["DISCOVERY"]|sm["CALIBRATION"]
 gs=gates(d,dev)
 pf={"events":len(d),"symbols":int(d.symbol.nunique()),"gates":len(gs),"benign_errors":len(benign),"hard_errors":len(hard),
 "split_counts":{k:int(v.sum()) for k,v in sm.items()}}
 if a.preflight:
  (a.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8");print(json.dumps(pf));return

 singles=[]
 for g in gs:
  m=apply(d,g)
  for p in PLANS:
   sc=dev_score(d,m,p,.70)
   if sc:singles.append({"gates":[g],"plan":p,**sc})
 singles.sort(key=lambda x:x["score"],reverse=True)
 pairs=[];seen=set()
 for i,a1 in enumerate(singles[:35]):
  for a2 in singles[i+1:35]:
   g1=a1["gates"][0];g2=a2["gates"][0]
   if g1["feature"]==g2["feature"]:continue
   kk=tuple(sorted((keyg(g1),keyg(g2))))
   if kk in seen:continue
   seen.add(kk);m=apply(d,g1)&apply(d,g2)
   for p in PLANS:
    sc=dev_score(d,m,p,.60)
    if sc:pairs.append({"gates":[g1,g2],"plan":p,**sc})
 pairs.sort(key=lambda x:x["score"],reverse=True)

 # targeted triples from top independent pairs + best single, but preserve >=55% DEV.
 triples=[]
 top_pairs=pairs[:20];top_s=singles[:15]
 seen3=set()
 for pr in top_pairs:
  used={g["feature"] for g in pr["gates"]}
  for sg in top_s:
   g3=sg["gates"][0]
   if g3["feature"] in used:continue
   gg=pr["gates"]+[g3];kk=tuple(sorted(keyg(g) for g in gg))
   if kk in seen3:continue
   seen3.add(kk);m=pd.Series(True,index=d.index)
   for g in gg:m&=apply(d,g)
   for p in PLANS:
    sc=dev_score(d,m,p,.55)
    if sc:triples.append({"gates":gg,"plan":p,**sc})
 triples.sort(key=lambda x:x["score"],reverse=True)

 pool=sorted(singles[:50]+pairs[:50]+triples[:50],key=lambda x:x["score"],reverse=True)
 champ=pool[0] if pool else None
 result=None;status="NO_DEV_STABLE_STATE_REFINEMENT"
 if champ:
  mask=pd.Series(True,index=d.index)
  for g in champ["gates"]:mask&=apply(d,g)
  result={"gate_text":[keyg(g) for g in champ["gates"]],"gates":champ["gates"],"plan":champ["plan"],
    "selection":{k:v for k,v in champ.items() if k not in ("gates","plan")},"evaluation":evaluate(d,mask,champ["plan"])}
  a26=result["evaluation"]["ALL_2026"];m=a26["metrics"];f=a26["frequency"]
  status="DEV_STABLE_STATE_REFINEMENT_HOLDOUT_EVALUATED"
  if f["signals_per_day"]>=1.5 and m["mean"]>0 and (m["pf"] or 0)>1:status="PROMISING_STATE_REFINEMENT"
  if f["signals_per_day"]>=2.0 and m["mean"]>0 and (m["pf"] or 0)>1:status="POSITIVE_2PLUS_PER_DAY_STATE_REFINEMENT"
 out={"status":status,"preflight":pf,
 "purpose":"Second-pass ER refinement focused on categorical 4H state and DEV-observed movement differences that v1 gate generator could not test.",
 "selection_lock":"All gates and combinations selected on Discovery+Calibration only; holdouts are evaluated only after lock.",
 "eligible_singles":len(singles),"eligible_pairs":len(pairs),"eligible_triples":len(triples),"champion":result,
 "top20":[{"gates":[keyg(g) for g in x["gates"]],"plan":x["plan"],"score":x["score"],"keep_discovery":x["keep_discovery"],"keep_calibration":x["keep_calibration"],"discovery":x["discovery"],"calibration":x["calibration"]} for x in pool[:20]]}
 (a.outdir/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,allow_nan=False))

if __name__=="__main__":main()
