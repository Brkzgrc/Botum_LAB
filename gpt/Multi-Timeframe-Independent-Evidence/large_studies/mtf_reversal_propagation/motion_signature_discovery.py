from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor, export_text
from sklearn.metrics import mean_absolute_error

import mtf_reversal_propagation as core

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "signature_output"
OUT.mkdir(parents=True, exist_ok=True)


def detailed_align(tf, delta, base_index, prefix):
    z=tf.copy(); z.index=z.index+delta
    cols=[
        "rsi_d1","rsi_d3","macd_hist_d1","macd_hist_d3","kdj_j_d1","kdj_j_d3","kdj_spread_d1","kdj_spread_d3",
        "wpr_d1","wpr_d3","obv_d1","obv_d3","stoch_k_d1","stoch_k_d3","stoch_spread_d1","stoch_spread_d3",
        "motion_pos","motion_net","motion_rise","net_rise","turn4","turn5","structure","higher_low","higher_high",
        "sweep_reclaim","reclaim_prev_high","bull_engulf","hammer","body_frac","close_loc","lower_wick"
    ]
    cols=[c for c in cols if c in z.columns]
    z=z[cols].rename(columns={c:f"{prefix}_{c}" for c in cols})
    return z.reindex(base_index,method="ffill")


def bars_since(mask, cap=9999):
    a=mask.fillna(False).to_numpy(); idx=np.arange(len(a)); last=np.where(a,idx,-10**9); last=np.maximum.accumulate(last)
    d=idx-last; d=np.where(last<0,cap,np.minimum(d,cap)); return pd.Series(d,index=mask.index)


def safe_ratio(a,b):
    return a / b.replace(0,np.nan)


def build_features(z, tf1a, tf4a):
    X=pd.DataFrame(index=z.index)
    # Only motion/shape. No absolute RSI/KDJ/W%R/StochRSI values.
    base_cols=["rsi_d1","rsi_d3","macd_hist_d1","macd_hist_d3","kdj_j_d1","kdj_j_d3","kdj_spread_d1","kdj_spread_d3","wpr_d1","wpr_d3","stoch_k_d1","stoch_k_d3","stoch_spread_d1","stoch_spread_d3","motion_pos","motion_net","motion_rise","net_rise","body_frac","close_loc","lower_wick"]
    for c in base_cols:
        if c in z: X["m15_"+c]=z[c]
    # Normalize OBV changes by recent volume to make them scale-free.
    X["m15_obv_d1_norm"]=safe_ratio(z.obv_d1,z.volume.rolling(96).median())
    X["m15_obv_d3_norm"]=safe_ratio(z.obv_d3,z.volume.rolling(96).median())
    rng=z.high-z.low
    X["m15_range_rel"]=safe_ratio(rng,rng.rolling(96).median())
    X["m15_volume_rel"]=safe_ratio(z.volume,z.volume.rolling(96).median())
    for c in ["structure","higher_low","higher_high","sweep_reclaim","reclaim_prev_high","bull_engulf","hammer"]:
        X["m15_"+c]=z[c].astype(float)

    for src,p in [(tf1a,"h1"),(tf4a,"h4")]:
        for c in src.columns:
            if c.endswith(("obv_d1","obv_d3")):
                continue
            if c.startswith(p+"_"):
                X[c]=pd.to_numeric(src[c],errors="coerce")

    # Past price motion, not future and not oscillator levels.
    X["price_ret_1h"]=z.close.pct_change(4)*100
    X["price_ret_4h"]=z.close.pct_change(16)*100
    X["price_ret_12h"]=z.close.pct_change(48)*100
    X["price_accel_1h"] = X.price_ret_1h - X.price_ret_1h.shift(4)
    X["price_accel_4h"] = X.price_ret_4h - X.price_ret_4h.shift(16)
    return X.replace([np.inf,-np.inf],np.nan)


def summarize(name, idx, fm):
    d=fm.loc[idx].dropna(subset=["ret_12h","mfe_12h","mae_12h"])
    if len(d)==0:return {"name":name,"n":0}
    return {
        "name":name,"n":int(len(d)),
        "mean_ret_3h":float(d.ret_3h.mean()),"mean_ret_6h":float(d.ret_6h.mean()),"mean_ret_12h":float(d.ret_12h.mean()),"mean_ret_24h":float(d.ret_24h.mean()),
        "median_ret_12h":float(d.ret_12h.median()),"win_12h":float((d.ret_12h>0).mean()*100),
        "mean_mfe_12h":float(d.mfe_12h.mean()),"mean_mae_12h":float(d.mae_12h.mean()),"mfe_gt_1":float((d.mfe_12h>=1).mean()*100),"ret_gt_1":float((d.ret_12h>=1).mean()*100)
    }


