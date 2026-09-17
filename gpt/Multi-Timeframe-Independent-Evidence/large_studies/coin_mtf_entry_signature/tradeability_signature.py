from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "output" / "entry_signature_events.csv"
OUT = ROOT / "tradeability_output"
OUT.mkdir(parents=True, exist_ok=True)

TRAIN_END = pd.Timestamp("2026-05-01", tz="UTC")
CAL_END = pd.Timestamp("2026-07-01", tz="UTC")
MIN_CAL = 120


def feature_cols(df):
    prefixes=("m15_","h1_","h4_","btc4_")
    banned={
        "h1_confirm_within4h","h1_confirm_time","gross_ret_12h","net_ret_12h_cost0p2",
        "mfe_12h","mae_12h","rank_quote_volume"
    }
    out=[]
    for c in df.columns:
        if c in banned or not c.startswith(prefixes):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c]):
            out.append(c)
    return out


def metr(d,name):
    d=d.dropna(subset=["net_ret_12h_cost0p2","mfe_12h","mae_12h"])
    if not len(d): return {"name":name,"n":0}
    return {
        "name":name,"n":int(len(d)),"symbols":int(d.symbol.nunique()),
        "h1_confirm_pct":float(d.h1_confirm_within4h.mean()*100),
        "net12_mean":float(d.net_ret_12h_cost0p2.mean()),
        "net12_median":float(d.net_ret_12h_cost0p2.median()),
        "net12_win_pct":float((d.net_ret_12h_cost0p2>0).mean()*100),
        "mfe12_mean":float(d.mfe_12h.mean()),"mae12_mean":float(d.mae_12h.mean()),
        "excursion_edge_mean":float((d.mfe_12h+d.mae_12h).mean()),
        "upside_dominates_pct":float((d.mfe_12h > -d.mae_12h).mean()*100),
        "mfe_ge_1_pct":float((d.mfe_12h>=1.0).mean()*100),
        "mfe_ge_2_pct":float((d.mfe_12h>=2.0).mean()*100),
    }


def cluster_boot(selected,broad,n=3000,seed=20260918):
    syms=sorted(broad.symbol.unique())
    rng=np.random.default_rng(seed); vals=[]
    for _ in range(n):
        draw=rng.choice(syms,len(syms),replace=True)
        aa=[];bb=[]
        for s in draw:
            a=selected.loc[selected.symbol==s,"net_ret_12h_cost0p2"].dropna().to_numpy()
            b=broad.loc[broad.symbol==s,"net_ret_12h_cost0p2"].dropna().to_numpy()
            if len(a):aa.append(a)
            if len(b):bb.append(b)
        if aa and bb: vals.append(np.concatenate(aa).mean()-np.concatenate(bb).mean())
    lo,hi=np.quantile(vals,[.025,.975])
    return {"mean":float(np.mean(vals)),"ci_low":float(lo),"ci_high":float(hi)}


def top_importance(model,feats,kind):
    if kind=="logistic": vals=np.abs(model.named_steps["model"].coef_[0])
    else: vals=model.named_steps["model"].feature_importances_
    return sorted([{"feature":f,"importance":float(v)} for f,v in zip(feats,vals)],key=lambda x:x["importance"],reverse=True)[:25]


