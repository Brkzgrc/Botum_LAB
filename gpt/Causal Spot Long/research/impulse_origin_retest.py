from __future__ import annotations

"""Causal impulse-origin retest discovery, isolated from frozen r2.

An impulse is a *closed 1H* break above a prior 16H high.  Its origin zone is
the latest bearish 1H candle before the break.  A later 15M signal is allowed
only after price revisits that exact origin zone without a 1H close below it,
then reclaims the zone and breaks local 15M structure.  Existing independent
price-family events are explicitly excluded, so this is not a renamed
breakout/pullback test.
"""

import argparse
import importlib.util
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRICE_PATH = HERE / "independent_price_families_v2.py"
spec = importlib.util.spec_from_file_location("price_v2", PRICE_PATH)
price = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(price)
mfd = price.mfd

FETCH_START, START, END = mfd.FETCH_START, mfd.START, mfd.END
PLANS, COST = mfd.PLANS, mfd.COST_PCT
COOLDOWN_HOURS = 12
FAMILY = "IMPULSE_ORIGIN_RETEST"


def candidate_rules():
    rules=[]; rid=0
    for impulse_ret in (2.0, 3.5, 5.0):
        for origin_lookback in (3, 6, 9):
            for max_age_h in (12, 24):
                rid += 1
                rules.append({"id":f"IOR_{rid:03d}", "family":FAMILY,
                    "impulse_ret":impulse_ret, "origin_lookback":origin_lookback,
                    "max_age_h":max_age_h})
    return rules