def bootstrap_diff(a,b,n=2000,seed=123):
    rng=np.random.default_rng(seed); a=np.asarray(a,float); b=np.asarray(b,float); vals=[]
    for _ in range(n): vals.append(rng.choice(a,len(a),True).mean()-rng.choice(b,len(b),True).mean())
    lo,hi=np.quantile(vals,[.025,.975]); return float(np.mean(vals)),float(lo),float(hi)


def main():
    base=core.fetch_15m(core.FETCH_START,core.END)
    base=base[(base.index>=core.FETCH_START)&(base.index<core.END)]
    t15=core.indicators(base); t1=core.indicators(core.resample(base,"1h")); t4=core.indicators(core.resample(base,"4h"))
    a1=core.completed_to_15m(t1,pd.Timedelta(hours=1),t15.index,"h1")
    a4=core.completed_to_15m(t4,pd.Timedelta(hours=4),t15.index,"h4")
    d1=detailed_align(t1,pd.Timedelta(hours=1),t15.index,"h1")
    d4=detailed_align(t4,pd.Timedelta(hours=4),t15.index,"h4")
    z=t15.join(a1).join(a4); z=z[(z.index>=core.START)&(z.index<core.END)].copy(); d1=d1.reindex(z.index); d4=d4.reindex(z.index)
    fm=core.forward_metrics(z[["open","high","low","close","volume"]])

    h1turn=z.h1_turn4.fillna(False)&(z.index.minute==0)
    h4turn=z.h4_turn4.fillna(False)&((z.index.hour%4)==0)&(z.index.minute==0)
    recent1=core.since_event(h1turn,16); recent4=core.since_event(h4turn,64)
    trig=(z.motion_pos>=4)&((z.turn4)|(z.motion_rise>=1))&z.structure
    broad=recent1&recent4&trig
    events=core.compress(broad,16)

    X=build_features(z,d1,d4)
    X["bars_since_h1turn"]=bars_since(h1turn,64)
    X["bars_since_h4turn"]=bars_since(h4turn,128)
    idx=events[events].index
    data=X.loc[idx].join(fm.loc[idx])
    data=data.dropna(subset=["ret_12h","mfe_12h","mae_12h"])

    feature_cols=[c for c in X.columns if c in data.columns]
    # Remove columns with excessive missingness; fill remaining with TRAIN medians only.
    train=data[data.index<core.SPLIT].copy(); hold=data[data.index>=core.SPLIT].copy()
    keep=[c for c in feature_cols if train[c].notna().mean()>=0.90 and train[c].nunique(dropna=True)>1]
    med=train[keep].median()
    Xtr=train[keep].fillna(med); Xho=hold[keep].fillna(med)
    ytr=train.ret_12h; yho=hold.ret_12h

    rf=RandomForestRegressor(n_estimators=700,max_depth=5,min_samples_leaf=25,max_features=0.65,bootstrap=True,oob_score=True,n_jobs=-1,random_state=37)
    rf.fit(Xtr,ytr)
    oob=pd.Series(rf.oob_prediction_,index=train.index)
    pred=pd.Series(rf.predict(Xho),index=hold.index)
    q80=float(oob.quantile(.80)); q90=float(oob.quantile(.90))
    sel80=pred[pred>=q80].index; sel90=pred[pred>=q90].index

    all_hold=hold.index
    summaries=[summarize("BROAD_HOLDOUT",all_hold,fm),summarize("MODEL_TOP20_HOLDOUT",sel80,fm),summarize("MODEL_TOP10_HOLDOUT",sel90,fm)]
    s=pd.DataFrame(summaries)

    diff80=bootstrap_diff(fm.loc[sel80,"ret_12h"].dropna(),fm.loc[all_hold,"ret_12h"].dropna()) if len(sel80)>5 else (np.nan,np.nan,np.nan)
    diff90=bootstrap_diff(fm.loc[sel90,"ret_12h"].dropna(),fm.loc[all_hold,"ret_12h"].dropna()) if len(sel90)>5 else (np.nan,np.nan,np.nan)

    imp=pd.DataFrame({"feature":keep,"importance":rf.feature_importances_}).sort_values("importance",ascending=False)

    # Shallow tree is not used for final selection; it exposes a human-readable movement interaction.
    tree=DecisionTreeRegressor(max_depth=3,min_samples_leaf=60,random_state=37)
    tree.fit(Xtr,ytr)
    tree_text=export_text(tree,feature_names=keep,decimals=4)

    train_mae=float(mean_absolute_error(ytr,rf.predict(Xtr))); hold_mae=float(mean_absolute_error(yho,pred)); oob_mae=float(mean_absolute_error(ytr,oob))

    out_events=hold[["ret_3h","ret_6h","ret_12h","ret_24h","mfe_12h","mae_12h"]].copy(); out_events["prediction_12h"]=pred; out_events["top20"]=out_events.index.isin(sel80); out_events["top10"]=out_events.index.isin(sel90)
    out_events.to_csv(OUT/"holdout_predictions.csv")
    imp.to_csv(OUT/"feature_importance.csv",index=False); s.to_csv(OUT/"holdout_summary.csv",index=False)
    (OUT/"shallow_tree.txt").write_text(tree_text,encoding="utf-8")

    summary={
        "base_event":"4H turn within 16h + 1H turn within 4h + structure-supported 15m movement turn",
        "absolute_indicator_levels_used_as_features":False,
        "train_events":int(len(train)),"holdout_events":int(len(hold)),"feature_count":len(keep),
        "rf_train_mae":train_mae,"rf_oob_mae":oob_mae,"rf_holdout_mae":hold_mae,"oob_cutoff_top20":q80,"oob_cutoff_top10":q90,
        "summaries":summaries,
        "top20_vs_broad_mean12h_diff_bootstrap":{"mean":diff80[0],"ci_low":diff80[1],"ci_high":diff80[2]},
        "top10_vs_broad_mean12h_diff_bootstrap":{"mean":diff90[0],"ci_low":diff90[1],"ci_high":diff90[2]},
        "top_features":imp.head(15).to_dict("records"),
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")

    lines=["# Motion Signature Discovery — true/false separation",""]
    lines.append("Bu ikinci aşama sabit RSI/W%R/KDJ/StochRSI seviyelerini özellik olarak bile kullanmaz. Yalnız değişim, eğim, spread, OBV akışı, geçmiş fiyat hareketi, mum/geometri ve zaman-dilimi dönüş gecikmeleri kullanılır.")
    lines.append("")
    lines.append(f"Baz olay: {summary['base_event']}. Keşif olayları={len(train)}, kör 2026 olayları={len(hold)}, hareket özelliği={len(keep)}.")
    lines.append(f"RF hata: train MAE={train_mae:.3f}, OOB MAE={oob_mae:.3f}, holdout MAE={hold_mae:.3f}.")
    lines.append("")
    lines.append("## 2026 sonuç")
    for r in summaries:
        lines.append(f"- {r['name']}: n={r['n']} | 3/6/12/24s ort getiri {r['mean_ret_3h']:.3f}/{r['mean_ret_6h']:.3f}/{r['mean_ret_12h']:.3f}/{r['mean_ret_24h']:.3f}% | 12s win {r['win_12h']:.1f}% | MFE {r['mean_mfe_12h']:.2f}% | MAE {r['mean_mae_12h']:.2f}%")
    lines.append(f"Top20 - broad 12s ort getiri farkı bootstrap: {diff80[0]:.3f}% [%95 GA {diff80[1]:.3f}, {diff80[2]:.3f}]")
    lines.append(f"Top10 - broad 12s ort getiri farkı bootstrap: {diff90[0]:.3f}% [%95 GA {diff90[1]:.3f}, {diff90[2]:.3f}]")
    lines.append("")
    lines.append("## En etkili hareket özellikleri")
    for _,r in imp.head(15).iterrows(): lines.append(f"- {r.feature}: {r.importance:.4f}")
    lines.append("")
    lines.append("## Sığ ağacın insan-okunur keşif kuralı")
    lines.append("```\n"+tree_text+"\n```")
    lines.append("Bu ağaç yalnız açıklama içindir; seçim Random Forest'ın 2024-2025 OOB tahmin kesimlerinden yapılır ve 2026'ya değişmeden uygulanır.")
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
