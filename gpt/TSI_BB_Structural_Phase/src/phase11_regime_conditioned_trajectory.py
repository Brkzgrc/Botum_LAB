from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
import phase10_cross_holdout_gated_trajectory as p10

H=p10.HORIZONS

def met(x): return p10.metrics(x)
def ok(m,h,n=15):
    return m.get('n',0)>=n and m.get(f'win{h}',0)>=55 and m.get(f'mean{h}',-99)>0.75 and m.get(f'median{h}',-99)>0 and (m.get(f'pf{h}') or 0)>=1.4

def main(indir,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    d=p10.load(indir); d['row_id']=np.arange(len(d)); res={}; errs=[]
    from concurrent.futures import ThreadPoolExecutor,as_completed
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs=[ex.submit(p10.fetch_path,r) for r in d.itertuples(index=False)]
        for k,f in enumerate(as_completed(fs),1):
            rid,v,e=f.result()
            if e: errs.append({'row_id':rid,'error':e})
            else: res[rid]=v
            if k%100==0 or k==len(fs): print(f'[PATH] {k}/{len(fs)} ok={len(res)} err={len(errs)}',flush=True)
    g=d[d.row_id.isin(res)].copy().reset_index(drop=True)
    X={lb:np.vstack([res[int(r)][0][lb] for r in g.row_id]) for lb in p10.LOOKBACKS}
    g['dd48']=[res[int(r)][1] for r in g.row_id]
    r2=(g.btc1_tsi_d1<=-0.211069)&(g.btc4_bb_width>=0.0942267)&(g.h4_bb_width>=p10.R2_BB)&(g.dd48<=p10.R2_DD)
    t=g.decision_time
    disc=(g.hash_mod>=30)&(t<pd.Timestamp('2025-01-01',tz='UTC'))
    cal=(g.hash_mod>=30)&(t>=pd.Timestamp('2025-01-01',tz='UTC'))&(t<pd.Timestamp('2026-01-01',tz='UTC'))
    cross=(g.hash_mod<30)&(t<pd.Timestamp('2026-01-01',tz='UTC'))
    y26=t>=pd.Timestamp('2026-01-01',tz='UTC'); pool=~r2
    # Regimes are defined only from causal BTC state already present at decision time.
    regimes={
      'TSI_DEEP':g.btc1_tsi_d1<=-0.21,
      'TSI_MID':(g.btc1_tsi_d1>-0.21)&(g.btc1_tsi_d1<=-0.05),
      'TSI_FLAT':g.btc1_tsi_d1>-0.05,
      'BTCBB_HIGH':g.btc4_bb_width>=0.094,
      'BTCBB_LOW':g.btc4_bb_width<0.094,
      'ALTBB_HIGH':g.h4_bb_width>=p10.R2_BB,
      'ALTBB_LOW':g.h4_bb_width<p10.R2_BB,
    }
    cand=[]; masks={}
    for rn,rg in regimes.items():
      for lb in p10.LOOKBACKS:
       for oh in H:
        built=p10.build_score(X,g,disc&rg,r2,lb,oh)
        if built is None: continue
        score,_,_,_=built
        base=pd.Series(score,index=g.index)
        sd=base[disc&rg&pool].dropna()
        if len(sd)<30: continue
        for q in [.70,.75,.80,.85,.875,.90,.925,.95]:
          th=float(sd.quantile(q)); m=rg&pool&(base>=th)
          md,mc,mx=met(g[disc&m]),met(g[cal&m]),met(g[cross&m])
          hs=[h for h in H if ok(md,h,15) and ok(mc,h,15) and ok(mx,h,20)]
          if not hs: continue
          def sc(h): return min(md[f'mean{h}'],mc[f'mean{h}'],mx[f'mean{h}']) + .02*min(md[f'win{h}'],mc[f'win{h}'],mx[f'win{h}']) + .12*min(md[f'pf{h}'],mc[f'pf{h}'],mx[f'pf{h}'])
          bh=max(hs,key=sc); name=f'{rn}_LB{lb}_P{oh}_Q{int(q*1000)}'
          rec={'name':name,'regime':rn,'lookback':lb,'prototype_h':oh,'q':q,'best_h':bh,'score':sc(bh),'discovery':md,'calibration':mc,'cross':mx}
          cand.append(rec); masks[name]=m
    cand.sort(key=lambda z:z['score'],reverse=True)
    # Greedy additions must preserve quality at the candidate's own pre-2026-selected horizon.
    union=r2.copy(); selected=[]
    for c in cand:
      trial=union|masks[c['name']]; h=c['best_h']
      md,mc,mx=met(g[disc&trial]),met(g[cal&trial]),met(g[cross&trial])
      if ok(md,h,20) and ok(mc,h,20) and ok(mx,h,20) and int((trial&~union&cross).sum())>0:
        selected.append(c['name']); union=trial
        if len(selected)>=5: break
    weeks=(pd.Timestamp('2026-09-18',tz='UTC')-pd.Timestamp('2026-01-01',tz='UTC')).days/7
    out={'method':'Causal BTC/alt volatility-regime-conditioned trajectory reverse engineering. Selection uses discovery+calibration+cross-holdout PRE-2026 only; 2026 is sealed until final evaluation.','selection_uses_2026':False,'events':len(g),'errors':len(errs),'robust_candidates':len(cand),'selected':selected,'r2_2026':met(g[y26&r2]),'expanded_2026':met(g[y26&union]),'signals_per_week_2026':int((y26&union).sum())/weeks,'top_candidates':[{**c,'all_2026':met(g[y26&masks[c['name']]])} for c in cand[:12]]}
    (outdir/'summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    (outdir/'REPORT.md').write_text('# Phase 11 Regime-Conditioned Trajectory\n\n```json\n'+json.dumps(out,indent=2,ensure_ascii=False)+'\n```\n',encoding='utf-8')
    pd.DataFrame(errs).to_csv(outdir/'errors.csv',index=False)
    print(json.dumps(out,ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--artifact-dir',type=Path,required=True); a.add_argument('--outdir',type=Path,required=True); x=a.parse_args(); main(x.artifact_dir,x.outdir)
