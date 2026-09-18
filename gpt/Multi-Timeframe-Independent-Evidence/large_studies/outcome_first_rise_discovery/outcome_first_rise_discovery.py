from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
CAUSAL=PARENT/"coin_mtf_causal_validation"
AUG=PARENT/"indicator_augmentation_discovery"
sys.path.insert(0,str(CAUSAL))
sys.path.insert(0,str(AUG))
import coin_mtf_causal_validation as core  # noqa: E402
import indicator_augmentation_discovery as aug  # noqa: E402

UNIVERSE=core.UNIVERSE_PATH
FETCH_START=pd.Timestamp("2022-10-01",tz="UTC")
START=pd.Timestamp("2023-01-01",tz="UTC")
END=pd.Timestamp("2026-09-18",tz="UTC")
COST=0.20

def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def load_symbols():
    raw=json.loads(Path(UNIVERSE).read_text(encoding="utf-8"))
    if isinstance(raw,dict):
        for k in ["symbols","universe","spot_symbols"]:
            if k in raw and isinstance(raw[k],list):
                raw=raw[k]; break
    syms=[str(x) for x in raw if str(x).endswith("USDT")]
    return sorted([s for s in syms if s!="BTCUSDT"])

def align(tf,delta,idx,prefix):
    z=tf.copy()
    z.index=z.index+delta
    cols=[c for c in z.columns if c not in ["open","high","low","close","volume","quote_volume"]]
    return z[cols].rename(columns={c:f"{prefix}_{c}" for c in cols}).reindex(idx,method="ffill")

def combined_features(base,btc15):
    # user's original movement indicators + proactive extra families
    c15=core.indicators(base)
    e15=aug.extra_indicators(base)
    x15=c15.copy()
    for c in e15.columns:
        if c not in x15.columns:
            x15[c]=e15[c]

    idx=x15.index+pd.Timedelta(minutes=15)
    d15=x15.copy(); d15.index=idx
    keep=[c for c in d15.columns if c not in ["open","high","low","close","volume","quote_volume"]]
    out=d15[keep].rename(columns={c:f"m15_{c}" for c in keep})

    for rule,delta,pfx in [("1h",pd.Timedelta(hours=1),"h1"),("4h",pd.Timedelta(hours=4),"h4")]:
        b=core.resample(base,rule)
        cc=core.indicators(b); ee=aug.extra_indicators(b)
        for c in ee.columns:
            if c not in cc.columns: cc[c]=ee[c]
        out=out.join(align(cc,delta,idx,pfx))

    for rule,delta,pfx in [("1h",pd.Timedelta(hours=1),"btc1"),("4h",pd.Timedelta(hours=4),"btc4")]:
        b=core.resample(btc15,rule)
        cc=core.indicators(b); ee=aug.extra_indicators(b)
        for c in ee.columns:
            if c not in cc.columns: cc[c]=ee[c]
        out=out.join(align(cc,delta,idx,pfx))
    return out

def path_stats(base,i,ep,h):
    j=min(i+h*4,len(base)-1)
    if j<=i:return np.nan,np.nan,np.nan
    sl=base.iloc[i:j+1]
    ret=(float(base.open.iloc[j])/ep-1)*100
    mfe=(float(sl.high.max())/ep-1)*100
    mae=(float(sl.low.min())/ep-1)*100
    return ret,mfe,mae

def classify_episode(base,i,ep):
    r12,m12,a12=path_stats(base,i,ep,12)
    r24,m24,a24=path_stats(base,i,ep,24)
    r72,m72,a72=path_stats(base,i,ep,72)
    if not np.isfinite(m72): return None,{}
    labels=[]
    if m12>=3 and a12>-1.5: labels.append("IMMEDIATE_CLEAN_3PCT_12H")
    if m24>=5 and a24>-2.5: labels.append("TREND_CLEAN_5PCT_24H")
    if m72>=8 and a72>-4.0: labels.append("IMPULSE_8PCT_72H")
    if m72>=5 and (r12<=0 or a12<=-1.0) and m12<3:
        labels.append("DELAYED_RECOVERY_5PCT_72H")
    primary=None
    for x in ["IMPULSE_8PCT_72H","TREND_CLEAN_5PCT_24H","IMMEDIATE_CLEAN_3PCT_12H","DELAYED_RECOVERY_5PCT_72H"]:
        if x in labels:
            primary=x; break
    st={"ret12":r12,"mfe12":m12,"mae12":a12,"ret24":r24,"mfe24":m24,"mae24":a24,
        "ret72":r72,"mfe72":m72,"mae72":a72}
    return primary,st

def pre_path(base,i,ep):
    rec={}
    for h in [1,2,4,8,12,24,48]:
        j=i-h*4
        if j<0:
            rec[f"pre_ret_{h}h"]=np.nan;rec[f"pre_dd_from_high_{h}h"]=np.nan;rec[f"pre_bounce_from_low_{h}h"]=np.nan
            continue
        sl=base.iloc[j:i+1]
        rec[f"pre_ret_{h}h"]=(ep/float(base.open.iloc[j])-1)*100
        rec[f"pre_dd_from_high_{h}h"]=(ep/float(sl.high.max())-1)*100
        rec[f"pre_bounce_from_low_{h}h"]=(ep/float(sl.low.min())-1)*100
    return rec

