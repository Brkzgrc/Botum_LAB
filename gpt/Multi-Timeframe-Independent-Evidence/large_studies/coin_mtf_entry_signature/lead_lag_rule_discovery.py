from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
SRC=ROOT/"output"/"entry_signature_events.csv"
OUT=ROOT/"lead_lag_output"
OUT.mkdir(parents=True,exist_ok=True)
TRAIN_END=pd.Timestamp("2026-05-01",tz="UTC")
CAL_END=pd.Timestamp("2026-07-01",tz="UTC")
ULTRA_START=pd.Timestamp("2026-09-01",tz="UTC")


def hmod(s): return int(hashlib.sha256(str(s).encode()).hexdigest()[:8],16)%100

def metrics(d,name):
    d=d.dropna(subset=["net_ret_12h_cost0p2","mfe_12h","mae_12h"])
    if not len(d): return {"name":name,"n":0}
    return {"name":name,"n":int(len(d)),"symbols":int(d.symbol.nunique()),"net12_mean":float(d.net_ret_12h_cost0p2.mean()),"net12_median":float(d.net_ret_12h_cost0p2.median()),"win12":float((d.net_ret_12h_cost0p2>0).mean()*100),"h1_confirm":float(d.h1_confirm_within4h.mean()*100),"mfe12":float(d.mfe_12h.mean()),"mae12":float(d.mae_12h.mean()),"excursion_edge":float((d.mfe_12h+d.mae_12h).mean())}

def cluster_boot(a,b,n=4000,seed=918):
    syms=sorted(b.symbol.unique());rng=np.random.default_rng(seed);v=[]
    for _ in range(n):
        draw=rng.choice(syms,len(syms),replace=True);aa=[];bb=[]
        for s in draw:
            x=a.loc[a.symbol==s,"net_ret_12h_cost0p2"].dropna().to_numpy();y=b.loc[b.symbol==s,"net_ret_12h_cost0p2"].dropna().to_numpy()
            if len(x):aa.append(x)
            if len(y):bb.append(y)
        if aa and bb:v.append(np.concatenate(aa).mean()-np.concatenate(bb).mean())
    lo,hi=np.quantile(v,[.025,.975]);return {"mean":float(np.mean(v)),"ci_low":float(lo),"ci_high":float(hi)}

def safe(d,c): return pd.to_numeric(d[c],errors="coerce") if c in d else pd.Series(np.nan,index=d.index)

