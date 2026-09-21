from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
import phase10_cross_holdout_gated_trajectory as p10

H=p10.HORIZONS

def met(x): return p10.metrics(x)
def quality(m,h,n=12):
    if m.get('n',0)<n: return False
    w=m.get(f'win{h}',0); mean=m.get(f'mean{h}',-99); med=m.get(f'median{h}',-99); pf=(m.get(f'pf{h}') or 0)
    # WR may be lower only when payoff quality compensates materially.
    return med>0 and ((w>=55 and mean>.75 and pf>=1.4) or (w>=45 and mean>=1.5 and pf>=2.0))
def utility(m,h):
    return m[f'mean{h}'] + .35*m[f'median{h}'] + .18*min(m[f'pf{h}'],10) + .012*m[f'win{h}']

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
    deep=g.btc1_tsi_d1<=-0.21; mid=(g.btc1_tsi_d1>-0.21)&(g.btc1_tsi_d1<=-0.05); flat=g.btc1_tsi_d1>-0.05
    bh=g.btc4_bb_width>=0.094; bl=~bh; ah=g.h4_bb_width>=p10.R2_BB; al=~ah
    # Phase13: multi-resolution trajectory-shape motifs. Use normalized price path + first differences so level/regime scale does not dominate similarity.
    regimes={'ALL':pd.Series(True,index=g.index),'DEEP':deep,'MID':mid,'BTCBB_HIGH':bh,'ALTBB_HIGH':ah}
    cand=[]; masks={}
    for rn,rg in regimes.items():
      for lb in p10.LOOKBACKS:
       for oh in H:
        Z=X[lb].copy()
        Z=(Z-Z[:,-1,None])
        scale=np.nanstd(Z,axis=1); scale[~np.isfinite(scale)|(scale<1e-6)]=1.0
        Z=Z/scale[:,None]
        DZ=np.diff(Z,axis=1)
        good=disc&rg&r2
        if int(good.sum())<12: continue
        y=g.loc[good,f'net_ret_{oh}'].to_numpy()
        win=y>0
        if win.sum()<6 or (~win).sum()<3: continue
        pw=np.nanmedian(Z[good.to_numpy()][win],axis=0); pl=np.nanmedian(Z[good.to_numpy()][~win],axis=0)
        dw=np.nanmedian(DZ[good.to_numpy()][win],axis=0); dl=np.nanmedian(DZ[good.to_numpy()][~win],axis=0)
        def dist(A,p):
            return np.sqrt(np.nanmean((A-p)**2,axis=1))
        score=(dist(Z,pl)-dist(Z,pw)) + .65*(dist(DZ,dl)-dist(DZ,dw))
        base=pd.Series(score,index=g.index); sd=base[disc&rg&pool].dropna()
        if len(sd)<25: continue
        for q in [.55,.60,.65,.70,.75,.80,.85,.90,.925,.95]:
          th=float(sd.quantile(q)); m=rg&pool&(base>=th)
          md,mc,mx=met(g[disc&m]),met(g[cal&m]),met(g[cross&m])
          hs=[h for h in H if quality(md,h,12) and quality(mc,h,12) and quality(mx,h,15)]
          if not hs: continue
          bhh=max(hs,key=lambda h:min(utility(md,h),utility(mc,h),utility(mx,h)))
          sc=min(utility(md,bhh),utility(mc,bhh),utility(mx,bhh)); name=f'MOTIF_{rn}_LB{lb}_P{oh}_Q{int(q*1000)}'
          cand.append({'name':name,'regime':rn,'lookback':lb,'prototype_h':oh,'q':q,'best_h':bhh,'score':sc,'discovery':md,'calibration':mc,'cross':mx}); masks[name]=m
    cand.sort(key=lambda z:z['score'],reverse=True)
    union=r2.copy(); selected=[]
    for c in cand:
      trial=union|masks[c['name']]; h=c['best_h']; md,mc,mx=met(g[disc&trial]),met(g[cal&trial]),met(g[cross&trial])
      if quality(md,h,20) and quality(mc,h,20) and quality(mx,h,20) and int((trial&~union&cross).sum())>0:
        selected.append(c['name']); union=trial
        if len(selected)>=8: break
    weeks=(pd.Timestamp('2026-09-18',tz='UTC')-pd.Timestamp('2026-01-01',tz='UTC')).days/7
    out={'method':'Phase13 multi-resolution normalized trajectory-shape motif similarity: r2 winner-vs-loser path prototypes using price-shape and first-difference distances. Selection PRE-2026 D+C+cross only; 2026 sealed until final evaluation.','selection_uses_2026':False,'events':len(g),'errors':len(errs),'robust_candidates':len(cand),'selected':selected,'r2_2026':met(g[y26&r2]),'expanded_2026':met(g[y26&union]),'signals_per_week_2026':int((y26&union).sum())/weeks,'top_candidates':[{**c,'all_2026':met(g[y26&masks[c['name']]])} for c in cand[:15]]}
    (outdir/'summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    (outdir/'REPORT.md').write_text('# Phase 13 Multi-Resolution Trajectory Motifs\n\n```json\n'+json.dumps(out,indent=2,ensure_ascii=False)+'\n```\n',encoding='utf-8')
    pd.DataFrame(errs).to_csv(outdir/'errors.csv',index=False)
    print(json.dumps(out,ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--artifact-dir',type=Path,required=True); a.add_argument('--outdir',type=Path,required=True); x=a.parse_args(); main(x.artifact_dir,x.outdir)