def process_symbol(symbol,btc15):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=END)
        if len(base)<3000:return None,{"symbol":symbol,"error":"too_short"}
        feat=combined_features(base,btc15)
        decision_times=feat.index[(feat.index>=START)&(feat.index<END)]
        # sample every hour: decision times where minute == 0
        decision_times=decision_times[decision_times.minute==0]
        rows=[]
        last_pos=None
        neg_pool=[]
        for t in decision_times:
            et=t+pd.Timedelta(minutes=15)
            if et not in base.index:continue
            i=base.index.get_loc(et)
            if not isinstance(i,(int,np.integer)):continue
            if i+72*4>=len(base):continue
            ep=float(base.open.iloc[i])
            primary,st=classify_episode(base,i,ep)
            if primary:
                # de-duplicate overlapping rises: keep one anchor per 24h per symbol
                if last_pos is not None and t-last_pos<pd.Timedelta(hours=24):
                    continue
                last_pos=t
                rec={"symbol":symbol,"decision_time":t,"entry_time":et,"label":"RISE","archetype":primary,
                     "year":int(t.year),"hash_mod":hmod(symbol),**st,**pre_path(base,i,ep)}
                fr=feat.loc[t]
                for c,v in fr.items():
                    if pd.notna(v) and np.isscalar(v):
                        try: rec[c]=float(v)
                        except Exception: pass
                rows.append(rec)
            else:
                # strict non-rise control candidate
                _,m24,a24=path_stats(base,i,ep,24)
                _,m72,a72=path_stats(base,i,ep,72)
                if np.isfinite(m24) and np.isfinite(m72) and m24<2.0 and m72<5.0:
                    neg_pool.append((t,et,i,ep,m24,a24,m72,a72))

        pos=[r for r in rows if r["label"]=="RISE"]
        if not pos:
            return pd.DataFrame(),None

        # Deterministic matched controls: same symbol/year, nearest in calendar distance, not within +/-72h of any positive.
        pos_times=[r["decision_time"] for r in pos]
        used=set()
        controls=[]
        for p in pos:
            cand=[]
            for q in neg_pool:
                t=q[0]
                if t.year!=p["decision_time"].year or t in used:continue
                if min(abs((t-pt).total_seconds()) for pt in pos_times)<72*3600:continue
                cand.append((abs((t-p["decision_time"]).total_seconds()),q))
            if not cand:continue
            cand.sort(key=lambda x:x[0])
            _,q=cand[0]; used.add(q[0])
            t,et,i,ep,m24,a24,m72,a72=q
            rec={"symbol":symbol,"decision_time":t,"entry_time":et,"label":"CONTROL","archetype":"MATCHED_NON_RISE",
                 "year":int(t.year),"hash_mod":hmod(symbol),"mfe24":m24,"mae24":a24,"mfe72":m72,"mae72":a72,**pre_path(base,i,ep)}
            fr=feat.loc[t]
            for c,v in fr.items():
                if pd.notna(v) and np.isscalar(v):
                    try: rec[c]=float(v)
                    except Exception: pass
            controls.append(rec)
        return pd.DataFrame(pos+controls),None
    except Exception as ex:
        return None,{"symbol":symbol,"error":repr(ex)}

