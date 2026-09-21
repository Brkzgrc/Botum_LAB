from __future__ import annotations
import argparse, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np, pandas as pd, requests

R2_BB=0.19233492
R2_DD=-7.3594696
BASES=["https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com","https://api2.binance.com","https://api3.binance.com"]
HTTP=requests.Session(); HTTP.headers.update({"User-Agent":"Botum-LAB-TSI-BB-Phase6/1.0"})

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
    d=pd.concat([pd.read_csv(f,low_memory=False) for f in fs],ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    for c in ["btc1_tsi_d1","btc4_bb_width","h4_bb_width","net_24h"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["btc1_tsi_d1","btc4_bb_width","h4_bb_width","net_24h"]).copy()
    d=d[(d.btc1_tsi_d1<=-0.211069)&(d.btc4_bb_width>=0.0942267)].copy()
    d=d.sort_values(["symbol","decision_time"]).drop_duplicates(["symbol","decision_time"]).reset_index(drop=True)
    return d

def fetch_path(row):
    t=pd.Timestamp(row.decision_time)
    end_ms=int(t.timestamp()*1000)-1
    start_ms=int((t-pd.Timedelta(hours=48)).timestamp()*1000)
    try:
        z=get_json("/api/v3/klines",{"symbol":str(row.symbol),"interval":"15m","startTime":start_ms,"endTime":end_ms,"limit":1000})
        if not isinstance(z,list) or len(z)<193: return row.row_id,None,f"short:{len(z) if isinstance(z,list) else -1}"
        a=np.array([float(x[4]) for x in z[-193:]],float)
        h=np.array([float(x[2]) for x in z[-193:]],float)
        ref=a[-1]
        dd=(ref/h.max()-1)*100
        # Track real movement path: normalized log-price at fixed lags across 48h.
        lags=[192,160,128,96,72,48,32,24,16,12,8,4,0]
        p=np.log(a/a[0])*100
        vec=np.array([p[-1-k] for k in lags[::-1]],float)
        # Convert to chronological path relative to its first sampled point.
        vec=vec-vec[0]
        return row.row_id,(vec,dd),None
    except Exception as e:
        return row.row_id,None,repr(e)

def metrics(x):
    if len(x)==0:return {"n":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v):return {"n":0}
    gp=float(v[v>0].sum()); gl=float(-v[v<0].sum())
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
            "win24":float((v>0).mean()*100),"mean24":float(v.mean()),
            "median24":float(v.median()),"pf24":float(gp/gl) if gl>0 else None,
            "p10":float(v.quantile(.10))}

