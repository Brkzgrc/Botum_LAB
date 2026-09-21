from __future__ import annotations

import argparse, importlib.util, json, math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
MFD_PATH=HERE/"movement_family_discovery.py"
spec=importlib.util.spec_from_file_location("mfd",MFD_PATH)
mfd=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(mfd)

START=mfd.START
END=mfd.END
FETCH_START=mfd.FETCH_START
PLANS=mfd.PLANS
COST=mfd.COST_PCT
COOLDOWN_HOURS=12
FAMILIES=("CONFIRMED_REVERSAL","SECOND_WAVE","BREAKOUT_HOLD","BEAR_TRAP_CONFIRM","PULLBACK_CONTINUATION")

def add_path_features(z:pd.DataFrame)->pd.DataFrame:
    x=z.copy()
    x["ret_15m_1"]=x.close.pct_change()*100
    x["ret_15m_4"]=x.close.pct_change(4)*100
    x["ret_15m_12"]=x.close.pct_change(12)*100
    h24=x.high.shift(1).rolling(24).max()
    l24=x.low.shift(1).rolling(24).min()
    x["from_high_6h"]= (x.close/h24-1)*100
    x["from_low_6h"]= (x.close/l24-1)*100
    h48=x.high.shift(1).rolling(48).max()
    l48=x.low.shift(1).rolling(48).min()
    x["from_high_12h"]=(x.close/h48-1)*100
    x["from_low_12h"]=(x.close/l48-1)*100
    x["low4_min"]=x.low.shift(1).rolling(4).min()
    x["low8_min"]=x.low.shift(1).rolling(8).min()
    x["high4_max"]=x.high.shift(1).rolling(4).max()
    x["range_pos_6h"]=(x.close-l24)/(h24-l24).replace(0,np.nan)
    x["range_pos_12h"]=(x.close-l48)/(h48-l48).replace(0,np.nan)
    x["h1_dist_ema20"]=((x.h1_close/x.h1_ema20)-1)*100
    x["h1_dist_ema50"]=((x.h1_close/x.h1_ema50)-1)*100
    x["h4_dist_ema20"]=((x.h4_close/x.h4_ema20)-1)*100
    x["h4_dist_ema50"]=((x.h4_close/x.h4_ema50)-1)*100
    x["h4_trend_score"]=(
       (x.h4_close>x.h4_ema50).astype(int)
       +(x.h4_ema20>x.h4_ema50).astype(int)
       +(x.h4_ema20_d1>0).astype(int)
    )
    x["h1_mom_turn_score"]=(
       (x.h1_macd_hist_d1>0).astype(int)
       +(x.h1_rsi_d1>0).astype(int)
       +(x.h1_stoch_spread_d1>0).astype(int)
       +(x.h1_di_spread_d1>0).astype(int)
    )
    x["m15_mom_turn_score"]=(
       (x.macd_hist_d1>0).astype(int)
       +(x.rsi_d1>0).astype(int)
       +(x.stoch_spread_d1>0).astype(int)
       +(x.di_spread_d1>0).astype(int)
       +(x.obv_d1>0).astype(int)
    )
    return x

