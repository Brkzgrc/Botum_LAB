from __future__ import annotations

import argparse, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

F1="btc1_tsi_d1"; F2="btc4_bb_width"
F1_MAX=-0.211069; F2_MIN=0.0942267
COST=0.20
BASE_URLS=[
    "https://data-api.binance.vision","https://api.binance.com",
    "https://api1.binance.com","https://api2.binance.com","https://api3.binance.com"
]
HTTP=requests.Session()
HTTP.headers.update({"User-Agent":"Botum-LAB-TSIBB-Phase3-MovementPath/1.0"})

def get_json(path,params=None,attempts=5):
    last=None
    for a in range(attempts):
        for b in BASE_URLS:
            try:
                r=HTTP.get(b+path,params=params or {},timeout=25)
                if r.status_code in (418,429):
                    last=RuntimeError(f"rate {r.status_code}"); continue
                r.raise_for_status(); return r.json()
            except Exception as e:
                last=e
        time.sleep(min(6,0.5*(2**a)))
    raise RuntimeError(last)

def fetch_15m(symbol,start,end):
    step=15*60*1000
    t=int(pd.Timestamp(start).timestamp()*1000); e=int(pd.Timestamp(end).timestamp()*1000)-1
    rows=[]
    while t<=e:
        a=get_json("/api/v3/klines",{
            "symbol":symbol,"interval":"15m","startTime":t,"endTime":e,"limit":1000
        })
        if not a: break
        rows.extend(a)
        last=int(a[-1][0])
        if len(a)<1000 or last+step<=t: break
        t=last+step
    if not rows: return pd.DataFrame()
    z=pd.DataFrame(rows,columns=[
        "ot","open","high","low","close","volume","ct","qv","trades","tb","tq","ignore"
    ])
    z=z.drop_duplicates("ot").sort_values("ot")
    for c in ["open","high","low","close","volume","qv"]:
        z[c]=pd.to_numeric(z[c],errors="coerce")
    z["time"]=pd.to_datetime(z.ot,unit="ms",utc=True)
    return z.set_index("time")[["open","high","low","close","volume","qv"]]

def pf(v):
    v=pd.to_numeric(v,errors="coerce").dropna()
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return float(gp/gl) if gl>0 else np.nan

def metrics(x):
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    return {
        "n":int(len(v)),
        "symbols":int(x.loc[v.index,"symbol"].nunique()),
        "win24":float((v>0).mean()*100),
        "mean24":float(v.mean()),
        "median24":float(v.median()),
        "pf24":pf(v),
        "p10_24":float(v.quantile(.10)),
        "up3_before_dn2":float(pd.to_numeric(x.loc[v.index,"up3_before_dn2"],errors="coerce").mean()*100),
        "danger_dn2_first":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100),
    }