def zdist(X,proto,scale):
    return np.sqrt(np.nanmean(((X-proto)/scale)**2,axis=1))

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
            if k%50==0 or k==len(fut): print(f"[PATH] {k}/{len(fut)} ok={len(res)} err={len(errs)}",flush=True)
    good=d[d.row_id.isin(res)].copy()
    X=np.vstack([res[int(i)][0] for i in good.row_id])
    good["causal_dd_high_48h"]=[res[int(i)][1] for i in good.row_id]
    r2=(good.h4_bb_width>=R2_BB)&(good.causal_dd_high_48h<=R2_DD)

    t=good.decision_time
    disc=(good.hash_mod>=30)&(t<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(good.hash_mod>=30)&(t>=pd.Timestamp("2025-01-01",tz="UTC"))&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(good.hash_mod<30)&(t<pd.Timestamp("2026-01-01",tz="UTC"))
    all26=t>=pd.Timestamp("2026-01-01",tz="UTC")

    # Reverse engineer complete 48h trajectory from discovery r2 winners/losers.
    win=disc&r2&(good.net_24h>0); los=disc&r2&(good.net_24h<=0)
    if win.sum()<8 or los.sum()<3: raise RuntimeError(f"not enough discovery r2 winner/loss paths: {win.sum()}/{los.sum()}")
    pw=np.nanmedian(X[win.to_numpy()],axis=0)
    pl=np.nanmedian(X[los.to_numpy()],axis=0)
    scale=np.nanpercentile(X[disc.to_numpy()],75,axis=0)-np.nanpercentile(X[disc.to_numpy()],25,axis=0)
    scale=np.where(np.isfinite(scale)&(scale>1e-6),scale,1.0)
    dw=zdist(X,pw,scale); dl=zdist(X,pl,scale)
    score=dl-dw
    good["trajectory_score"]=score

    # Search only non-r2 baseline TSI+BB events. Thresholds fixed from DISCOVERY.
    pool=~r2
    sd=good.loc[disc&pool,"trajectory_score"].dropna()
    qs=[.50,.60,.70,.75,.80,.85,.90,.925,.95]
    rows=[]; masks={}
    for q in qs:
        th=float(sd.quantile(q))
        m=pool&(good.trajectory_score>=th)
        md=metrics(good[disc&m]); mc=metrics(good[cal&m])
        if md.get("n",0)<10 or mc.get("n",0)<8: continue
        nm=f"NON_R2_TRAJECTORY_Q{int(q*1000)}"
        rows.append({"name":nm,"q":q,"threshold":th,
                     "disc_n":md["n"],"cal_n":mc["n"],"disc_win":md["win24"],"cal_win":mc["win24"],
                     "disc_mean":md["mean24"],"cal_mean":mc["mean24"],"disc_pf":md["pf24"],"cal_pf":mc["pf24"]})
        masks[nm]=m
    tab=pd.DataFrame(rows)
    viable=pd.DataFrame()
    if len(tab):
        viable=tab[(tab.disc_win>=55)&(tab.cal_win>=55)&(tab.disc_mean>0.5)&(tab.cal_mean>0.5)&(tab.disc_pf>1.2)&(tab.cal_pf>1.2)].copy()
        if len(viable):
            viable["score"]=np.minimum(viable.disc_mean,viable.cal_mean)+.04*np.minimum(viable.disc_win,viable.cal_win)+.1*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))
            viable=viable.sort_values("score",ascending=False)

    weeks26=(pd.Timestamp("2026-09-18",tz="UTC")-pd.Timestamp("2026-01-01",tz="UTC")).days/7
    top=[]
    for _,r in viable.head(8).iterrows():
        m=masks[r["name"]]; combo=r2|m
        top.append({"name":r["name"],
                    "second":{"discovery":metrics(good[disc&m]),"calibration":metrics(good[cal&m]),"cross_pre2026":metrics(good[cross&m]),"all_2026":metrics(good[all26&m])},
                    "combined":{"discovery":metrics(good[disc&combo]),"calibration":metrics(good[cal&combo]),"cross_pre2026":metrics(good[cross&combo]),"all_2026":metrics(good[all26&combo]),"signals_per_week_2026":metrics(good[all26&combo]).get("n",0)/weeks26}})
    summary={"method":"Direct 48h 15m pre-entry trajectory reverse engineering from r2 winners vs losers; nearest trajectory search on non-r2 TSI+BB events",
             "selection_uses_2026":False,"events":len(good),"path_points":13,"errors":len(errs),
             "r2":{"discovery":metrics(good[disc&r2]),"calibration":metrics(good[cal&r2]),"cross_pre2026":metrics(good[cross&r2]),"all_2026":metrics(good[all26&r2]),"signals_per_week_2026":metrics(good[all26&r2]).get("n",0)/weeks26},
             "thresholds_tested":len(tab),"viable_pre2026":len(viable),"top":top}
    tab.to_csv(outdir/"trajectory_candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)
    pd.DataFrame({"winner_proto":pw,"loser_proto":pl,"scale":scale}).to_csv(outdir/"trajectory_prototypes.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (outdir/"REPORT.md").write_text("# Phase 6 Direct Movement Trajectory Reverse Engineering\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--artifact-dir",type=Path,required=True); ap.add_argument("--outdir",type=Path,required=True)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir)