def build_tokens(d):
    T={}
    # 15M trigger quality: movement count/direction and price structure only.
    T["M15_POS5"] = safe(d,"m15_motion_pos")>=5
    T["M15_POS6"] = safe(d,"m15_motion_pos")>=6
    T["M15_RISING"] = safe(d,"m15_motion_rise")>0
    for c,n in [("m15_sweep_reclaim","M15_SWEEP"),("m15_bull_engulf","M15_ENGULF"),("m15_reclaim_prev_high","M15_RECLAIM_HIGH")]: T[n]=safe(d,c)>0
    T["M15_HL_HH"]=(safe(d,"m15_higher_low")>0)&(safe(d,"m15_higher_high")>0)
    T["STOCH_M0PP"] = d.stoch_pattern.astype(str).eq("-0++")
    T["STOCH_M00P"] = d.stoch_pattern.astype(str).eq("-00+")

    # The hypothesis from the previous experiment: 15M leads while the LAST COMPLETED 1H is still weak.
    T["H1_NET_NEG"] = safe(d,"h1_motion_net")<0
    T["H1_NET_NONPOS"] = safe(d,"h1_motion_net")<=0
    T["H1_RISE_NEG"] = safe(d,"h1_motion_rise")<0
    T["H1_PRICE1_NEG"] = safe(d,"h1_price_ret_1")<0
    T["H1_BODY_NEG"] = safe(d,"h1_body_signed_pct")<0

    # Higher-TF support is movement-based, never oscillator-level based.
    T["H4_NET_POS"] = safe(d,"h4_motion_net")>0
    T["H4_RISING"] = safe(d,"h4_motion_rise")>0
    T["H4_PRICE1_POS"] = safe(d,"h4_price_ret_1")>0
    T["BTC4_NET_POS"] = safe(d,"btc4_motion_net")>0
    T["BTC4_RISING"] = safe(d,"btc4_motion_rise")>0
    T["BTC4_PRICE1_POS"] = safe(d,"btc4_price_ret_1")>0

    fam=[("rsi","rsi"),("macd_hist","macd"),("kdj_j","kdj"),("wpr","wpr"),("obv","obv"),("stoch_k","stoch")]
    lead=[];h4sup=[];btcsup=[]
    for col,label in fam:
        m=safe(d,f"m15_{col}_d1n");h=safe(d,f"h1_{col}_d1n");q=safe(d,f"h4_{col}_d1n");b=safe(d,f"btc4_{col}_d1n")
        x=(m>0)&(h<=0);T[f"LEAD_{label.upper()}"]=x;lead.append(x.astype(int))
        h4sup.append((q>0).astype(int));btcsup.append((b>0).astype(int))
    lead_count=sum(lead); h4_count=sum(h4sup); btc_count=sum(btcsup)
    for k in [2,3,4]: T[f"LEAD_FAMILIES_{k}P"] = lead_count>=k
    for k in [3,4]: T[f"H4_FAMILIES_{k}P"] = h4_count>=k; T[f"BTC4_FAMILIES_{k}P"] = btc_count>=k

    # Relative lead gap uses only directional movement scores.
    gap=safe(d,"m15_motion_net")-safe(d,"h1_motion_net")
    T["LEAD_GAP4"] = gap>=4
    T["LEAD_GAP6"] = gap>=6
    return T

