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

# Frozen from Outcome Second Family Screen. DO NOT optimize here.
H1_ATR_PCT_MIN=1.58953710752988
COST=0.20
FETCH_START=pd.Timestamp("2024-11-01",tz="UTC")
START=pd.Timestamp("2025-01-01",tz="UTC")
END=pd.Timestamp("2026-09-18",tz="UTC")
COOLDOWN_HOURS=24

STABLE_BASE_ASSETS={
    "USDT","USDC","FDUSD","TUSD","USDP","DAI","BUSD","USDS","USDE","USD1",
    "USDJ","PYUSD","EURC","AEUR","EURI","RLUSD","XUSD","U","KGST","USTC","BFUSD",
}
FIAT_BASE_ASSETS={
    "USD","EUR","TRY","GBP","JPY","CHF","AUD","CAD","BRL","ARS","MXN","PLN",
    "RON","RUB","UAH","ZAR","NGN","IDR","BIDR","KGS",
}
EXCLUDED_BASE_ASSETS=STABLE_BASE_ASSETS|FIAT_BASE_ASSETS


def hmod(s):
    return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100


def load_symbols():
    info,_=core.get_json("/api/v3/exchangeInfo",{})
    syms=[]
    for s in info.get("symbols",[]):
        symbol=str(s.get("symbol","")).upper()
        base=str(s.get("baseAsset","")).upper()
        quote=str(s.get("quoteAsset","")).upper()
        if s.get("status")!="TRADING": continue
        if quote!="USDT": continue
        if not bool(s.get("isSpotTradingAllowed",True)): continue
        if base in EXCLUDED_BASE_ASSETS: continue
        if symbol=="BTCUSDT": continue
        syms.append(symbol)
    return sorted(set(syms))


def net_ret(exit_px,entry_px):
    return (exit_px/entry_px-1.0)*100.0-COST


def outcome(base,decision_time):
    entry_time=decision_time+pd.Timedelta(minutes=15)
    if entry_time not in base.index:
        return None
    i=base.index.get_loc(entry_time)
    if not isinstance(i,(int,np.integer)):
        return None
    j=i+24*4
    if j>=len(base):
        return None
    entry=float(base.open.iloc[i]); exitp=float(base.open.iloc[j])
    if not np.isfinite(entry) or entry<=0 or not np.isfinite(exitp):
        return None
    sl=base.iloc[i:j+1]
    hi=(sl.high.to_numpy(float)/entry-1.0)*100.0
    lo=(sl.low.to_numpy(float)/entry-1.0)*100.0
    u=np.flatnonzero(hi>=3.0); d=np.flatnonzero(lo<=-2.0)
    tu=(u[0]/4.0) if len(u) else np.nan
    td=(d[0]/4.0) if len(d) else np.nan
    return {
        "entry_time":entry_time,
        "entry_open":entry,
        "net24":net_ret(exitp,entry),
        "mfe24":float(np.nanmax(hi)),
        "mae24":float(np.nanmin(lo)),
        "up3_before_dn2":int(pd.notna(tu) and (pd.isna(td) or tu<td)),
        "danger_dn2_first":int(pd.notna(td) and (pd.isna(tu) or td<tu)),
    }


def apply_cooldown(x,hours=24):
    x=x.sort_values("decision_time").copy()
    keep=[]
    last=None
    for t in x.decision_time:
        ok=last is None or t-last>=pd.Timedelta(hours=hours)
        keep.append(ok)
        if ok:last=t
    x["cooldown24"]=keep
    return x


