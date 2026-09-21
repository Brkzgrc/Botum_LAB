from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"lib"))
import coin_mtf_core_snapshot as core

F1="btc1_tsi_d1"; F2="btc4_bb_width"

def metrics(x):
    if len(x)==0: return {"n":0}
    v=pd.to_numeric(x.net_24h,errors="coerce").dropna()
    if not len(v): return {"n":0}
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return {"n":int(len(v)),"symbols":int(x.loc[v.index,"symbol"].nunique()),
            "win24":float((v>0).mean()*100),"mean24":float(v.mean()),
            "median24":float(v.median()),"pf24":float(gp/gl) if gl>0 else None,
            "p10":float(v.quantile(.10))}

def extract_symbol(symbol,ev):
    try:
        lo=ev.decision_time.min()-pd.Timedelta(days=10)
        hi=ev.decision_time.max()+pd.Timedelta(days=2)
        b=core.fetch_15m(symbol,start=lo,end=hi)
        t=core.indicators(b)
        rows=[]
        for _,e in ev.iterrows():
            dt=e.decision_time
            closed=dt-pd.Timedelta(minutes=15)
            if closed not in t.index: continue
            i=t.index.get_loc(closed)
            if not isinstance(i,(int,np.integer)) or i<24: continue
            z=t.iloc[i-24:i+1]
            # sequence features: sell pressure fades -> recovery -> structure confirmation
            macd=z.macd_hist
            stoch=z.stoch_spread
            motion=z.motion_net
            close=z.close
            low=z.low
            high=z.high
            rec=e.to_dict()
            rec.update({
              "macd_fade_6":float(macd.iloc[-1]-macd.iloc[-7]),
              "macd_turn_3":float(macd.iloc[-1]-macd.iloc[-4]),
              "stoch_turn_3":float(stoch.iloc[-1]-stoch.iloc[-4]),
              "motion_turn_3":float(motion.iloc[-1]-motion.iloc[-4]),
              "motion_net_now":float(motion.iloc[-1]),
              "ret_3h":float((close.iloc[-1]/close.iloc[-13]-1)*100),
              "pullback_6h":float((close.iloc[-1]/high.iloc[:-1].max()-1)*100),
              "rebound_from_6h_low":float((close.iloc[-1]/low.iloc[:-1].min()-1)*100),
              "hl3":int(low.iloc[-1]>low.iloc[-5]),
              "hh3":int(high.iloc[-1]>high.iloc[-5]),
              "reclaim_prev_high":int(close.iloc[-1]>high.iloc[-2]),
              "sequence_A":int((macd.iloc[-7]<macd.iloc[-4]) and (macd.iloc[-1]>macd.iloc[-4]) and (low.iloc[-1]>low.iloc[-5])),
              "sequence_B":int((motion.iloc[-7]<=motion.iloc[-4]) and (motion.iloc[-1]>motion.iloc[-4]) and (close.iloc[-1]>high.iloc[-2])),
            })
            rows.append(rec)
        return pd.DataFrame(rows),None
    except Exception as e:
        return None,{"symbol":symbol,"error":repr(e)}