def shard_main(shard,shards,outdir):
    syms=load_symbols()
    mine=[s for i,s in enumerate(syms) if i%shards==shard]
    outdir.mkdir(parents=True,exist_ok=True)
    btc15=core.fetch_15m("BTCUSDT",start=FETCH_START,end=END)
    frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(process_symbol,s,btc15):s for s in mine}
        for k,f in enumerate(as_completed(futs),1):
            x,e=f.result()
            if e:errs.append(e)
            elif x is not None and len(x):frames.append(x)
            if k%10==0 or k==len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} rows={sum(len(x) for x in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"episodes.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"symbols":len(mine),"rows":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def effect(a,b):
    a=pd.to_numeric(a,errors="coerce").dropna();b=pd.to_numeric(b,errors="coerce").dropna()
    if len(a)<30 or len(b)<30:return None
    va=a.var(ddof=1);vb=b.var(ddof=1)
    sp=np.sqrt(((len(a)-1)*va+(len(b)-1)*vb)/max(len(a)+len(b)-2,1))
    d=(a.mean()-b.mean())/sp if sp>0 else 0.0
    return {"rise_mean":float(a.mean()),"control_mean":float(b.mean()),"rise_median":float(a.median()),
            "control_median":float(b.median()),"std_effect":float(d),"n_rise":int(len(a)),"n_control":int(len(b))}

def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("episodes.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames:raise RuntimeError("no episodes")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    outdir.mkdir(parents=True,exist_ok=True)

    meta={"symbol","decision_time","entry_time","label","archetype","year","hash_mod"}
    outcomes={"ret12","mfe12","mae12","ret24","mfe24","mae24","ret72","mfe72","mae72"}
    feats=[c for c in d.columns if c not in meta|outcomes and pd.api.types.is_numeric_dtype(d[c])]
    feats=[c for c in feats if d[c].notna().sum()>=300]

    splits={
      "DISCOVERY":(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC")),
      "CALIBRATION":(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC")),
      "CROSS_HOLDOUT_PRE2026":(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC")),
      "FINAL_HOLDOUT_2026":(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC")),
    }

    tables={}
    stable=[]
    for name,mask in splits.items():
        z=d[mask]
        rise=z[z.label=="RISE"]; ctl=z[z.label=="CONTROL"]
        rows=[]
        for c in feats:
            e=effect(rise[c],ctl[c])
            if e is not None: rows.append({"feature":c,**e})
        t=pd.DataFrame(rows)
        if len(t): t=t.sort_values("std_effect",key=lambda s:s.abs(),ascending=False)
        tables[name]=t
        t.to_csv(outdir/f"{name.lower()}_feature_effects.csv",index=False)

    disc=tables["DISCOVERY"].set_index("feature") if len(tables["DISCOVERY"]) else pd.DataFrame()
    cal=tables["CALIBRATION"].set_index("feature") if len(tables["CALIBRATION"]) else pd.DataFrame()
    cross=tables["CROSS_HOLDOUT_PRE2026"].set_index("feature") if len(tables["CROSS_HOLDOUT_PRE2026"]) else pd.DataFrame()
    final=tables["FINAL_HOLDOUT_2026"].set_index("feature") if len(tables["FINAL_HOLDOUT_2026"]) else pd.DataFrame()
    common=set(disc.index)&set(cal.index)&set(cross.index)&set(final.index)
    for c in common:
        vals=[float(disc.at[c,"std_effect"]),float(cal.at[c,"std_effect"]),float(cross.at[c,"std_effect"]),float(final.at[c,"std_effect"])]
        same=(all(v>0 for v in vals) or all(v<0 for v in vals))
        if same:
            stable.append({"feature":c,"disc_effect":vals[0],"cal_effect":vals[1],"cross_effect":vals[2],"final_effect":vals[3],
                           "min_abs_effect":min(abs(v) for v in vals)})
    stable=pd.DataFrame(stable).sort_values("min_abs_effect",ascending=False) if stable else pd.DataFrame()
    stable.to_csv(outdir/"stable_precursors.csv",index=False)

    arche={}
    for a,g in d[d.label=="RISE"].groupby("archetype"):
        arche[str(a)]={"n":int(len(g)),"symbols":int(g.symbol.nunique()),
                       "mfe24_mean":float(pd.to_numeric(g.mfe24,errors="coerce").mean()),
                       "mae24_mean":float(pd.to_numeric(g.mae24,errors="coerce").mean()),
                       "mfe72_mean":float(pd.to_numeric(g.mfe72,errors="coerce").mean()),
                       "mae72_mean":float(pd.to_numeric(g.mae72,errors="coerce").mean())}

    summary={
      "purpose":"Outcome-first discovery: find independent real rise episodes first, then ask what the market/indicators were doing BEFORE them, instead of starting from one hand-written signal rule.",
      "cost_reference_pct":COST,
      "causality":"rise/control labels use future only to define retrospective outcomes; every precursor feature is measured strictly at or before the decision time",
      "episode_types":["IMMEDIATE_CLEAN_3PCT_12H","TREND_CLEAN_5PCT_24H","IMPULSE_8PCT_72H","DELAYED_RECOVERY_5PCT_72H"],
      "rows":int(len(d)),"rise_events":int((d.label=="RISE").sum()),"controls":int((d.label=="CONTROL").sum()),
      "symbols":int(d.symbol.nunique()),"archetypes":arche,
      "stable_precursors_across_all_splits":stable.head(100).to_dict("records") if len(stable) else []
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Outcome-First Rise Discovery","",
           "Önce yükseliş olayları bulundu; sonra sinyal kuralı dayatmadan bu olayların öncesindeki fiyat/indikatör davranışı matched non-rise kontrollerle karşılaştırıldı.",
           "",f"Rows={len(d)} | rise={summary['rise_events']} | controls={summary['controls']} | symbols={summary['symbols']}",
           "","## Rise archetypes"]
    for k,v in arche.items():lines.append(f"- {k}: {v}")
    lines+=["","## Stable precursor features across discovery/calibration/cross-holdout/final"]
    if len(stable):
        for _,r in stable.head(30).iterrows(): lines.append(f"- {r.feature}: effects {r.disc_effect:.3f}, {r.cal_effect:.3f}, {r.cross_effect:.3f}, {r.final_effect:.3f}")
    else: lines.append("- none")
    (outdir/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard",type=int)
    ap.add_argument("--shards",type=int,default=8)
    ap.add_argument("--outdir",type=Path)
    ap.add_argument("--aggregate-dir",type=Path)
    args=ap.parse_args()
    if args.aggregate_dir:
        aggregate_main(args.aggregate_dir,args.outdir or ROOT/"output")
    else:
        if args.shard is None:raise SystemExit("--shard required")
        shard_main(args.shard,args.shards,args.outdir or ROOT/f"shard_{args.shard}")

if __name__=="__main__":
    main()