def process_symbol(symbol):
    try:
        base=core.fetch_15m(symbol,start=FETCH_START,end=END+pd.Timedelta(days=2))
        if len(base)<1000:
            return pd.DataFrame(),{"symbol":symbol,"error":f"too_short:{len(base)}"}
        h1=aug.extra_indicators(core.resample(base,"1h"))
        # h1 row stamped at candle open; it is known only after that 1h candle closes.
        h1=h1[["atr_pct"]].copy()
        h1.index=h1.index+pd.Timedelta(hours=1)
        h1=h1[(h1.index>=START)&(h1.index<END)]
        raw=h1[pd.to_numeric(h1.atr_pct,errors="coerce")>=H1_ATR_PCT_MIN]
        rows=[]
        for t,r in raw.iterrows():
            oc=outcome(base,t)
            if oc is None: continue
            rows.append({
                "symbol":symbol,
                "decision_time":t,
                "h1_atr_pct":float(r.atr_pct),
                "hash_mod":hmod(symbol),
                **oc,
            })
        out=pd.DataFrame(rows)
        if len(out):
            out=apply_cooldown(out,COOLDOWN_HOURS)
        return out,None
    except Exception as ex:
        return pd.DataFrame(),{"symbol":symbol,"error":repr(ex)}


def shard_main(shard,shards,outdir,symbols_arg=None,max_symbols=0):
    syms=load_symbols()
    if symbols_arg:
        wanted={s.strip().upper() for s in symbols_arg.split(",") if s.strip()}
        syms=[s for s in syms if s in wanted]
    if max_symbols:
        syms=syms[:max_symbols]
    mine=[s for i,s in enumerate(syms) if i%shards==shard]
    outdir.mkdir(parents=True,exist_ok=True)
    frames=[];errs=[]
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs={ex.submit(process_symbol,s):s for s in mine}
        for k,f in enumerate(as_completed(futs),1):
            x,e=f.result()
            if e:errs.append(e)
            if x is not None and len(x):frames.append(x)
            if k%5==0 or k==len(futs):
                print(f"[SHARD {shard}] {k}/{len(futs)} events={sum(len(z) for z in frames)} errors={len(errs)}",flush=True)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(outdir/"events.csv",index=False)
    pd.DataFrame(errs).to_csv(outdir/"errors.csv",index=False)
    meta={"shard":shard,"shards":shards,"symbols":len(mine),"events":int(len(out)),"errors":len(errs)}
    (outdir/"meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    if symbols_arg and len(mine) and len(out)==0:
        raise RuntimeError(f"smoke produced zero events for {mine}")
    print(json.dumps(meta),flush=True)


def metrics(x):
    if len(x)==0:return {"n":0,"symbols":0}
    v=pd.to_numeric(x.net24,errors="coerce").dropna()
    z=x.loc[v.index]
    gp=float(v[v>0].sum());gl=float(-v[v<0].sum())
    return {
        "n":int(len(v)),"symbols":int(z.symbol.nunique()),
        "mean24":float(v.mean()),"median24":float(v.median()),
        "win24":float((v>0).mean()*100),
        "pf24":gp/gl if gl>0 else None,
        "up3_before_dn2":float(pd.to_numeric(z.up3_before_dn2,errors="coerce").mean()*100),
        "danger_dn2_first":float(pd.to_numeric(z.danger_dn2_first,errors="coerce").mean()*100),
        "mfe24":float(pd.to_numeric(z.mfe24,errors="coerce").mean()),
        "mae24":float(pd.to_numeric(z.mae24,errors="coerce").mean()),
    }


def frequency(x,start,end):
    days=max(1,(end.normalize()-start.normalize()).days+1)
    if len(x)==0:return {"calendar_days":days,"signals":0,"signals_per_day":0.0}
    c=x.groupby(x.decision_time.dt.floor("D")).size()
    return {
        "calendar_days":int(days),"signals":int(len(x)),"signals_per_day":float(len(x)/days),
        "active_days":int(len(c)),"active_day_share_pct":float(len(c)/days*100),
        "median_on_active_day":float(c.median()),"p90_on_active_day":float(c.quantile(.90)),
        "max_in_day":int(c.max()),
    }


def aggregate_main(indir,outdir):
    fs=sorted(indir.rglob("events.csv"))
    if len(fs)<32:raise RuntimeError(f"too few shard event files: {len(fs)}")
    frames=[]
    for f in fs:
        try:
            x=pd.read_csv(f,low_memory=False)
            if len(x):frames.append(x)
        except pd.errors.EmptyDataError:
            pass
    if not frames:raise RuntimeError("no population events")
    d=pd.concat(frames,ignore_index=True)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    d=d.drop_duplicates(["symbol","decision_time"]).sort_values(["decision_time","symbol"]).reset_index(drop=True)

    raw=d.copy()
    cool=d[d.cooldown24.astype(str).str.lower().isin(["true","1"])].copy()

    periods={
      "CALIBRATION_2025":(pd.Timestamp("2025-01-01",tz="UTC"),pd.Timestamp("2025-12-31",tz="UTC")),
      "OOS_2026":(pd.Timestamp("2026-01-01",tz="UTC"),END-pd.Timedelta(days=1)),
    }
    summary={
      "purpose":"Population validation of the frozen independent second-family screen champion. Threshold is fixed before this run; no selection or tuning occurs here.",
      "rule":{"h1_atr_pct_min":H1_ATR_PCT_MIN,"entry":"next 15m open","exit":"24h later open","round_trip_cost_pct":COST},
      "universe":"active Binance Spot USDT, exact stable/fiat base exclusions, BTC excluded",
      "primary_policy":"24h per-symbol cooldown to match independent event logic; raw hourly trigger is diagnostic only",
      "events_raw":int(len(raw)),"events_cooldown24":int(len(cool)),"symbols":int(d.symbol.nunique()),
      "periods":{},
    }
    for name,(a,b) in periods.items():
        rm=(raw.decision_time>=a)&(raw.decision_time<b+pd.Timedelta(days=1))
        cm=(cool.decision_time>=a)&(cool.decision_time<b+pd.Timedelta(days=1))
        summary["periods"][name]={
          "raw_hourly":{"metrics":metrics(raw[rm]),"frequency":frequency(raw[rm],a,b)},
          "cooldown24":{"metrics":metrics(cool[cm]),"frequency":frequency(cool[cm],a,b)},
        }

    # Symbol-cluster bootstrap on OOS 2026 cooldown returns.
    z=cool[(cool.decision_time>=pd.Timestamp("2026-01-01",tz="UTC"))&(cool.decision_time<END)].copy()
    g=z.groupby("symbol").net24.agg(["sum","count"])
    if len(g)>=20:
        rng=np.random.default_rng(260919);vals=np.empty(10000)
        sums=g["sum"].to_numpy(float);cnt=g["count"].to_numpy(float);n=len(g)
        for i in range(len(vals)):
            idx=rng.integers(0,n,n)
            vals[i]=sums[idx].sum()/cnt[idx].sum()
        summary["oos2026_symbol_cluster_bootstrap_mean24"]={
          "mean":float(vals.mean()),"ci_low":float(np.quantile(vals,.025)),
          "ci_high":float(np.quantile(vals,.975)),"p_gt_0":float((vals>0).mean())
        }

    outdir.mkdir(parents=True,exist_ok=True)
    raw.to_csv(outdir/"population_events.csv",index=False)
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    (outdir/"REPORT.md").write_text("# Outcome Second Family Population Validation\n\n"+json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,allow_nan=False),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard",type=int)
    ap.add_argument("--shards",type=int,default=64)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--aggregate-dir",type=Path)
    ap.add_argument("--symbols",type=str)
    ap.add_argument("--max-symbols",type=int,default=0)
    a=ap.parse_args()
    if a.aggregate_dir:
        aggregate_main(a.aggregate_dir,a.outdir)
    else:
        if a.shard is None:raise SystemExit("--shard required")
        shard_main(a.shard,a.shards,a.outdir,a.symbols,a.max_symbols)

if __name__=="__main__":
    main()
