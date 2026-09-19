from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
R2_DIR = HERE.parent.parent / "r2_candidate"
sys.path.insert(0, str(R2_DIR))
import r2_common as rc  # noqa: E402

COST = rc.COST
HORIZON_H = 72


def fetch_path(row):
    t = pd.Timestamp(row.entry_time)
    start_ms = int(t.timestamp() * 1000)
    end_ms = int((t + pd.Timedelta(hours=HORIZON_H, minutes=15)).timestamp() * 1000) - 1
    try:
        rows = rc.ext.get_json("/api/v3/klines", {
            "symbol": str(row.symbol), "interval": "15m",
            "startTime": start_ms, "endTime": end_ms, "limit": 1000,
        })
        if not isinstance(rows, list) or len(rows) < 48:
            return {"row_id": int(row.row_id), "error": f"short:{len(rows) if isinstance(rows,list) else -1}"}
        z = pd.DataFrame(rows, columns=[
            "open_time","open","high","low","close","volume","close_time","qv","trades","tb","tq","ignore"
        ])
        for c in ["open","high","low","close"]:
            z[c] = pd.to_numeric(z[c], errors="coerce")
        z = z.dropna(subset=["open","high","low","close"]).reset_index(drop=True)
        if not len(z):
            return {"row_id": int(row.row_id), "error": "empty"}
        ep = float(z.open.iloc[0])
        rec = {"row_id": int(row.row_id), "entry_price_path": ep, "error": ""}
        for i, q in z.iterrows():
            rec[f"h_{i}"] = float(q.high)
            rec[f"l_{i}"] = float(q.low)
            rec[f"c_{i}"] = float(q.close)
        rec["bars"] = int(len(z))
        return rec
    except Exception as exc:
        return {"row_id": int(row.row_id), "error": repr(exc)}


def enrich_paths(d, workers):
    x = d.reset_index(drop=True).copy()
    x["row_id"] = np.arange(len(x), dtype=int)
    recs = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(fetch_path, r): int(r.row_id) for r in x.itertuples(index=False)}
        for i, f in enumerate(as_completed(futs), 1):
            recs.append(f.result())
            if i % 40 == 0 or i == len(futs):
                ok = sum(not q.get("error") for q in recs)
                print(f"[PATH] {i}/{len(futs)} ok={ok}", flush=True)
    p = pd.DataFrame(recs)
    return x.merge(p, on="row_id", how="left")


def get_arrays(row):
    n = int(row.get("bars", 0) or 0)
    hi = np.array([row.get(f"h_{i}", np.nan) for i in range(n)], float)
    lo = np.array([row.get(f"l_{i}", np.nan) for i in range(n)], float)
    cl = np.array([row.get(f"c_{i}", np.nan) for i in range(n)], float)
    ep = float(row.entry_price_path)
    return ep, hi, lo, cl


def net_ret(exit_price, entry):
    return (exit_price / entry - 1.0) * 100.0 - COST


def eval_fixed(row, hours):
    ep, hi, lo, cl = get_arrays(row)
    idx = min(len(cl)-1, max(0, hours*4-1))
    return net_ret(cl[idx], ep)


def eval_tpsl(row, tp, sl, maxh):
    ep, hi, lo, cl = get_arrays(row)
    n = min(len(cl), maxh*4)
    tp_px = ep * (1 + tp/100)
    sl_px = ep * (1 + sl/100)
    for i in range(n):
        hit_tp = hi[i] >= tp_px
        hit_sl = lo[i] <= sl_px
        if hit_tp and hit_sl:
            return sl - COST  # pessimistic same-candle ambiguity
        if hit_sl:
            return sl - COST
        if hit_tp:
            return tp - COST
    return net_ret(cl[n-1], ep)


def eval_trailing(row, activate, trail, maxh):
    ep, hi, lo, cl = get_arrays(row)
    n = min(len(cl), maxh*4)
    peak = ep
    active = False
    stop = None
    for i in range(n):
        peak = max(peak, hi[i])
        if not active and (peak/ep-1)*100 >= activate:
            active = True
        if active:
            stop = peak * (1 - trail/100)
            if lo[i] <= stop:
                return net_ret(stop, ep)
    return net_ret(cl[n-1], ep)


