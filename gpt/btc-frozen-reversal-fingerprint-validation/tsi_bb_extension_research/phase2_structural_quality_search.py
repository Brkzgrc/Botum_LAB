from __future__ import annotations

import argparse, json, math, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

F1="btc1_tsi_d1"; F2="btc4_bb_width"
F1_MAX=-0.211069; F2_MIN=0.0942267
COST=0.20
BASE_URLS=["https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com","https://api2.binance.com","https://api3.binance.com"]
HTTP=requests.Session(); HTTP.headers.update({"User-Agent":"Botum-LAB-TSIBB-Phase2/1.0"})

def get_json(path,params=None,attempts=5):
    last=None
    for a in range(attempts):
        for b in BASE_URLS:
            try:
                r=HTTP.get(b+path,params=params or {},timeout=25)
                if r.status_code in (418,429):
                    last=RuntimeError(f"rate {r.status_code}"); continue
                r.raise_for_status(); return r.json()
            except Exception as e: last=e
        time.sleep(min(6,0.5*(2**a)))
    raise RuntimeError(last)

def fetch_15m(symbol,start,end):
    step=15*60*1000
    t=int(pd.Timestamp(start).timestamp()*1000); e=int(pd.Timestamp(end).timestamp()*1000)-1
    rows=[]
    while t<=e:
        a=get_json("/api/v3/klines",{"symbol":symbol,"interval":"15m","startTime":t,"endTime":e,"limit":1000})
        if not a: break
        rows.extend(a)
        last=int(a[-1][0])
        if len(a)<1000 or last+step<=t: break
        t=last+step
    if not rows: return pd.DataFrame()
    z=pd.DataFrame(rows,columns=["ot","open","high","low","close","volume","ct","qv","trades","tb","tq","ignore"])
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
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
            "win24":float((v>0).mean()*100),"mean24":float(v.mean()),
            "median24":float(v.median()),"pf24":pf(v),
            "p10_24":float(v.quantile(.10)),
            "up3_before_dn2":float(pd.to_numeric(x.loc[v.index,"up3_before_dn2"],errors="coerce").mean()*100),
            "danger_dn2_first":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100)}