def candidate_rules():
    rules=[];rid=0
    # 1) Decline -> break -> higher-low/momentum confirmation.
    for dd in (-3.0,-5.0,-7.0):
      for br in (8,16):
       for h1mom in (2,3):
        rid+=1;rules.append({"id":f"CR_{rid:03d}","family":"CONFIRMED_REVERSAL",
          "dd":dd,"break_window":br,"h1mom":h1mom})
    # 2) First impulse -> meaningful pullback -> second wave trigger.
    for impulse in (2.0,3.5,5.0):
      for pb in (-1.0,-2.0,-3.0):
       for trend in (2,3):
        rid+=1;rules.append({"id":f"SW_{rid:03d}","family":"SECOND_WAVE",
          "impulse":impulse,"pullback":pb,"trend":trend})
    # 3) Breakout already happened and level holds before continuation.
    for window in (16,24,32):
      for hold in (0.3,0.7):
       for rvol in (0.8,1.2):
        rid+=1;rules.append({"id":f"BH_{rid:03d}","family":"BREAKOUT_HOLD",
          "window":window,"hold_pct":hold,"rvol":rvol})
    # 4) Sweep on prior/current candle then confirmation above local structure.
    for window in (16,32):
      for loc in (0.60,0.75):
       for mom in (2,3):
        rid+=1;rules.append({"id":f"BT_{rid:03d}","family":"BEAR_TRAP_CONFIRM",
          "window":window,"close_loc":loc,"mom":mom})
    # 5) H4 trend, H1 controlled pullback, 15M re-acceleration.
    for trend in (2,3):
      for dmax in (1.0,2.0,3.0):
       for mom in (2,3):
        rid+=1;rules.append({"id":f"PC_{rid:03d}","family":"PULLBACK_CONTINUATION",
          "trend":trend,"dist_max":dmax,"mom":mom})
    return rules

def rule_mask(z,r):
    fam=r["family"]
    if fam=="CONFIRMED_REVERSAL":
      w=r["break_window"]
      return (
        (z.dd_12h_prev<=r["dd"])
        &(z.close>z[f"prev_high_{w}"])
        &(z.hl_count4>=2)
        &(z.h1_mom_turn_score>=r["h1mom"])
        &(z.m15_mom_turn_score>=3)
        &(z.close_loc>=.55)
      ).fillna(False)
    if fam=="SECOND_WAVE":
      # Prior six-hour impulse, current pullback still above mid-range, then local break.
      impulse=z.ret_6h.shift(8)
      return (
        (impulse>=r["impulse"])
        &(z.from_high_6h<=r["pullback"])
        &(z.from_high_6h>=-6.0)
        &(z.range_pos_12h>=.45)
        &(z.h4_trend_score>=r["trend"])
        &(z.close>z.prev_high_8)
        &(z.m15_mom_turn_score>=3)
      ).fillna(False)
    if fam=="BREAKOUT_HOLD":
      w=r["window"];res=z[f"h1_prev_high_{w}"] if f"h1_prev_high_{w}" in z else z.h1_prev_high_24
      prior_above=(z.close.shift(1)>res.shift(1))|(z.close.shift(2)>res.shift(2))|(z.close.shift(3)>res.shift(3))
      held=z.low4_min >= res*(1-r["hold_pct"]/100)
      return (
        prior_above & held &(z.close>res)&(z.close>z.prev_high_8)
        &(z.rvol20>=r["rvol"])&(z.m15_mom_turn_score>=3)
      ).fillna(False)
    if fam=="BEAR_TRAP_CONFIRM":
      w=r["window"];sup=z[f"prev_low_{w}"]
      sweep_now=(z.low<sup)&(z.close>sup)
      sweep_prev=(z.low.shift(1)<sup.shift(1))&(z.close.shift(1)>sup.shift(1))
      confirm_prev=sweep_prev&(z.close>z.high.shift(1))
      return (
        (sweep_now|confirm_prev)
        &(z.close_loc>=r["close_loc"])
        &(z.m15_mom_turn_score>=r["mom"])
        &(z.h1_mom_turn_score>=2)
      ).fillna(False)
    if fam=="PULLBACK_CONTINUATION":
      near=np.minimum(z.h1_dist_ema20.abs(),z.h1_dist_ema50.abs())<=r["dist_max"]
      controlled=(z.h1_ret_3p<0)&(z.h1_ret_6p>-6)
      trigger=(z.close>z.prev_high_8)&(z.close>z.open)&(z.close_loc>=.55)
      return (
        (z.h4_trend_score>=r["trend"])&near&controlled&trigger
        &(z.m15_mom_turn_score>=r["mom"])&(z.h1_close>z.h1_ema50*.97)
      ).fillna(False)
    raise KeyError(fam)

