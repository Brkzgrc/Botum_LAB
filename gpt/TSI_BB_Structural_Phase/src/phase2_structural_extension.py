from __future__ import annotations

import argparse, json, math, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
CORE=Path(__file__).resolve().parents[1]/"lib"
sys.path.insert(0,str(CORE))
import coin_mtf_core_snapshot as core

F1="btc1_tsi_d1"; F2="btc4_bb_width"
COST=0.20

def confirmed_pivots(df,k=2):
    hi=df.high.to_numpy(float); lo=df.low.to_numpy(float); idx=df.index
    ph=[]; pl=[]
    for i in range(k,len(df)-k):
        if all(hi[i]>hi[j] for j in range(i-k,i+k+1) if j!=i): ph.append((idx[i+k],hi[i]))
        if all(lo[i]<lo[j] for j in range(i-k,i+k+1) if j!=i): pl.append((idx[i+k],lo[i]))
    return ph,pl

def latest(seq,t,n=2):
    # seq is sorted by confirmation time
    # binary search would be faster, but event count is modest after broad prefilter.
    a=[x for x in seq if x[0]<=t]
    return a[-n:]

def atr14(x):
    pc=x.close.shift(1)
    tr=pd.concat([(x.high-x.low).abs(),(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()

def align_closed(df,delta,decision_index):
    z=df.copy(); z.index=z.index+delta
    return z.reindex(decision_index,method="ffill")

def extract_symbol(symbol,ev):
    try:
        lo=ev.decision_time.min()-pd.Timedelta(days=35)
        hi=ev.decision_time.max()+pd.Timedelta(days=3)
        b=core.fetch_15m(symbol,start=lo,end=hi)
        t15=core.indicators(b)
        h1=core.indicators(core.resample(b,"1h"))
        h4=core.indicators(core.resample(b,"4h"))
        ph15,pl15=confirmed_pivots(b,2)
        ph1,pl1=confirmed_pivots(core.resample(b,"1h"),2)

        a15=atr14(b)
        prev48h=b.high.shift(1).rolling(192,min_periods=48).max()
        prev24low=b.low.shift(1).rolling(96,min_periods=32).min()
        rows=[]

        for _,e in ev.iterrows():
            t=e.decision_time
            # decision_time is a boundary at which the prior 15m candle is closed.
            closed=t-pd.Timedelta(minutes=15)
            if closed not in t15.index: continue
            i=t15.index.get_loc(closed)
            if not isinstance(i,(int,np.integer)) or i<5: continue
            r=t15.iloc[i]; prev=t15.iloc[i-1]
            close=float(r.close)
            # exact video-inspired candle confirmation: prior candle is bullish reaction, current closed candle breaks its high.
            prev_reaction=bool(prev.get("bull_engulf",False) or prev.get("hammer",False) or prev.get("sweep_reclaim",False))
            candle_high_break=bool(prev_reaction and close>float(prev.high))
            reaction_now=bool(r.get("bull_engulf",False) or r.get("hammer",False) or r.get("sweep_reclaim",False))
            reclaim_prev_high=bool(r.get("reclaim_prev_high",False))
            hl_hh=bool(r.get("higher_low",False) and r.get("higher_high",False))

            hs15=latest(ph15,t,1); ls15=latest(pl15,t,2)
            choch_hl=False
            swing_low=np.nan
            if len(ls15)>=2 and len(hs15)>=1:
                swing_low=float(ls15[-1][1])
                sh=float(hs15[-1][1])
                prev_close=float(t15.close.iloc[i-1])
                choch_hl=bool(ls15[-1][1]>ls15[-2][1] and prev_close<=sh and close>sh)

            hs1=latest(ph1,t,2); ls1=latest(pl1,t,2)
            h1_bear=False; h1_bull=False
            if len(hs1)>=2 and len(ls1)>=2:
                h1_bear=bool(hs1[-1][1]<hs1[-2][1] and ls1[-1][1]<ls1[-2][1])
                h1_bull=bool(hs1[-1][1]>hs1[-2][1] and ls1[-1][1]>ls1[-2][1])

            at=float(a15.loc[closed]) if closed in a15.index and pd.notna(a15.loc[closed]) else np.nan
            atr_pct=100*at/close if np.isfinite(at) and close>0 else np.nan
            room48=100*(float(prev48h.loc[closed])/close-1) if closed in prev48h.index and pd.notna(prev48h.loc[closed]) else np.nan
            sl=swing_low if np.isfinite(swing_low) else (float(prev24low.loc[closed]) if closed in prev24low.index and pd.notna(prev24low.loc[closed]) else np.nan)
            risk_pct=100*(close-sl)/close if np.isfinite(sl) and sl<close else np.nan
            rr_proxy=(room48/risk_pct) if np.isfinite(room48) and np.isfinite(risk_pct) and room48>0 and risk_pct>0 else np.nan

            rec=e.to_dict()
            rec.update({
              "candle_high_break":int(candle_high_break),
              "reaction_now":int(reaction_now),
              "reclaim_prev_high":int(reclaim_prev_high),
              "hl_hh":int(hl_hh),
              "choch_hl":int(choch_hl),
              "h1_bear":int(h1_bear),
              "h1_bull":int(h1_bull),
              "atr15_pct":atr_pct,
              "room48_pct":room48,
              "risk_to_swing_pct":risk_pct,
              "rr_proxy":rr_proxy,
            })
            rows.append(rec)
        return pd.DataFrame(rows),None
    except Exception as ex:
        return None,{"symbol":symbol,"error":repr(ex)}

def metrics(x):
    if len(x)==0:return {"n":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v):return {"n":0}
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
      "win24":float((v>0).mean()*100),"mean24":float(v.mean()),"median24":float(v.median()),
      "pf24":float(gp/gl) if gl>0 else None,"p10":float(v.quantile(.10)),
      "up3_before_dn2":float(pd.to_numeric(x.loc[v.index,"up3_before_dn2"],errors="coerce").mean()*100),
      "danger_dn2_first":float(pd.to_numeric(x.loc[v.index,"danger_dn2_first"],errors="coerce").mean()*100)}

def shard(indir,outdir,shard_id,shards):
    fs=sorted(indir.rglob("features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    d=pd.concat([x for x in frames if len(x)],ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [F1,F2]: d[c]=pd.to_numeric(d[c],errors="coerce")
    # broad envelope from phase 1 grid; structural layer will recover quality.
    d=d[(d[F1]<=0.10)&(d[F2]>=0.045)].copy()
    syms=sorted(d.symbol.astype(str).unique())
    mine=[s for i,s in enumerate(syms) if i%shards==shard_id]
    frames=[]; errs=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut={ex.submit(extract_symbol,s,d[d.symbol.astype(str)==s].copy()):s for s in mine}
        for k,f in enumerate(as_completed(fut),1):
            x,e=f.result()
            if e: errs.append(e)
            elif x is not None and len(x): frames.append(x)
            if k%10==0 or k==len(fut): print(f"[{shard_id}] {k}/{len(fut)} rows={sum(len(x) for x in frames)} err={len(errs)}",flush=True)
    outdir.mkdir(parents=True,exist_ok=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"structure.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    (outdir/"meta.json").write_text(json.dumps({"shard":shard_id,"symbols":len(mine),"rows":len(out),"errors":len(errs)},indent=2),encoding="utf-8")

def aggregate(indir,outdir):
    fs=sorted(indir.rglob("structure.csv"))
    d=pd.concat([pd.read_csv(f,low_memory=False) for f in fs if f.stat().st_size>0],ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [F1,F2,"net_24h"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))

    f1_grid=[-0.211069,-0.15,-0.10,-0.05,0.0,0.05,0.10]
    f2_grid=[0.0942267,0.085,0.075,0.065,0.055,0.045]
    structural={
      "CANDLE_HIGH_BREAK": lambda x:x.candle_high_break==1,
      "CHOCH_HL":lambda x:x.choch_hl==1,
      "REACTION_OR_RECLAIM":lambda x:(x.reaction_now==1)|(x.reclaim_prev_high==1),
      "HL_HH":lambda x:x.hl_hh==1,
      "NOT_H1_BEAR":lambda x:x.h1_bear==0,
      "H1_BULL":lambda x:x.h1_bull==1,
      "CHOCH_OR_CANDLE_BREAK":lambda x:(x.choch_hl==1)|(x.candle_high_break==1),
      "REACTION_PLUS_NOT_BEAR":lambda x:((x.reaction_now==1)|(x.reclaim_prev_high==1))&(x.h1_bear==0),
      "CHOCH_PLUS_NOT_BEAR":lambda x:(x.choch_hl==1)&(x.h1_bear==0),
      "RR_GE_1":lambda x:pd.to_numeric(x.rr_proxy,errors="coerce")>=1.0,
      "RR_GE_1_5":lambda x:pd.to_numeric(x.rr_proxy,errors="coerce")>=1.5,
      "ROOM48_GE_2":lambda x:pd.to_numeric(x.room48_pct,errors="coerce")>=2.0,
      "RISK_LE_6":lambda x:pd.to_numeric(x.risk_to_swing_pct,errors="coerce")<=6.0,
    }

    wd=(pd.Timestamp("2025-01-01",tz="UTC")-pd.Timestamp("2023-01-01",tz="UTC")).days/7
    wc=365/7
    rows=[]; masks={}
    for a in f1_grid:
      for b in f2_grid:
        base=(d[F1]<=a)&(d[F2]>=b)
        for nm,fn in structural.items():
            m=base&fn(d)
            md=metrics(d[disc&m]); mc=metrics(d[cal&m])
            if md.get("n",0)<25 or mc.get("n",0)<15: continue
            fd=md["n"]/wd; fc=mc["n"]/wc
            name=f"TSI<={a}|BB>={b}|{nm}"
            rows.append({"name":name,"f1":a,"f2":b,"structure":nm,"disc_freq":fd,"cal_freq":fc,
              "disc_win":md["win24"],"cal_win":mc["win24"],"disc_mean":md["mean24"],"cal_mean":mc["mean24"],
              "disc_pf":md["pf24"],"cal_pf":mc["pf24"],"disc_p10":md["p10"],"cal_p10":mc["p10"]})
            masks[name]=m
    tab=pd.DataFrame(rows)
    viable=tab[(tab.disc_freq>=3)&(tab.cal_freq>=3)&(tab.disc_freq<=15)&(tab.cal_freq<=15)&
               (tab.disc_mean>0.75)&(tab.cal_mean>0.75)&(tab.disc_pf>1.3)&(tab.cal_pf>1.3)&
               (tab.disc_win>=55)&(tab.cal_win>=55)].copy()
    if len(viable):
        viable["score"]=np.minimum(viable.disc_mean,viable.cal_mean)+0.05*np.minimum(viable.disc_win,viable.cal_win)+0.12*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))-0.05*(abs(viable.disc_freq-6)+abs(viable.cal_freq-6))
        viable=viable.sort_values("score",ascending=False)

    outdir.mkdir(parents=True,exist_ok=True)
    tab.to_csv(outdir/"all_structural_candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)
    top=[]
    for _,r in viable.head(15).iterrows():
        m=masks[r["name"]]
        top.append({"name":r["name"],"discovery":metrics(d[disc&m]),"calibration":metrics(d[cal&m]),
          "cross_holdout_pre2026":metrics(d[cross&m]),"holdout_2026":metrics(d[hold&m]),
          "holdout_2026_signals_per_week":metrics(d[hold&m]).get("n",0)/((pd.Timestamp("2026-09-18",tz="UTC")-pd.Timestamp("2026-01-01",tz="UTC")).days/7)})
    summary={"selection_uses_2026":False,"cost_pct":COST,"rows":len(d),"tested":len(tab),"viable_pre2026":len(viable),"top":top}
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Structural Extension Phase 2","",f"rows={len(d)} tested={len(tab)} viable={len(viable)}","",
           "Selection uses only 2023-25; 2026 is read only after pre-2026 selection.","","## Top"]
    for x in top: lines.append("- "+json.dumps(x,ensure_ascii=False))
    (outdir/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--shard",type=int)
    ap.add_argument("--shards",type=int,default=8)
    ap.add_argument("--aggregate-dir",type=Path)
    a=ap.parse_args()
    if a.aggregate_dir: aggregate(a.aggregate_dir,a.outdir)
    else: shard(a.artifact_dir,a.outdir,a.shard,a.shards)