def load_base(indir):
    fs=sorted(Path(indir).rglob("features.csv"))
    fr=[pd.read_csv(f,low_memory=False) for f in fs]; fr=[x for x in fr if len(x)]
    if not fr: raise RuntimeError("no features")
    d=pd.concat(fr,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    for c in [F1,F2,"net_24h","up3_before_dn2","danger_dn2_first"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=[F1,F2,"net_24h"])
    d=d[(d[F1]<=F1_MAX)&(d[F2]>=F2_MIN)].copy()
    return d.sort_values(["symbol","decision_time"]).drop_duplicates(["symbol","decision_time"])

def atr14(x):
    pc=x.close.shift(1)
    tr=pd.concat([(x.high-x.low).abs(),(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()

def structural_features(base,row):
    t=pd.Timestamp(row.decision_time)
    z=base[base.index<t].tail(240).copy()  # closed candles only
    if len(z)<120: return None
    o,h,l,c,v=z.open,z.high,z.low,z.close,z.volume

    prev=z.iloc[-2]; cur=z.iloc[-1]
    body=abs(cur.close-cur.open); rng=max(cur.high-cur.low,1e-12)
    lower=min(cur.open,cur.close)-cur.low
    upper=cur.high-max(cur.open,cur.close)

    bullish_engulf=int(cur.close>cur.open and prev.close<prev.open and cur.open<=prev.close and cur.close>=prev.open)
    hammer=int(cur.close>=cur.open and lower>=2*max(body,1e-12) and upper<=max(body,1e-12))
    pinbull=int(lower/rng>=0.50 and cur.close>=cur.low+0.60*rng)

    # Causal local structure from left-only rolling extrema.
    recent_high_8=float(h.iloc[-9:-1].max())
    recent_high_16=float(h.iloc[-17:-1].max())
    recent_low_8=float(l.iloc[-9:-1].min())
    recent_low_16=float(l.iloc[-17:-1].min())
    break8=int(cur.close>recent_high_8)
    break16=int(cur.close>recent_high_16)
    hl8=int(recent_low_8>float(l.iloc[-17:-9].min())) if len(z)>=17 else 0

    ema20=c.ewm(span=20,adjust=False).mean().iloc[-1]
    ema50=c.ewm(span=50,adjust=False).mean().iloc[-1]
    ema200=c.ewm(span=200,adjust=False).mean().iloc[-1] if len(z)>=200 else np.nan
    ema_stack=int(np.isfinite(ema200) and cur.close>ema20>ema50>ema200)
    above50=int(cur.close>ema50)

    a=atr14(z).iloc[-1]
    atr_pct=100*a/cur.close if np.isfinite(a) and cur.close>0 else np.nan
    rvol=float(v.iloc[-1]/v.iloc[-20:].mean()) if v.iloc[-20:].mean()>0 else np.nan

    # Headroom to prior 48h/72h high, excluding current candle.
    hi48=float(h.iloc[-193:-1].max()) if len(z)>=193 else float(h.iloc[:-1].max())
    hi72=float(h.iloc[-240:-1].max())
    head48=100*(hi48/cur.close-1) if cur.close>0 else np.nan
    head72=100*(hi72/cur.close-1) if cur.close>0 else np.nan

    # Pullback location and "room/risk" proxy: nearest prior high vs recent 8-bar swing low.
    swing_low=recent_low_8
    risk=100*(cur.close/swing_low-1) if swing_low>0 else np.nan
    rr48=head48/risk if np.isfinite(risk) and risk>0 else np.nan

    # Compression / repeated resistance pressure proxies.
    hh8=float(h.iloc[-8:].max()); ll8=float(l.iloc[-8:].min())
    range8=100*(hh8/ll8-1) if ll8>0 else np.nan
    lows4=[float(l.iloc[-4:].min()),float(l.iloc[-8:-4].min())]
    rising_lows=int(lows4[0]>lows4[1])

    return {
      "bullish_engulf":bullish_engulf,"hammer":hammer,"pinbull":pinbull,
      "break8":break8,"break16":break16,"hl8":hl8,"rising_lows":rising_lows,
      "ema_stack":ema_stack,"above50":above50,
      "atr_pct":atr_pct,"rvol20":rvol,"head48":head48,"head72":head72,
      "risk8":risk,"rr48":rr48,"range8":range8,
      "close_pos":float((cur.close-cur.low)/rng),
      "lower_wick_ratio":float(lower/rng),
    }

def enrich_symbol(symbol,g):
    try:
        st=g.decision_time.min()-pd.Timedelta(days=4)
        en=g.decision_time.max()+pd.Timedelta(days=1)
        x=fetch_15m(symbol,st,en)
        if x.empty: return [],{"symbol":symbol,"error":"empty"}
        rows=[]
        for _,r in g.iterrows():
            f=structural_features(x,r)
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

    binary=["bullish_engulf","hammer","pinbull","break8","break16","hl8","rising_lows","ema_stack","above50"]
    numeric=["atr_pct","rvol20","head48","head72","risk8","rr48","range8","close_pos","lower_wick_ratio"]

    rules=[]
    masks={}
    for c in binary:
        if c in d:
            m=d[c]==1; rules.append((c+"==1",m,c))
    for c in numeric:
        s=pd.to_numeric(d.loc[disc,c],errors="coerce").dropna()
        if len(s)<80: continue
        for q in [.25,.40,.50,.60,.75]:
            th=float(s.quantile(q))
            for side in ["GE","LE"]:
                m=(pd.to_numeric(d[c],errors="coerce")>=th) if side=="GE" else (pd.to_numeric(d[c],errors="coerce")<=th)
                rules.append((f"{c}{side}Q{int(q*100)}({th:.5g})",m,c))

    rows=[]
    baseD=metrics(d[disc]); baseC=metrics(d[cal])
    for nm,m,fam in rules:
        md=metrics(d[disc&m]); mc=metrics(d[cal&m])
        if md.get("n",0)<18 or mc.get("n",0)<15: continue
        # must improve both dev splits in return and not crater win rate
        if md["mean24"]<=baseD["mean24"] or mc["mean24"]<=baseC["mean24"]: continue
        if md["win24"]<baseD["win24"]-3 or mc["win24"]<baseC["win24"]-3: continue
        score=min(md["mean24"],mc["mean24"])+0.05*min(md["win24"],mc["win24"])+0.12*min(md["pf24"],mc["pf24"])
        rows.append({"name":nm,"family":fam,"score":score,"disc":md,"cal":mc})
        masks[nm]=m

    singles=sorted(rows,key=lambda x:x["score"],reverse=True)
    pairs=[]
    top=singles[:25]
    for i,a in enumerate(top):
      for b in top[i+1:]:
        if a["family"]==b["family"]: continue
        m=masks[a["name"]]&masks[b["name"]]
        md=metrics(d[disc&m]); mc=metrics(d[cal&m])
        if md.get("n",0)<15 or mc.get("n",0)<12: continue
        if md["mean24"]<=baseD["mean24"] or mc["mean24"]<=baseC["mean24"]: continue
        if md["win24"]<baseD["win24"]-2 or mc["win24"]<baseC["win24"]-2: continue
        score=min(md["mean24"],mc["mean24"])+0.05*min(md["win24"],mc["win24"])+0.12*min(md["pf24"],mc["pf24"])
        nm=a["name"]+" & "+b["name"]
        pairs.append({"name":nm,"families":[a["family"],b["family"]],"score":score,"disc":md,"cal":mc})
        masks[nm]=m
    pairs=sorted(pairs,key=lambda x:x["score"],reverse=True)

    # Final candidate selection is pre-2026 only, using Discovery+Calibration and requiring cross-holdout to stay profitable.
    pool=[("single",x) for x in singles[:15]]+[("pair",x) for x in pairs[:15]]
    finalists=[]
    for typ,x in pool:
        m=masks[x["name"]]
        xc=metrics(d[cross&m])
        if xc.get("n",0)<10 or xc["mean24"]<=0 or xc["pf24"]<=1.1: continue
        # stronger preference: high success + good mean P&L, but minimum sample retained
        pre=min(x["disc"]["win24"],x["cal"]["win24"],xc["win24"])
        gain=min(x["disc"]["mean24"],x["cal"]["mean24"],xc["mean24"])
        robust_score=pre*0.08+gain+0.15*min(x["disc"]["pf24"],x["cal"]["pf24"],xc["pf24"])
        finalists.append((robust_score,typ,x,xc,m))
    finalists.sort(key=lambda z:z[0],reverse=True)

    report=[]
    for sc,typ,x,xc,m in finalists[:10]:
        h=metrics(d[hold&m])
        report.append({"type":typ,"name":x["name"],"robust_pre2026_score":sc,
                       "discovery":x["disc"],"calibration":x["cal"],
                       "cross_holdout_pre2026":xc,"holdout_2026":h})
    summary={
      "purpose":"Phase 2 structural confirmation/veto search on frozen TSI+BB events. Optimize high win24 and meaningful mean24 without using 2026 for selection.",
      "cost_pct":COST,
      "selection_uses_2026":False,
      "base":{"discovery":baseD,"calibration":baseC,"cross_holdout_pre2026":metrics(d[cross]),"holdout_2026":metrics(d[hold])},
      "single_candidates_passing_dev":len(singles),"pair_candidates_passing_dev":len(pairs),
      "finalists_passing_pre2026_cross_holdout":len(finalists),
      "top_finalists":report
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{"type":x["type"],"name":x["name"],"score":x["robust_pre2026_score"],
                   "d_n":x["discovery"]["n"],"d_win":x["discovery"]["win24"],"d_mean":x["discovery"]["mean24"],
                   "c_n":x["calibration"]["n"],"c_win":x["calibration"]["win24"],"c_mean":x["calibration"]["mean24"],
                   "x_n":x["cross_holdout_pre2026"]["n"],"x_win":x["cross_holdout_pre2026"]["win24"],"x_mean":x["cross_holdout_pre2026"]["mean24"],
                   "h_n":x["holdout_2026"]["n"],"h_win":x["holdout_2026"]["win24"],"h_mean":x["holdout_2026"]["mean24"],"h_pf":x["holdout_2026"]["pf24"]}
                  for x in report]).to_csv(outdir/"top_finalists.csv",index=False)
    print(json.dumps(summary,ensure_ascii=False))

def main(artifact_dir,outdir,workers):
    d=load_base(artifact_dir)
    groups=[(s,g.copy()) for s,g in d.groupby("symbol")]
    rows=[]; errs=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(enrich_symbol,s,g):s for s,g in groups}
        for k,f in enumerate(as_completed(fut),1):
            rr,e=f.result(); rows.extend(rr)
            if e: errs.append(e)
            if k%25==0 or k==len(fut): print(f"{k}/{len(fut)} enriched={len(rows)} errors={len(errs)}",flush=True)
    z=pd.DataFrame(rows)
    outdir.mkdir(parents=True,exist_ok=True)
    z.to_csv(outdir/"enriched_events.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    search(z,outdir)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=10)
    a=ap.parse_args(); main(a.artifact_dir,a.outdir,a.workers)
