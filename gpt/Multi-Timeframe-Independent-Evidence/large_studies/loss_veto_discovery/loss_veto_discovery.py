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

EVENTS=PARENT/"coin_mtf_broad_frozen_validation"/"output"/"frozen_rule_events.csv"
FETCH_START=pd.Timestamp("2022-10-01",tz="UTC")
FETCH_END=pd.Timestamp("2026-09-18",tz="UTC")
COST=0.20

def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def enrich(df):
    x=core.indicators(df)
    e=aug.extra_indicators(df)
    for c in e.columns:
        if c not in x.columns:
            x[c]=e[c]

    ema20=x.close.ewm(span=20,adjust=False).mean()
    ema50=x.close.ewm(span=50,adjust=False).mean()
    ema200=x.close.ewm(span=200,adjust=False).mean()
    x["ema20_50_spread_pct"]=100*(ema20/ema50-1)
    x["ema50_200_spread_pct"]=100*(ema50/ema200-1)
    x["price_ema20_pct"]=100*(x.close/ema20-1)
    x["price_ema50_pct"]=100*(x.close/ema50-1)
    x["ema20_50_spread_d1"]=x.ema20_50_spread_pct.diff()
    x["ema20_50_spread_d3"]=x.ema20_50_spread_pct.diff(3)
    x["ema50_200_spread_d3"]=x.ema50_200_spread_pct.diff(3)
    x["range_pct"]=100*(x.high-x.low)/x.close.replace(0,np.nan)
    x["body_pct"]=100*(x.close-x.open).abs()/x.open.replace(0,np.nan)
    x["close_ret1"]=100*x.close.pct_change()
    x["close_ret4"]=100*x.close.pct_change(4)
    x["close_ret12"]=100*x.close.pct_change(12)
    return x

def align(tf,delta,idx,prefix):
    z=tf.copy()
    z.index=z.index+delta
    cols=[c for c in z.columns if c not in ["open","high","low","close","volume","quote_volume"]]
    return z[cols].rename(columns={c:f"{prefix}_{c}" for c in cols}).reindex(idx,method="ffill")

def context(base,btc15):
    c15=enrich(base)
    idx=c15.index+pd.Timedelta(minutes=15)
    d15=c15.copy(); d15.index=idx
    cols=[c for c in d15.columns if c not in ["open","high","low","close","volume","quote_volume"]]
    out=d15[cols].rename(columns={c:f"m15_{c}" for c in cols})

    for rule,delta,pfx in [("1h",pd.Timedelta(hours=1),"h1"),("4h",pd.Timedelta(hours=4),"h4")]:
        out=out.join(align(enrich(core.resample(base,rule)),delta,idx,pfx))
    for rule,delta,pfx in [("1h",pd.Timedelta(hours=1),"btc1"),("4h",pd.Timedelta(hours=4),"btc4")]:
        out=out.join(align(enrich(core.resample(btc15,rule)),delta,idx,pfx))
    return out

def forward_labels(base,et):
    if et not in base.index:return None
    i=base.index.get_loc(et)
    if not isinstance(i,(int,np.integer)):return None
    ep=float(base.open.iloc[i])
    if not np.isfinite(ep) or ep<=0:return None

    rec={}
    for h in [12,24,48,72]:
        j=i+h*4
        if j>=len(base):
            rec[f"net_{h}h"]=np.nan;rec[f"mfe_{h}h"]=np.nan;rec[f"mae_{h}h"]=np.nan
            continue
        xp=float(base.open.iloc[j])
        sl=base.iloc[i:j+1]
        rec[f"net_{h}h"]=(xp/ep-1)*100-COST
        rec[f"mfe_{h}h"]=(float(sl.high.max())/ep-1)*100
        rec[f"mae_{h}h"]=(float(sl.low.min())/ep-1)*100

    j=min(i+72*4,len(base)-1)
    sl=base.iloc[i:j+1]
    hi=(sl.high.to_numpy(float)/ep-1)*100
    lo=(sl.low.to_numpy(float)/ep-1)*100
    u3=np.flatnonzero(hi>=3.0)
    d2=np.flatnonzero(lo<=-2.0)
    d3=np.flatnonzero(lo<=-3.0)
    tu3=(u3[0]/4.0) if len(u3) else np.nan
    td2=(d2[0]/4.0) if len(d2) else np.nan
    td3=(d3[0]/4.0) if len(d3) else np.nan
    rec["t_up3_h"]=tu3;rec["t_dn2_h"]=td2;rec["t_dn3_h"]=td3
    rec["clean_winner"]=int(pd.notna(tu3) and (pd.isna(td2) or tu3<td2))
    rec["delayed_winner"]=int(pd.notna(tu3) and pd.notna(td2) and td2<tu3<=72)
    rec["dead_signal"]=int(pd.isna(tu3) and rec.get("net_72h",np.nan)<0)
    rec["hard_loss"]=int(pd.notna(td3) and (pd.isna(tu3) or td3<tu3) and rec.get("net_72h",0)<0)
    rec["bad_union"]=int(rec["dead_signal"] or rec["hard_loss"])
    return rec

