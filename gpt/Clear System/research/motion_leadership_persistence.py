from __future__ import annotations

"""Clear System movement-leadership persistence study.

This is not a dip/reclaim or BTC-shock recovery setup.  It tests whether a
coin that has already persistently outperformed BTC during a neutral-to-up
market regime can accept above its own short-term value area, then continue
from a fresh 15M expansion.  All inputs are closed candles; selection uses
Discovery + Calibration only.
"""
import argparse, importlib.util, json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("price",HERE/"independent_price_families_v2.py")
price=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(price)
mfd=price.mfd
FETCH_START,START,END=mfd.FETCH_START,mfd.START,mfd.END
PLANS,COST=mfd.PLANS,mfd.COST_PCT
FAMILY="MOTION_LEADERSHIP_PERSISTENCE"; COOLDOWN_HOURS=12

def candidate_rules():
    out=[]; i=0
    for lead in (1.5,3.0,5.0):
      for persistence in (4,8,12):
       for mom in (2,3):
        i+=1; out.append({"id":f"RSP_{i:03d}","family":FAMILY,"lead":lead,"persistence":persistence,"mom":mom})
    return out

def btc_context(fs,ss,ee):
    b=mfd.core.fetch_15m("BTCUSDT",start=fs,end=ee+pd.Timedelta(days=2))
    h=mfd.enrich(mfd.resample(b,"1h")); h["ret8h"]=h.close.pct_change(8)*100
    h["ema8"]=h.close.ewm(span=8,adjust=False).mean()
    # Decision timestamps only see the already closed 1H candle.
    h.index=h.index+pd.Timedelta(hours=1)
    return h[["close","ret8h","ema8"]].rename(columns=lambda c:"btc_"+c)

def add_features(base,z,btc):
    x=price.add_path_features(z)
    x=x.join(btc.reindex(x.index,method="ffill"))
    x["coin_ret8h"]=x.close.pct_change(32)*100
    x["rel8h"]=x.coin_ret8h-x.btc_ret8h
    x["rel_pos"]=x.rel8h>0
    x["btc_permission"]=(x.btc_close>=x.btc_ema8)&(x.btc_ret8h>=-1.0)
    x["value_high_16"]=x.high.shift(1).rolling(16).max()
    x["value_mean_16"]=x.close.shift(1).rolling(16).mean()
    return x

def old_events(z):
    o=pd.Series(False,index=z.index)
    for r in price.candidate_rules(): o|=price.rule_mask(z,r)
    return o.fillna(False)

def mask(z,r,old):
    # Persistence is measured *before* the trigger candle, preventing a
    # single sudden relative-price jump from manufacturing the signal.
    lead=z.rel8h.shift(1)>=r["lead"]
    persistence=z.rel_pos.shift(1).rolling(r["persistence"],min_periods=r["persistence"]).sum()>=r["persistence"]
    accepted=(z.close.shift(1)>=z.value_mean_16.shift(1))
    trigger=(z.close>z.value_high_16)&(z.close_loc>=.65)&(z.mom_score>=r["mom"])
    return (lead&persistence&accepted&z.btc_permission&trigger&~old).fillna(False)

def process(symbol,btc,fs,ss,ee):
  try:
    base=mfd.core.fetch_15m(symbol,start=fs,end=ee+pd.Timedelta(days=2))
    if len(base)<2000:return pd.DataFrame(),{"symbol":symbol,"error":f"too_short:{len(base)}"}
    z=add_features(base,mfd.build_symbol_frame(base,ss,ee),btc); old=old_events(z); hits=defaultdict(list)
    for r in candidate_rules():
      q=mfd.compress(mask(z,r,old),z.index,COOLDOWN_HOURS)
      for t in z.index[q.to_numpy(bool)]:hits[t].append(r["id"])
    rows=[]
    for t in sorted(hits):
      oc=mfd.outcome(base,t)
      if oc is not None: rows.append({"symbol":symbol,"hash_mod":mfd.hmod(symbol),"decision_time":t,"rules":";".join(hits[t]),**oc})
    return pd.DataFrame(rows),None
  except Exception as ex:return pd.DataFrame(),{"symbol":symbol,"error":f"{type(ex).__name__}:{ex}"}

