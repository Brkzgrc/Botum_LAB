from __future__ import annotations
import argparse, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np, pandas as pd, requests

R2_BB=0.19233492
R2_DD=-7.3594696
BASES=["https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com","https://api2.binance.com","https://api3.binance.com"]
HTTP=requests.Session(); HTTP.headers.update({"User-Agent":"Botum-LAB-TSI-BB-Phase8/1.0"})
HORIZONS=[12,24,48,72,168]
LOOKBACKS=[12,24,48]
PROTO_H=[12,24,48,72,168]

def get_json(path,params=None):
    last=None
    for i in range(5):
        for base in BASES:
            try:
                r=HTTP.get(base+path,params=params or {},timeout=20)
                if r.status_code in (418,429): continue
                r.raise_for_status(); return r.json()
            except Exception as e: last=e
        time.sleep(min(6,.5*(2**i)))
    raise RuntimeError(last)

def load(indir):
    fs=sorted(indir.rglob("features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames: raise RuntimeError("no features.csv artifacts")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    num=["btc1_tsi_d1","btc4_bb_width","h4_bb_width"]+[f"net_{h}h" for h in HORIZONS if f"net_{h}h" in d.columns]
    for c in num: d[c]=pd.to_numeric(d[c],errors="coerce")
    need=["btc1_tsi_d1","btc4_bb_width","h4_bb_width","net_24h","net_72h","net_168h"]
    miss=[c for c in need if c not in d.columns]
    if miss: raise RuntimeError("missing required columns: "+str(miss))
    d=d.dropna(subset=["btc1_tsi_d1","btc4_bb_width","h4_bb_width","net_24h","net_72h","net_168h"]).copy()
    d=d[(d.btc1_tsi_d1<=0.10)&(d.btc4_bb_width>=0.045)].copy()
    return d.sort_values(["symbol","decision_time"]).drop_duplicates(["symbol","decision_time"]).reset_index(drop=True)

def fetch_path(row):
    t=pd.Timestamp(row.decision_time)
    end_ms=int(t.timestamp()*1000)-1
    start_ms=int((t-pd.Timedelta(hours=50)).timestamp()*1000)
    try:
        z=get_json("/api/v3/klines",{"symbol":str(row.symbol),"interval":"15m","startTime":start_ms,"endTime":end_ms,"limit":1000})
        if not isinstance(z,list) or len(z)<193:
            return int(row.row_id),None,f"short:{len(z) if isinstance(z,list) else -1}"
        a=np.array([float(x[4]) for x in z[-193:]],float)
        h=np.array([float(x[2]) for x in z[-193:]],float)
        ref=a[-1]
        dd=(ref/h.max()-1)*100
        paths={}
        for lb in LOOKBACKS:
            n=lb*4
            seg=a[-(n+1):]
            p=np.log(seg/seg[0])*100
            idx=np.linspace(0,len(seg)-1,13).round().astype(int)
            v=p[idx].astype(float); v=v-v[0]
            paths[lb]=v
        return int(row.row_id),(paths,dd),None
    except Exception as e:
        return int(row.row_id),None,repr(e)

def metrics(x):
    out={"n":int(len(x)),"symbols":int(x.symbol.nunique()) if len(x) else 0}
    if not len(x): return out
    for h in HORIZONS:
        c=f"net_{h}h"
        if c not in x.columns: continue
        v=pd.to_numeric(x[c],errors="coerce").dropna()
        if not len(v): continue
        gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
        out[f"win{h}"]=float((v>0).mean()*100)
        out[f"mean{h}"]=float(v.mean())
        out[f"median{h}"]=float(v.median())
        out[f"pf{h}"]=float(gp/gl) if gl>0 else None
        out[f"p10_{h}"]=float(v.quantile(.10))
    return out

def zdist(X,proto,scale):
    return np.sqrt(np.nanmean(((X-proto)/scale)**2,axis=1))

def build_score(X,good,train,r2,lb,outcome_h):
    y=pd.to_numeric(good[f"net_{outcome_h}h"],errors="coerce")
    win=train&r2&(y>0); los=train&r2&(y<=0)
    if win.sum()<8 or los.sum()<3: return None
    pw=np.nanmedian(X[lb][win.to_numpy()],axis=0)
    pl=np.nanmedian(X[lb][los.to_numpy()],axis=0)
    scale=np.nanpercentile(X[lb][train.to_numpy()],75,axis=0)-np.nanpercentile(X[lb][train.to_numpy()],25,axis=0)
    scale=np.where(np.isfinite(scale)&(scale>1e-6),scale,1.0)
    return zdist(X[lb],pl,scale)-zdist(X[lb],pw,scale),pw,pl,scale

def viable_for_horizon(md,mc,h):
    return (
        md.get("n",0)>=15 and mc.get("n",0)>=15 and
        md.get(f"win{h}",0)>=55 and mc.get(f"win{h}",0)>=55 and
        md.get(f"mean{h}",-99)>0.5 and mc.get(f"mean{h}",-99)>0.5 and
        (md.get(f"pf{h}") or 0)>1.2 and (mc.get(f"pf{h}") or 0)>1.2
    )

def survives_cross(mx,h):
    return (
        mx.get("n",0)>=20 and
        mx.get(f"win{h}",0)>=55 and
        mx.get(f"mean{h}",-99)>0.5 and
        (mx.get(f"pf{h}") or 0)>1.2
    )

def _old_viable_for_horizon(md,mc,h):
    return (
        md.get("n",0)>=10 and mc.get("n",0)>=8 and
        md.get(f"win{h}",0)>=55 and mc.get(f"win{h}",0)>=55 and
        md.get(f"mean{h}",-99)>0.5 and mc.get(f"mean{h}",-99)>0.5 and
        (md.get(f"pf{h}") or 0)>1.2 and (mc.get(f"pf{h}") or 0)>1.2
    )

def main(indir,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    d=load(indir); d["row_id"]=np.arange(len(d))
    res={}; errs=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        fut=[ex.submit(fetch_path,r) for r in d.itertuples(index=False)]
        for k,f in enumerate(as_completed(fut),1):
            rid,val,err=f.result()
            if err: errs.append({"row_id":rid,"error":err})
            else: res[rid]=val
            if k%100==0 or k==len(fut): print(f"[PATH] {k}/{len(fut)} ok={len(res)} err={len(errs)}",flush=True)
    good=d[d.row_id.isin(res)].copy().reset_index(drop=True)
    if not len(good): raise RuntimeError("no usable path rows")
    X={lb:np.vstack([res[int(rid)][0][lb] for rid in good.row_id]) for lb in LOOKBACKS}
    good["causal_dd_high_48h"]=[res[int(rid)][1] for rid in good.row_id]
    r2=(good.btc1_tsi_d1<=-0.211069)&(good.btc4_bb_width>=0.0942267)&(good.h4_bb_width>=R2_BB)&(good.causal_dd_high_48h<=R2_DD)

    t=good.decision_time
    disc=(good.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(good.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(good.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    all26=t>=pd.Timestamp("2026-01-01",tz="UTC")
    pool=~r2

    candidates=[]; masks={}; proto_rows=[]
    for lb in LOOKBACKS:
        for oh in PROTO_H:
            built=build_score(X,good,disc,r2,lb,oh)
            if built is None: continue
            score,pw,pl,scale=built
            col=f"score_lb{lb}_out{oh}"
            good[col]=score
            for i in range(len(pw)):
                proto_rows.append({"lookback_h":lb,"outcome_h":oh,"point":i,"winner":float(pw[i]),"loser":float(pl[i]),"scale":float(scale[i])})
            sd=good.loc[disc&pool,col].dropna()
            for q in [.70,.75,.80,.85,.875,.90,.925,.95,.965]:
                th=float(sd.quantile(q))
                m=pool&(good[col]>=th)
                md=metrics(good[disc&m]); mc=metrics(good[cal&m])
                if md.get("n",0)<10 or mc.get("n",0)<8: continue
                nm=f"LB{lb}_PROTO{oh}_Q{int(q*1000)}"
                viable_h=[h for h in HORIZONS if viable_for_horizon(md,mc,h)]
                rec={"name":nm,"lookback_h":lb,"prototype_outcome_h":oh,"q":q,"threshold":th,
                     "discovery":md,"calibration":mc,"viable_horizons":viable_h,"viable":bool(viable_h)}
                candidates.append(rec); masks[nm]=m

    viable=[]
    for r in candidates:
        if not r["viable"]: continue
        mx=metrics(good[cross&masks[r["name"]]])
        hs=[h for h in r["viable_horizons"] if survives_cross(mx,h)]
        if hs:
            r["cross_pre2026"]=mx
            r["robust_horizons"]=hs
            viable.append(r)
    def horizon_score(r,h):
        d0=r["discovery"]; c0=r["calibration"]
        return min(d0.get(f"mean{h}",-99),c0.get(f"mean{h}",-99))+0.02*min(d0.get(f"win{h}",0),c0.get(f"win{h}",0))+0.15*min(d0.get(f"pf{h}") or 0,c0.get(f"pf{h}") or 0)
    for r in viable:
        r["best_horizon"]=max(r["robust_horizons"],key=lambda h:horizon_score(r,h))
        r["best_score"]=horizon_score(r,r["best_horizon"])
    viable=sorted(viable,key=lambda r:r["best_score"],reverse=True)

    # Greedy union: pre-2026 only. Add distinct families while preserving quality floor.
    selected=[]; union=r2.copy()
    base_cross=metrics(good[cross&union])
    for rec in viable:
        m=masks[rec["name"]]
        trial=union|m
        md=metrics(good[disc&trial]); mc=metrics(good[cal&trial]); mx=metrics(good[cross&trial])
        h=rec["best_horizon"]
        if not viable_for_horizon(md,mc,h): continue
        if not survives_cross(mx,h): continue
        gain=int((trial&~union&cross).sum())
        if gain<=0: continue
        selected.append(rec["name"]); union=trial
        if len(selected)>=4: break

    weeks26=(pd.Timestamp("2026-09-18",tz="UTC")-pd.Timestamp("2026-01-01",tz="UTC")).days/7
    summary={
      "method":"Cross-holdout-gated horizon-adaptive reverse engineering: each trajectory family must survive discovery, calibration and CROSS_HOLDOUT_PRE2026 at the same 12/24/48/72/168h outcome horizon before 2026 is opened.",
      "selection_uses_2026":False,
      "events":int(len(good)),"errors":int(len(errs)),
      "candidate_families_tested":int(len(candidates)),
      "viable_pre2026_cross_gated":int(len(viable)),
      "selected_union_families":selected,
      "r2":{"discovery":metrics(good[disc&r2]),"calibration":metrics(good[cal&r2]),"cross_pre2026":metrics(good[cross&r2]),"all_2026":metrics(good[all26&r2]),"signals_per_week_2026":metrics(good[all26&r2]).get("n",0)/weeks26},
      "expanded_union":{"discovery":metrics(good[disc&union]),"calibration":metrics(good[cal&union]),"cross_pre2026":metrics(good[cross&union]),"all_2026":metrics(good[all26&union]),"signals_per_week_2026":metrics(good[all26&union]).get("n",0)/weeks26},
      "top_viable":[{"name":r["name"],"lookback_h":r["lookback_h"],"prototype_outcome_h":r["prototype_outcome_h"],"best_horizon":r["best_horizon"],"discovery":r["discovery"],"calibration":r["calibration"],"cross_pre2026":r["cross_pre2026"],"all_2026":metrics(good[all26&masks[r["name"]]])} for r in viable[:10]]
    }
    pd.DataFrame([{
      "name":r["name"],"lookback_h":r["lookback_h"],"prototype_outcome_h":r["prototype_outcome_h"],"q":r["q"],"threshold":r["threshold"],"viable":r["viable"],"viable_horizons":";".join(map(str,r["viable_horizons"])),
      "disc_n":r["discovery"].get("n"),"disc_win24":r["discovery"].get("win24"),"disc_mean24":r["discovery"].get("mean24"),"disc_mean72":r["discovery"].get("mean72"),"disc_mean168":r["discovery"].get("mean168"),
      "cal_n":r["calibration"].get("n"),"cal_win24":r["calibration"].get("win24"),"cal_mean24":r["calibration"].get("mean24"),"cal_mean72":r["calibration"].get("mean72"),"cal_mean168":r["calibration"].get("mean168")
    } for r in candidates]).to_csv(outdir/"candidates.csv",index=False)
    pd.DataFrame(proto_rows).to_csv(outdir/"prototypes.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (outdir/"REPORT.md").write_text("# Phase 10 Cross-Holdout-Gated Trajectory Families\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir)
