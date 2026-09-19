from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R2_DIR=HERE.parent.parent/"r2_candidate"
sys.path.insert(0,str(R2_DIR))
import r2_common as rc  # noqa: E402
import r2_candidate_scanner as sc  # noqa: E402


def fetch_closed_15m(symbol, decision_time):
    t=pd.Timestamp(decision_time)
    end_ms=int(t.timestamp()*1000)-1
    rows=sc.get_json("/api/v3/klines",{"symbol":symbol,"interval":"15m","endTime":end_ms,"limit":1000})
    cols=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
    d=pd.DataFrame(rows,columns=cols)
    for c in ["open","high","low","close","volume","quote_volume"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d["time"]=pd.to_datetime(d.open_time,unit="ms",utc=True)
    return d.dropna(subset=["open","high","low","close"]).set_index("time")[["open","high","low","close","volume","quote_volume"]]


def recompute_one(row):
    try:
        t=pd.Timestamp(row.decision_time)
        coin=fetch_closed_15m(str(row.symbol),t)
        btc=fetch_closed_15m("BTCUSDT",t)
        if len(coin)<400 or len(btc)<400:
            return {"row_id":int(row.row_id),"error":"short_history"}

        # The last closed 15m candle should map exactly to decision time after +15m.
        c15=sc.indicators(coin)
        d15=sc.decision_15m(c15)
        if t not in d15.index:
            return {"row_id":int(row.row_id),"error":"decision_not_in_15m"}

        coin4_price=sc.resample(coin,"4h")
        coin4_extra=sc.add_tsi_bb(coin4_price)
        coin4=sc.align_columns(coin4_extra,["bb_width"],pd.Timedelta(hours=4),d15.index,"coin4")

        btc1=sc.add_tsi_bb(sc.resample(btc,"1h"))
        btc4_price=sc.resample(btc,"4h")
        btc4_extra=sc.add_tsi_bb(btc4_price)
        b1=sc.align_columns(btc1,["tsi_d1"],pd.Timedelta(hours=1),d15.index,"btc1")
        b4=sc.align_columns(btc4_extra,["bb_width"],pd.Timedelta(hours=4),d15.index,"btc4")

        dd=100.0*(d15["close"]/d15["high"].rolling(sc.PULLBACK_48H_BARS_15M,min_periods=sc.PULLBACK_48H_BARS_15M).max()-1.0)
        vals={
            "scanner_coin4_bb_width":float(coin4.loc[t,"coin4_bb_width"]),
            "scanner_btc1_tsi_d1":float(b1.loc[t,"btc1_tsi_d1"]),
            "scanner_btc4_bb_width":float(b4.loc[t,"btc4_bb_width"]),
            "scanner_dd48":float(dd.loc[t]),
        }
        vals["scanner_r2_filter"]=bool(
            vals["scanner_coin4_bb_width"]>=sc.COIN4_BB_WIDTH_MIN
            and vals["scanner_btc1_tsi_d1"]<=sc.TSI_D1_MAX
            and vals["scanner_btc4_bb_width"]>=sc.BTC4_BB_WIDTH_MIN
            and vals["scanner_dd48"]<=sc.PULLBACK_48H_MAX_PCT
        )
        return {"row_id":int(row.row_id),"error":"",**vals}
    except Exception as exc:
        return {"row_id":int(row.row_id),"error":repr(exc)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact-dir",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    ap.add_argument("--workers",type=int,default=10)
    ap.add_argument("--sample",type=int,default=96)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)

    # Use frozen r1 universe, then classify r2. This lets fidelity include both pass and fail cases.
    d=rc.ext.load_frozen_candidate(args.artifact_dir)
    d=rc.ext.add_causal_pullbacks(d,workers=max(1,args.workers))
    d=d[d.pullback_error.fillna("")==""].copy()
    d["research_r2"]=(
        (pd.to_numeric(d.h4_bb_width,errors="coerce")>=rc.R2_H4_BB_MIN)
        &(pd.to_numeric(d.causal_dd_high_48h,errors="coerce")<=rc.R2_DD48_MAX)
    )
    d["distance"]=(
        abs(pd.to_numeric(d.h4_bb_width,errors="coerce")-rc.R2_H4_BB_MIN)/(abs(rc.R2_H4_BB_MIN)+1e-9)
        +abs(pd.to_numeric(d.causal_dd_high_48h,errors="coerce")-rc.R2_DD48_MAX)/(abs(rc.R2_DD48_MAX)+1e-9)
    )
    pos=d[d.research_r2].sort_values("distance").head(args.sample//2)
    neg=d[~d.research_r2].sort_values("distance").head(args.sample-len(pos))
    q=pd.concat([pos,neg]).sort_values(["decision_time","symbol"]).reset_index(drop=True)
    q["row_id"]=np.arange(len(q),dtype=int)

    recs=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(recompute_one,r):int(r.row_id) for r in q.itertuples(index=False)}
        for i,f in enumerate(as_completed(futs),1):
            recs.append(f.result())
            if i%20==0 or i==len(futs): print(f"[FIDELITY] {i}/{len(futs)}",flush=True)
    z=q.merge(pd.DataFrame(recs),on="row_id",how="left")
    ok=z.error.fillna("")==""
    z["agree_r2"]=z.scanner_r2_filter==z.research_r2
    z["diff_coin4_bb"]=z.scanner_coin4_bb_width-pd.to_numeric(z.h4_bb_width,errors="coerce")
    z["diff_btc1_tsi"]=z.scanner_btc1_tsi_d1-pd.to_numeric(z.btc1_tsi_d1,errors="coerce")
    z["diff_btc4_bb"]=z.scanner_btc4_bb_width-pd.to_numeric(z.btc4_bb_width,errors="coerce")
    z["diff_dd48"]=z.scanner_dd48-pd.to_numeric(z.causal_dd_high_48h,errors="coerce")

    def diffstat(c):
        v=pd.to_numeric(z.loc[ok,c],errors="coerce").abs().dropna()
        return {"n":int(len(v)),"median_abs":float(v.median()) if len(v) else np.nan,
                "p95_abs":float(v.quantile(.95)) if len(v) else np.nan,"max_abs":float(v.max()) if len(v) else np.nan}

    summary={
        "purpose":"Historical replay fidelity between the frozen r2 research features and the standalone live scanner calculations.",
        "sample":int(len(z)),"usable":int(ok.sum()),"errors":int((~ok).sum()),
        "r2_classification_agreement_pct":float(z.loc[ok,"agree_r2"].mean()*100) if ok.any() else np.nan,
        "false_negative_count":int(((z.research_r2)&(~z.scanner_r2_filter)&ok).sum()),
        "false_positive_count":int(((~z.research_r2)&(z.scanner_r2_filter)&ok).sum()),
        "feature_differences":{
            "coin4_bb":diffstat("diff_coin4_bb"),"btc1_tsi_d1":diffstat("diff_btc1_tsi"),
            "btc4_bb":diffstat("diff_btc4_bb"),"dd48":diffstat("diff_dd48"),
        }
    }
    z.to_csv(args.outdir/"replay_comparison.csv",index=False)
    (args.outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (args.outdir/"REPORT.md").write_text("# r2 Live Scanner Fidelity\n\n"+json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