def shard(indir,outdir,shard_id,shards):
    fs=sorted(indir.rglob("features.csv"))
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    d=pd.concat([x for x in frames if len(x)],ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [F1,F2]: d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d[(d[F1]<=0.10)&(d[F2]>=0.045)].copy()
    syms=sorted(d.symbol.astype(str).unique())
    mine=[s for i,s in enumerate(syms) if i%shards==shard_id]
    out=[]; errs=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut={ex.submit(extract_symbol,s,d[d.symbol.astype(str)==s].copy()):s for s in mine}
        for k,f in enumerate(as_completed(fut),1):
            x,e=f.result()
            if e: errs.append(e)
            elif x is not None and len(x): out.append(x)
            if k%10==0 or k==len(fut): print(f"[{shard_id}] {k}/{len(fut)} rows={sum(len(q) for q in out)} err={len(errs)}",flush=True)
    outdir.mkdir(parents=True,exist_ok=True)
    (pd.concat(out,ignore_index=True) if out else pd.DataFrame()).to_csv(outdir/"path_features.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)

def aggregate(indir,outdir):
    fs=sorted(indir.rglob("path_features.csv"))
    d=pd.concat([pd.read_csv(f,low_memory=False) for f in fs if f.stat().st_size>0],ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in [F1,F2,"net_24h"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    disc=(d.hash_mod>=30)&(d.decision_time<pd.Timestamp("2025-01-01",tz="UTC"))
    cal=(d.hash_mod>=30)&(d.decision_time>=pd.Timestamp("2025-01-01",tz="UTC"))&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    cross=(d.hash_mod<30)&(d.decision_time<pd.Timestamp("2026-01-01",tz="UTC"))
    hold=(d.hash_mod<30)&(d.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))
    f1_grid=[-0.211069,-0.15,-0.10,-0.05,0,0.05,0.10]
    f2_grid=[0.0942267,0.085,0.075,0.065,0.055,0.045]
    seqs={
      "SEQ_A":lambda x:x.sequence_A==1,
      "SEQ_B":lambda x:x.sequence_B==1,
      "HL_RECLAIM":lambda x:(x.hl3==1)&(x.reclaim_prev_high==1),
      "MACD_STOCH_TURN":lambda x:(x.macd_turn_3>0)&(x.stoch_turn_3>0),
      "MOTION_HL":lambda x:(x.motion_turn_3>0)&(x.hl3==1),
      "PULLBACK_REBOUND":lambda x:(x.pullback_6h<=-1.0)&(x.rebound_from_6h_low>=0.5),
    }
    wd=104.4; wc=52.14
    rows=[]; masks={}
    for a in f1_grid:
      for b in f2_grid:
        base=(d[F1]<=a)&(d[F2]>=b)
        for name,fn in seqs.items():
          m=base&fn(d)
          md=metrics(d[disc&m]); mc=metrics(d[cal&m])
          if md.get("n",0)<20 or mc.get("n",0)<12: continue
          rows.append({"name":f"TSI<={a}|BB>={b}|{name}","f1":a,"f2":b,"seq":name,
                       "disc_freq":md["n"]/wd,"cal_freq":mc["n"]/wc,
                       "disc_win":md["win24"],"cal_win":mc["win24"],
                       "disc_mean":md["mean24"],"cal_mean":mc["mean24"],
                       "disc_pf":md["pf24"],"cal_pf":mc["pf24"]})
          masks[rows[-1]["name"]]=m
    tab=pd.DataFrame(rows)
    if len(tab):
      viable=tab[(tab.disc_freq>=2)&(tab.cal_freq>=2)&(tab.disc_mean>0.5)&(tab.cal_mean>0.5)&
                 (tab.disc_pf>1.2)&(tab.cal_pf>1.2)&(tab.disc_win>=52)&(tab.cal_win>=52)].copy()
      if len(viable):
        viable["score"]=np.minimum(viable.disc_mean,viable.cal_mean)+0.04*np.minimum(viable.disc_win,viable.cal_win)+0.1*np.minimum(viable.disc_pf.clip(upper=10),viable.cal_pf.clip(upper=10))
        viable=viable.sort_values("score",ascending=False)
    else: viable=pd.DataFrame()
    outdir.mkdir(parents=True,exist_ok=True)
    tab.to_csv(outdir/"all_path_candidates.csv",index=False)
    viable.to_csv(outdir/"viable_pre2026.csv",index=False)
    top=[]
    for _,r in viable.head(12).iterrows():
      m=masks[r["name"]]
      top.append({"name":r["name"],"discovery":metrics(d[disc&m]),"calibration":metrics(d[cal&m]),"cross_holdout_pre2026":metrics(d[cross&m]),"holdout_2026":metrics(d[hold&m])})
    summary={"selection_uses_2026":False,"rows":len(d),"tested":len(tab),"viable_pre2026":len(viable),"top":top}
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (outdir/"REPORT.md").write_text("# TSI BB Structural Phase 3 — Movement Path\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
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
