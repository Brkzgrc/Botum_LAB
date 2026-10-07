import os, sys, types, importlib.util, json, time, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import requests
ROOT=Path(__file__).parent
os.environ.update(PORTFOLIO_URL='',TELEGRAM_ENABLED='false',PORTFOLIO_TOKEN='',TELEGRAM_TOKEN='')
sys.modules['evren_kurallari']=types.ModuleType('evren_kurallari')
spec=importlib.util.spec_from_file_location('subject',ROOT/'source/stochrsi_mtf.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._post=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('EXTERNAL WRITE FORBIDDEN'))
m._telegram=m._post
END=m._ms(2026,10,7,16) # last fully closed hour at requested review time
START=m._ms(2026,1,1)
DEADLINE=time.monotonic()+420
errors=[]
def fetch(symbol,iv,start,label):
    cache=ROOT/'data'/f'{symbol}_{iv}_{label}.npy'
    if cache.exists(): return np.load(cache)
    rows=[]; cur=start; step=m.ARALIK_MS[iv]
    while cur+step<=END:
        if time.monotonic()>DEADLINE: raise TimeoutError('420 second audit budget exceeded')
        r=requests.get(m.BASE_URLS[0]+'/api/v3/klines',params=dict(symbol=symbol,interval=iv,startTime=cur,endTime=END-1,limit=1000),timeout=12)
        r.raise_for_status(); batch=r.json()
        if not batch: break
        rows.extend([[float(x[0]),*[float(v) for v in x[1:5]],float(x[0])+step] for x in batch if float(x[0])+step<=END])
        nxt=int(batch[-1][0])+step
        if nxt<=cur: raise ValueError('pagination did not advance')
        cur=nxt
        if len(batch)<1000:break
    a=np.asarray(rows,dtype=float).reshape(-1,6)
    if not len(a):raise ValueError('no data')
    if np.any(np.diff(a[:,0])!=step):raise ValueError('gap/duplicate candle')
    if not np.isfinite(a).all() or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4])):raise ValueError('invalid OHLC')
    cache.parent.mkdir(exist_ok=True);np.save(cache,a);return a

def tests():
    # Original indicator exit at hour 2 wins over stop occurring during same hour.
    t=np.array([m.SIM_BASLA+m.H,m.SIM_BASLA+2*m.H],float)
    c={95.0:[{'t':t[1],'fiyat':101.,'tf':'1h + 4h'}],80.0:[]}
    result=m._cikis(0,t,np.array([100.,102.]),np.array([100.,94.]),np.array([100.,101.]),c)
    # t5 report can lie after actual stop because it was computed before stop replacement.
    t2=np.array([m.SIM_BASLA+j*m.H for j in (1,2,3)],float)
    result2=m._cikis(0,t2,np.array([100.,101.,106.]),np.array([100.,94.,100.]),np.array([100.,95.,105.]),{95.:[],80.:[]})
    return {'compile':'PASS','same_bar_stop_and_indicator_exit':result,'t5_after_stop':result2,'missing_universe_dependency':'evren_kurallari.py not supplied; original production universe not verified','delivery_blocked':True}

out={'source_sha256':hashlib.sha256((ROOT/'source/stochrsi_mtf.py').read_bytes()).hexdigest(),'tests':tests(),'window':['2026-01-01T00:00:00Z','2026-10-07T16:00:00Z'],'selection':'nine fixed examples including screenshot coins; NOT full historical universe/OOS; same exact strategy, breadth and BTC filters enabled','errors':errors}
print(json.dumps(out['tests'],ensure_ascii=False),flush=True)
breadth={}
with ThreadPoolExecutor(max_workers=8) as pool:
    fut={pool.submit(fetch,c+'USDT','1d',m.GENISLIK_BASLA,'breadth'):c for c in m.EK_A}
    for f in as_completed(fut):
        c=fut[f]
        try:breadth[c+'USDT']=f.result()
        except Exception as e:errors.append({'symbol':c+'USDT','interval':'1d','window':'2019-06-01/2026-10-07','reason':str(e)})
print('BREADTH',len(breadth),'skips',len(errors),flush=True)
gn=m.genislik_hesapla(breadth)
btc=fetch('BTCUSDT','4h',m.VERI_BASLA['4h'],'strategy')
results=[]
def calc(s):
    a={iv:fetch(s,iv,m.VERI_BASLA[iv],'strategy') for iv in ('1h','4h','1d')}
    tr=m.hesapla(a['1h'],a['4h'],a['1d'],gn,btc4=btc)[0]
    for x in tr:
        x['symbol']=s
        end=x['cikis_t'] if x['cikis_t'] is not None else END
        path=a['1h'][(a['1h'][:,5]>x['alim_t'])&(a['1h'][:,5]<=end)]
        x['mfe_pct']=None if not len(path) else float((path[:,2].max()/x['alim_fiyat']-1)*100)
        x['mae_pct']=None if not len(path) else float((path[:,3].min()/x['alim_fiyat']-1)*100)
        x['t5_after_exit']=bool(x['t5'] and x['cikis_t'] and x['t5']>x['cikis_t'])
    return {'symbol':s,'candles':{iv:len(v) for iv,v in a.items()},'trades':tr}
with ThreadPoolExecutor(max_workers=6) as pool:
    fut={pool.submit(calc,s):s for s in ('BTCUSDT','ETHUSDT','SOLUSDT','AVAXUSDT','SUIUSDT','ZECUSDT','MIRAUSDT','LUMIAUSDT','TSTUSDT')}
    for f in as_completed(fut):
        s=fut[f]
        try:
            rr=f.result();results.append(rr);print('COIN',s,'signals',len(rr['trades']),flush=True)
        except Exception as e:errors.append({'symbol':s,'window':out['window'],'reason':str(e)})
tr=[x for r in results for x in r['trades']];closed=[x for x in tr if x['net'] is not None]
def metric(xs):
    cl=[x for x in xs if x['net'] is not None];p=[x['net']*100 for x in cl];pos=sum(v for v in p if v>0);neg=sum(v for v in p if v<0)
    return {'signals':len(xs),'closed':len(cl),'open':len(xs)-len(cl),'wins':sum(v>0 for v in p),'losses':sum(v<0 for v in p),'net_percentage_points':sum(p),'expectancy_pct':None if not p else float(np.mean(p)),'PF':None if neg==0 else pos/-neg,'worst_pct':min(p) if p else None,'signals_per_day':len(xs)/((END-START)/m.GUN),'active_days':len({int(x['alim_t']//m.GUN) for x in xs}),'reasons':{v:sum(x['neden']==v for x in cl) for v in {x['neden'] for x in cl}},'mfe_mae_note':'hourly exit candle extrema may occur after exit inside that candle; not exact execution-path evidence','t5_after_exit_count':sum(x['t5_after_exit'] for x in xs)}
out.update(breadth_symbols=len(breadth),coins_completed=len(results),summary=metric(tr),by_type={k:metric([x for x in tr if x['tip']==k]) for k in ('dip','trend')},by_coin={r['symbol']:metric(r['trades']) for r in results},trades=tr)
(ROOT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
print(json.dumps(out['summary'],ensure_ascii=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),flush=True)
