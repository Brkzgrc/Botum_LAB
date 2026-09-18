from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
CAUSAL=PARENT/"coin_mtf_causal_validation"
sys.path.insert(0,str(CAUSAL))
import coin_mtf_causal_validation as core  # noqa: E402

EVENTS=PARENT/"coin_mtf_broad_frozen_validation"/"output"/"frozen_rule_events.csv"
FETCH_START=pd.Timestamp("2022-10-01",tz="UTC")
FETCH_END=pd.Timestamp("2026-09-18",tz="UTC")
COST=0.20

def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def true_range(x):
    pc=x.close.shift(1)
    return pd.concat([(x.high-x.low).abs(),(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)

def extra_indicators(df):
    x=df.copy()
    tr=true_range(x)
    atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    x["atr_pct"]=100*atr/x.close.replace(0,np.nan)

    up=x.high.diff(); dn=-x.low.diff()
    plus_dm=pd.Series(np.where((up>dn)&(up>0),up,0.0),index=x.index)
    minus_dm=pd.Series(np.where((dn>up)&(dn>0),dn,0.0),index=x.index)
    atr_w=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    pdi=100*plus_dm.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr_w.replace(0,np.nan)
    mdi=100*minus_dm.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr_w.replace(0,np.nan)
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    x["adx"]=dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    x["di_spread"]=pdi-mdi

    mid=x.close.rolling(20).mean(); sd=x.close.rolling(20).std(ddof=0)
    upper=mid+2*sd; lower=mid-2*sd
    x["bb_width"]=(upper-lower)/mid.replace(0,np.nan)
    x["bb_pctb"]=(x.close-lower)/(upper-lower).replace(0,np.nan)

    tp=(x.high+x.low+x.close)/3
    raw_mf=tp*x.volume
    pos=raw_mf.where(tp.diff()>0,0.0).rolling(14).sum()
    neg=raw_mf.where(tp.diff()<0,0.0).rolling(14).sum()
    mfr=pos/neg.replace(0,np.nan)
    x["mfi"]=100-100/(1+mfr)

    mf_mult=((x.close-x.low)-(x.high-x.close))/(x.high-x.low).replace(0,np.nan)
    mf_vol=mf_mult*x.volume
    x["cmf"]=mf_vol.rolling(20).sum()/x.volume.rolling(20).sum().replace(0,np.nan)

    pv=(tp*x.volume).rolling(96,min_periods=24).sum()
    vv=x.volume.rolling(96,min_periods=24).sum()
    rvwap=pv/vv.replace(0,np.nan)
    x["vwap_dist"]=100*(x.close/rvwap-1)

    x["roc4"]=100*(x.close/x.close.shift(4)-1)
    x["roc12"]=100*(x.close/x.close.shift(12)-1)
    ppo=100*(ema(x.close,12)-ema(x.close,26))/ema(x.close,26).replace(0,np.nan)
    x["ppo_hist"]=ppo-ema(ppo,9)

    mom=x.close.diff()
    a1=ema(ema(mom,25),13)
    a2=ema(ema(mom.abs(),25),13)
    x["tsi"]=100*a1/a2.replace(0,np.nan)

    d=x.close.diff()
    su=d.clip(lower=0).rolling(14).sum()
    sd=(-d.clip(upper=0)).rolling(14).sum()
    x["cmo"]=100*(su-sd)/(su+sd).replace(0,np.nan)

    hh=x.high.rolling(20).max(); ll=x.low.rolling(20).min()
    x["donch_pos"]=(x.close-ll)/(hh-ll).replace(0,np.nan)

    change=(x.close-x.close.shift(10)).abs()
    vol=x.close.diff().abs().rolling(10).sum()
    x["er10"]=change/vol.replace(0,np.nan)

    trsum=tr.rolling(14).sum()
    hh14=x.high.rolling(14).max(); ll14=x.low.rolling(14).min()
    x["chop14"]=100*np.log10(trsum/(hh14-ll14).replace(0,np.nan))/np.log10(14)

    x["rvol20"]=x.volume/x.volume.rolling(20).mean().replace(0,np.nan)

    bases=["atr_pct","adx","di_spread","bb_width","bb_pctb","mfi","cmf","vwap_dist","roc4","roc12",
           "ppo_hist","tsi","cmo","donch_pos","er10","chop14","rvol20"]
    for c in bases:
        x[c+"_d1"]=x[c].diff()
        x[c+"_d3"]=x[c].diff(3)
        x[c+"_acc"]=x[c+"_d1"]-x[c+"_d1"].shift(1)
    return x

def align_tf(feat,delta,decision_index,prefix):
    cols=[c for c in feat.columns if c not in ["open","high","low","close","volume","quote_volume"]]
    z=feat[cols].copy()
    z.index=z.index+delta
    z=z.rename(columns={c:f"{prefix}_{c}" for c in cols})
    return z.reindex(decision_index,method="ffill")

def forward_outcomes(base, entry_time):
    idx=base.index
    if entry_time not in idx: return None
    i=idx.get_loc(entry_time)
    if not isinstance(i,(int,np.integer)): return None
    ep=float(base.open.iloc[i])
    if not np.isfinite(ep) or ep<=0: return None
    rec={}
    for h in [12,24,48,72,168]:
        j=i+h*4
        if j>=len(base):
            rec[f"net_{h}h"]=np.nan; rec[f"mfe_{h}h"]=np.nan; rec[f"mae_{h}h"]=np.nan
            continue
        xp=float(base.open.iloc[j])
        rec[f"net_{h}h"]=(xp/ep-1)*100-COST
        sl=base.iloc[i:j+1]
        rec[f"mfe_{h}h"]=(float(sl.high.max())/ep-1)*100
        rec[f"mae_{h}h"]=(float(sl.low.min())/ep-1)*100
    j=min(i+72*4,len(base)-1)
    sl=base.iloc[i:j+1]
    hi=(sl.high.to_numpy(float)/ep-1)*100
    lo=(sl.low.to_numpy(float)/ep-1)*100
    u=np.flatnonzero(hi>=3.0); d=np.flatnonzero(lo<=-2.0)
    tu=(u[0]/4.0) if len(u) else np.nan
    td=(d[0]/4.0) if len(d) else np.nan
    rec["t_up3_h"]=tu; rec["t_dn2_h"]=td
    rec["up3_before_dn2"]=int(pd.notna(tu) and (pd.isna(td) or tu<td))
    rec["up3_within72"]=int(pd.notna(tu) and tu<=72)
    rec["danger_dn2_first"]=int(pd.notna(td) and (pd.isna(tu) or td<tu))
    return rec

def build_context(symbol,base,btc15):
    t15=extra_indicators(base)
    d15=t15.copy(); d15.index=d15.index+pd.Timedelta(minutes=15)
    d15=d15[~d15.index.duplicated(keep="last")]
    idx=d15.index
    h1=extra_indicators(core.resample(base,"1h"))
    h4=extra_indicators(core.resample(base,"4h"))
    out=d15.rename(columns={c:f"m15_{c}" for c in d15.columns if c not in ["open","high","low","close","volume","quote_volume"]})
    keep=[c for c in out.columns if c.startswith("m15_")]
    out=out[keep]
    out=out.join(align_tf(h1,pd.Timedelta(hours=1),idx,"h1"))
    out=out.join(align_tf(h4,pd.Timedelta(hours=4),idx,"h4"))

    b1=extra_indicators(core.resample(btc15,"1h"))
    b4=extra_indicators(core.resample(btc15,"4h"))
    out=out.join(align_tf(b1,pd.Timedelta(hours=1),idx,"btc1"))
    out=out.join(align_tf(b4,pd.Timedelta(hours=4),idx,"btc4"))
    return out

def process_symbol(symbol,ev,btc15):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=FETCH_END)
        ctx=build_context(symbol,base,btc15)
        rows=[]
        feature_cols=[c for c in ctx.columns if any(c.endswith(s) for s in ["_d1","_d3","_acc"]) or c.split("_",1)[-1] in [
            "atr_pct","adx","di_spread","bb_width","bb_pctb","mfi","cmf","vwap_dist","roc4","roc12",
            "ppo_hist","tsi","cmo","donch_pos","er10","chop14","rvol20"
        ]]
        for _,e in ev.iterrows():
            t=e.decision_time; et=e.entry_time
            if t not in ctx.index: continue
            oc=forward_outcomes(base,et)
            if oc is None: continue
            rec={"symbol":symbol,"decision_time":t,"entry_time":et,"hash_mod":hmod(symbol),"year":int(t.year)}
            row=ctx.loc[t]
            for c in feature_cols:
                v=row.get(c,np.nan)
                rec[c]=float(v) if pd.notna(v) and np.isscalar(v) else np.nan
            rec.update(oc)
            rows.append(rec)
        return pd.DataFrame(rows),None
    except Exception as ex:
        return None,{"symbol":symbol,"error":repr(ex)}

def shard_main(shard,shards,outdir):
    d=pd.read_csv(EVENTS,low_memory=False)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    syms=sorted(d.symbol.astype(str).unique())
    mine=[s for i,s in enumerate(syms) if i%shards==shard]
    outdir.mkdir(parents=True,exist_ok=True)
    btc15=core.fetch_15m("BTCUSDT",start=FETCH_START,end=FETCH_END)
    frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={}
        for s in mine:
            ev=d[d.symbol.astype(str)==s].copy()
            futs[ex.submit(process_symbol,s,ev,btc15)]=s
        for k,f in enumerate(as_completed(futs),1):
            x,e=f.result()
            if e: errs.append(e)
            elif x is not None and len(x): frames.append(x)
            if k%10==0 or k==len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"features.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"symbols":len(mine),"events":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def metrics(d):
    if len(d)==0:return {"n":0}
    return {
        "n":int(len(d)),"symbols":int(d.symbol.nunique()),
        "net12":float(d.net_12h.mean()),"net24":float(d.net_24h.mean()),"net72":float(d.net_72h.mean()),
        "win12":float((d.net_12h>0).mean()*100),"win24":float((d.net_24h>0).mean()*100),"win72":float((d.net_72h>0).mean()*100),
        "up3_before_dn2":float(d.up3_before_dn2.mean()*100),"up3_72":float(d.up3_within72.mean()*100),
        "danger_dn2_first":float(d.danger_dn2_first.mean()*100),
        "mfe72":float(d.mfe_72h.mean()),"mae72":float(d.mae_72h.mean())
    }

def family_of(feature):
    s=feature.lower()
    for fam in ["adx","di_spread","atr","bb_","mfi","cmf","vwap","roc","ppo","tsi","cmo","donch","er10","chop","rvol"]:
        if fam in s:return fam
    return "other"

def eval_filter(d,mask):
    return metrics(d[mask.fillna(False)])

def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames: raise RuntimeError("no features")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d=d.dropna(subset=["net_12h","net_24h","net_72h"])
    outdir.mkdir(parents=True,exist_ok=True)

    discovery=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    calibration=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    final=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))
    cross_holdout=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))

    meta={"symbol","decision_time","entry_time","hash_mod","year"}
    outcome_prefix=("net_","mfe_","mae_","t_","up3_","danger_")
    feats=[c for c in d.columns if c not in meta and not c.startswith(outcome_prefix)]
    # Remove near-empty / near-constant features.
    feats=[c for c in feats if d.loc[discovery,c].notna().sum()>=500 and d.loc[discovery,c].nunique(dropna=True)>=20]

    base_disc=metrics(d[discovery]); base_cal=metrics(d[calibration]); base_final=metrics(d[final]); base_cross=metrics(d[cross_holdout])

    rows=[]
    masks={}
    qset=[.20,.30,.40,.50,.60,.70,.80]
    for c in feats:
        s=pd.to_numeric(d.loc[discovery,c],errors="coerce")
        for q in qset:
            th=float(s.quantile(q))
            for side in ["GE","LE"]:
                name=f"{c} {side} Q{int(q*100)}({th:.6g})"
                m=(pd.to_numeric(d[c],errors="coerce")>=th) if side=="GE" else (pd.to_numeric(d[c],errors="coerce")<=th)
                md=metrics(d[discovery&m]); mc=metrics(d[calibration&m])
                if md.get("n",0)<180 or mc.get("n",0)<100: continue
                frac_d=md["n"]/base_disc["n"]; frac_c=mc["n"]/base_cal["n"]
                if not (0.10<=frac_d<=0.85 and 0.10<=frac_c<=0.85): continue
                imp_d={
                    "net24":md["net24"]-base_disc["net24"],"net72":md["net72"]-base_disc["net72"],
                    "success":md["up3_before_dn2"]-base_disc["up3_before_dn2"],
                    "danger":base_disc["danger_dn2_first"]-md["danger_dn2_first"]
                }
                imp_c={
                    "net24":mc["net24"]-base_cal["net24"],"net72":mc["net72"]-base_cal["net72"],
                    "success":mc["up3_before_dn2"]-base_cal["up3_before_dn2"],
                    "danger":base_cal["danger_dn2_first"]-mc["danger_dn2_first"]
                }
                stable=min(imp_d["net24"],imp_c["net24"])+min(imp_d["net72"],imp_c["net72"])+0.03*min(imp_d["success"],imp_c["success"])+0.02*min(imp_d["danger"],imp_c["danger"])
                rows.append({"name":name,"feature":c,"family":family_of(c),"side":side,"q":q,"threshold":th,
                             "disc_n":md["n"],"cal_n":mc["n"],"disc_net24_imp":imp_d["net24"],"cal_net24_imp":imp_c["net24"],
                             "disc_net72_imp":imp_d["net72"],"cal_net72_imp":imp_c["net72"],
                             "disc_success_imp":imp_d["success"],"cal_success_imp":imp_c["success"],
                             "disc_danger_imp":imp_d["danger"],"cal_danger_imp":imp_c["danger"],"score":stable})
                masks[name]=m

    tab=pd.DataFrame(rows).sort_values("score",ascending=False)
    tab.to_csv(outdir/"single_filters.csv",index=False)

    # Top stable singles, one representative per family/timeframe direction, then pairs across different families.
    stable=tab[(tab.disc_net24_imp>0)&(tab.cal_net24_imp>0)&(tab.disc_net72_imp>0)&(tab.cal_net72_imp>0)]
    top=stable.head(40).copy()
    pair_rows=[]; pair_masks={}
    for _,a in top.iterrows():
        for _,b in top.iterrows():
            if a["name"]>=b["name"]: continue
            if a["family"]==b["family"]: continue
            m=masks[a["name"]]&masks[b["name"]]
            md=metrics(d[discovery&m]); mc=metrics(d[calibration&m])
            if md.get("n",0)<140 or mc.get("n",0)<80: continue
            impd24=md["net24"]-base_disc["net24"]; impc24=mc["net24"]-base_cal["net24"]
            impd72=md["net72"]-base_disc["net72"]; impc72=mc["net72"]-base_cal["net72"]
            succd=md["up3_before_dn2"]-base_disc["up3_before_dn2"]; succc=mc["up3_before_dn2"]-base_cal["up3_before_dn2"]
            dangd=base_disc["danger_dn2_first"]-md["danger_dn2_first"]; dangc=base_cal["danger_dn2_first"]-mc["danger_dn2_first"]
            score=min(impd24,impc24)+min(impd72,impc72)+0.03*min(succd,succc)+0.02*min(dangd,dangc)
            nm=a["name"]+" & "+b["name"]
            pair_rows.append({"name":nm,"a":a["name"],"b":b["name"],"family_a":a["family"],"family_b":b["family"],
                              "disc_n":md["n"],"cal_n":mc["n"],"disc_net24_imp":impd24,"cal_net24_imp":impc24,
                              "disc_net72_imp":impd72,"cal_net72_imp":impc72,"disc_success_imp":succd,"cal_success_imp":succc,
                              "disc_danger_imp":dangd,"cal_danger_imp":dangc,"score":score})
            pair_masks[nm]=m
    pairs=pd.DataFrame(pair_rows).sort_values("score",ascending=False) if pair_rows else pd.DataFrame()
    pairs.to_csv(outdir/"pair_filters.csv",index=False)

    candidates=[]
    for _,r in stable.head(15).iterrows(): candidates.append(("single",r["name"],masks[r["name"]]))
    if len(pairs):
        pstable=pairs[(pairs.disc_net24_imp>0)&(pairs.cal_net24_imp>0)&(pairs.disc_net72_imp>0)&(pairs.cal_net72_imp>0)]
        for _,r in pstable.head(15).iterrows(): candidates.append(("pair",r["name"],pair_masks[r["name"]]))

    finals=[]
    for typ,nm,m in candidates:
        finals.append({"type":typ,"name":nm,
                       "discovery":metrics(d[discovery&m]),"calibration":metrics(d[calibration&m]),
                       "cross_holdout_pre2026":metrics(d[cross_holdout&m]),"final_holdout_2026":metrics(d[final&m])})
    # Never use final to choose; champion shown only by train/cal score.
    champion=None
    if len(stable):
        best=("single",stable.iloc[0]["name"],masks[stable.iloc[0]["name"]],float(stable.iloc[0]["score"]))
        if len(pairs):
            ps=pairs[(pairs.disc_net24_imp>0)&(pairs.cal_net24_imp>0)&(pairs.disc_net72_imp>0)&(pairs.cal_net72_imp>0)]
            if len(ps) and float(ps.iloc[0]["score"])>best[3]:
                best=("pair",ps.iloc[0]["name"],pair_masks[ps.iloc[0]["name"]],float(ps.iloc[0]["score"]))
        typ,nm,m,sc=best
        champion={"type":typ,"name":nm,"score":sc,
                  "discovery":metrics(d[discovery&m]),"calibration":metrics(d[calibration&m]),
                  "cross_holdout_pre2026":metrics(d[cross_holdout&m]),"final_holdout_2026":metrics(d[final&m])}

    family_best={}
    for fam,g in stable.groupby("family"):
        r=g.iloc[0]; m=masks[r["name"]]
        family_best[fam]={"name":r["name"],"score":float(r["score"]),
                          "discovery":metrics(d[discovery&m]),"calibration":metrics(d[calibration&m]),
                          "final_holdout_2026":metrics(d[final&m])}

    summary={
        "purpose":"Proactively test additional indicator families not required by the user's original set, seeking filters that reduce signal count while improving real trade outcomes.",
        "round_trip_cost_pct":COST,
        "future_features_used":False,
        "symbol_id_used_as_feature":False,
        "selection_policy":"quantile thresholds learned only on discovery; require positive 24h and 72h improvement in discovery+calibration; final holdouts never used to select",
        "splits":{"discovery":"hash>=30, 2023-2024","calibration":"hash>=30, 2025","cross_holdout_pre2026":"hash<30, 2023-2025","final_holdout_2026":"hash<30, 2026"},
        "indicator_families":["ADX/DMI","ATR","Bollinger width/%B","MFI","CMF","rolling VWAP","ROC","PPO histogram","TSI","CMO","Donchian position","Efficiency Ratio","Choppiness","Relative Volume"],
        "timeframes":["coin 15m","coin 1h","coin 4h","BTC 1h","BTC 4h"],
        "base":{"discovery":base_disc,"calibration":base_cal,"cross_holdout_pre2026":base_cross,"final_holdout_2026":base_final},
        "feature_count":len(feats),"single_candidates_tested":int(len(tab)),"stable_singles":int(len(stable)),
        "pair_candidates_tested":int(len(pairs)) if len(pairs) else 0,
        "champion_selected_without_final":champion,
        "family_best":family_best,
        "top_final_diagnostics":finals
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Indicator Augmentation Discovery — Strictly Causal","",
           "Amaç: Kullanıcının verdiği gösterge setine körü körüne bağlı kalmadan, ek gösterge ailelerinin sinyal sayısını azaltırken işlem sonucunu iyileştirip iyileştirmediğini araştırmak.",
           "",f"Feature={len(feats)} | singles tested={len(tab)} | stable singles={len(stable)} | pairs tested={len(pairs) if len(pairs) else 0}",
           f"Cost={COST:.2f}% | future features=False | symbol ID feature=False","",
           "## Base",f"Discovery: {base_disc}",f"Calibration: {base_cal}",f"Cross-holdout pre2026: {base_cross}",f"Final holdout 2026: {base_final}","",
           "## Champion selected WITHOUT final holdout",str(champion),"","## Best stable filter per added indicator family"]
    for fam,v in family_best.items(): lines.append(f"- {fam}: {v}")
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
        if args.shard is None: raise SystemExit("--shard required")
        shard_main(args.shard,args.shards,args.outdir or ROOT/f"shard_{args.shard}")

if __name__=="__main__":
    main()