def main():
    d=pd.read_csv(SRC,low_memory=False)
    d["decision_time"]=pd.to_datetime(d.decision_time,utc=True)
    for c in ["h1_confirm_within4h"]: d[c]=pd.to_numeric(d[c],errors="coerce").fillna(0).astype(int)
    feats=feature_cols(d)
    X=d[feats].replace([np.inf,-np.inf],np.nan)

    train=(d.symbol_bucket=="DEV_SYMBOL")&(d.decision_time<TRAIN_END)
    calib=(d.symbol_bucket=="DEV_SYMBOL")&(d.decision_time>=TRAIN_END)&(d.decision_time<CAL_END)
    final=(d.symbol_bucket=="HOLDOUT_SYMBOL")&(d.decision_time>=CAL_END)
    late_all=d.decision_time>=CAL_END

    # Three distinct targets. All are FUTURE labels only; none are input features.
    y_win=(d.net_ret_12h_cost0p2>0).astype(int)
    y_dom=(d.mfe_12h > -d.mae_12h).astype(int)
    y_confirm=d.h1_confirm_within4h.astype(int)
    y_ret=d.net_ret_12h_cost0p2.astype(float)

    specs={
        "WIN_LOGISTIC":("clf",y_win,Pipeline([("imp",SimpleImputer(strategy="median")),("sc",StandardScaler()),("model",LogisticRegression(max_iter=1600,class_weight="balanced",C=.35))]),"logistic"),
        "WIN_RF":("clf",y_win,Pipeline([("imp",SimpleImputer(strategy="median")),("model",RandomForestClassifier(n_estimators=600,max_depth=8,min_samples_leaf=28,max_features="sqrt",class_weight="balanced_subsample",n_jobs=-1,random_state=41))]),"rf"),
        "DOM_RF":("clf",y_dom,Pipeline([("imp",SimpleImputer(strategy="median")),("model",RandomForestClassifier(n_estimators=600,max_depth=8,min_samples_leaf=28,max_features="sqrt",class_weight="balanced_subsample",n_jobs=-1,random_state=42))]),"rf"),
        "CONFIRM_RF":("clf",y_confirm,Pipeline([("imp",SimpleImputer(strategy="median")),("model",RandomForestClassifier(n_estimators=500,max_depth=8,min_samples_leaf=30,max_features="sqrt",class_weight="balanced_subsample",n_jobs=-1,random_state=43))]),"rf"),
        "RET_RF":("reg",y_ret,Pipeline([("imp",SimpleImputer(strategy="median")),("model",RandomForestRegressor(n_estimators=600,max_depth=8,min_samples_leaf=28,max_features="sqrt",n_jobs=-1,random_state=44))]),"rf"),
    }

    fitted={}; train_scores={}
    for name,(typ,y,m,kind) in specs.items():
        m.fit(X.loc[train],y.loc[train]); fitted[name]=(typ,m,kind)
        train_scores[name]=m.predict_proba(X.loc[train])[:,1] if typ=="clf" else m.predict(X.loc[train])

    # Also test a two-stage score: probability of eventual 1H confirmation * probability of profitable close.
    cal_scores={}; final_scores={}; late_scores={}
    for name,(typ,m,kind) in fitted.items():
        cal_scores[name]=m.predict_proba(X.loc[calib])[:,1] if typ=="clf" else m.predict(X.loc[calib])
        final_scores[name]=m.predict_proba(X.loc[final])[:,1] if typ=="clf" else m.predict(X.loc[final])
        late_scores[name]=m.predict_proba(X.loc[late_all])[:,1] if typ=="clf" else m.predict(X.loc[late_all])
    train_scores["DUAL_CONFIRM_WIN"] = np.sqrt(np.clip(train_scores["CONFIRM_RF"],0,1)*np.clip(train_scores["WIN_RF"],0,1))
    cal_scores["DUAL_CONFIRM_WIN"] = np.sqrt(np.clip(cal_scores["CONFIRM_RF"],0,1)*np.clip(cal_scores["WIN_RF"],0,1))
    final_scores["DUAL_CONFIRM_WIN"] = np.sqrt(np.clip(final_scores["CONFIRM_RF"],0,1)*np.clip(final_scores["WIN_RF"],0,1))
    late_scores["DUAL_CONFIRM_WIN"] = np.sqrt(np.clip(late_scores["CONFIRM_RF"],0,1)*np.clip(late_scores["WIN_RF"],0,1))

    # Thresholds are train-score quantiles. Which model/quantile to use is selected on calibration only.
    candidates=[]
    for name in train_scores:
        for q in [.50,.60,.70,.80,.90]:
            thr=float(np.quantile(train_scores[name],q))
            mask=cal_scores[name]>=thr
            idx=X.loc[calib].index[mask]
            if len(idx)<MIN_CAL: continue
            mm=metr(d.loc[idx],f"{name}_q{int(q*100)}")
            mm.update({"model":name,"quantile":q,"threshold":thr,"selected_frac":float(mask.mean())})
            # Profit is primary; excursion quality and sample stability are mild tie-breakers.
            mm["score"]=mm["net12_mean"] + 0.03*mm["excursion_edge_mean"] + 0.001*mm["h1_confirm_pct"]
            candidates.append(mm)
    candidates.sort(key=lambda x:x["score"],reverse=True)
    champ=candidates[0]
    name=champ["model"];thr=champ["threshold"]

    def pick(mask,scores,label):
        take=scores[name]>=thr
        idx=X.loc[mask].index[take]
        return d.loc[idx].copy(),metr(d.loc[idx],label),float(take.mean())

    fs,fm,ff=pick(final,final_scores,"FINAL_SELECTED")
    ls,lm,lf=pick(late_all,late_scores,"LATE_ALL_SELECTED")
    fb=metr(d.loc[final],"FINAL_BASE");lb=metr(d.loc[late_all],"LATE_ALL_BASE")
    boot=cluster_boot(fs,d.loc[final]) if len(fs) else {"mean":np.nan,"ci_low":np.nan,"ci_high":np.nan}

    # Frozen-model importance. For DUAL, show both component model importances.
    importance={}
    names=[name] if name!="DUAL_CONFIRM_WIN" else ["WIN_RF","CONFIRM_RF"]
    for nm in names:
        typ,m,kind=fitted[nm]
        importance[nm]=top_importance(m,feats,kind)

    pd.DataFrame(candidates).to_csv(OUT/"calibration_candidates.csv",index=False)
    fs.to_csv(OUT/"final_selected_events.csv",index=False)
    summary={
        "purpose":"Use only information known at entry-decision time to find a genuinely tradable subset, not merely to predict later 1H confirmation.",
        "lookahead_lock":{"future_features":False,"absolute_oscillator_levels":False,"entry_model":"same strict causal dataset: closed 15m decision, completed 1h/4h/BTC4h only, fill after extra 15m delay","final_double_holdout_used_for_selection":False},
        "splits":{"train":"DEV symbols <2026-05-01","calibration":"DEV symbols 2026-05-01..2026-06-30","final":"HOLDOUT symbols >=2026-07-01"},
        "events":int(len(d)),"features":len(feats),
        "champion_calibration_only":champ,
        "final":{"base":fb,"selected":{**fm,"selected_frac":ff},"selected_minus_base_cluster_bootstrap":boot},
        "late_all":{"base":lb,"selected":{**lm,"selected_frac":lf}},
        "importance":importance,
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    lines=["# Tradeability Signature — Strictly Causal","","Bu aşamada hedef artık gelecekteki 1H teyidini tahmin etmek değil; giriş anındaki hareket geometrisinden gerçekten işlem yapılabilir alt kümeyi ayırmaktır.","","- Sabit osilatör seviyesi yok.","- Gelecek 1H/4H verisi feature değil.","- Aynı katı giriş modeli korunur: sinyal kapanışı + ek 15M gecikme + sonraki açılış.","- Model/eşik yalnız calibration'da seçilir; final double-holdout dokunulmadan kalır.","",f"Champion={name} q={champ['quantile']:.2f} threshold={thr:.4f}",f"Calibration: n={champ['n']} net12={champ['net12_mean']:.3f}% win={champ['net12_win_pct']:.1f}% H1conf={champ['h1_confirm_pct']:.1f}% excursion_edge={champ['excursion_edge_mean']:.3f}%","","## FINAL double-holdout",f"BASE n={fb['n']} net12={fb['net12_mean']:.3f}% win={fb['net12_win_pct']:.1f}% MFE={fb['mfe12_mean']:.2f}% MAE={fb['mae12_mean']:.2f}%",f"SELECTED n={fm['n']} ({ff*100:.1f}%) net12={fm.get('net12_mean',np.nan):.3f}% win={fm.get('net12_win_pct',np.nan):.1f}% MFE={fm.get('mfe12_mean',np.nan):.2f}% MAE={fm.get('mae12_mean',np.nan):.2f}% H1conf={fm.get('h1_confirm_pct',np.nan):.1f}%",f"Selected-base net12 cluster bootstrap: {boot['mean']:.3f}% [%95 {boot['ci_low']:.3f}, {boot['ci_high']:.3f}]","","## Top movement features"]
    for nm,arr in importance.items():
        lines.append(f"### {nm}")
        for r in arr[:15]: lines.append(f"- {r['feature']}: {r['importance']:.4f}")
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__=="__main__": main()
