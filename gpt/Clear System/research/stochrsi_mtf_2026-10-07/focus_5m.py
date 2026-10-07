import runpy,time,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests,numpy as np
ROOT=Path(__file__).parent
ctx=runpy.run_path(str(ROOT/'exit_compare.py'));m=ctx['m'];policies=ctx['POLICIES'][:6];floor=ctx['floor']; END=ctx['END'];summary=ctx['summary']
selected=[x for x in summary['trades'] if x['tip']=='dip' and x['symbol'] in ('LUMIAUSDT','MIRAUSDT','TSTUSDT') and x['alim_t']>=m._ms(2026,10,1)]
def one(tr):
 s=tr['symbol'];cur=int(tr['alim_t']);rows=[]
 while cur+300000<=END:
  r=requests.get(m.BASE_URLS[0]+'/api/v3/klines',params={'symbol':s,'interval':'5m','startTime':cur,'endTime':END-1,'limit':1000},timeout=12);r.raise_for_status();b=r.json()
  if not b:break
  rows += [[float(z[0]),*[float(v) for v in z[1:5]],float(z[0])+300000] for z in b if float(z[0])+300000<=END]
  cur=int(b[-1][0])+300000
  if len(b)<1000:break
 a=np.array(rows);assert len(a) and a[0,0]==tr['alim_t'] and a[-1,5]==END and np.all(np.diff(a[:,0])==300000)
 a1=np.load(ROOT/'data'/f'{s}_1h_strategy.npy');a4=np.load(ROOT/'data'/f'{s}_4h_strategy.npy');ag=np.load(ROOT/'data'/f'{s}_1d_strategy.npy');g1,g4,gg=m.gostergeler(a1),m.gostergeler(a4),m.gostergeler(ag)
 cifts={e:m.satis_cifti(m.h1_satis(g1,e),m.h4_satis(g4,e),m.g_satis(gg)) for e in (95.,80.)};hour={row[5]:row for row in a1}
 P=tr['alim_fiyat'];res={}
 for policy in policies:
  stop=.95*P;active=False;t5=None;peak=P;exit=None
  for row in a:
   ot,o,hi,lo,c,t=row
   if lo<=stop:
    px=min(o,stop);exit={'t':t,'price':px,'reason':'protect' if active else 'stop'};break
   if policy=='fixed_tp5' and hi>=P*1.05:exit={'t':t,'price':P*1.05,'reason':'tp5'};break
   if t not in hour:continue
   hi=hour[t][2];peak=max(peak,hi)
   if hi>=P*1.05 and not active:active=True;t5=t
   if any(z['t']==t for z in cifts[95.]) or (active and any(z['t']==t and z['t']>=t5 for z in cifts[80.])):
    exit={'t':t,'price':c,'reason':'indicator'};break
   if active:
    if policy=='original_stop_first':stop=max(stop,P)
    elif policy=='cost_floor_net0.1':stop=max(stop,floor(P,.1))
    elif policy=='lock_net2':stop=max(stop,floor(P,2))
    elif policy=='stair_5_7_10':stop=max(stop,floor(P,6 if peak/P>=1.10 else 4 if peak/P>=1.07 else 2))
    elif policy=='trail3_net2':stop=max(stop,floor(P,2),peak*.97)
  if exit:exit['net_pct']=(exit['price']*(1-m.KOMISYON)/(P*(1+m.KOMISYON))-1)*100
  res[policy]=exit
 np.save(ROOT/'data'/f'{s}_5m_focus.npy',a)
 orig5=res['original_stop_first'];end=orig5['t'] if orig5 else END;before=a[a[:,5]<=end]
 return {'symbol':s,'entry_t':tr['alim_t'],'original_net_pct':tr['net_%'],'five_minute_bars':len(a),'coverage_pct':100,'mfe_to_original_exit_pct':(before[:,2].max()/P-1)*100,'policies':res}
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(one,selected))
out={'status':'REAL_5M_FIXED_COHORT_DIAGNOSTIC','hourly_closed_activation':True,'same_entries':True,'coins':len(results),'results':results,'not_oos':True,'fill_note':'5m stop-first with gap-open price; no slippage; not exact tick fills; policies are illustrative not promoted'}
(ROOT/'focus_5m.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
print(json.dumps(out,ensure_ascii=False,indent=2))