def _latest_bearish_origin(h1: pd.DataFrame, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    bear = (h1.close < h1.open).to_numpy(bool)
    pos = np.arange(len(h1))
    last = pd.Series(np.where(bear, pos, np.nan), index=h1.index).ffill().to_numpy()
    age = pos - np.nan_to_num(last, nan=-10**9)
    ok = np.isfinite(last) & (age >= 1) & (age <= lookback)
    low = np.full(len(h1), np.nan); high = np.full(len(h1), np.nan)
    ii = last[ok].astype(int)
    low[ok] = np.minimum(h1.open.to_numpy(float)[ii], h1.close.to_numpy(float)[ii])
    high[ok] = np.maximum(h1.open.to_numpy(float)[ii], h1.close.to_numpy(float)[ii])
    return low, high


def add_origin_features(base: pd.DataFrame, z: pd.DataFrame) -> pd.DataFrame:
    h1 = mfd.enrich(mfd.resample(base, "1h"))
    h1["prior_high_16"] = h1.high.shift(1).rolling(16).max()
    h1["ret_3h"] = h1.close.pct_change(3) * 100
    close_delay = pd.Timedelta(hours=1)
    for lookback in (3, 6, 9):
        origin_low, origin_high = _latest_bearish_origin(h1, lookback)
        for impulse_ret in (2.0, 3.5, 5.0):
            impulse = (h1.close > h1.prior_high_16) & (h1.ret_3h >= impulse_ret)
            p = np.arange(len(h1)); last = pd.Series(np.where(impulse, p, np.nan), index=h1.index).ffill().to_numpy()
            age = p - np.nan_to_num(last, nan=-10**9)
            valid = np.isfinite(last)
            lo = np.full(len(h1), np.nan); hi=np.full(len(h1), np.nan)
            ii=last[valid].astype(int); lo[valid]=origin_low[ii]; hi[valid]=origin_high[ii]
            tag=f"ior_{int(impulse_ret*10)}_{lookback}"
            q=pd.DataFrame({f"{tag}_origin_low":lo, f"{tag}_origin_high":hi,
                            f"{tag}_age_h":age},index=h1.index)
            q.index=q.index+close_delay
            z=z.join(q.reindex(z.index,method="ffill"))
    return z


def old_price_event(z: pd.DataFrame) -> pd.Series:
    out=pd.Series(False,index=z.index)
    for r in price.candidate_rules(): out |= price.rule_mask(z,r)
    return out.fillna(False)


def rule_mask(z: pd.DataFrame, r: dict, old: pd.Series) -> pd.Series:
    tag=f"ior_{int(r['impulse_ret']*10)}_{r['origin_lookback']}"
    lo=z[f"{tag}_origin_low"]; hi=z[f"{tag}_origin_high"]; age=z[f"{tag}_age_h"]
    # Origin-zone retest must have occurred recently; signal confirms reclaim.
    touched=(z.low<=hi) & (z.high>=lo)
    retained=z.h1_close>=lo
    reclaim=(z.close>hi) & (z.close>z.prev_high_8) & (z.close_loc>=.60)
    retest_recent=touched.shift(1).rolling(8,min_periods=1).max().astype(bool)
    return ((age>=1)&(age<=r["max_age_h"])&retest_recent&retained&reclaim
            &(z.mom_score>=2)&(~old)).fillna(False)


def process_symbol(symbol, fetch_start, study_start, end):
    try:
        base=mfd.core.fetch_15m(symbol,start=fetch_start,end=end+pd.Timedelta(days=2))
        if len(base)<2000:return pd.DataFrame(),{"symbol":symbol,"error":f"too_short:{len(base)}"}
        z=price.add_path_features(mfd.build_symbol_frame(base,study_start,end))
        z=add_origin_features(base,z)
        if len(z)<1000:return pd.DataFrame(),{"symbol":symbol,"error":f"study_too_short:{len(z)}"}
        old=old_price_event(z); matches=defaultdict(list)
        for r in candidate_rules():
            m=mfd.compress(rule_mask(z,r,old),z.index,COOLDOWN_HOURS)
            for t in z.index[m.to_numpy(bool)]:matches[t].append(r["id"])
        rows=[]
        for t in sorted(matches):
            oc=mfd.outcome(base,t)
            if oc is not None:rows.append({"symbol":symbol,"hash_mod":mfd.hmod(symbol),"decision_time":t,
                "rules":";".join(matches[t]),**oc})
        return pd.DataFrame(rows),None
    except Exception as ex:return pd.DataFrame(),{"symbol":symbol,"error":f"{type(ex).__name__}:{ex}"}


def shard_main(shard, shards, outdir, symbols_arg, fetch_start, study_start, end):
    syms=mfd.load_symbols()
    if symbols_arg:
        wanted={x.strip().upper() for x in symbols_arg.split(",") if x.strip()};syms=[s for s in syms if s in wanted]
    mine=[s for i,s in enumerate(syms) if i%shards==shard];outdir.mkdir(parents=True,exist_ok=True);frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=2) as ex:
        fs={ex.submit(process_symbol,s,fetch_start,study_start,end):s for s in mine}
        for k,f in enumerate(as_completed(fs),1):
            q,e=f.result()
            if e:errs.append(e);print("[SYMBOL_ERROR] "+json.dumps(e),flush=True)
            if len(q):frames.append(q)
            if k%3==0 or k==len(fs):print(f"[SHARD {shard}] {k}/{len(fs)} events={sum(map(len,frames))} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame();out.to_csv(outdir/"events.csv",index=False);pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"shards":shards,"symbols":len(mine),"events":len(out),"errors":len(errs)},indent=2))


def eval_rule(q):
    out={}
    for split,mask in mfd.split_masks(q).items():
        x=q[mask];out[split]={"metrics":mfd.metrics(x),"frequency":mfd.frequency(x,mfd.period_days(split))}
    return out


def plan_score(rec, plan):
    d,c=rec["DISCOVERY"],rec["CALIBRATION"]
    if min(d["metrics"].get("n",0),c["metrics"].get("n",0))<80:return None
    a,b=d["metrics"].get(plan,{}),c["metrics"].get(plan,{})
    if min(a.get("mean",-999),b.get("mean",-999))<=0 or min(a.get("pf",0) or 0,b.get("pf",0) or 0)<=1:return None
    if min(a.get("target_first",0),b.get("target_first",0))<45:return None
    freq=min(d["frequency"].get("signals_per_day",0),c["frequency"].get("signals_per_day",0))
    return None if freq<.10 else min(a["mean"],b["mean"])+.02*min(a["target_first"],b["target_first"])+.20*min(freq,1.5)


def aggregate_main(indir,outdir):
    metas=[json.loads(p.read_text()) for p in indir.rglob("meta.json")]
    if len(metas)!=64 or {int(x["shard"]) for x in metas}!=set(range(64)):raise RuntimeError("incomplete shard set")
    if sum(int(x["symbols"]) for x in metas)<400:raise RuntimeError("small universe")
    frames=[];errors=[]
    for p in indir.rglob("events.csv"):
        try:q=pd.read_csv(p,low_memory=False)
        except pd.errors.EmptyDataError:continue
        if len(q):frames.append(q)
    for p in indir.rglob("errors.csv"):
        try:errors.extend(pd.read_csv(p).to_dict("records"))
        except pd.errors.EmptyDataError:pass
    hard=[x for x in errors if not str(x.get("error","")).startswith(("too_short:","study_too_short:"))]
    if hard:raise RuntimeError(f"hard errors: {hard[:10]}")
    d=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    if not len(d):raise RuntimeError("no events")
    d.decision_time=pd.to_datetime(d.decision_time,utc=True);d=d.drop_duplicates(["symbol","decision_time"])
    long=d.assign(rule_id=d.rules.str.split(";")).explode("rule_id",ignore_index=True);defs={x["id"]:x for x in candidate_rules()};best=[]
    for rid,r in defs.items():
        rec=eval_rule(long[long.rule_id==rid].copy())
        for plan in PLANS:
            score=plan_score(rec,plan)
            if score is not None:best.append((score,plan,r,rec))
    champions={}
    if best:
        score,plan,rule,rec=max(best,key=lambda x:x[0]);champions[FAMILY]={"score":float(score),"plan":plan,"rule":rule,**rec}
    ids={x["rule"]["id"] for x in champions.values()};selected=d[d.rules.apply(lambda s:any(x in ids for x in str(s).split(";")))].copy()
    selected=mfd.dedupe_combined(selected,12) if len(selected) else selected;combined=eval_rule(selected) if len(selected) else {}
    status="NO_STABLE_CAUSAL_IMPULSE_ORIGIN_RETEST"
    summary={"status":status,"candidate_rules":len(defs),"events":len(d),"symbols":int(d.symbol.nunique()),"champions":champions,"combined":combined,
      "overlap_guard":"Events coinciding with any Independent Price Families v2 rule are excluded before scoring.",
      "selection_lock":"Rule and plan selection use Discovery+Calibration only; holdouts are diagnostics."}
    outdir.mkdir(parents=True,exist_ok=True);(outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")


def self_test():
    assert len(candidate_rules())==18
    idx=pd.date_range("2025-01-01",periods=2400,freq="15min",tz="UTC")
    wave=np.linspace(100,130,len(idx))+2*np.sin(np.arange(len(idx))/9)
    base=pd.DataFrame({"open":wave-.1,"high":wave+.5,"low":wave-.6,"close":wave,
                       "volume":np.full(len(idx),100.0),"quote_volume":np.full(len(idx),10000.0)},index=idx)
    z=price.add_path_features(mfd.build_symbol_frame(base,idx[500],idx[-1]))
    z=add_origin_features(base,z)
    required={"ior_20_3_origin_low","ior_35_6_origin_high","ior_50_9_age_h"}
    assert not(required-set(z.columns))
    old=old_price_event(z); assert old.index.equals(z.index)
    assert rule_mask(z,candidate_rules()[0],old).index.equals(z.index)
    print(json.dumps({"self_test":"ok","rules":len(candidate_rules()),"rows":len(z)}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard",type=int);ap.add_argument("--shards",type=int,default=64);ap.add_argument("--outdir",type=Path,required=True);ap.add_argument("--aggregate-dir",type=Path);ap.add_argument("--symbols");ap.add_argument("--fetch-start");ap.add_argument("--study-start");ap.add_argument("--end");ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:self_test();return
    if a.aggregate_dir:aggregate_main(a.aggregate_dir,a.outdir);return
    if a.shard is None:raise SystemExit("--shard required")
    fs=pd.Timestamp(a.fetch_start,tz="UTC") if a.fetch_start else FETCH_START;ss=pd.Timestamp(a.study_start,tz="UTC") if a.study_start else START;ee=pd.Timestamp(a.end,tz="UTC") if a.end else END
    shard_main(a.shard,a.shards,a.outdir,a.symbols,fs,ss,ee)

if __name__=="__main__":main()