def pre_path(base,et):
    if et not in base.index:return {}
    i=base.index.get_loc(et)
    if not isinstance(i,(int,np.integer)):return {}
    ep=float(base.open.iloc[i]); rec={}
    for h in [1,2,4,8,12,24,48]:
        j=i-h*4
        if j<0:
            continue
        sl=base.iloc[j:i+1]
        rec[f"pre_ret_{h}h"]=100*(ep/float(base.open.iloc[j])-1)
        rec[f"pre_dd_from_high_{h}h"]=100*(ep/float(sl.high.max())-1)
        rec[f"pre_bounce_from_low_{h}h"]=100*(ep/float(sl.low.min())-1)
        rec[f"pre_range_{h}h"]=100*(float(sl.high.max())/float(sl.low.min())-1)
    return rec

def process_symbol(symbol,ev,btc15):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=FETCH_END)
        ctx=context(base,btc15)
        rows=[]
        for _,e in ev.iterrows():
            t=e.decision_time;et=e.entry_time
            if t not in ctx.index:continue
            lab=forward_labels(base,et)
            if lab is None:continue
            rec={"symbol":symbol,"decision_time":t,"entry_time":et,"year":int(t.year),"hash_mod":hmod(symbol)}
            row=ctx.loc[t]
            for c,v in row.items():
                if pd.notna(v) and np.isscalar(v):
                    try:rec[c]=float(v)
                    except Exception:pass
            rec.update(pre_path(base,et))
            rec.update(lab)
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
            if e:errs.append(e)
            elif x is not None and len(x):frames.append(x)
            if k%10==0 or k==len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(x) for x in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"loss_features.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard,"symbols":len(mine),"events":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def base_metrics(x):
    if len(x)==0:return {"n":0}
    return {
        "n":int(len(x)),"symbols":int(x.symbol.nunique()),
        "net24":float(pd.to_numeric(x.net_24h,errors="coerce").mean()),
        "net72":float(pd.to_numeric(x.net_72h,errors="coerce").mean()),
        "win24":float((pd.to_numeric(x.net_24h,errors="coerce")>0).mean()*100),
        "win72":float((pd.to_numeric(x.net_72h,errors="coerce")>0).mean()*100),
        "bad_pct":float(pd.to_numeric(x.bad_union,errors="coerce").mean()*100),
        "hard_loss_pct":float(pd.to_numeric(x.hard_loss,errors="coerce").mean()*100),
        "dead_signal_pct":float(pd.to_numeric(x.dead_signal,errors="coerce").mean()*100),
        "clean_winner_pct":float(pd.to_numeric(x.clean_winner,errors="coerce").mean()*100),
        "delayed_winner_pct":float(pd.to_numeric(x.delayed_winner,errors="coerce").mean()*100),
    }

def veto_metrics(x,mask):
    veto=mask.fillna(False)
    kept=x[~veto]
    b=base_metrics(x);k=base_metrics(kept)
    bad_total=max(int(x.bad_union.sum()),1)
    clean_total=max(int(x.clean_winner.sum()),1)
    delayed_total=max(int(x.delayed_winner.sum()),1)
    return {
        "veto_pct":float(veto.mean()*100),
        "kept_n":int(len(kept)),
        "bad_removed_pct":float(x.loc[veto,"bad_union"].sum()/bad_total*100),
        "clean_winner_preserved_pct":float(kept.clean_winner.sum()/clean_total*100),
        "delayed_winner_preserved_pct":float(kept.delayed_winner.sum()/delayed_total*100),
        "net24":k["net24"],"net72":k["net72"],"win24":k["win24"],"win72":k["win72"],
        "bad_pct_after":k["bad_pct"],"hard_loss_pct_after":k["hard_loss_pct"],"dead_signal_pct_after":k["dead_signal_pct"],
        "base_net24":b["net24"],"base_net72":b["net72"],
    }

def family(c):
    s=c.lower()
    keys=["btc","adx","di_","atr","bb_","mfi","cmf","vwap","roc","ppo","tsi","cmo","donch","er10","chop","rvol","ema","stoch","kdj","rsi","macd","obv","wpr","pre_","structure","motion"]
    for k in keys:
        if k in s:return k
    return "other"

