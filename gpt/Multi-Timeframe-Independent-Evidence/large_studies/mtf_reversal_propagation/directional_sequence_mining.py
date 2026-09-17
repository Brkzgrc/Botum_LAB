from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

import mtf_reversal_propagation as core

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"sequence_output"
OUT.mkdir(parents=True,exist_ok=True)
FAMS=["RSI","MACD","KDJ","WPR","OBV","STOCH"]


def direction_frame(x):
    f=pd.DataFrame(index=x.index)
    f["RSI"]=np.sign(x.rsi_d1.fillna(0))+np.sign(x.rsi_d3.fillna(0))
    f["MACD"]=np.sign(x.macd_hist_d1.fillna(0))+np.sign(x.macd_hist_d3.fillna(0))
    f["KDJ"]=np.sign(x.kdj_j_d1.fillna(0))+np.sign(x.kdj_spread_d1.fillna(0))
    f["WPR"]=np.sign(x.wpr_d1.fillna(0))+np.sign(x.wpr_d3.fillna(0))
    f["OBV"]=np.sign(x.obv_d1.fillna(0))+np.sign(x.obv_d3.fillna(0))
    f["STOCH"]=np.sign(x.stoch_k_d1.fillna(0))+np.sign(x.stoch_spread_d1.fillna(0))
    return f.apply(np.sign).astype(int)


def pat_char(v):
    return "+" if v>0 else ("-" if v<0 else "0")


def patterns(df,n,prefix):
    d=direction_frame(df); out=pd.DataFrame(index=df.index)
    for fam in FAMS:
        pieces=[]
        for lag in range(n-1,-1,-1): pieces.append(d[fam].shift(lag).map(pat_char))
        s=pieces[0]
        for p in pieces[1:]: s=s+p
        out[f"{prefix}_{fam}_P{n}"]=s
    return out


def align_completed(pats,delta,index):
    z=pats.copy(); z.index=z.index+delta
    return z.reindex(index,method="ffill")


def metric(idx,fm):
    d=fm.loc[idx].dropna(subset=["ret_12h","mfe_12h","mae_12h"])
    if not len(d): return {"n":0,"mean12":np.nan,"median12":np.nan,"win12":np.nan,"mfe12":np.nan,"mae12":np.nan,"mean24":np.nan}
    return {"n":int(len(d)),"mean12":float(d.ret_12h.mean()),"median12":float(d.ret_12h.median()),"win12":float((d.ret_12h>0).mean()*100),"mfe12":float(d.mfe_12h.mean()),"mae12":float(d.mae_12h.mean()),"mean24":float(d.ret_24h.mean())}


def bootstrap_diff(a,b,n=3000,seed=91):
    rng=np.random.default_rng(seed); a=np.asarray(a,float); b=np.asarray(b,float); vals=[]
    for _ in range(n): vals.append(rng.choice(a,len(a),True).mean()-rng.choice(b,len(b),True).mean())
    q=np.quantile(vals,[.025,.975]); return float(np.mean(vals)),float(q[0]),float(q[1])


