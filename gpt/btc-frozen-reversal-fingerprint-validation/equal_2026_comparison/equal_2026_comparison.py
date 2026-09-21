from __future__ import annotations

import json, math, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/"output"
OUT.mkdir(parents=True,exist_ok=True)

START=pd.Timestamp("2026-01-01",tz="UTC")
END=pd.Timestamp("2026-09-18",tz="UTC")
FETCH_1H=pd.Timestamp("2025-12-01",tz="UTC")
FETCH_4H=pd.Timestamp("2025-09-01",tz="UTC")
FETCH_END=END+pd.Timedelta(days=2)
COST=0.20
WORKERS=10

BASE_EVENTS=Path("gpt/Multi-Timeframe-Independent-Evidence/large_studies/coin_mtf_broad_frozen_validation/output/frozen_rule_events.csv")
TSI_SUM=Path("gpt/Multi-Timeframe-Independent-Evidence/large_studies/indicator_champion_robustness/output/summary.json")
R2_SUM=Path("gpt/Multi-Timeframe-Independent-Evidence/large_studies/r2_frozen_robustness/output/summary.json")

BASE_URLS=[
 "https://data-api.binance.vision","https://api.binance.com",
 "https://api1.binance.com","https://api2.binance.com","https://api3.binance.com"
]
HTTP=requests.Session(); HTTP.headers.update({"User-Agent":"Botum-LAB-equal-2026-comparison/1.0"})

def get_json(path,params,attempts=5):
    last=None
    for a in range(attempts):
        for b in BASE_URLS:
            try:
                r=HTTP.get(b+path,params=params,timeout=25)
                if r.status_code in (418,429):
                    last=RuntimeError(f"rate {r.status_code}"); continue
                r.raise_for_status(); return r.json()
            except Exception as e: last=e
        time.sleep(min(6,0.5*(2**a)))
    raise RuntimeError(last)

def fetch(symbol,interval,start,end):
    step={"1h":3600_000,"4h":4*3600_000}[interval]
    t=int(start.timestamp()*1000); endms=int(end.timestamp()*1000)-1; rows=[]
    while t<=endms:
        a=get_json("/api/v3/klines",{"symbol":symbol,"interval":interval,"startTime":t,"endTime":endms,"limit":1000})
        if not a: break
        rows.extend(a)
        last=int(a[-1][0])
        if len(a)<1000 or last+step<=t: break
        t=last+step
    if not rows: return pd.DataFrame()
    z=pd.DataFrame(rows,columns=["open_time","open","high","low","close","volume","close_time","qv","trades","tb","tq","ignore"])
    z=z.drop_duplicates("open_time").sort_values("open_time")
    for c in ["open","high","low","close"]: z[c]=pd.to_numeric(z[c],errors="coerce")
    z["time"]=pd.to_datetime(z.open_time,unit="ms",utc=True)
    return z.set_index("time")[["open","high","low","close"]]

def pivots(df,k=2):
    h=df.high.to_numpy(float); l=df.low.to_numpy(float); idx=df.index
    highs=[]; lows=[]
    for i in range(k,len(df)-k):
        if all(h[i]>h[j] for j in range(i-k,i+k+1) if j!=i):
            highs.append((idx[i+k],h[i]))
        if all(l[i]<l[j] for j in range(i-k,i+k+1) if j!=i):
            lows.append((idx[i+k],l[i]))
    return highs,lows

def latest_before(seq,t,n=2):
    a=[x for x in seq if x[0]<=t]
    return a[-n:]

def fourh_regime(ph,pl,t):
    hs=latest_before(ph,t,2); ls=latest_before(pl,t,2)
    if len(hs)<2 or len(ls)<2: return "unknown"
    if hs[-1][1]<hs[-2][1] and ls[-1][1]<ls[-2][1]: return "bear"
    if hs[-1][1]>hs[-2][1] and ls[-1][1]>ls[-2][1]: return "bull"
    return "mixed"

def wilder_rsi(close,period=2):
    d=close.diff().fillna(0.0); gain=d.clip(lower=0); loss=(-d).clip(lower=0)
    ag=gain.ewm(alpha=1/period,adjust=False,min_periods=period).mean()
    al=loss.ewm(alpha=1/period,adjust=False,min_periods=period).mean()
    rs=ag/al.replace(0,np.nan)
    out=100-100/(1+rs)
    return out.mask((al==0)&ag.notna(),100.0)

def causal_pct(x,lookback=500):
    v=x.to_numpy(float); o=np.full(len(v),np.nan)
    for i in range(lookback,len(v)):
        cur=v[i]; hist=v[i-lookback:i]; hist=hist[np.isfinite(hist)]
        if not np.isfinite(cur) or len(hist)<int(.8*lookback): continue
        o[i]=100*np.mean(hist<=cur)
    return pd.Series(o,index=x.index)

def features4(df):
    x=df.copy()
    rl=x.low.rolling(100,min_periods=100).min()
    dip=100*(x.close/rl-1)
    dp=causal_pct(dip.diff(3),500)
    r=wilder_rsi(x.close,2); rd=r.diff(); scale=rd.abs().rolling(20,min_periods=20).mean()
    speed=rd/scale.replace(0,np.nan); acc=speed-speed.shift(1); rp=causal_pct(acc,500)
    return pd.DataFrame({"dip":dp,"rsi":rp},index=x.index)

def wmean(s,t,far,near):
    z=s[(s.index>=t-pd.Timedelta(hours=far))&(s.index<t-pd.Timedelta(hours=near))].dropna()
    return float(z.mean()) if len(z) else np.nan

