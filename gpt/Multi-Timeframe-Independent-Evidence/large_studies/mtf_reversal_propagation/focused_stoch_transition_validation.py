from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import mtf_reversal_propagation as core
import directional_sequence_mining as dsm

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"focused_output"
OUT.mkdir(parents=True,exist_ok=True)


def metric(idx,fm):
    d=fm.loc[idx].dropna(subset=["ret_12h","mfe_12h","mae_12h"])
    if not len(d): return {"n":0}
    return {"n":int(len(d)),"ret3":float(d.ret_3h.mean()),"ret6":float(d.ret_6h.mean()),"ret12":float(d.ret_12h.mean()),"ret24":float(d.ret_24h.mean()),"median12":float(d.ret_12h.median()),"win12":float((d.ret_12h>0).mean()*100),"mfe12":float(d.mfe_12h.mean()),"mae12":float(d.mae_12h.mean())}


def next_event_after(t,event_idx,max_h):
    pos=event_idx.searchsorted(t,side="right")
    if pos>=len(event_idx): return pd.NaT
    q=event_idx[pos]
    return q if q<=t+pd.Timedelta(hours=max_h) else pd.NaT


def bootstrap_diff(a,b,n=3000,seed=77):
    rng=np.random.default_rng(seed);a=np.asarray(a,float);b=np.asarray(b,float);vals=[]
    for _ in range(n):vals.append(rng.choice(a,len(a),True).mean()-rng.choice(b,len(b),True).mean())
    lo,hi=np.quantile(vals,[.025,.975]);return float(np.mean(vals)),float(lo),float(hi)


