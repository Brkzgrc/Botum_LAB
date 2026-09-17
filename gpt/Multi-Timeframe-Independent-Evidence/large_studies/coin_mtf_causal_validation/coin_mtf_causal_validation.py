from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

PROJECT_ROOT = ROOT.parents[1]
UNIVERSE_PATH = PROJECT_ROOT / "frozen_universe.json"

RANK_START = pd.Timestamp("2026-01-01", tz="UTC")
RANK_END = pd.Timestamp("2026-01-15", tz="UTC")
FETCH_START = pd.Timestamp("2025-12-01", tz="UTC")
START = pd.Timestamp("2026-01-15", tz="UTC")
LATE_SPLIT = pd.Timestamp("2026-07-01", tz="UTC")
END = pd.Timestamp("2026-09-18", tz="UTC")
MAX_COINS = 100
COOLDOWN_BARS = 16
ROUND_TRIP_COSTS = [0.0, 0.20, 0.40]

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]

def get_json(path, params, timeout=30, tries=3):
    last = None
    for _ in range(tries):
        for base in BASE_URLS:
            try:
                r = requests.get(base + path, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.json(), base
                last = RuntimeError(f"{base} HTTP {r.status_code}: {r.text[:120]}")
            except Exception as e:
                last = e
        time.sleep(0.2)
    raise RuntimeError(f"all Binance transports failed: {last}")

def fetch_daily_rank(symbol):
    try:
        data, _ = get_json("/api/v3/klines", {
            "symbol": symbol, "interval": "1d",
            "startTime": int(RANK_START.timestamp()*1000),
            "endTime": int(RANK_END.timestamp()*1000)-1,
            "limit": 30,
        })
        if not data:
            return symbol, np.nan, 0
        qv = np.asarray([float(r[7]) for r in data], float)
        return symbol, float(np.nanmedian(qv)), len(data)
    except Exception:
        return symbol, np.nan, 0

def fetch_15m(symbol, start=FETCH_START, end=END):
    rows, used = [], set()
    cur = int(start.timestamp()*1000)
    end_ms = int(end.timestamp()*1000)-1
    while cur <= end_ms:
        data, base = get_json("/api/v3/klines", {
            "symbol": symbol, "interval": "15m",
            "startTime": cur, "endTime": end_ms, "limit": 1000,
        })
        used.add(base)
        if not data:
            break
        rows.extend(data)
        nxt = int(data[-1][0]) + 15*60*1000
        if nxt <= cur:
            break
        cur = nxt
        if len(data) < 1000:
            break
        time.sleep(0.015)
    if not rows:
        raise RuntimeError("no 15m data")
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_volume","trades","taker_base","taker_quote","ignore"]
    d = pd.DataFrame(rows, columns=cols).drop_duplicates("open_time").sort_values("open_time")
    for c in ["open","high","low","close","volume","quote_volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d.open_time, unit="ms", utc=True)
    d = d.set_index("time")[["open","high","low","close","volume","quote_volume"]]
    d.attrs["transports"] = sorted(used)
    return d

def rsi(s, n=14):
    d=s.diff(); up=d.clip(lower=0); dn=-d.clip(upper=0)
    au=up.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    ad=dn.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rs=au/ad.replace(0,np.nan)
    out=100-100/(1+rs)
    return out.where(~((au==0)&(ad==0)),50.0)

def indicators(df):
    x=df.copy()
    x["rsi"]=rsi(x.close)
    e12=x.close.ewm(span=12,adjust=False).mean(); e26=x.close.ewm(span=26,adjust=False).mean()
    x["macd_hist"]=(e12-e26)-(e12-e26).ewm(span=9,adjust=False).mean()
    ll9=x.low.rolling(9).min(); hh9=x.high.rolling(9).max()
    rsv=100*(x.close-ll9)/(hh9-ll9).replace(0,np.nan)
    x["kdj_k"]=rsv.ewm(alpha=1/3,adjust=False).mean()
    x["kdj_d"]=x.kdj_k.ewm(alpha=1/3,adjust=False).mean()
    x["kdj_j"]=3*x.kdj_k-2*x.kdj_d
    x["kdj_spread"]=x.kdj_k-x.kdj_d
    ll14=x.low.rolling(14).min(); hh14=x.high.rolling(14).max()
    x["wpr"]=-100*(hh14-x.close)/(hh14-ll14).replace(0,np.nan)
    sign=np.sign(x.close.diff()).fillna(0); x["obv"]=(sign*x.volume).cumsum()
    rrmin=x.rsi.rolling(14).min(); rrmax=x.rsi.rolling(14).max()
    x["stoch_raw"]=100*(x.rsi-rrmin)/(rrmax-rrmin).replace(0,np.nan)
    x["stoch_k"]=x.stoch_raw.rolling(3).mean()
    x["stoch_d"]=x.stoch_k.rolling(3).mean()
    x["stoch_spread"]=x.stoch_k-x.stoch_d
    for c in ["rsi","macd_hist","kdj_j","kdj_spread","wpr","obv","stoch_k","stoch_spread"]:
        x[c+"_d1"]=x[c].diff()
        x[c+"_d3"]=x[c].diff(3)

    rng=(x.high-x.low).replace(0,np.nan); body=(x.close-x.open).abs()
    x["body_frac"]=body/rng
    x["close_loc"]=(x.close-x.low)/rng
    x["lower_wick"]=(np.minimum(x.open,x.close)-x.low)/rng
    x["hammer"]=(x.lower_wick>=0.5)&(x.body_frac<=0.4)&(x.close_loc>=0.55)
    prev_bear=x.close.shift(1)<x.open.shift(1)
    x["bull_engulf"]=(x.close>x.open)&prev_bear&(x.open<=x.close.shift(1))&(x.close>=x.open.shift(1))
    x["higher_low"]=x.low>x.low.shift(1)
    x["higher_high"]=x.high>x.high.shift(1)
    prev8=x.low.shift(1).rolling(8).min()
    x["sweep_reclaim"]=(x.low<prev8)&(x.close>prev8)
    x["reclaim_prev_high"]=x.close>x.high.shift(1)
    x["structure"]=x.hammer|x.bull_engulf|x.sweep_reclaim|x.reclaim_prev_high|(x.higher_low&x.higher_high)

    fam=pd.DataFrame(index=x.index)
    fam["RSI"]=np.sign(x.rsi_d1.fillna(0))+np.sign(x.rsi_d3.fillna(0))
    fam["MACD"]=np.sign(x.macd_hist_d1.fillna(0))+np.sign(x.macd_hist_d3.fillna(0))
    fam["KDJ"]=np.sign(x.kdj_j_d1.fillna(0))+np.sign(x.kdj_spread_d1.fillna(0))
    fam["WPR"]=np.sign(x.wpr_d1.fillna(0))+np.sign(x.wpr_d3.fillna(0))
    fam["OBV"]=np.sign(x.obv_d1.fillna(0))+np.sign(x.obv_d3.fillna(0))
    fam["STOCH"]=np.sign(x.stoch_k_d1.fillna(0))+np.sign(x.stoch_spread_d1.fillna(0))
    x["motion_pos"]=(fam>0).sum(axis=1)
    x["motion_neg"]=(fam<0).sum(axis=1)
    x["motion_net"]=x.motion_pos-x.motion_neg
    x["motion_rise"]=x.motion_pos.diff()
    x["turn4"]=(x.motion_pos>=4)&((x.motion_pos.shift(1)<4)|(x.motion_rise>=2))
    return x

def resample(df, rule):
    return df.resample(rule,origin="epoch",label="left",closed="left").agg(
        open=("open","first"),high=("high","max"),low=("low","min"),
        close=("close","last"),volume=("volume","sum"),
        quote_volume=("quote_volume","sum"),
    ).dropna()

def to_decision_time(tf, delta, decision_index, prefix):
    z=tf.copy()
    z.index=z.index+delta
    cols=["motion_pos","motion_net","motion_rise","turn4","structure",
          "higher_low","higher_high","sweep_reclaim","reclaim_prev_high",
          "bull_engulf","hammer"]
    z=z[[c for c in cols if c in z.columns]].rename(columns={c:f"{prefix}_{c}" for c in cols if c in z.columns})
    return z.reindex(decision_index,method="ffill")

def stoch_pattern(t15_decision):
    score=np.sign(t15_decision.stoch_k_d1.fillna(0))+np.sign(t15_decision.stoch_spread_d1.fillna(0))
    state=pd.Series(np.where(score>0,"+",np.where(score<0,"-","0")),index=t15_decision.index)
    return state.shift(3)+state.shift(2)+state.shift(1)+state

def compress(mask, cooldown_bars=COOLDOWN_BARS):
    arr=mask.fillna(False).to_numpy(); out=np.zeros(len(arr),dtype=bool); last=-10**9
    for i,v in enumerate(arr):
        if v and i-last>cooldown_bars:
            out[i]=True; last=i
    return pd.Series(out,index=mask.index)

def next_event_after(t,event_idx,max_h):
    pos=event_idx.searchsorted(t,side="right")
    if pos>=len(event_idx):
        return pd.NaT
    q=event_idx[pos]
    return q if q<=t+pd.Timedelta(hours=max_h) else pd.NaT

def forward_from_next_open(base, decision_times):
    # A signal from the CLOSED candle [t-15m,t) is known only at t.
    # To avoid boundary-fill optimism, we DO NOT fill at the candle opening exactly at t.
    # Earliest modeled fill is the following 15m candle open at t+15m.
    idx=base.index
    rows=[]
    for t in decision_times:
        entry_time=t+pd.Timedelta(minutes=15)
        if entry_time not in idx:
            continue
        i=idx.get_loc(entry_time)
        if not isinstance(i,(int,np.integer)):
            continue
        entry=float(base.open.iloc[i])
        if not np.isfinite(entry) or entry<=0:
            continue
        rec={"decision_time":t,"entry_time":entry_time,"entry_open":entry}
        for h in [3,4,6,12,24]:
            b=h*4
            if i+b>=len(base):
                rec[f"gross_ret_{h}h"]=np.nan
            else:
                exitp=float(base.open.iloc[i+b])
                rec[f"gross_ret_{h}h"]=(exitp/entry-1)*100
            if i+1<=min(i+b,len(base)-1):
                hi=float(base.high.iloc[i:min(i+b,len(base)-1)+1].max())
                lo=float(base.low.iloc[i:min(i+b,len(base)-1)+1].min())
                rec[f"mfe_{h}h"]=(hi/entry-1)*100
                rec[f"mae_{h}h"]=(lo/entry-1)*100
        rows.append(rec)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("decision_time")

def symbol_bucket(symbol):
    h=int(hashlib.sha256(symbol.encode()).hexdigest()[:8],16)%100
    return "HOLDOUT_SYMBOL" if h<30 else "DEV_SYMBOL"

def process_symbol(symbol, rank_qv, btc_ctx):
    try:
        base=fetch_15m(symbol)
        if len(base)<2000:
            return symbol,None,None,f"too_short:{len(base)}"
        if base.index.min()>FETCH_START+pd.Timedelta(days=5):
            return symbol,None,None,"listed_after_start"

        t15=indicators(base)
        d15=t15.copy()
        d15.index=d15.index+pd.Timedelta(minutes=15)
        d15=d15[~d15.index.duplicated(keep="last")]
        decision_index=d15.index

        t1=indicators(resample(base,"1h"))
        t4=indicators(resample(base,"4h"))
        a1=to_decision_time(t1,pd.Timedelta(hours=1),decision_index,"h1")
        a4=to_decision_time(t4,pd.Timedelta(hours=4),decision_index,"h4")
        z=d15.join(a1).join(a4)
        z=z.join(btc_ctx.reindex(z.index,method="ffill"))
        z=z[(z.index>=START)&(z.index<END)].copy()
        z["stoch_pattern"]=stoch_pattern(z)

        btc_ok=(z.btc_h4_motion_pos>=2)&(
            (z.btc_h4_motion_rise>=0)|
            (z.btc_h4_motion_net>z.btc_h4_motion_net.shift(16))
        )
        coin_h4_ok=(z.h4_motion_pos>=2)&(
            (z.h4_motion_rise>=0)|
            (z.h4_motion_net>z.h4_motion_net.shift(16))
        )
        trig=(z.motion_pos>=4)&((z.turn4)|(z.motion_rise>=1))&z.structure
        pat=z.stoch_pattern.isin(["-0++","-00+"])
        raw=btc_ok&coin_h4_ok&trig&pat
        sig=compress(raw,COOLDOWN_BARS)
        times=sig[sig].index
        if not len(times):
            return symbol,pd.DataFrame(),pd.DataFrame(),None

        fm=forward_from_next_open(base,times)
        if fm.empty:
            return symbol,pd.DataFrame(),pd.DataFrame(),None

        h1_events=z.index[z.h1_turn4.fillna(False)&(z.index.minute==0)]
        records=[]
        confirm_decisions=[]
        for t in fm.index:
            h1t=next_event_after(t,h1_events,4)
            if pd.notna(h1t):
                confirm_decisions.append(h1t)
            rec=fm.loc[t].to_dict()
            rec.update({
                "symbol":symbol,
                "rank_quote_volume":rank_qv,
                "symbol_bucket":symbol_bucket(symbol),
                "period_bucket":"LATE_HOLDOUT" if t>=LATE_SPLIT else "EARLY",
                "stoch_pattern":z.at[t,"stoch_pattern"] if t in z.index else None,
                "h1_confirm_within4h":pd.notna(h1t),
                "h1_confirm_time":h1t,
                "decision_coin_h4_pos":float(z.at[t,"h4_motion_pos"]),
                "decision_btc_h4_pos":float(z.at[t,"btc_h4_motion_pos"]),
                "decision_15m_pos":float(z.at[t,"motion_pos"]),
            })
            rec["managed_gross_ret"]=rec.get("gross_ret_12h") if pd.notna(h1t) else rec.get("gross_ret_4h")
            for cost in ROUND_TRIP_COSTS:
                tag=str(cost).replace(".","p")
                rec[f"net_ret_12h_cost_{tag}"]=rec.get("gross_ret_12h",np.nan)-cost
                rec[f"managed_net_ret_cost_{tag}"]=rec["managed_gross_ret"]-cost if pd.notna(rec["managed_gross_ret"]) else np.nan
            records.append((t,rec))
        ev=pd.DataFrame([r for _,r in records],index=pd.DatetimeIndex([t for t,_ in records],name="decision_time"))

        # Fully causal alternative: do NOT enter on 15m setup. Wait for a completed 1H
        # confirmation within 4h, then enter one full 15m bar AFTER that 1H close.
        confirm_decisions=pd.DatetimeIndex(sorted(set(confirm_decisions)))
        cfm=forward_from_next_open(base,confirm_decisions) if len(confirm_decisions) else pd.DataFrame()
        if not cfm.empty:
            cfm["symbol"]=symbol
            cfm["rank_quote_volume"]=rank_qv
            cfm["symbol_bucket"]=symbol_bucket(symbol)
            cfm["period_bucket"]=np.where(cfm.index>=LATE_SPLIT,"LATE_HOLDOUT","EARLY")
            for cost in ROUND_TRIP_COSTS:
                tag=str(cost).replace(".","p")
                cfm[f"net_ret_12h_cost_{tag}"]=cfm["gross_ret_12h"]-cost
        return symbol,ev,cfm,None
    except Exception as e:
        return symbol,None,None,f"{type(e).__name__}:{e}"

def summarize(df,name):
    if df is None or df.empty:
        return {"name":name,"n":0}
    d=df.dropna(subset=["gross_ret_12h","mfe_12h","mae_12h"])
    if d.empty:
        return {"name":name,"n":0}
    r={"name":name,"n":int(len(d)),"symbols":int(d.symbol.nunique())}
    for h in [3,6,12,24]:
        s=d[f"gross_ret_{h}h"]
        r[f"gross_mean_{h}h"]=float(s.mean())
        r[f"gross_median_{h}h"]=float(s.median())
        r[f"gross_win_{h}h"]=float((s>0).mean()*100)
    r["mfe_12h"]=float(d.mfe_12h.mean())
    r["mae_12h"]=float(d.mae_12h.mean())
    r["h1_confirm_pct"]=float(d.h1_confirm_within4h.mean()*100)
    for cost in ROUND_TRIP_COSTS:
        tag=str(cost).replace(".","p")
        s=d[f"net_ret_12h_cost_{tag}"]
        m=d[f"managed_net_ret_cost_{tag}"]
        r[f"net12_mean_cost_{tag}"]=float(s.mean())
        r[f"net12_win_cost_{tag}"]=float((s>0).mean()*100)
        r[f"managed_mean_cost_{tag}"]=float(m.mean())
        r[f"managed_win_cost_{tag}"]=float((m>0).mean()*100)
    return r

def summarize_confirm_entry(df,name):
    if df is None or df.empty:
        return {"name":name,"n":0}
    d=df.dropna(subset=["gross_ret_12h","mfe_12h","mae_12h"])
    if d.empty:
        return {"name":name,"n":0}
    r={"name":name,"n":int(len(d)),"symbols":int(d.symbol.nunique())}
    for h in [3,6,12,24]:
        q=d[f"gross_ret_{h}h"]
        r[f"gross_mean_{h}h"]=float(q.mean())
        r[f"gross_median_{h}h"]=float(q.median())
        r[f"gross_win_{h}h"]=float((q>0).mean()*100)
    r["mfe_12h"]=float(d.mfe_12h.mean())
    r["mae_12h"]=float(d.mae_12h.mean())
    for cost in ROUND_TRIP_COSTS:
        tag=str(cost).replace(".","p")
        q=d[f"net_ret_12h_cost_{tag}"]
        r[f"net12_mean_cost_{tag}"]=float(q.mean())
        r[f"net12_win_cost_{tag}"]=float((q>0).mean()*100)
    return r

def bootstrap_symbol_cluster_diff(a,b,col="net_ret_12h_cost_0p2",n=2000,seed=42):
    rng=np.random.default_rng(seed)
    A={s:g[col].dropna().to_numpy() for s,g in a.groupby("symbol")}
    B={s:g[col].dropna().to_numpy() for s,g in b.groupby("symbol")}
    sa=list(A); sb=list(B)
    if len(sa)<2 or len(sb)<2:
        return {"mean":np.nan,"ci_low":np.nan,"ci_high":np.nan}
    vals=[]
    for _ in range(n):
        xa=rng.choice(sa,len(sa),replace=True); xb=rng.choice(sb,len(sb),replace=True)
        av=np.concatenate([A[s] for s in xa if len(A[s])])
        bv=np.concatenate([B[s] for s in xb if len(B[s])])
        if len(av) and len(bv):
            vals.append(float(np.mean(av)-np.mean(bv)))
    if not vals:
        return {"mean":np.nan,"ci_low":np.nan,"ci_high":np.nan}
    lo,hi=np.quantile(vals,[.025,.975])
    return {"mean":float(np.mean(vals)),"ci_low":float(lo),"ci_high":float(hi)}

def main():
    universe=json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"]
    universe=[s for s in universe if s.endswith("USDT") and s!="BTCUSDT"]

    print(f"[UNIVERSE] frozen={len(universe)}; ranking 2026-01-01..14 by historical quote volume")
    ranks=[]
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs={ex.submit(fetch_daily_rank,s):s for s in universe}
        for k,f in enumerate(as_completed(futs),1):
            ranks.append(f.result())
            if k%50==0: print(f"[RANK] {k}/{len(futs)}")
    rdf=pd.DataFrame(ranks,columns=["symbol","median_daily_quote_volume","days"])
    rdf=rdf[(rdf.days>=10)&rdf.median_daily_quote_volume.notna()].sort_values("median_daily_quote_volume",ascending=False)
    selected=rdf.head(MAX_COINS).copy()
    selected.to_csv(OUT/"selected_universe.csv",index=False)
    print(f"[SELECT] {len(selected)} coins; min rank qv={selected.median_daily_quote_volume.min():,.0f}")

    print("[BTC] downloading context")
    btc=fetch_15m("BTCUSDT")
    bt4=indicators(resample(btc,"4h"))
    decision_grid=pd.date_range(FETCH_START+pd.Timedelta(minutes=15),END,freq="15min",inclusive="left",tz="UTC")
    btc_ctx=to_decision_time(bt4,pd.Timedelta(hours=4),decision_grid,"btc_h4")
    btc_ctx=btc_ctx[["btc_h4_motion_pos","btc_h4_motion_net","btc_h4_motion_rise","btc_h4_turn4","btc_h4_structure"]]

    print(f"[COINS] downloading/analyzing {len(selected)} symbols")
    events=[]; confirm_entries=[]; errors=[]
    rank_map=dict(zip(selected.symbol,selected.median_daily_quote_volume))
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs={ex.submit(process_symbol,s,rank_map[s],btc_ctx):s for s in selected.symbol}
        for k,f in enumerate(as_completed(futs),1):
            s,ev,cfm,err=f.result()
            if err:
                errors.append({"symbol":s,"error":err})
            else:
                if ev is not None and not ev.empty:
                    events.append(ev)
                if cfm is not None and not cfm.empty:
                    confirm_entries.append(cfm)
            print(f"[COIN {k}/{len(futs)}] {s} events={0 if ev is None else len(ev)} confirm_entries={0 if cfm is None else len(cfm)} err={err or '-'}")

    if not events:
        raise RuntimeError("no events produced")
    all_ev=pd.concat(events).sort_index()
    all_ev.to_csv(OUT/"events.csv")
    all_cfm=pd.concat(confirm_entries).sort_index() if confirm_entries else pd.DataFrame()
    if not all_cfm.empty:
        all_cfm.to_csv(OUT/"confirm_entry_events.csv")
    pd.DataFrame(errors).to_csv(OUT/"errors.csv",index=False)

    views={
        "ALL":all_ev,
        "DEV_SYMBOLS":all_ev[all_ev.symbol_bucket=="DEV_SYMBOL"],
        "HOLDOUT_SYMBOLS":all_ev[all_ev.symbol_bucket=="HOLDOUT_SYMBOL"],
        "EARLY":all_ev[all_ev.period_bucket=="EARLY"],
        "LATE_HOLDOUT":all_ev[all_ev.period_bucket=="LATE_HOLDOUT"],
        "DOUBLE_HOLDOUT":all_ev[(all_ev.symbol_bucket=="HOLDOUT_SYMBOL")&(all_ev.period_bucket=="LATE_HOLDOUT")],
        "H1_CONFIRMS_WITHIN4H":all_ev[all_ev.h1_confirm_within4h],
        "NO_H1_CONFIRM_WITHIN4H":all_ev[~all_ev.h1_confirm_within4h],
    }
    sums={k:summarize(v,k) for k,v in views.items()}

    dh=views["DOUBLE_HOLDOUT"]
    conf=dh[dh.h1_confirm_within4h]
    no=dh[~dh.h1_confirm_within4h]
    boot=bootstrap_symbol_cluster_diff(conf,no)

    cfm_summaries={}
    if not all_cfm.empty:
        cfm_summaries={
            "ALL":summarize_confirm_entry(all_cfm,"WAIT_H1_CONFIRM_ALL"),
            "HOLDOUT_SYMBOLS":summarize_confirm_entry(all_cfm[all_cfm.symbol_bucket=="HOLDOUT_SYMBOL"],"WAIT_H1_CONFIRM_HOLDOUT_SYMBOLS"),
            "LATE_HOLDOUT":summarize_confirm_entry(all_cfm[all_cfm.period_bucket=="LATE_HOLDOUT"],"WAIT_H1_CONFIRM_LATE_HOLDOUT"),
            "DOUBLE_HOLDOUT":summarize_confirm_entry(all_cfm[(all_cfm.symbol_bucket=="HOLDOUT_SYMBOL")&(all_cfm.period_bucket=="LATE_HOLDOUT")],"WAIT_H1_CONFIRM_DOUBLE_HOLDOUT"),
        }

    summary={
        "architecture":"BTC completed-4H context + coin completed-4H context + coin CLOSED-15M movement/structure trigger + StochRSI direction pattern; entry after 15m latency; 1H confirmation only after entry",
        "absolute_oscillator_levels_used_as_setup_features":False,
        "intrabar_higher_timeframe_data_used":False,
        "same_signal_candle_fill_used":False,
        "entry_model":"signal known at 15m close t; conservative fill = following 15m candle open at t+15m",
        "h1_management_model":"early-entry branch: if no completed-1H confirmation within 4h, causal early exit; wait-for-confirm branch enters only after completed 1H confirm and one extra 15m latency",
        "round_trip_cost_scenarios_pct":ROUND_TRIP_COSTS,
        "ranking_window":[str(RANK_START),str(RANK_END)],
        "study_window":[str(START),str(END)],
        "late_holdout_start":str(LATE_SPLIT),
        "selected_symbols":int(len(selected)),
        "analyzed_symbols":int(all_ev.symbol.nunique()),
        "error_symbols":int(len(errors)),
        "total_events":int(len(all_ev)),
        "wait_h1_confirm_entries":int(len(all_cfm)),
        "summaries":sums,
        "wait_h1_confirm_summaries":cfm_summaries,
        "double_holdout_confirm_vs_no_confirm_net12_cost0p2_cluster_bootstrap":boot,
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    lines=[
        "# Coin MTF Reversal Propagation — Causal/Tradable Validation",
        "",
        "Bu testte setup için sabit RSI/KDJ/W%R/StochRSI seviyeleri kullanılmaz. Üst zaman dilimlerinde yalnızca TAMAMLANMIŞ mumlar kullanılır.",
        "",
        "## Look-ahead kilidi",
        "- 15M sinyali ancak 15 dakikalık mum kapandıktan sonra var sayılır.",
        "- Giriş aynı kapanış sınırındaki yeni mum açılışından bile yapılmaz; sinyal kapanışından sonra TAM 1 adet 15M gecikme bırakılır ve sonraki mum açılışı kullanılır.",
        "- 1H ve 4H bilgisi yalnızca ilgili mum kapandıktan sonra alt zaman dilimine taşınır.",
        "- 1H teyidi giriş şartı olarak gelecekte bilinmiş sayılmaz; girişten SONRA oluşursa yönetim bilgisi olur.",
        "- Ayrıca tamamen nedensel ikinci kol vardır: 1H teyidi beklenir, teyit mumu kapandıktan sonra bir 15M daha beklenir ve ancak sonraki açılışta giriş yapılır.",
        "",
        f"Seçili coin: {len(selected)} | Analiz edilen: {all_ev.symbol.nunique()} | Olay: {len(all_ev)} | Hatalı/uygunsuz: {len(errors)}",
        "",
        "## Özet",
    ]
    for k in ["ALL","HOLDOUT_SYMBOLS","LATE_HOLDOUT","DOUBLE_HOLDOUT","H1_CONFIRMS_WITHIN4H","NO_H1_CONFIRM_WITHIN4H"]:
        r=sums[k]
        lines.append(
            f"- {k}: n={r.get('n',0)}, symbols={r.get('symbols',0)}, gross12={r.get('gross_mean_12h',np.nan):.3f}%, "
            f"net12(cost0.20)={r.get('net12_mean_cost_0p2',np.nan):.3f}%, net-win={r.get('net12_win_cost_0p2',np.nan):.1f}%, "
            f"MFE12={r.get('mfe_12h',np.nan):.2f}%, MAE12={r.get('mae_12h',np.nan):.2f}%, H1<=4h={r.get('h1_confirm_pct',np.nan):.1f}%, "
            f"managed-net={r.get('managed_mean_cost_0p2',np.nan):.3f}%"
        )
    lines.append("")
    if cfm_summaries:
        lines.append("## 1H teyidini BEKLEYEREK gerçek giriş (teyit kapanışı + 15M gecikme)")
        for k in ["ALL","HOLDOUT_SYMBOLS","LATE_HOLDOUT","DOUBLE_HOLDOUT"]:
            r=cfm_summaries[k]
            lines.append(
                f"- {k}: n={r.get('n',0)}, symbols={r.get('symbols',0)}, gross12={r.get('gross_mean_12h',np.nan):.3f}%, "
                f"net12(cost0.20)={r.get('net12_mean_cost_0p2',np.nan):.3f}%, net-win={r.get('net12_win_cost_0p2',np.nan):.1f}%, "
                f"MFE12={r.get('mfe_12h',np.nan):.2f}%, MAE12={r.get('mae_12h',np.nan):.2f}%"
            )
    lines.append("")
    lines.append(
        "Double-holdout'ta 1H teyit gelenler - gelmeyenler net12(cost0.20) farkı, symbol-cluster bootstrap: "
        f"{boot['mean']:.3f}% [%95 GA {boot['ci_low']:.3f}, {boot['ci_high']:.3f}]."
    )
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__=="__main__":
    main()