def process_symbol(symbol,fetch_start,study_start,end):
    try:
      base=mfd.core.fetch_15m(symbol,start=fetch_start,end=end+pd.Timedelta(days=2))
      if len(base)<2000:return pd.DataFrame(),{"symbol":symbol,"error":f"too_short:{len(base)}"}
      z=add_path_features(mfd.build_symbol_frame(base,study_start,end))
      if len(z)<1000:return pd.DataFrame(),{"symbol":symbol,"error":f"study_too_short:{len(z)}"}
      matches=defaultdict(list)
      for r in candidate_rules():
        m=mfd.compress(rule_mask(z,r),z.index,COOLDOWN_HOURS)
        for t in z.index[m.to_numpy(bool)]:matches[t].append(r["id"])
      rows=[]
      for t in sorted(matches):
        oc=mfd.outcome(base,t)
        if oc is not None:rows.append({"symbol":symbol,"hash_mod":mfd.hmod(symbol),"decision_time":t,"rules":";".join(matches[t]),**oc})
      return pd.DataFrame(rows),None
    except Exception as ex:
      return pd.DataFrame(),{"symbol":symbol,"error":f"{type(ex).__name__}:{ex}"}

def shard_main(shard,shards,outdir,symbols_arg,fetch_start,study_start,end):
    syms=mfd.load_symbols()
    if symbols_arg:
      wanted={x.strip().upper() for x in symbols_arg.split(",") if x.strip()};syms=[s for s in syms if s in wanted]
    mine=[s for i,s in enumerate(syms) if i%shards==shard]
    outdir.mkdir(parents=True,exist_ok=True);frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=2) as ex:
      futs={ex.submit(process_symbol,s,fetch_start,study_start,end):s for s in mine}
      for k,f in enumerate(as_completed(futs),1):
        x,e=f.result()
        if e:
          errs.append(e);print("[SYMBOL_ERROR] "+json.dumps(e),flush=True)
        if x is not None and len(x):frames.append(x)
        if k%3==0 or k==len(futs):print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(q) for q in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"events.csv",index=False);pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    meta={"shard":shard,"shards":shards,"symbols":len(mine),"events":int(len(out)),"errors":len(errs)}
    (outdir/"meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta),flush=True)

def split_masks(d):return mfd.split_masks(d)

def eval_rule(q):
    sm=split_masks(q);out={}
    for sp,m in sm.items():
      z=q[m];out[sp]={"metrics":mfd.metrics(z),"frequency":mfd.frequency(z,mfd.period_days(sp))}
    return out

def plan_score(rec,plan):
    D=rec["DISCOVERY"];C=rec["CALIBRATION"]
    if min(D["metrics"].get("n",0),C["metrics"].get("n",0))<80:return None
    dm=D["metrics"].get(plan,{});cm=C["metrics"].get(plan,{})
    if min(dm.get("mean",-999),cm.get("mean",-999))<=0:return None
    if min(dm.get("pf",0) or 0,cm.get("pf",0) or 0)<=1:return None
    if min(dm.get("target_first",0),cm.get("target_first",0))<45:return None
    freq=min(D["frequency"].get("signals_per_day",0),C["frequency"].get("signals_per_day",0))
    if freq<.10:return None
    return min(dm["mean"],cm["mean"])+.02*min(dm["target_first"],cm["target_first"])+.20*min(freq,1.5)

def benign_errors(indir):
    hard=[];benign=[]
    for p in indir.rglob("errors.csv"):
      try:e=pd.read_csv(p)
      except pd.errors.EmptyDataError:continue
      for _,r in e.iterrows():
        rec={"symbol":str(r.get("symbol","")),"error":str(r.get("error",""))}
        if rec["error"].startswith(("too_short:","study_too_short:")):benign.append(rec)
        else:hard.append(rec)
    return benign,hard

def aggregate_main(indir,outdir):
    metas=[json.loads(p.read_text()) for p in indir.rglob("meta.json")]
    if len(metas)!=64 or {int(x["shard"]) for x in metas}!=set(range(64)):raise RuntimeError("incomplete shard set")
    if sum(int(x["symbols"]) for x in metas)<400:raise RuntimeError("small universe")
    benign,hard=benign_errors(indir)
    if hard:raise RuntimeError(f"hard errors: {hard[:10]}")
    frames=[]
    for p in indir.rglob("events.csv"):
      try:q=pd.read_csv(p,low_memory=False)
      except pd.errors.EmptyDataError:continue
      if len(q):frames.append(q)
    if not frames:raise RuntimeError("no events")
    d=pd.concat(frames,ignore_index=True)
    d.decision_time=pd.to_datetime(d.decision_time,utc=True)
    d=d.drop_duplicates(["symbol","decision_time"]).sort_values(["decision_time","symbol"]).reset_index(drop=True)
    defs={r["id"]:r for r in candidate_rules()}
    long=d.assign(rule_id=d.rules.str.split(";")).explode("rule_id",ignore_index=True)
    evals=[];champions={}
    for rid,r in defs.items():
      q=long[long.rule_id==rid].copy();rec=eval_rule(q)
      evals.append({"rule":r,"splits":rec})
    for fam in FAMILIES:
      cand=[]
      for e in evals:
        if e["rule"]["family"]!=fam:continue
        for p in PLANS:
          sc=plan_score(e["splits"],p)
          if sc is not None:cand.append((sc,p,e))
      if cand:
        cand.sort(key=lambda x:x[0],reverse=True);sc,p,e=cand[0]
        champions[fam]={"score":float(sc),"plan":p,"rule":e["rule"],**e["splits"]}
    ids={v["rule"]["id"] for v in champions.values()}
    selected=d[d.rules.apply(lambda s:any(x in ids for x in str(s).split(";")))].copy()
    selected=mfd.dedupe_combined(selected,12) if len(selected) else selected
    combined=eval_rule(selected) if len(selected) else {}
    status="NO_STABLE_INDEPENDENT_PRICE_FAMILIES"
    if champions:
      status="DEV_STABLE_FAMILIES_HOLDOUT_EVALUATED"
      a=combined.get("ALL_2026",{})
      if a.get("frequency",{}).get("signals_per_day",0)>=2:
        best=max((a.get("metrics",{}).get(p,{}).get("mean",-999) for p in PLANS),default=-999)
        if best>0:status="OOS_POSITIVE_2PLUS_PER_DAY"
    summary={"status":status,"candidate_rules":len(defs),"events":len(d),"symbols":int(d.symbol.nunique()),
      "benign_short_history_exclusions":benign,"champions":champions,"combined":combined,
      "selection_lock":"Rule and plan selection use Discovery+Calibration only; holdouts are diagnostics.",
      "families":list(FAMILIES)}
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,allow_nan=False))

def self_test():
    assert len(candidate_rules())==62, len(candidate_rules())
    idx=pd.date_range("2026-01-01",periods=200,freq="15min",tz="UTC")
    z=pd.DataFrame(index=idx)
    print(json.dumps({"self_test":"ok","rules":len(candidate_rules())}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard",type=int);ap.add_argument("--shards",type=int,default=64)
    ap.add_argument("--outdir",type=Path,required=True);ap.add_argument("--aggregate-dir",type=Path);ap.add_argument("--symbols")
    ap.add_argument("--fetch-start");ap.add_argument("--study-start");ap.add_argument("--end");ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return
    if a.aggregate_dir:aggregate_main(a.aggregate_dir,a.outdir);return
    if a.shard is None:raise SystemExit("--shard required")
    fs=pd.Timestamp(a.fetch_start,tz="UTC") if a.fetch_start else FETCH_START
    ss=pd.Timestamp(a.study_start,tz="UTC") if a.study_start else START
    ee=pd.Timestamp(a.end,tz="UTC") if a.end else END
    shard_main(a.shard,a.shards,a.outdir,a.symbols,fs,ss,ee)

if __name__=="__main__":main()