def shard_main(shard,shards,outdir,symbols,fs,ss,ee):
  syms=mfd.load_symbols();
  if symbols: wanted={x.strip().upper() for x in symbols.split(",")}; syms=[s for s in syms if s in wanted]
  mine=[s for i,s in enumerate(syms) if i%shards==shard]; btc=btc_context(fs,ss,ee); outdir.mkdir(parents=True,exist_ok=True); frames=[]; errs=[]
  with ThreadPoolExecutor(max_workers=2) as ex:
    fut={ex.submit(process,s,btc,fs,ss,ee):s for s in mine}
    for n,f in enumerate(as_completed(fut),1):
      q,e=f.result(); frames.extend([q] if len(q) else []); errs.extend([e] if e else [])
      if n%3==0 or n==len(fut):print(f"[SHARD {shard}] {n}/{len(fut)} events={sum(map(len,frames))} errors={len(errs)}",flush=True)
  out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(); out.to_csv(outdir/"events.csv",index=False); pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
  (outdir/"meta.json").write_text(json.dumps({"shard":shard,"shards":shards,"symbols":len(mine),"events":len(out),"errors":len(errs)},indent=2))

def evaluate(q):
  return {k:{"metrics":mfd.metrics(q[v]),"frequency":mfd.frequency(q[v],mfd.period_days(k))} for k,v in mfd.split_masks(q).items()}
def score(rec,plan):
  d,c=rec["DISCOVERY"],rec["CALIBRATION"]; a,b=d["metrics"].get(plan,{}),c["metrics"].get(plan,{})
  if min(a.get("n",0),b.get("n",0))<80 or min(a.get("mean",-99),b.get("mean",-99))<=0 or min(a.get("pf",0) or 0,b.get("pf",0) or 0)<=1:return None
  if min(a.get("target_first",0),b.get("target_first",0))<45:return None
  f=min(d["frequency"].get("signals_per_day",0),c["frequency"].get("signals_per_day",0)); return None if f<.10 else min(a["mean"],b["mean"])+.02*min(a["target_first"],b["target_first"])+.2*min(f,1.5)
def aggregate(indir,outdir):
  metas=[json.loads(p.read_text()) for p in indir.rglob("meta.json")]
  if len(metas)!=64 or {int(x["shard"]) for x in metas}!=set(range(64)):raise RuntimeError("incomplete shards")
  fs=[]
  for p in indir.rglob("events.csv"):
    try:q=pd.read_csv(p,low_memory=False); fs.extend([q] if len(q) else [])
    except pd.errors.EmptyDataError:pass
  d=pd.concat(fs,ignore_index=True) if fs else pd.DataFrame()
  if not len(d):raise RuntimeError("no events")
  d.decision_time=pd.to_datetime(d.decision_time,utc=True); d=d.drop_duplicates(["symbol","decision_time"]); long=d.assign(rule_id=d.rules.str.split(";")).explode("rule_id")
  best=[]
  for r in candidate_rules():
    rec=evaluate(long[long.rule_id==r["id"]].copy())
    for p in PLANS:
      s=score(rec,p)
      if s is not None:best.append((s,p,r,rec))
  champs={}
  if best:
    s,p,r,rec=max(best,key=lambda x:x[0]); champs[FAMILY]={"score":float(s),"plan":p,"rule":r,**rec}
  ids={x["rule"]["id"] for x in champs.values()}; selected=d[d.rules.apply(lambda x:any(i in str(x).split(";") for i in ids))]
  summary={"status":"NO_STABLE_MOTION_LEADERSHIP_PERSISTENCE" if not champs else "DEV_CHAMPION_HOLDOUT_DIAGNOSTIC","candidate_rules":len(candidate_rules()),"events":len(d),"symbols":int(d.symbol.nunique()),"champions":champs,"combined":evaluate(selected) if len(selected) else {},"overlap_guard":"Events overlapping any Price Families v2 rule are excluded.","selection_lock":"Selection uses Discovery+Calibration only; holdout is diagnostic."}
  outdir.mkdir(parents=True,exist_ok=True);(outdir/"summary.json").write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf-8")
def self_test():
  assert len(candidate_rules())==18; print(json.dumps({"self_test":"ok","rules":18}))
def main():
  a=argparse.ArgumentParser(); a.add_argument("--shard",type=int);a.add_argument("--shards",type=int,default=64);a.add_argument("--outdir",type=Path,required=True);a.add_argument("--aggregate-dir",type=Path);a.add_argument("--symbols");a.add_argument("--fetch-start");a.add_argument("--study-start");a.add_argument("--end");a.add_argument("--self-test",action="store_true");z=a.parse_args()
  if z.self_test:self_test();return
  if z.aggregate_dir:aggregate(z.aggregate_dir,z.outdir);return
  if z.shard is None:raise SystemExit("--shard required")
  fs=pd.Timestamp(z.fetch_start,tz="UTC") if z.fetch_start else FETCH_START;ss=pd.Timestamp(z.study_start,tz="UTC") if z.study_start else START;ee=pd.Timestamp(z.end,tz="UTC") if z.end else END; shard_main(z.shard,z.shards,z.outdir,z.symbols,fs,ss,ee)
if __name__=="__main__":main()
