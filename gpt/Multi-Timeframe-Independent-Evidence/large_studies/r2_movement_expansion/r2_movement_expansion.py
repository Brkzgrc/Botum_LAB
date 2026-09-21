from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

R1_TSI_MAX=-0.211069
R1_BTC4_BB_MIN=0.0942267
TARGET_RETENTIONS=(0.40,0.45,0.50,0.55,0.60,0.65,0.70)

META={"symbol","decision_time","entry_time","hash_mod","year","r1","r2"}
OUTCOME_PREFIX=("net_","mfe_","mae_","t_","up3_","danger_")

def split_masks(d):
    t=d.decision_time
    return {
      "DISCOVERY":(d.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC")),
      "CALIBRATION":(d.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "CROSS_HOLDOUT_PRE2026":(d.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC")),
      "FINAL_SYMBOL_HOLDOUT_2026":(d.hash_mod<30)&(t>=pd.Timestamp("2026-01-01",tz="UTC")),
      "ALL_2026":t>=pd.Timestamp("2026-01-01",tz="UTC"),
    }

def metrics(x):
    if len(x)==0:return {"n":0,"symbols":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v):return {"n":0,"symbols":0}
    z=x.loc[v.index]
    gp=float(v[v>0].sum());gl=float(-v[v<0].sum())
    return {
      "n":int(len(v)),"symbols":int(z.symbol.nunique()),
      "mean24":float(v.mean()),"median24":float(v.median()),
      "win24":float((v>0).mean()*100),
      "pf24":float(gp/gl) if gl>0 else None,
      "up3_before_dn2":float(pd.to_numeric(z.up3_before_dn2,errors="coerce").mean()*100),
      "danger_dn2_first":float(pd.to_numeric(z.danger_dn2_first,errors="coerce").mean()*100),
      "mean12":float(pd.to_numeric(z.net_12h,errors="coerce").mean()),
      "mean72":float(pd.to_numeric(z.net_72h,errors="coerce").mean()),
      "mfe24":float(pd.to_numeric(z.mfe_24h,errors="coerce").mean()),
      "mae24":float(pd.to_numeric(z.mae_24h,errors="coerce").mean()),
    }

def freq(x,start,end):
    days=max(1,(end.normalize()-start.normalize()).days+1)
    c=x.groupby(x.decision_time.dt.floor("D")).size() if len(x) else pd.Series(dtype=float)
    return {
      "calendar_days":int(days),"signals":int(len(x)),"signals_per_day":float(len(x)/days),
      "active_days":int(len(c)),"active_day_share_pct":float(len(c)/days*100),
      "median_on_active_day":float(c.median()) if len(c) else 0.0,
      "p90_on_active_day":float(c.quantile(.90)) if len(c) else 0.0,
      "max_in_day":int(c.max()) if len(c) else 0,
    }

def load(indicator_dir,r2_dataset_dir):
    fs=sorted(indicator_dir.rglob("features.csv"))
    if not fs:raise RuntimeError("no indicator feature artifacts")
    frames=[]
    for f in fs:
        try:
            x=pd.read_csv(f,low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if len(x):frames.append(x)
    if not frames:raise RuntimeError("empty indicator artifacts")
    d=pd.concat(frames,ignore_index=True)
    req={"symbol","decision_time","entry_time","hash_mod","btc1_tsi_d1","btc4_bb_width",
         "net_12h","net_24h","net_72h","mfe_24h","mae_24h","up3_before_dn2","danger_dn2_first"}
    miss=sorted(req-set(d.columns))
    if miss:raise RuntimeError(f"missing broad columns {miss}")
    d.decision_time=pd.to_datetime(d.decision_time,utc=True)
    d.entry_time=pd.to_datetime(d.entry_time,utc=True)
    d.hash_mod=pd.to_numeric(d.hash_mod,errors="raise").astype(int)
    d=d.drop_duplicates(["symbol","decision_time"],keep="last").reset_index(drop=True)
    r2=pd.read_csv(r2_dataset_dir/"r2_events.csv",usecols=["symbol","decision_time"],low_memory=False)
    r2.decision_time=pd.to_datetime(r2.decision_time,utc=True)
    keys=set(zip(r2.symbol.astype(str),r2.decision_time.astype(str)))
    d["r2"]=[k in keys for k in zip(d.symbol.astype(str),d.decision_time.astype(str))]
    d["r1"]=(pd.to_numeric(d.btc1_tsi_d1,errors="coerce")<=R1_TSI_MAX)&(pd.to_numeric(d.btc4_bb_width,errors="coerce")>=R1_BTC4_BB_MIN)
    return d

def preflight(indicator_dir,r2_dataset_dir):
    d=load(indicator_dir,r2_dataset_dir); sm=split_masks(d)
    counts={k:int(v.sum()) for k,v in sm.items()}
    if len(d)!=8174:raise RuntimeError(f"expected broad_events=8174 got {len(d)}")
    if int(d.r1.sum())!=577:raise RuntimeError(f"expected r1=577 got {int(d.r1.sum())}")
    if int(d.r2.sum())!=225:raise RuntimeError(f"expected r2=225 got {int(d.r2.sum())}")
    if counts["ALL_2026"]!=1556:raise RuntimeError(f"expected all2026=1556 got {counts['ALL_2026']}")
    return {"broad_events":len(d),"symbols":int(d.symbol.nunique()),"r1":int(d.r1.sum()),"r2":int(d.r2.sum()),"splits":counts}

def movement_features(d,disc):
    out=[]
    for c in d.columns:
        if c in META or c.startswith(OUTCOME_PREFIX):continue
        lc=c.lower()
        # Movement/state only: changes, acceleration, returns, relative position/participation.
        movement=(
          lc.endswith(("_d1","_d3","_acc"))
          or any(k in lc for k in ("_roc4","_roc12","vwap_dist","donch_pos","bb_pctb","rvol20","di_spread","ppo_hist","cmf","cmo","er10","chop14"))
        )
        if not movement:continue
        s=pd.to_numeric(d[c],errors="coerce")
        if s[disc].notna().sum()<500 or s[disc].nunique(dropna=True)<20:continue
        out.append(c)
    return out

def tf_family(c):
    tf="other"
    for p in ("m15_","h1_","h4_","btc1_","btc4_"):
        if c.startswith(p):tf=p[:-1];break
    base=c
    if tf!="other":base=c[len(tf)+1:]
    fam=base
    for suff in ("_d1","_d3","_acc"):fam=fam.removesuffix(suff)
    return tf,fam

def robust_stats(s):
    x=pd.to_numeric(s,errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
    med=float(x.median()); q1=float(x.quantile(.25));q3=float(x.quantile(.75));iqr=q3-q1
    if not np.isfinite(iqr) or abs(iqr)<1e-12:iqr=float(x.std())
    if not np.isfinite(iqr) or abs(iqr)<1e-12:iqr=1.0
    return med,iqr

def stable_effects(d,features,sm):
    rows=[]
    for c in features:
        vals=[]
        for split in ("DISCOVERY","CALIBRATION"):
            z=d[sm[split]].copy()
            x=pd.to_numeric(z[c],errors="coerce")
            good=(pd.to_numeric(z.net_24h,errors="coerce")>0)&(pd.to_numeric(z.up3_before_dn2,errors="coerce")==1)
            bad=(pd.to_numeric(z.net_24h,errors="coerce")<=0)|(pd.to_numeric(z.danger_dn2_first,errors="coerce")==1)
            a=x[good].dropna();b=x[bad].dropna()
            if min(len(a),len(b))<50:vals=[];break
            _,scale=robust_stats(x)
            vals.append(float((a.median()-b.median())/scale))
        if len(vals)!=2 or vals[0]==0 or vals[1]==0 or np.sign(vals[0])!=np.sign(vals[1]):continue
        strength=min(abs(vals[0]),abs(vals[1]))
        if strength<0.05:continue
        tf,fam=tf_family(c)
        rows.append({"feature":c,"tf":tf,"family":fam,"direction":1 if vals[0]>0 else -1,
                     "effect_discovery":vals[0],"effect_calibration":vals[1],"stable_strength":strength})
    rows.sort(key=lambda r:r["stable_strength"],reverse=True)
    # Avoid counting the same indicator/timeframe many times.
    chosen=[];seen=set()
    for r in rows:
        key=(r["tf"],r["family"])
        if key in seen:continue
        chosen.append(r);seen.add(key)
        if len(chosen)>=16:break
    return rows,chosen

def fit_scores(d,selected,dev):
    zdev=d.loc[dev]
    quality=np.zeros(len(d),dtype=float); quality_n=np.zeros(len(d),dtype=float)
    zcols={}
    for r in selected:
        c=r["feature"];med,scale=robust_stats(zdev[c])
        x=(pd.to_numeric(d[c],errors="coerce")-med)/scale
        x=x.clip(-4,4)
        arr=x.to_numpy(float)
        ok=np.isfinite(arr)
        quality[ok]+=r["direction"]*arr[ok]*r["stable_strength"]
        quality_n[ok]+=r["stable_strength"]
        zcols[c]=(arr,med,scale)
    quality=np.divide(quality,quality_n,out=np.full_like(quality,np.nan),where=quality_n>0)

    # R2 movement fingerprint learned only from D+C r2 events.
    anchor=dev & d.r2
    sim_num=np.zeros(len(d),dtype=float);sim_den=np.zeros(len(d),dtype=float)
    for r in selected:
        c=r["feature"];arr,med,scale=zcols[c]
        av=arr[anchor.to_numpy(bool)]
        av=av[np.isfinite(av)]
        if len(av)<15:continue
        center=float(np.median(av))
        ok=np.isfinite(arr)
        w=r["stable_strength"]
        sim_num[ok]+=w*np.abs(arr[ok]-center)
        sim_den[ok]+=w
    dist=np.divide(sim_num,sim_den,out=np.full_like(sim_num,np.nan),where=sim_den>0)
    similarity=-dist

    def rank01(arr):
        s=pd.Series(arr,index=d.index)
        base=s[dev].dropna()
        vals=np.sort(base.to_numpy(float))
        if len(vals)==0:return np.full(len(d),np.nan)
        x=s.to_numpy(float)
        out=np.full(len(d),np.nan)
        ok=np.isfinite(x)
        out[ok]=np.searchsorted(vals,x[ok],side="right")/len(vals)
        return out
    qrank=rank01(quality);srank=rank01(similarity)
    hybrid=.70*qrank+.30*srank
    return {"QUALITY":quality,"R2_SIMILARITY":similarity,"HYBRID":hybrid}

def eval_method(d,sm,scores,method,retention):
    arr=scores[method]
    dev=sm["DISCOVERY"]|sm["CALIBRATION"]
    v=arr[dev.to_numpy(bool)]
    v=v[np.isfinite(v)]
    if len(v)<100: return None
    th=float(np.quantile(v,1-retention))
    mask=pd.Series(np.isfinite(arr)&(arr>=th),index=d.index)
    rec={"method":method,"target_retention":retention,"threshold":th}
    for k,m in sm.items():
        z=d[mask&m]
        rec[k]={"metrics":metrics(z)}
    for k in ("DISCOVERY","CALIBRATION"):
        base_n=int(sm[k].sum())
        rec[k]["retention"]=float(rec[k]["metrics"]["n"]/base_n) if base_n else 0
    return rec,mask

def candidate_score(rec):
    D=rec["DISCOVERY"]["metrics"];C=rec["CALIBRATION"]["metrics"]
    if min(D["n"],C["n"])<300:return -1e9
    if min(D["mean24"],C["mean24"])<=0:return -1e9
    if min(D["pf24"] or 0,C["pf24"] or 0)<=1:return -1e9
    ret=min(rec["DISCOVERY"]["retention"],rec["CALIBRATION"]["retention"])
    # Strongly favor the frequency band needed to map ~6 broad events/day into ~3/day.
    freq_pen=abs(ret-.50)
    return (min(D["mean24"],C["mean24"]) + .025*min(D["win24"],C["win24"])
            +.015*min(D["up3_before_dn2"],C["up3_before_dn2"])
            -.010*max(D["danger_dn2_first"],C["danger_dn2_first"])
            -3.0*freq_pen)

def eval_baselines(d,sm):
    out={}
    for name,mask in {"BROAD":pd.Series(True,index=d.index),"R1":d.r1,"R2":d.r2}.items():
        out[name]={k:metrics(d[mask&m]) for k,m in sm.items()}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indicator-dir",type=Path,required=True)
    ap.add_argument("--r2-dataset-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--preflight",action="store_true")
    a=ap.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
    pf=preflight(a.indicator_dir,a.r2_dataset_dir)
    if a.preflight:
        (a.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
        print(json.dumps(pf));return
    d=load(a.indicator_dir,a.r2_dataset_dir);sm=split_masks(d)
    disc=sm["DISCOVERY"];dev=disc|sm["CALIBRATION"]
    feats=movement_features(d,disc)
    if len(feats)<80:raise RuntimeError(f"too few movement features {len(feats)}")
    all_effects,selected=stable_effects(d,feats,sm)
    if len(selected)<6:raise RuntimeError(f"too few stable movement families {len(selected)}")
    scores=fit_scores(d,selected,dev)
    candidates=[];masks={}
    for method in scores:
        for r in TARGET_RETENTIONS:
            q=eval_method(d,sm,scores,method,r)
            if q is None:continue
            rec,mask=q
            rec["selection_score"]=candidate_score(rec)
            candidates.append(rec);masks[(method,r)]=mask
    candidates.sort(key=lambda x:x["selection_score"],reverse=True)
    champion=candidates[0] if candidates else None
    if champion is None or champion["selection_score"]<-1e8:
        status="NO_DEV_STABLE_MOVEMENT_EXPANSION";chosen_mask=pd.Series(False,index=d.index)
    else:
        status="DEV_SELECTED_MOVEMENT_EXPANSION";chosen_mask=masks[(champion["method"],champion["target_retention"])]

    # Frequency diagnostics are never used for selection.
    period={
      "DISCOVERY":(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2024-12-31",tz="UTC")),
      "CALIBRATION":(pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
      "CROSS_HOLDOUT_PRE2026":(pd.Timestamp("2023-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
      "FINAL_SYMBOL_HOLDOUT_2026":(pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-17",tz="UTC")),
      "ALL_2026":(pd.Timestamp("2026-01-01",tz="UTC"),pd.Timestamp("2026-09-17",tz="UTC")),
    }
    if champion:
        champion["frequency"]={k:freq(d[chosen_mask&sm[k]],*period[k]) for k in sm}
        a26=champion["ALL_2026"]["metrics"];f26=champion["frequency"]["ALL_2026"]
        if f26["signals_per_day"]>=2.0 and a26.get("mean24",-999)>0 and (a26.get("pf24") or 0)>1:
            status="OOS_POSITIVE_FREQUENCY_EXPANSION"
        # Explicitly mark whether original r2 quality was preserved.
        r2_26=metrics(d[d.r2&sm["ALL_2026"]])
        champion["quality_vs_r2_all2026"]={
          "win24_delta_pp":a26.get("win24",0)-r2_26.get("win24",0),
          "mean24_delta_pct":a26.get("mean24",0)-r2_26.get("mean24",0),
          "up3_before_dn2_delta_pp":a26.get("up3_before_dn2",0)-r2_26.get("up3_before_dn2",0),
          "r2_quality_preserved":bool(a26.get("win24",0)>=r2_26.get("win24",0) and a26.get("mean24",0)>=r2_26.get("mean24",0))
        }

    summary={
      "status":status,
      "purpose":"Analyze causal 15M/1H/4H coin and BTC movement states around the existing broad lead-lag signal, seeking ~50% retention (~3/day from ~6 broad events/day) without using holdouts for selection.",
      "preflight":pf,
      "selection_lock":"Feature directions, feature set, method and threshold selected from Discovery+Calibration only. Holdouts/2026 are diagnostics.",
      "movement_feature_count":len(feats),
      "stable_effect_count":len(all_effects),
      "selected_independent_movement_features":selected,
      "baselines":eval_baselines(d,sm),
      "champion":champion,
      "all_candidates":candidates,
    }
    (a.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    pd.DataFrame(all_effects).to_csv(a.outdir/"movement_effects.csv",index=False)
    pd.DataFrame([{
      "rank":i+1,"method":x["method"],"target_retention":x["target_retention"],"selection_score":x["selection_score"],
      "disc_retention":x["DISCOVERY"]["retention"],"disc_mean24":x["DISCOVERY"]["metrics"]["mean24"],"disc_win24":x["DISCOVERY"]["metrics"]["win24"],
      "cal_retention":x["CALIBRATION"]["retention"],"cal_mean24":x["CALIBRATION"]["metrics"]["mean24"],"cal_win24":x["CALIBRATION"]["metrics"]["win24"],
      "cross_n":x["CROSS_HOLDOUT_PRE2026"]["metrics"]["n"],"cross_mean24":x["CROSS_HOLDOUT_PRE2026"]["metrics"].get("mean24"),
      "cross_win24":x["CROSS_HOLDOUT_PRE2026"]["metrics"].get("win24"),
      "all2026_n":x["ALL_2026"]["metrics"]["n"],"all2026_mean24":x["ALL_2026"]["metrics"].get("mean24"),
      "all2026_win24":x["ALL_2026"]["metrics"].get("win24"),
    } for i,x in enumerate(candidates)]).to_csv(a.outdir/"candidates.csv",index=False)
    print(json.dumps({"status":status,"champion":champion,"selected_features":selected},ensure_ascii=False,allow_nan=False),flush=True)

if __name__=="__main__":
    main()
