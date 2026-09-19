from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
EXT_DIR = HERE.parent / "frozen_candidate_outcome_extension"
sys.path.insert(0, str(EXT_DIR))
import frozen_candidate_outcome_extension as ext  # noqa: E402

R2_H4_BB_MIN = 0.19233492
R2_DD48_MAX = -7.3594696
PATH_HOURS = 72
REQUIRED = {
    "symbol","decision_time","entry_time","hash_mod",
    "btc1_tsi_d1","btc4_bb_width","h4_bb_width",
    "h1_rvol20_d1","h1_donch_pos_d3",
    "net_12h","net_24h","net_72h",
}
BASE_URLS = [
    "https://data-api.binance.vision","https://api.binance.com",
    "https://api1.binance.com","https://api2.binance.com","https://api3.binance.com",
]
HTTP=requests.Session()
HTTP.headers.update({"User-Agent":"Botum-LAB-r2-round2/1.0"})


def get_json(path, params=None, attempts=6):
    last=None
    for i in range(attempts):
        for base in BASE_URLS:
            try:
                r=HTTP.get(base+path,params=params or {},timeout=20)
                if r.status_code in (418,429):
                    last=RuntimeError(f"rate limit {r.status_code}")
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last=exc
        time.sleep(min(8.0,.5*(2**i)))
    raise RuntimeError(f"Binance request failed {path}: {last}")


def load_raw(indir: Path):
    fs=sorted(indir.rglob("features.csv"))
    if not fs:
        raise RuntimeError("no indicator augmentation features.csv artifacts")
    frames=[pd.read_csv(f,low_memory=False) for f in fs]
    frames=[x for x in frames if len(x)]
    if not frames:
        raise RuntimeError("all indicator artifacts empty")
    d=pd.concat(frames,ignore_index=True)
    missing=sorted(REQUIRED-set(d.columns))
    if missing:
        raise RuntimeError(f"missing required columns: {missing}")
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    d["entry_time"]=pd.to_datetime(d.entry_time,utc=True)
    return d


def preflight(indir: Path):
    d=load_raw(indir)
    x=d[
        (pd.to_numeric(d.btc1_tsi_d1,errors="coerce")<=ext.F1_MAX)
        &(pd.to_numeric(d.btc4_bb_width,errors="coerce")>=ext.F2_MIN)
    ].copy()
    masks=ext.split_masks(x)
    counts={k:int(v.sum()) for k,v in masks.items()}
    if len(x)<300:
        raise RuntimeError(f"frozen r1 cohort unexpectedly small: {len(x)}")
    if min(counts.values())<30:
        raise RuntimeError(f"split unexpectedly small before r2: {counts}")
    numeric=sum(pd.api.types.is_numeric_dtype(d[c]) for c in d.columns)
    out={"artifact_files":len(list(indir.rglob("features.csv"))),"raw_rows":int(len(d)),
         "r1_rows":int(len(x)),"split_counts":counts,"numeric_columns":int(numeric)}
    print(json.dumps(out,ensure_ascii=False))
    return out


def fetch_path(row):
    symbol=str(row.symbol)
    t=pd.Timestamp(row.entry_time)
    start_ms=int(t.timestamp()*1000)
    end_ms=int((t+pd.Timedelta(hours=PATH_HOURS,minutes=15)).timestamp()*1000)-1
    try:
        rows=get_json("/api/v3/klines",{
            "symbol":symbol,"interval":"15m","startTime":start_ms,"endTime":end_ms,"limit":1000
        })
        if not isinstance(rows,list) or len(rows)<96:
            return int(row.event_id), None, f"short:{len(rows) if isinstance(rows,list) else -1}"
        rec=[]
        for bar_i,q in enumerate(rows):
            rec.append({
                "event_id":int(row.event_id),"symbol":symbol,"bar_i":bar_i,
                "open_time":pd.to_datetime(int(q[0]),unit="ms",utc=True).isoformat(),
                "open":float(q[1]),"high":float(q[2]),"low":float(q[3]),"close":float(q[4]),
            })
        return int(row.event_id), rec, ""
    except Exception as exc:
        return int(row.event_id), None, repr(exc)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=12)
    ap.add_argument("--preflight",action="store_true")
    args=ap.parse_args()
    args.outdir.mkdir(parents=True,exist_ok=True)

    pf=preflight(args.artifact_dir)
    if args.preflight:
        (args.outdir/"preflight.json").write_text(json.dumps(pf,indent=2),encoding="utf-8")
        return

    d=ext.load_frozen_candidate(args.artifact_dir)
    d=ext.add_causal_pullbacks(d,workers=max(1,args.workers))
    d=d[d.pullback_error.fillna("")==""].copy()
    d["r2"]=(
        (pd.to_numeric(d.h4_bb_width,errors="coerce")>=R2_H4_BB_MIN)
        &(pd.to_numeric(d.causal_dd_high_48h,errors="coerce")<=R2_DD48_MAX)
    )
    r2=d[d.r2].copy().sort_values(["decision_time","symbol"]).reset_index(drop=True)
    r2["event_id"]=np.arange(len(r2),dtype=int)
    masks=ext.split_masks(r2)
    split_counts={k:int(v.sum()) for k,v in masks.items()}
    if len(r2)<150 or min(split_counts.values())<20:
        raise RuntimeError(f"r2 cohort/splits unexpected: rows={len(r2)} splits={split_counts}")

    paths=[]
    errors=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(fetch_path,r):int(r.event_id) for r in r2.itertuples(index=False)}
        for i,f in enumerate(as_completed(futs),1):
            eid,rows,err=f.result()
            if err: errors.append({"event_id":eid,"error":err})
            else: paths.extend(rows)
            if i%40==0 or i==len(futs):
                print(f"[PATH] {i}/{len(futs)} ok={i-len(errors)} errors={len(errors)}",flush=True)

    if errors:
        bad={x["event_id"] for x in errors}
        if len(bad)>max(3,int(.03*len(r2))):
            raise RuntimeError(f"too many path errors: {len(bad)}/{len(r2)}")
        r2=r2[~r2.event_id.isin(bad)].copy()

    p=pd.DataFrame(paths)
    if p.empty:
        raise RuntimeError("no path rows")
    p=p[p.event_id.isin(set(r2.event_id))].copy()
    bars=p.groupby("event_id").size()
    if bars.min()<96:
        raise RuntimeError(f"path coverage too short: min bars={bars.min()}")

    r2.to_csv(args.outdir/"r2_events.csv",index=False)
    p.to_csv(args.outdir/"r2_paths.csv",index=False)
    pd.DataFrame(errors).to_csv(args.outdir/"path_errors.csv",index=False)
    meta={"r2_events":int(len(r2)),"symbols":int(r2.symbol.nunique()),
          "split_counts":{k:int(ext.split_masks(r2)[k].sum()) for k in ext.split_masks(r2)},
          "path_rows":int(len(p)),"min_bars":int(bars.min()),"max_bars":int(bars.max()),
          "path_hours":PATH_HOURS,"errors":len(errors)}
    (args.outdir/"dataset_meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