def main():
    d=pd.read_csv(SRC,low_memory=False);d["decision_time"]=pd.to_datetime(d.decision_time,utc=True);d["hash_mod"]=d.symbol.map(hmod)
    train=(d.symbol_bucket=="DEV_SYMBOL")&(d.decision_time<TRAIN_END)
    cal=(d.symbol_bucket=="DEV_SYMBOL")&(d.decision_time>=TRAIN_END)&(d.decision_time<CAL_END)
    final=(d.symbol_bucket=="HOLDOUT_SYMBOL")&(d.decision_time>=CAL_END)
    # New reserve created before these rules are inspected: half of held-out symbols, September only.
    ultra=(d.hash_mod<15)&(d.decision_time>=ULTRA_START)
    T=build_tokens(d); names=list(T)

    rows=[]
    combos=[]
    for r in [1,2,3]:
        combos.extend(itertools.combinations(names,r))
    for combo in combos:
        m=pd.Series(True,index=d.index)
        for n in combo:m &= T[n].fillna(False)
        ti=d.loc[train&m];ca=d.loc[cal&m]
        if len(ti)<160 or len(ca)<80:continue
        tm=metrics(ti,"train");cm=metrics(ca,"cal")
        rec={"rule":" & ".join(combo),"parts":len(combo),"train_n":tm["n"],"cal_n":cm["n"],"train_net":tm["net12_mean"],"cal_net":cm["net12_mean"],"train_win":tm["win12"],"cal_win":cm["win12"],"train_h1":tm["h1_confirm"],"cal_h1":cm["h1_confirm"],"train_exc":tm["excursion_edge"],"cal_exc":cm["excursion_edge"]}
        rec["conservative_net"]=min(rec["train_net"],rec["cal_net"])
        rec["score"]=rec["conservative_net"] + .01*min(rec["train_exc"],rec["cal_exc"])
        rows.append(rec)
    tab=pd.DataFrame(rows).sort_values(["score","cal_n"],ascending=[False,False])
    tab.to_csv(OUT/"all_candidate_rules.csv",index=False)
    if tab.empty:raise RuntimeError("no candidates")

    # Prefer a rule that was positive in both development periods. If none exist, report best conservative rule but do not promote it.
    stable=tab[(tab.train_net>0)&(tab.cal_net>0)]
    chosen=(stable.iloc[0] if len(stable) else tab.iloc[0])
    parts=chosen.rule.split(" & ");mask=pd.Series(True,index=d.index)
    for n in parts:mask &= T[n].fillna(False)

    base_train=metrics(d.loc[train],"TRAIN_BASE");base_cal=metrics(d.loc[cal],"CAL_BASE");base_final=metrics(d.loc[final],"FINAL_BASE");base_ultra=metrics(d.loc[ultra],"ULTRA_BASE")
    sel_train=metrics(d.loc[train&mask],"TRAIN_SELECTED");sel_cal=metrics(d.loc[cal&mask],"CAL_SELECTED");sel_final=metrics(d.loc[final&mask],"FINAL_SELECTED");sel_ultra=metrics(d.loc[ultra&mask],"ULTRA_SELECTED")
    boot_final=cluster_boot(d.loc[final&mask],d.loc[final]) if sel_final.get("n",0)>0 else None
    boot_ultra=cluster_boot(d.loc[ultra&mask],d.loc[ultra],n=3000,seed=919) if sel_ultra.get("n",0)>0 and base_ultra.get("symbols",0)>1 else None

    summary={"absolute_oscillator_levels_used":False,"future_features_used":False,"rule_search":"movement/lead-lag states only; singles+pairs+triples selected on DEV train+calibration only","ultra_holdout":"hash<15 symbols and t>=2026-09-01; not used for selection","token_count":len(names),"tested_rules":int(len(tab)),"stable_positive_dev_rules":int(len(stable)),"chosen_rule":chosen.to_dict(),"train":{"base":base_train,"selected":sel_train},"calibration":{"base":base_cal,"selected":sel_cal},"final_double_holdout":{"base":base_final,"selected":sel_final,"bootstrap_selected_minus_base":boot_final},"ultra_holdout":{"base":base_ultra,"selected":sel_ultra,"bootstrap_selected_minus_base":boot_ultra}}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    d.loc[mask].to_csv(OUT/"chosen_rule_events.csv",index=False)
    lines=["# Lead-Lag Movement Rule Discovery — Strictly Causal","","Arama sabit RSI/KDJ/W%R/StochRSI değerleri kullanmaz. Yalnız hareket yönleri, 15M→1H lead/lag ilişkisi, kapanmış H4/BTC4 hareketi ve mum/fiyat yapısı kullanılır.","",f"Token={len(names)} | test edilen kural={len(tab)} | train+calibration'da ikisi de pozitif kural={len(stable)}",f"Seçilen: `{chosen.rule}`",f"Train: n={sel_train['n']} net12={sel_train['net12_mean']:.3f}% win={sel_train['win12']:.1f}%",f"Calibration: n={sel_cal['n']} net12={sel_cal['net12_mean']:.3f}% win={sel_cal['win12']:.1f}%","","## Final double-holdout",f"Base: n={base_final['n']} net12={base_final['net12_mean']:.3f}% win={base_final['win12']:.1f}%",f"Selected: n={sel_final.get('n',0)} net12={sel_final.get('net12_mean',np.nan):.3f}% win={sel_final.get('win12',np.nan):.1f}%",f"Bootstrap selected-base: {boot_final}","","## Ultra holdout (yeni rezerv)",f"Base: n={base_ultra.get('n',0)} net12={base_ultra.get('net12_mean',np.nan):.3f}%",f"Selected: n={sel_ultra.get('n',0)} net12={sel_ultra.get('net12_mean',np.nan):.3f}% win={sel_ultra.get('win12',np.nan):.1f}%",f"Bootstrap selected-base: {boot_ultra}"]
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__=="__main__":main()