def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("loss_features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames:raise RuntimeError("no loss feature files")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d=d.dropna(subset=["net_24h","net_72h"])
    outdir.mkdir(parents=True,exist_ok=True)

    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    final=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))

    label_cols={"net_12h","mfe_12h","mae_12h","net_24h","mfe_24h","mae_24h","net_48h","mfe_48h","mae_48h",
                "net_72h","mfe_72h","mae_72h","t_up3_h","t_dn2_h","t_dn3_h","clean_winner","delayed_winner",
                "dead_signal","hard_loss","bad_union","hash_mod","year"}
    meta={"symbol","decision_time","entry_time"}
    feats=[c for c in d.columns if c not in label_cols|meta and pd.api.types.is_numeric_dtype(d[c])]
    feats=[c for c in feats if d.loc[disc,c].notna().sum()>=500 and d.loc[disc,c].nunique(dropna=True)>=20]

    qset=[.10,.20,.30,.40,.50,.60,.70,.80,.90]
    rows=[]; masks={}
    bd=base_metrics(d[disc]);bc=base_metrics(d[cal])
    for c in feats:
        s=pd.to_numeric(d.loc[disc,c],errors="coerce")
        for q in qset:
            th=float(s.quantile(q))
            for side in ["GE","LE"]:
                m=(pd.to_numeric(d[c],errors="coerce")>=th) if side=="GE" else (pd.to_numeric(d[c],errors="coerce")<=th)
                md=veto_metrics(d[disc],m[disc]);mc=veto_metrics(d[cal],m[cal])
                if md["kept_n"]<200 or mc["kept_n"]<120:continue
                if not (10<=md["veto_pct"]<=70 and 10<=mc["veto_pct"]<=70):continue

                # We explicitly reward removal of bad paths while preserving both clean and delayed winners.
                # This prevents a "filter" from looking good only because it deletes almost everything.
                impd24=md["net24"]-md["base_net24"];impc24=mc["net24"]-mc["base_net24"]
                impd72=md["net72"]-md["base_net72"];impc72=mc["net72"]-mc["base_net72"]
                stable=(impd24>0 and impc24>0 and impd72>0 and impc72>0
                        and md["bad_removed_pct"]>md["veto_pct"] and mc["bad_removed_pct"]>mc["veto_pct"]
                        and md["clean_winner_preserved_pct"]>=45 and mc["clean_winner_preserved_pct"]>=45
                        and md["delayed_winner_preserved_pct"]>=45 and mc["delayed_winner_preserved_pct"]>=45)
                score=(min(impd24,impc24)+min(impd72,impc72)
                       +0.02*min(md["bad_removed_pct"]-md["veto_pct"],mc["bad_removed_pct"]-mc["veto_pct"])
                       +0.005*min(md["clean_winner_preserved_pct"],mc["clean_winner_preserved_pct"])
                       +0.005*min(md["delayed_winner_preserved_pct"],mc["delayed_winner_preserved_pct"]))
                name=f"{c} {side} Q{int(q*100)}({th:.6g})"
                rows.append({"name":name,"feature":c,"family":family(c),"side":side,"q":q,"threshold":th,
                             "stable_dev":stable,"score":score,
                             "disc_veto":md["veto_pct"],"cal_veto":mc["veto_pct"],
                             "disc_bad_removed":md["bad_removed_pct"],"cal_bad_removed":mc["bad_removed_pct"],
                             "disc_clean_preserved":md["clean_winner_preserved_pct"],"cal_clean_preserved":mc["clean_winner_preserved_pct"],
                             "disc_delayed_preserved":md["delayed_winner_preserved_pct"],"cal_delayed_preserved":mc["delayed_winner_preserved_pct"],
                             "disc_net24_imp":impd24,"cal_net24_imp":impc24,"disc_net72_imp":impd72,"cal_net72_imp":impc72})
                masks[name]=m

    tab=pd.DataFrame(rows).sort_values(["stable_dev","score"],ascending=[False,False])
    tab.to_csv(outdir/"single_vetoes.csv",index=False)

    stable=tab[tab.stable_dev].head(40)
    pair_rows=[];pair_masks={}
    for i,a in stable.iterrows():
        for j,b in stable.iterrows():
            if i>=j or a["family"]==b["family"]:continue
            # veto if either danger condition fires
            m=masks[a["name"]]|masks[b["name"]]
            md=veto_metrics(d[disc],m[disc]);mc=veto_metrics(d[cal],m[cal])
            if md["kept_n"]<160 or mc["kept_n"]<100:continue
            if not (10<=md["veto_pct"]<=75 and 10<=mc["veto_pct"]<=75):continue
            impd24=md["net24"]-md["base_net24"];impc24=mc["net24"]-mc["base_net24"]
            impd72=md["net72"]-md["base_net72"];impc72=mc["net72"]-mc["base_net72"]
            stable_pair=(impd24>0 and impc24>0 and impd72>0 and impc72>0
                         and md["bad_removed_pct"]>md["veto_pct"] and mc["bad_removed_pct"]>mc["veto_pct"]
                         and md["clean_winner_preserved_pct"]>=35 and mc["clean_winner_preserved_pct"]>=35
                         and md["delayed_winner_preserved_pct"]>=35 and mc["delayed_winner_preserved_pct"]>=35)
            score=(min(impd24,impc24)+min(impd72,impc72)
                   +0.02*min(md["bad_removed_pct"]-md["veto_pct"],mc["bad_removed_pct"]-mc["veto_pct"]))
            nm=a["name"]+" OR "+b["name"]
            pair_rows.append({"name":nm,"a":a["name"],"b":b["name"],"stable_dev":stable_pair,"score":score,
                              "disc_veto":md["veto_pct"],"cal_veto":mc["veto_pct"],
                              "disc_bad_removed":md["bad_removed_pct"],"cal_bad_removed":mc["bad_removed_pct"],
                              "disc_clean_preserved":md["clean_winner_preserved_pct"],"cal_clean_preserved":mc["clean_winner_preserved_pct"],
                              "disc_delayed_preserved":md["delayed_winner_preserved_pct"],"cal_delayed_preserved":mc["delayed_winner_preserved_pct"],
                              "disc_net24_imp":impd24,"cal_net24_imp":impc24,"disc_net72_imp":impd72,"cal_net72_imp":impc72})
            pair_masks[nm]=m
    pairs=pd.DataFrame(pair_rows).sort_values(["stable_dev","score"],ascending=[False,False]) if pair_rows else pd.DataFrame()
    pairs.to_csv(outdir/"pair_vetoes.csv",index=False)

    candidates=[]
    for _,r in tab[tab.stable_dev].head(15).iterrows():
        candidates.append(("single",r["name"],masks[r["name"]],float(r["score"])))
    if len(pairs):
        for _,r in pairs[pairs.stable_dev].head(15).iterrows():
            candidates.append(("pair",r["name"],pair_masks[r["name"]],float(r["score"])))
    candidates=sorted(candidates,key=lambda x:x[3],reverse=True)

    details=[]
    for typ,nm,m,score in candidates[:20]:
        details.append({"type":typ,"name":nm,"score":score,
                        "discovery":veto_metrics(d[disc],m[disc]),
                        "calibration":veto_metrics(d[cal],m[cal]),
                        "cross_holdout_pre2026":veto_metrics(d[cross],m[cross]),
                        "final_holdout_2026":veto_metrics(d[final],m[final])})
    champion=details[0] if details else None

    summary={
        "purpose":"Find causal vetoes that remove likely losing/dangerous setups while preserving both clean winners and delayed winners. This directly addresses loss reduction rather than only studying successful rises.",
        "round_trip_cost_pct":COST,
        "loss_labels":{
            "clean_winner":"+3% before -2% within 72h",
            "delayed_winner":"-2% occurs first but +3% still arrives within 72h",
            "dead_signal":"never reaches +3% within 72h and net72 is negative",
            "hard_loss":"-3% occurs before any +3% and net72 is negative",
            "bad_union":"dead_signal OR hard_loss"
        },
        "selection_policy":"thresholds learned on discovery only; must improve 24h and 72h expectancy in discovery+calibration; must remove bad paths faster than it removes all signals; must preserve a meaningful share of both clean and delayed winners; holdouts never used for selection",
        "base":{"discovery":bd,"calibration":bc,"cross_holdout_pre2026":base_metrics(d[cross]),"final_holdout_2026":base_metrics(d[final])},
        "features_tested":len(feats),"single_vetoes_tested":int(len(tab)),"stable_single_vetoes":int(tab.stable_dev.sum()),
        "pair_vetoes_tested":int(len(pairs)) if len(pairs) else 0,
        "champion_selected_without_holdouts":champion,
        "top_candidates":details
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Loss Veto Discovery — Causal","",
           "Amaç: yalnız yükselenleri bulmak değil; kötü setup'ları işlem anında ayıklamak ve bunu yaparken temiz + gecikmeli kazananları mümkün olduğunca korumak.",
           "",f"Cost={COST:.2f}% | features={len(feats)} | singles={len(tab)} | stable singles={int(tab.stable_dev.sum())} | pairs={len(pairs) if len(pairs) else 0}",
           "","## Base",str(summary["base"]),"","## Champion selected without holdouts",str(champion)]
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