def metrics(df):
    if df.empty: return {"n":0}
    v=pd.to_numeric(df.net24,errors="coerce").dropna()
    gp=v[v>0].sum(); gl=-v[v<0].sum()
    return {
      "n":int(len(v)),
      "symbols":int(df.loc[v.index,"symbol"].nunique()),
      "win24":float((v>0).mean()*100),
      "net24_mean":float(v.mean()),
      "net24_median":float(v.median()),
      "pf24":float(gp/gl) if gl>0 else None,
      "p10_24":float(v.quantile(.10)),
      "sum24_fixed_notional":float(v.sum()),
    }

def process(symbol):
    try:
        h1=fetch(symbol,"1h",FETCH_1H,FETCH_END)
        h4=fetch(symbol,"4h",FETCH_4H,FETCH_END)
        if len(h1)<800 or len(h4)<650: return [],{"symbol":symbol,"error":"short_history"}
        h1h,h1l=pivots(h1); h4h,h4l=pivots(h4); f4=features4(h4)
        rows=[]
        idx=list(h1.index)
        for i in range(1,len(h1)-26):
            t=idx[i]
            if t<START or t>=END: continue
            if fourh_regime(h4h,h4l,t)!="bear": continue
            hs=latest_before(h1h,t,1); ls=latest_before(h1l,t,2)
            if len(hs)<1 or len(ls)<2 or not (ls[-1][1]>ls[-2][1]): continue
            swing_high=hs[-1][1]
            if not (float(h1.close.iloc[i-1])<=swing_high and float(h1.close.iloc[i])>swing_high): continue
            a=wmean(f4.dip,t,24,12); b=wmean(f4.rsi,t,48,24)
            if not (np.isfinite(a) and np.isfinite(b) and a<=36.6 and b>=48.4): continue
            entry=float(h1.open.iloc[i+1]); exitp=float(h1.open.iloc[i+25])
            net=(exitp/entry-1)*100-COST
            rows.append({"symbol":symbol,"decision_time":str(t),"entry_time":str(idx[i+1]),"net24":net,"dip":a,"rsi":b})
        return rows,None
    except Exception as e:
        return [],{"symbol":symbol,"error":repr(e)}

def baseline_rows():
    tsi=json.loads(TSI_SUM.read_text(encoding="utf-8"))["yearly_selected"]["2026"]
    r2=json.loads(R2_SUM.read_text(encoding="utf-8"))["yearly"]["2026"]
    return {
      "TSI_BB":{
        "n":tsi["n"],"symbols":tsi["symbols"],"win24":tsi["win24"],
        "net24_mean":tsi["net24_mean"],"net24_median":tsi["net24_median"],
        "pf24":tsi["pf24"],"p10_24":tsi["p10_24"]
      },
      "TSI_BB_R2":{
        "n":r2["n"],"symbols":r2["symbols"],"win24":r2["win24"],
        "net24_mean":r2["net24_mean"],"net24_median":r2["net24_median"],
        "pf24":r2["pf24"],"p10_24":r2.get("net24_drop_top1pct")
      }
    }

def main():
    ev=pd.read_csv(BASE_EVENTS,usecols=["symbol","decision_time"])
    ev["decision_time"]=pd.to_datetime(ev.decision_time,utc=True,errors="coerce")
    symbols=sorted(ev.loc[(ev.decision_time>=START)&(ev.decision_time<END),"symbol"].dropna().astype(str).unique())
    allrows=[]; errs=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fut={ex.submit(process,s):s for s in symbols}
        for k,f in enumerate(as_completed(fut),1):
            rows,e=f.result(); allrows.extend(rows)
            if e: errs.append(e)
            if k%20==0 or k==len(fut): print(f"{k}/{len(fut)} signals={len(allrows)} errors={len(errs)}",flush=True)
    d=pd.DataFrame(allrows)
    if len(d): d.to_csv(OUT/"fingerprint_events.csv",index=False)
    pd.DataFrame(errs).to_csv(OUT/"errors.csv",index=False)
    fp=metrics(d)
    days=(END-START).total_seconds()/86400; weeks=days/7
    base=baseline_rows()
    comp=[]
    for name,m in [("TSI+BB",base["TSI_BB"]),("TSI+BB r2",base["TSI_BB_R2"]),("Reconstructed fingerprint",fp)]:
        comp.append({
          "system":name,**m,
          "signals_per_week":float(m["n"]/weeks) if m.get("n") else 0.0
        })
    out={
      "period":{"start":str(START),"end_exclusive":str(END),"days":days,"weeks":weeks},
      "universe_source":str(BASE_EVENTS),
      "universe_symbols":len(symbols),
      "cost_pct_round_trip":COST,
      "fingerprint_status":"reconstructed exploratory system; exact legacy implementation unavailable",
      "comparison":comp,
      "errors":len(errs),
    }
    (OUT/"summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Equal 2026 Three-Way Comparison","",
      f"Period: {START.date()} to {(END-pd.Timedelta(days=1)).date()} | universe symbols: {len(symbols)} | cost: {COST:.2f}%","",
      "| System | Signals | /week | Win24 | Mean24 | Median24 | PF24 |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    for x in comp:
        lines.append(f"| {x['system']} | {x['n']} | {x['signals_per_week']:.2f} | {x['win24']:.2f}% | {x['net24_mean']:.3f}% | {x['net24_median']:.3f}% | {x['pf24'] if x['pf24'] is not None else 'NA'} |")
    lines += ["","Fingerprint note: this is the frozen reconstructed fingerprint applied to the same 2026 date span and symbol universe source. It is not the exact missing legacy scratchpad implementation."]
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(out,indent=2))

if __name__=="__main__": main()
