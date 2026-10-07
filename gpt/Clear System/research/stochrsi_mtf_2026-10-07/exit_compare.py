"""Fixed entry cohort diagnostic. Hourly pessimistic order; NOT production/portfolio."""
import sys, types, os, importlib.util,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
os.environ.update(PORTFOLIO_URL='',TELEGRAM_ENABLED='false')
sys.modules['evren_kurallari']=types.ModuleType('evren_kurallari')
sp=importlib.util.spec_from_file_location('subject',ROOT/'source/stochrsi_mtf.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
summary=json.loads((ROOT/'summary.json').read_text()); END=m._ms(2026,10,7,16)
POLICIES=['original_stop_first','fixed_tp5','cost_floor_net0.1','lock_net2','stair_5_7_10','trail3_net2','atr2_cost_floor','atr3_cost_floor','momentum_2h_after5','partial50_at5']
def floor(P,pct):return P*(1+m.KOMISYON)/(1-m.KOMISYON)*(1+pct/100)
def replay(a,entry,policy,cifts):
 P=entry['alim_fiyat'];T=entry['alim_t'];stop=.95*P;peak=P;active=False;t5=None;partial=False
 h,l,c=a[:,2],a[:,3],a[:,4];prev=np.r_[c[0],c[:-1]]
 tr=np.maximum(h-l,np.maximum(abs(h-prev),abs(l-prev)));atr=np.full(len(a),np.nan)
 if len(a)>=14:
  atr[13]=tr[:14].mean()
  for j in range(14,len(a)):atr[j]=(atr[j-1]*13+tr[j])/14
 _,_,hist=m.macd(c);idx={row[5]:j for j,row in enumerate(a)}
 def realized(px):
  full=(px*(1-m.KOMISYON)/(P*(1+m.KOMISYON))-1)*100
  tp=(1.05*(1-m.KOMISYON)/(1+m.KOMISYON)-1)*100
  return .5*tp+.5*full if partial else full
 for row in a[a[:,5]>T]:
  ot,o,hi,lo,c,t=row
  # Only levels known BEFORE this bar can be executed. No retroactive trailing.
  if lo<=stop:
   px=min(o,stop);return {'exit_t':t,'px':px,'net_pct':realized(px),'reason':'protect' if active else 'stop','protected':active}
  if policy=='fixed_tp5' and hi>=P*1.05:
   px=P*1.05;return {'exit_t':t,'px':px,'net_pct':(px*(1-m.KOMISYON)/(P*(1+m.KOMISYON))-1)*100,'reason':'tp5','protected':True}
  peak=max(peak,hi)
  if policy=='partial50_at5' and hi>=P*1.05:partial=True
  if hi>=P*1.05 and not active:active=True;t5=t
  # Indicator exits occur at bar close, AFTER stop checks.
  hit=any(z['t']==t for z in cifts[95.]) or (active and any(z['t']==t and z['t']>=t5 for z in cifts[80.]))
  j=idx[t]
  if policy=='momentum_2h_after5' and active and j>=2:
   hit=hit or bool(c<a[j-1,4]<a[j-2,4] and hist[j]<hist[j-1]<hist[j-2])
  if hit:return {'exit_t':t,'px':c,'net_pct':realized(c),'reason':'indicator','protected':active}
  if active:
   if policy=='original_stop_first':stop=max(stop,P)
   elif policy=='cost_floor_net0.1':stop=max(stop,floor(P,.1))
   elif policy=='lock_net2':stop=max(stop,floor(P,2))
   elif policy=='stair_5_7_10':stop=max(stop,floor(P,6 if peak/P>=1.10 else 4 if peak/P>=1.07 else 2))
   elif policy=='trail3_net2':stop=max(stop,floor(P,2),peak*.97)
   elif policy=='atr2_cost_floor':stop=max(stop,floor(P,.1),peak-2*atr[j])
   elif policy=='atr3_cost_floor':stop=max(stop,floor(P,.1),peak-3*atr[j])
   elif policy in ('momentum_2h_after5','partial50_at5'):stop=max(stop,floor(P,.1))
 return {'exit_t':None,'net_pct':None,'reason':'open','protected':active}
def metrics(xs):
 p=[x['net_pct'] for x in xs if x['net_pct'] is not None];pos=sum(v for v in p if v>0);neg=sum(v for v in p if v<0)
 return {'closed':len(p),'open':len(xs)-len(p),'wins':sum(v>0 for v in p),'losses':sum(v<0 for v in p),'net_pp':sum(p),'expectancy_pct':float(np.mean(p)) if p else None,'PF':pos/-neg if neg else None,'worst_pct':min(p) if p else None,'protected_losses':sum(x['protected'] and x['net_pct'] is not None and x['net_pct']<0 for x in xs)}
results={p:[] for p in POLICIES};original=[];collisions=[]
for coin in summary['by_coin']:
 a=np.load(ROOT/'data'/f'{coin}_1h_strategy.npy');a4=np.load(ROOT/'data'/f'{coin}_4h_strategy.npy');ag=np.load(ROOT/'data'/f'{coin}_1d_strategy.npy')
 g1,g4,gg=m.gostergeler(a),m.gostergeler(a4),m.gostergeler(ag)
 cifts={e:m.satis_cifti(m.h1_satis(g1,e),m.h4_satis(g4,e),m.g_satis(gg)) for e in (95.,80.)}
 for tr in [x for x in summary['trades'] if x['symbol']==coin and x['tip']=='dip']:
  original.append(tr)
  for p in POLICIES:results[p].append({'symbol':coin,'entry_t':tr['alim_t'],**replay(a,tr,p,cifts)})
  if tr['cikis_t'] is not None and (tr['neden'] or '').startswith('satis_cifti'):
   rows=a[a[:,5]==tr['cikis_t']]
   if len(rows) and rows[0,3]<=tr['alim_fiyat']*.95:collisions.append({'symbol':coin,'entry_t':tr['alim_t'],'exit_t':tr['cikis_t']})
out={'status':'EXPLORATORY_HOURLY_FIXED_COHORT_NOT_OOS','policy_selection':{'initial_six':'chosen before first six-coin result','additional_four':'added after exploratory results; not preregistered'},'untouched_oos':False,'window':summary['window'],'dip_events':len(original),'original':{'closed':sum(x['net'] is not None for x in original),'net_pp':sum(x['net']*100 for x in original if x['net'] is not None),'losses':sum(x['net'] is not None and x['net']<0 for x in original)},'comparisons':{p:metrics(v) for p,v in results.items()},'original_same_hour_stop_indicator_collisions':collisions,'trades':results,'limitations':['same original entries; changed exits do not generate new entries; hypothetical paths may overlap','hourly high/low cannot establish intrabar ordering; stop-first and next-bar activation used','closed-candle high/low still idealized barrier fills; gap opens accounted, spread/slippage not','not full universe; not untouched OOS; do not choose/deploy solely from this sample']}
(ROOT/'exit_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))); print(json.dumps({k:v for k,v in out.items() if k!='trades'},ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