def eval_progress(row, checkh, min_mfe, exith, finalh):
    ep, hi, lo, cl = get_arrays(row)
    ncheck = min(len(hi), checkh*4)
    mfe = (np.nanmax(hi[:ncheck]) / ep - 1) * 100
    if mfe < min_mfe:
        idx = min(len(cl)-1, exith*4-1)
    else:
        idx = min(len(cl)-1, finalh*4-1)
    return net_ret(cl[idx], ep)


def policy_defs():
    out = []
    for h in (12,24,36,48,72):
        out.append(("fixed", f"FIXED_{h}H", {"h":h}))
    for tp in (3,5,7):
        for sl in (-2,-3,-5):
            for h in (24,48,72):
                out.append(("tpsl", f"TP{tp}_SL{abs(sl)}_{h}H", {"tp":tp,"sl":sl,"h":h}))
    for activate, trail, h in ((3,2,24),(3,2,48),(5,3,48),(5,3,72)):
        out.append(("trail", f"TRAIL_A{activate}_T{trail}_{h}H", {"activate":activate,"trail":trail,"h":h}))
    for checkh,minm,exith,finalh in ((6,.5,6,24),(6,1,6,24),(12,1,12,48),(12,2,12,48)):
        out.append(("progress", f"PROGRESS_{checkh}H_MFE{minm}_{finalh}H", {"checkh":checkh,"minm":minm,"exith":exith,"finalh":finalh}))
    return out


def score_metrics(v):
    v = pd.Series(v).dropna()
    if not len(v): return {"n":0}
    gp = v[v>0].sum(); gl = -v[v<0].sum()
    return {"n":int(len(v)),"mean":float(v.mean()),"median":float(v.median()),"win":float((v>0).mean()*100),
            "pf":float(gp/gl) if gl>0 else np.nan,"q10":float(v.quantile(.1)),"q25":float(v.quantile(.25))}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=12)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    d=rc.load_r2(args.artifact_dir,args.workers)
    print(f"[R2] events={len(d)} symbols={d.symbol.nunique()}",flush=True)
    d=enrich_paths(d,args.workers)
    d=d[d.error.fillna("")==""].copy()
    masks=rc.split_masks(d)

    rows=[]
    returns={}
    for typ,name,p in policy_defs():
        vals=[]
        for _,r in d.iterrows():
            if typ=="fixed": v=eval_fixed(r,p["h"])
            elif typ=="tpsl": v=eval_tpsl(r,p["tp"],p["sl"],p["h"])
            elif typ=="trail": v=eval_trailing(r,p["activate"],p["trail"],p["h"])
            else: v=eval_progress(r,p["checkh"],p["minm"],p["exith"],p["finalh"])
            vals.append(v)
        s=pd.Series(vals,index=d.index)
        returns[name]=s
        rec={"policy":name,"type":typ}
        for split,m in masks.items():
            met=score_metrics(s[m])
            rec[split]=met
        disc=rec["DISCOVERY"]; cal=rec["CALIBRATION"]
        if disc.get("n",0)>=20 and cal.get("n",0)>=20:
            rec["train_score"]=min(disc["mean"],cal["mean"]) + .25*min(disc["median"],cal["median"]) + .02*min(disc["win"],cal["win"])
        else: rec["train_score"]=-999
        rows.append(rec)

    ranked=sorted(rows,key=lambda x:x["train_score"],reverse=True)
    champion=ranked[0]
    champ=champion["policy"]
    d["champion_return"]=returns[champ]
    hold=masks["CROSS_HOLDOUT_PRE2026"]|masks["FINAL_HOLDOUT_2026"]
    boot=rc.cluster_bootstrap_mean(d[hold].rename(columns={"champion_return":"_ret"}),"_ret",reps=10000)

    summary={"purpose":"Frozen r2 exit/holding policy discovery. Selection uses Discovery+Calibration only.",
             "events":int(len(d)),"policies":len(rows),"champion_selected_without_holdouts":champion,
             "champion_holdout_bootstrap":boot,"top10":ranked[:10]}
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    pd.DataFrame([{**{"policy":r["policy"],"type":r["type"],"train_score":r["train_score"]},
                   **{f"{s}_{k}":v for s in masks for k,v in r[s].items()}} for r in ranked]).to_csv(args.outdir/"policies.csv",index=False)
    (args.outdir/"REPORT.md").write_text("# r2 Exit / Holding Research\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