def main():
    base=core.fetch_15m(core.FETCH_START,core.END); base=base[(base.index>=core.FETCH_START)&(base.index<core.END)]
    t15=core.indicators(base); t1=core.indicators(core.resample(base,"1h")); t4=core.indicators(core.resample(base,"4h"))
    a1=core.completed_to_15m(t1,pd.Timedelta(hours=1),t15.index,"h1"); a4=core.completed_to_15m(t4,pd.Timedelta(hours=4),t15.index,"h4")
    z=t15.join(a1).join(a4); z=z[(z.index>=core.START)&(z.index<core.END)].copy()
    fm=core.forward_metrics(z[["open","high","low","close","volume"]])

    p15=patterns(t15,4,"M15").reindex(z.index)
    p1=align_completed(patterns(t1,4,"H1"),pd.Timedelta(hours=1),z.index)
    p4=align_completed(patterns(t4,3,"H4"),pd.Timedelta(hours=4),z.index)
    P=p15.join(p1).join(p4)

    # Broad movement setup: permissive 4H improvement + structure-supported 15M turn.
    h4ctx=(z.h4_motion_pos>=2)&((z.h4_motion_rise>=0)|(z.h4_motion_net>z.h4_motion_net.shift(16)))
    trig=(z.motion_pos>=4)&((z.turn4)|(z.motion_rise>=1))&z.structure
    ev=core.compress(h4ctx&trig,16)
    idx=ev[ev].index
    P=P.loc[idx].copy()
    # Dynamic price-action tokens only.
    P["S_SWEEP"]=z.loc[idx,"sweep_reclaim"].map(lambda v:"Y" if v else "N")
    P["S_ENGULF"]=z.loc[idx,"bull_engulf"].map(lambda v:"Y" if v else "N")
    P["S_RECLAIM"]=z.loc[idx,"reclaim_prev_high"].map(lambda v:"Y" if v else "N")
    P["S_HLHH"]=(z.loc[idx,"higher_low"]&z.loc[idx,"higher_high"]).map(lambda v:"Y" if v else "N")

    # Base metrics by year.
    years={2024:idx[idx.year==2024],2025:idx[idx.year==2025],2026:idx[idx.year==2026]}
    base_metrics={str(y):metric(ix,fm) for y,ix in years.items()}

    # Tokens are categorical direction sequences, e.g. H4_STOCH_P3=--+.
    token_masks={}
    for c in P.columns:
        vc=P.loc[P.index.year.isin([2024,2025]),c].value_counts()
        for val,n in vc.items():
            if n>=80:
                token=f"{c}={val}"; token_masks[token]=(P[c]==val)

    singles=[]
    stable=[]
    for tok,m in token_masks.items():
        rec={"token":tok}
        ok=True; vals=[]
        for y in [2024,2025,2026]:
            ix=P.index[m & (P.index.year==y)]; mm=metric(ix,fm)
            for k,v in mm.items(): rec[f"{y}_{k}"]=v
            if y in [2024,2025]:
                basey=base_metrics[str(y)]["mean12"]
                if mm["n"]<35 or not np.isfinite(mm["mean12"]) or mm["mean12"]<=basey: ok=False
                vals.append(mm["mean12"]-basey if np.isfinite(mm["mean12"]) else -99)
        rec["conservative_train_lift"]=min(vals)
        singles.append(rec)
        if ok: stable.append((tok,rec["conservative_train_lift"]))
    singles=pd.DataFrame(singles).sort_values("conservative_train_lift",ascending=False)
    stable=sorted(stable,key=lambda x:x[1],reverse=True)[:24]

    pairs=[]
    for (a,_),(b,_) in itertools.combinations(stable,2):
        ma=token_masks[a]; mb=token_masks[b]; m=ma&mb
        rec={"pair":a+" AND "+b}; ok=True; lifts=[]
        for y in [2024,2025,2026]:
            ix=P.index[m & (P.index.year==y)]; mm=metric(ix,fm)
            for k,v in mm.items():rec[f"{y}_{k}"]=v
            if y in [2024,2025]:
                basey=base_metrics[str(y)]["mean12"]
                if mm["n"]<25 or not np.isfinite(mm["mean12"]) or mm["mean12"]<=basey: ok=False
                lifts.append(mm["mean12"]-basey if np.isfinite(mm["mean12"]) else -99)
        if ok:
            rec["conservative_train_lift"]=min(lifts); pairs.append(rec)
    pairs=pd.DataFrame(pairs)
    if len(pairs): pairs=pairs.sort_values(["conservative_train_lift","2025_n"],ascending=[False,False])

    # Champion picked from 2024+2025 only, with no 2026 information.
    if len(pairs):
        champ_type="pair"; champ=pairs.iloc[0]["pair"]; parts=champ.split(" AND "); cm=token_masks[parts[0]]&token_masks[parts[1]]
    elif stable:
        champ_type="single"; champ=stable[0][0]; cm=token_masks[champ]
    else:
        champ_type="none"; champ=None; cm=pd.Series(False,index=P.index)

    champ_metrics={str(y):metric(P.index[cm&(P.index.year==y)],fm) for y in [2024,2025,2026]}
    ix26=P.index[P.index.year==2026]; champ26=P.index[cm&(P.index.year==2026)]
    diff=(np.nan,np.nan,np.nan)
    if len(champ26)>5:
        diff=bootstrap_diff(fm.loc[champ26,"ret_12h"].dropna(),fm.loc[ix26,"ret_12h"].dropna())

    # Store exact holdout events so we can inspect winners/losers later.
    if champ:
        ce=z.loc[champ26,["open","high","low","close","motion_pos","motion_net","structure"]].join(P.loc[champ26]).join(fm.loc[champ26])
        ce.to_csv(OUT/"champion_2026_events.csv")
    singles.to_csv(OUT/"single_patterns.csv",index=False); pairs.to_csv(OUT/"pair_patterns.csv",index=False)

    summary={
        "absolute_indicator_levels_used":False,
        "pattern_definition":{"15m":"last 4 direction states","1h":"last 4 completed 1H direction states","4h":"last 3 completed 4H direction states"},
        "base_event_count":{"2024":len(years[2024]),"2025":len(years[2025]),"2026":len(years[2026])},
        "base_metrics":base_metrics,"stable_single_count":len(stable),"stable_pair_count":int(len(pairs)),
        "champion_type":champ_type,"champion":champ,"champion_metrics":champ_metrics,
        "holdout_12h_mean_return_lift_vs_broad_bootstrap":{"mean":diff[0],"ci_low":diff[1],"ci_high":diff[2]},
        "top_stable_singles":singles.head(12).to_dict("records"),
        "top_stable_pairs":pairs.head(12).to_dict("records") if len(pairs) else []
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    lines=["# Directional Sequence Mining — sabit değer yok",""]
    lines.append("Bu aşama RSI=30, W%R=-80, StochRSI=20 gibi hiçbir sabit gösterge değerini kullanmaz. Her gösterge yalnız + / - / 0 yön dizisine çevrilir. Örnek: `H4_STOCH_P3=--+` son üç tamamlanmış 4H barda StochRSI hareketinin aşağı, aşağı, yukarı döndüğü anlamına gelir.")
    lines.append("")
    lines.append(f"Geniş olay sayısı: 2024={len(years[2024])}, 2025={len(years[2025])}, kör 2026={len(years[2026])}.")
    lines.append(f"2024 ve 2025'in ikisinde de geniş tabandan iyi kalan tekil desen={len(stable)}; ikili desen={len(pairs)}.")
    lines.append(f"Keşif/ara-validasyonla seçilen setup: **{champ}**")
    for y in [2024,2025,2026]:
        m=champ_metrics[str(y)]; lines.append(f"- {y}: n={m['n']} | 12s ort {m['mean12']:.3f}% | medyan {m['median12']:.3f}% | win {m['win12']:.1f}% | MFE {m['mfe12']:.2f}% | MAE {m['mae12']:.2f}% | 24s ort {m['mean24']:.3f}%")
    lines.append(f"2026 setup - geniş taban 12s getiri farkı bootstrap: {diff[0]:.3f}% [%95 GA {diff[1]:.3f}, {diff[2]:.3f}]")
    lines.append("")
    lines.append("## En güçlü tekil yön desenleri")
    for _,r in singles.head(12).iterrows(): lines.append(f"- {r.token} | train konservatif lift {r.conservative_train_lift:.3f}% | 2026 n={int(r['2026_n'])}, 12s={r['2026_mean12']:.3f}%")
    if len(pairs):
        lines.append("\n## En güçlü ikili yön desenleri")
        for _,r in pairs.head(12).iterrows(): lines.append(f"- {r['pair']} | train konservatif lift {r.conservative_train_lift:.3f}% | 2026 n={int(r['2026_n'])}, 12s={r['2026_mean12']:.3f}%")
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__=="__main__":main()