def main():
    base=core.fetch_15m(core.FETCH_START,core.END);base=base[(base.index>=core.FETCH_START)&(base.index<core.END)]
    t15=core.indicators(base);t1=core.indicators(core.resample(base,"1h"));t4=core.indicators(core.resample(base,"4h"))
    a1=core.completed_to_15m(t1,pd.Timedelta(hours=1),t15.index,"h1");a4=core.completed_to_15m(t4,pd.Timedelta(hours=4),t15.index,"h4")
    z=t15.join(a1).join(a4);z=z[(z.index>=core.START)&(z.index<core.END)].copy()
    fm=core.forward_metrics(z[["open","high","low","close","volume"]])
    p15=dsm.patterns(t15,4,"M15").reindex(z.index)

    h4ctx=(z.h4_motion_pos>=2)&((z.h4_motion_rise>=0)|(z.h4_motion_net>z.h4_motion_net.shift(16)))
    trig=(z.motion_pos>=4)&((z.turn4)|(z.motion_rise>=1))&z.structure
    broad=core.compress(h4ctx&trig,16)
    broad_idx=broad[broad].index
    pat=p15.loc[broad_idx,"M15_STOCH_P4"]
    chosen=pat.isin(["-0++","-00+"])
    setup_idx=broad_idx[chosen]

    h1mask=z.h1_turn4.fillna(False)&(z.index.minute==0); h4mask=z.h4_turn4.fillna(False)&((z.index.hour%4)==0)&(z.index.minute==0)
    h1idx=z.index[h1mask];h4idx=z.index[h4mask]

    rows=[]
    for t in setup_idx:
        n1_1=next_event_after(t,h1idx,1);n1_2=next_event_after(t,h1idx,2);n1_4=next_event_after(t,h1idx,4)
        n4_4=next_event_after(t,h4idx,4);n4_8=next_event_after(t,h4idx,8);n4_12=next_event_after(t,h4idx,12)
        ordered=pd.notna(n1_4) and pd.notna(n4_12) and n1_4<n4_12
        rows.append({"entry":t,"pattern":p15.loc[t,"M15_STOCH_P4"],"h1_within1h":pd.notna(n1_1),"h1_within2h":pd.notna(n1_2),"h1_within4h":pd.notna(n1_4),"h1_time":n1_4,"h4_within4h":pd.notna(n4_4),"h4_within8h":pd.notna(n4_8),"h4_within12h":pd.notna(n4_12),"h4_time":n4_12,"ordered_15_1_4":ordered})
    ev=pd.DataFrame(rows).set_index("entry")
    ev=ev.join(fm.loc[ev.index])
    ev.to_csv(OUT/"events.csv")

    summary={"setup":"4H movement context + 15M structure-supported multi-indicator turn + StochRSI motion state (-0++ OR -00+)","fixed_oscillator_levels":False,"years":{}}
    for y in [2024,2025,2026]:
        e=ev[ev.index.year==y]; bi=broad_idx[broad_idx.year==y]
        m=metric(e.index,fm); bm=metric(bi,fm)
        rec={"setup":m,"broad":bm,"h1_confirm_1h_pct":float(e.h1_within1h.mean()*100),"h1_confirm_2h_pct":float(e.h1_within2h.mean()*100),"h1_confirm_4h_pct":float(e.h1_within4h.mean()*100),"h4_confirm_4h_pct":float(e.h4_within4h.mean()*100),"h4_confirm_8h_pct":float(e.h4_within8h.mean()*100),"h4_confirm_12h_pct":float(e.h4_within12h.mean()*100),"ordered_15m_1h_4h_pct":float(e.ordered_15_1_4.mean()*100)}
        # Entry delayed to actual 1H confirmation, if it arrives within 4h.
        ci=pd.DatetimeIndex(e.h1_time.dropna().unique())
        rec["entry_at_h1_confirmation"]=metric(ci,fm)
        rec["setup_if_h1_confirms_within4h"]=metric(e.index[e.h1_within4h],fm)
        rec["setup_if_no_h1_confirm_within4h"]=metric(e.index[~e.h1_within4h],fm)
        summary["years"][str(y)]=rec

    a=ev.loc[ev.index.year==2026,"ret_12h"].dropna();b=fm.loc[broad_idx[broad_idx.year==2026],"ret_12h"].dropna();summary["holdout_setup_vs_broad_bootstrap_12h"]=dict(zip(["mean","ci_low","ci_high"],bootstrap_diff(a,b)))
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    lines=["# Focused StochRSI Motion Transition Validation",""]
    lines.append("Setup sabit StochRSI seviyesi kullanmaz. `-0++` ve `-00+`, StochRSI K hareketi + K/D spread hareketinin 15 dakikalık yön durumlarıdır: düşüş -> nötrleme -> yukarı dönüş.")
    lines.append("")
    for y in [2024,2025,2026]:
        r=summary['years'][str(y)];m=r['setup'];lines.append(f"## {y}\nSetup n={m['n']} | 3/6/12/24s ort {m.get('ret3',np.nan):.3f}/{m.get('ret6',np.nan):.3f}/{m.get('ret12',np.nan):.3f}/{m.get('ret24',np.nan):.3f}% | 12s win {m.get('win12',np.nan):.1f}% | MFE {m.get('mfe12',np.nan):.2f}% | MAE {m.get('mae12',np.nan):.2f}%.\n1H teyit <=1/2/4s: {r['h1_confirm_1h_pct']:.1f}/{r['h1_confirm_2h_pct']:.1f}/{r['h1_confirm_4h_pct']:.1f}%. 4H teyit <=4/8/12s: {r['h4_confirm_4h_pct']:.1f}/{r['h4_confirm_8h_pct']:.1f}/{r['h4_confirm_12h_pct']:.1f}%. Sıralı 15M->1H->4H: {r['ordered_15m_1h_4h_pct']:.1f}%.\n")
        c=r['setup_if_h1_confirms_within4h'];n=r['setup_if_no_h1_confirm_within4h'];lines.append(f"15M girişten sonra 1H <=4s teyit GELİRSE: n={c.get('n',0)}, 12s={c.get('ret12',np.nan):.3f}%, win={c.get('win12',np.nan):.1f}%. Teyit GELMEZSE: n={n.get('n',0)}, 12s={n.get('ret12',np.nan):.3f}%, win={n.get('win12',np.nan):.1f}%.\n")
    d=summary['holdout_setup_vs_broad_bootstrap_12h'];lines.append(f"2026 setup - geniş olay 12s getiri farkı: {d['mean']:.3f}% [%95 GA {d['ci_low']:.3f}, {d['ci_high']:.3f}].")
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__=="__main__":main()