def load_base(indir):
    fs=sorted(Path(indir).rglob("features.csv"))
    fr=[pd.read_csv(f,low_memory=False) for f in fs]
    fr=[x for x in fr if len(x)]
    if not fr: raise RuntimeError("no features")
    d=pd.concat(fr,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    for c in [F1,F2,"net_24h","up3_before_dn2","danger_dn2_first"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=[F1,F2,"net_24h"])
    # Frozen TSI+BB parent only. Phase 3 studies movement PATH after parent eligibility.
    d=d[(d[F1]<=F1_MAX)&(d[F2]>=F2_MIN)].copy()
    return d.sort_values(["symbol","decision_time"]).drop_duplicates(["symbol","decision_time"])

def ret(c,n):
    if len(c)<=n or c.iloc[-1-n]<=0: return np.nan
    return 100*(c.iloc[-1]/c.iloc[-1-n]-1)

def slope_last(s,n):
    z=pd.to_numeric(s.tail(n),errors="coerce").dropna()
    if len(z)<max(3,n//2): return np.nan
    y=z.to_numpy(float); x=np.arange(len(y),dtype=float)
    den=((x-x.mean())**2).sum()
    return float(((x-x.mean())*(y-y.mean())).sum()/den) if den>0 else np.nan

def path_features(coin,btc,t):
    # only fully CLOSED 15m candles before decision time
    z=coin[coin.index<t].tail(220).copy()
    b=btc[btc.index<t].tail(220).copy()
    if len(z)<200 or len(b)<200: return None

    c=z.close; h=z.high; l=z.low; v=z.volume
    bc=b.close

    f={}
    # 1) multi-horizon returns and acceleration of returns
    bars={"1h":4,"3h":12,"6h":24,"12h":48,"24h":96,"48h":192}
    for name,n in bars.items():
        f[f"ret_{name}"]=ret(c,n)
        f[f"btc_ret_{name}"]=ret(bc,n)
        f[f"rel_ret_{name}"]=f[f"ret_{name}"]-f[f"btc_ret_{name}"] if np.isfinite(f[f"ret_{name}"]) and np.isfinite(f[f"btc_ret_{name}"]) else np.nan

    f["accel_1_3"]=f["ret_1h"]-(f["ret_3h"]/3 if np.isfinite(f["ret_3h"]) else np.nan)
    f["accel_3_6"]=(f["ret_3h"]/3 if np.isfinite(f["ret_3h"]) else np.nan)-(f["ret_6h"]/6 if np.isfinite(f["ret_6h"]) else np.nan)
    f["rel_accel_1_6"]=f["rel_ret_1h"]-(f["rel_ret_6h"]/6 if np.isfinite(f["rel_ret_6h"]) else np.nan)

    # 2) drawdown -> stabilization -> rebound path
    hi24=float(h.tail(96).max()); lo24=float(l.tail(96).min()); last=float(c.iloc[-1])
    hi48=float(h.tail(192).max()); lo48=float(l.tail(192).min())
    f["dd24"]=100*(last/hi24-1) if hi24>0 else np.nan
    f["dd48"]=100*(last/hi48-1) if hi48>0 else np.nan
    f["offlow24"]=100*(last/lo24-1) if lo24>0 else np.nan
    f["offlow48"]=100*(last/lo48-1) if lo48>0 else np.nan
    # recovery ratio: where current price sits inside recent 24h/48h range
    f["range_pos24"]=(last-lo24)/(hi24-lo24) if hi24>lo24 else np.nan
    f["range_pos48"]=(last-lo48)/(hi48-lo48) if hi48>lo48 else np.nan

    # 3) path efficiency / chop vs directed move
    for name,n in [("6h",24),("12h",48),("24h",96)]:
        seg=c.tail(n+1)
        net=abs(float(seg.iloc[-1]-seg.iloc[0]))
        travel=float(seg.diff().abs().sum())
        f[f"eff_{name}"]=net/travel if travel>0 else np.nan

    # 4) realized volatility path: recent vs prior
    r=c.pct_change()
    rv_recent=float(r.tail(16).std(ddof=0)*100)
    rv_prev=float(r.iloc[-32:-16].std(ddof=0)*100)
    f["rv_4h"]=rv_recent
    f["rv_ratio_4h_prev"]=rv_recent/rv_prev if rv_prev>0 else np.nan

    # 5) volume path
    v4=float(v.tail(16).mean()); vprev=float(v.iloc[-32:-16].mean())
    v12=float(v.tail(48).mean()); v12prev=float(v.iloc[-96:-48].mean())
    f["vol_ratio_4h_prev"]=v4/vprev if vprev>0 else np.nan
    f["vol_ratio_12h_prev"]=v12/v12prev if v12prev>0 else np.nan
    f["vol_slope_4h"]=slope_last(v,16)

    # 6) Bollinger-width path: squeeze -> expansion, not absolute level only
    mid=c.rolling(20).mean(); sd=c.rolling(20).std(ddof=0)
    bbw=(4*sd)/mid.replace(0,np.nan)
    f["bbw_now"]=float(bbw.iloc[-1])
    f["bbw_d1h"]=float(bbw.iloc[-1]-bbw.iloc[-5]) if len(bbw)>=5 else np.nan
    f["bbw_ratio_4h_prev"]=float(bbw.tail(16).mean()/bbw.iloc[-32:-16].mean()) if float(bbw.iloc[-32:-16].mean())>0 else np.nan

    # 7) candle-direction / higher-low pressure path
    last16=z.tail(16)
    f["green_share_4h"]=float((last16.close>last16.open).mean())
    f["close_location_4h"]=float(((last16.close-last16.low)/(last16.high-last16.low).replace(0,np.nan)).mean())
    lows_a=float(l.iloc[-8:].min()); lows_b=float(l.iloc[-16:-8].min())
    highs_a=float(h.iloc[-8:].max()); highs_b=float(h.iloc[-16:-8].max())
    f["higher_low_2h"]=int(lows_a>lows_b)
    f["higher_high_2h"]=int(highs_a>highs_b)
    f["compression_up"]=int(lows_a>lows_b and highs_a<=highs_b*1.003)

    # 8) relative-strength trajectory vs BTC
    rel=(c/c.iloc[-97])/(bc/bc.iloc[-97]) if len(c)>=97 and len(bc)>=97 else None
    if rel is not None:
        f["rel_slope_6h"]=slope_last(rel,24)
        f["rel_slope_12h"]=slope_last(rel,48)
        f["rel_slope_24h"]=slope_last(rel,96)
        f["rel_accel_slope"]=f["rel_slope_6h"]-f["rel_slope_24h"] if np.isfinite(f["rel_slope_6h"]) and np.isfinite(f["rel_slope_24h"]) else np.nan

    # 9) reversal sequence categorical path
    # falling 12h + positive 3h + positive 1h = early rebound pattern
    f["fall_then_rebound"]=int(
        np.isfinite(f["ret_12h"]) and np.isfinite(f["ret_3h"]) and np.isfinite(f["ret_1h"]) and
        f["ret_12h"]<0 and f["ret_3h"]>0 and f["ret_1h"]>0
    )
    f["rel_lead_turn"]=int(
        np.isfinite(f["rel_ret_12h"]) and np.isfinite(f["rel_ret_3h"]) and
        f["rel_ret_12h"]<=0 and f["rel_ret_3h"]>0
    )
    return f

def enrich_symbol(symbol,g,btc):
    try:
        st=g.decision_time.min()-pd.Timedelta(days=4)
        en=g.decision_time.max()+pd.Timedelta(days=1)
        x=fetch_15m(symbol,st,en)
        if x.empty: return [],{"symbol":symbol,"error":"empty"}
        rows=[]
        for _,r in g.iterrows():
            f=path_features(x,btc,r.decision_time)
            if f is None: continue
            q=r.to_dict(); q.update(f); rows.append(q)
        return rows,None
    except Exception as e:
        return [],{"symbol":symbol,"error":repr(e)}

def search(d,outdir):
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))

    meta={"symbol","decision_time","entry_time","hash_mod","year","net_12h","net_24h","net_48h","net_72h","net_168h",
          "mfe_12h","mfe_24h","mfe_48h","mfe_72h","mfe_168h","mae_12h","mae_24h","mae_48h","mae_72h","mae_168h",
          "t_up3_h","t_dn2_h","up3_before_dn2","up3_within72","danger_dn2_first"}
    feats=[c for c in d.columns if c not in meta and c not in [F1,F2]]
    binary=[c for c in feats if set(pd.to_numeric(d[c],errors="coerce").dropna().unique()).issubset({0,1})]
    numeric=[c for c in feats if c not in binary and pd.to_numeric(d.loc[disc,c],errors="coerce").notna().sum()>=80]

    baseD=metrics(d[disc]); baseC=metrics(d[cal]); baseX=metrics(d[cross]); baseH=metrics(d[hold])

    singles=[]; masks={}
    for c in binary:
        m=pd.to_numeric(d[c],errors="coerce")==1
        md=metrics(d[disc&m]); mc=metrics(d[cal&m])
        if md.get("n",0)>=18 and mc.get("n",0)>=15:
            nm=f"{c}==1"; masks[nm]=m
            singles.append((nm,c,m,md,mc))
    for c in numeric:
        s=pd.to_numeric(d.loc[disc,c],errors="coerce").dropna()
        for q in [.20,.30,.40,.50,.60,.70,.80]:
            th=float(s.quantile(q))
            for side in ["GE","LE"]:
                m=(pd.to_numeric(d[c],errors="coerce")>=th) if side=="GE" else (pd.to_numeric(d[c],errors="coerce")<=th)
                md=metrics(d[disc&m]); mc=metrics(d[cal&m])
                if md.get("n",0)<18 or mc.get("n",0)<15: continue
                nm=f"{c}_{side}_Q{int(q*100)}({th:.6g})"; masks[nm]=m
                singles.append((nm,c,m,md,mc))

    # Keep only movement rules improving BOTH dev periods on economics, with no big WR collapse.
    stable=[]
    for nm,fam,m,md,mc in singles:
        if md["mean24"]<=baseD["mean24"] or mc["mean24"]<=baseC["mean24"]: continue
        if md["pf24"]<=baseD["pf24"] or mc["pf24"]<=baseC["pf24"]: continue
        if md["win24"]<baseD["win24"]-2 or mc["win24"]<baseC["win24"]-2: continue
        score=min(md["mean24"],mc["mean24"])+0.06*min(md["win24"],mc["win24"])+0.12*min(md["pf24"],mc["pf24"])
        stable.append({"name":nm,"family":fam,"score":score,"disc":md,"cal":mc})
    stable=sorted(stable,key=lambda x:x["score"],reverse=True)

    pairs=[]
    for i,a in enumerate(stable[:30]):
        for b in stable[i+1:30]:
            if a["family"]==b["family"]: continue
            m=masks[a["name"]]&masks[b["name"]]
            md=metrics(d[disc&m]); mc=metrics(d[cal&m])
            if md.get("n",0)<15 or mc.get("n",0)<12: continue
            if md["mean24"]<=baseD["mean24"] or mc["mean24"]<=baseC["mean24"]: continue
            if md["pf24"]<=baseD["pf24"] or mc["pf24"]<=baseC["pf24"]: continue
            if md["win24"]<baseD["win24"]-2 or mc["win24"]<baseC["win24"]-2: continue
            nm=a["name"]+" & "+b["name"]; masks[nm]=m
            score=min(md["mean24"],mc["mean24"])+0.06*min(md["win24"],mc["win24"])+0.12*min(md["pf24"],mc["pf24"])
            pairs.append({"name":nm,"families":[a["family"],b["family"]],"score":score,"disc":md,"cal":mc})
    pairs=sorted(pairs,key=lambda x:x["score"],reverse=True)

    # Cross-holdout gate before 2026 is revealed.
    cand=[("single",x) for x in stable[:20]]+[("pair",x) for x in pairs[:20]]
    finalists=[]
    for typ,x in cand:
        m=masks[x["name"]]; xm=metrics(d[cross&m])
        if xm.get("n",0)<10: continue
        if xm["mean24"]<=baseX["mean24"] or xm["pf24"]<=baseX["pf24"]: continue
        if xm["win24"]<baseX["win24"]: continue
        robust=min(x["disc"]["win24"],x["cal"]["win24"],xm["win24"])*0.08 +                min(x["disc"]["mean24"],x["cal"]["mean24"],xm["mean24"]) +                0.12*min(x["disc"]["pf24"],x["cal"]["pf24"],xm["pf24"])
        finalists.append((robust,typ,x,xm,m))
    finalists.sort(key=lambda z:z[0],reverse=True)

    out=[]
    for sc,typ,x,xm,m in finalists[:12]:
        hm=metrics(d[hold&m])
        out.append({"type":typ,"name":x["name"],"robust_pre2026_score":sc,
                    "discovery":x["disc"],"calibration":x["cal"],
                    "cross_holdout_pre2026":xm,"holdout_2026":hm})
    summary={
        "purpose":"Phase 3 movement-path research: track trajectories, acceleration, squeeze/expansion, volume path, structure path and coin-vs-BTC relative path after frozen TSI+BB parent eligibility.",
        "cost_pct":COST,
        "selection_uses_2026":False,
        "base":{"discovery":baseD,"calibration":baseC,"cross_holdout_pre2026":baseX,"holdout_2026":baseH},
        "movement_feature_count":len(feats),
        "stable_singles_pre2026_dev":len(stable),
        "stable_pairs_pre2026_dev":len(pairs),
        "finalists_after_cross_holdout":len(finalists),
        "top_finalists":out
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{
        "type":x["type"],"name":x["name"],"score":x["robust_pre2026_score"],
        "d_n":x["discovery"]["n"],"d_win":x["discovery"]["win24"],"d_mean":x["discovery"]["mean24"],"d_pf":x["discovery"]["pf24"],
        "c_n":x["calibration"]["n"],"c_win":x["calibration"]["win24"],"c_mean":x["calibration"]["mean24"],"c_pf":x["calibration"]["pf24"],
        "x_n":x["cross_holdout_pre2026"]["n"],"x_win":x["cross_holdout_pre2026"]["win24"],"x_mean":x["cross_holdout_pre2026"]["mean24"],"x_pf":x["cross_holdout_pre2026"]["pf24"],
        "h_n":x["holdout_2026"]["n"],"h_win":x["holdout_2026"]["win24"],"h_mean":x["holdout_2026"]["mean24"],"h_pf":x["holdout_2026"]["pf24"]
    } for x in out]).to_csv(outdir/"top_finalists.csv",index=False)
    print(json.dumps(summary,ensure_ascii=False))

def main(artifact_dir,outdir,workers):
    d=load_base(artifact_dir)
    global_start=d.decision_time.min()-pd.Timedelta(days=4)
    global_end=d.decision_time.max()+pd.Timedelta(days=1)
    btc=fetch_15m("BTCUSDT",global_start,global_end)
    groups=[(s,g.copy()) for s,g in d.groupby("symbol")]
    rows=[]; errs=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(enrich_symbol,s,g,btc):s for s,g in groups}
        for k,f in enumerate(as_completed(fut),1):
            rr,e=f.result(); rows.extend(rr)
            if e: errs.append(e)
            if k%25==0 or k==len(fut):
                print(f"{k}/{len(fut)} enriched={len(rows)} errors={len(errs)}",flush=True)
    z=pd.DataFrame(rows)
    outdir.mkdir(parents=True,exist_ok=True)
    z.to_csv(outdir/"movement_enriched_events.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    search(z,outdir)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=10)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir,a.workers)
