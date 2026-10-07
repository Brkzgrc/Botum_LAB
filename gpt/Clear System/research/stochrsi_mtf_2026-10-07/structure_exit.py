"""One frozen causal support-loss family. Exploratory fixed entries, never OOS."""
import contextlib,io,json,runpy,time,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
with contextlib.redirect_stdout(io.StringIO()):ctx=runpy.run_path(str(ROOT/'exit_compare.py'))
m=ctx['m']
def portable(value):
    if isinstance(value,np.generic):return value.item()
    raise TypeError(f'unsupported result type: {type(value).__name__}')

def replay(a,entry,sells,with_cost_floor):
    P,T=entry['alim_fiyat'],entry['alim_t'];stop=.95*P;t5=None;support=None;breaks=0
    cost_price=P*1.001/.999
    for j in range(len(a)):
        ot,o,hi,lo,c,t=a[j]
        if t<=T:continue
        if lo<=stop:
            px=min(o,stop)
            return {'exit_t':t,'net_pct':(px*.999/(P*1.001)-1)*100,'reason':'protect' if t5 else 'stop','protected':bool(t5)}
        if hi>=P*1.05 and t5 is None:t5=t
        # A low at j-1 only becomes confirmed after bar j has CLOSED.
        # The entire 3-bar pivot must be after entry. Only recoveries with a
        # cost-covered current close may establish a support reference.
        if j>=2 and a[j-2,5]>T and c>cost_price and a[j-1,3]<a[j-2,3] and a[j-1,3]<lo:
            support=float(a[j-1,3]);breaks=0
        breaks=breaks+1 if support is not None and c<support else 0
        ind=t in sells[95.] or (t5 is not None and t in sells[80.])
        if ind or breaks>=2:
            return {'exit_t':t,'net_pct':(c*.999/(P*1.001)-1)*100,
                    'reason':'indicator' if ind else 'confirmed_support_loss','protected':bool(t5)}
        if t5 is not None:stop=max(stop,ctx['floor'](P,.1) if with_cost_floor else P)
    return {'exit_t':None,'net_pct':None,'reason':'open','protected':bool(t5)}

def tests():
    sells={95.:set(),80.:set()};entry={'alim_fiyat':100.,'alim_t':0}
    a=np.array([[0,102,103,102,102,1],[1,102,104,101,103,2],
                [2,103,104,102,103,3],[3,103,103,99,100,4],[4,100,101,98,99,5]],float)
    z=replay(a,entry,sells,False);assert z['reason']=='confirmed_support_loss' and z['exit_t']==5
    # Truncating before second below-support close keeps the trade open.
    assert replay(a[:-1],entry,sells,False)['exit_t'] is None
    b=a.copy();b[-1,3]=94;assert replay(b,entry,sells,False)['reason']=='stop'
    assert json.loads(json.dumps({'n':np.int64(2),'x':np.float64(.1),'ok':np.bool_(True)},default=portable))['n']==2
    return 4

def main():
    prereg=json.loads((ROOT/'structure_exit_preregistration.json').read_text())
    assert prereg['variants']==['structure_only','structure_plus_cost_floor']
    tests();start=time.monotonic();results={k:[] for k in prereg['variants']}
    for coin in ctx['summary']['by_coin']:
        arrays={iv:np.load(ROOT/'data'/f'{coin}_{iv}_strategy.npy') for iv in ('1h','4h','1d')}
        gs={iv:m.gostergeler(a) for iv,a in arrays.items()}
        sells={e:{z['t'] for z in m.satis_cifti(m.h1_satis(gs['1h'],e),m.h4_satis(gs['4h'],e),m.g_satis(gs['1d']))} for e in (95.,80.)}
        for entry in [x for x in ctx['summary']['trades'] if x['symbol']==coin and x['tip']=='dip']:
            for k in results:results[k].append({'symbol':coin,'entry_t':entry['alim_t'],**replay(arrays['1h'],entry,sells,k=='structure_plus_cost_floor')})
    baselines={k:ctx['out']['comparisons'][k] for k in ('original_stop_first','cost_floor_net0.1')}
    def totals(xs):return sum(x['net_pct'] for x in xs if x['net_pct'] is not None and x['net_pct']<0)
    metrics={k:{**ctx['metrics'](xs),'negative_pp':totals(xs),'structure_closes':sum(x['reason']=='confirmed_support_loss' for x in xs)} for k,xs in results.items()}
    # Fixed-cohort acceptance is only a screen, not promotion.
    gates={}
    for k,v in metrics.items():
        ref='cost_floor_net0.1' if k=='structure_plus_cost_floor' else 'original_stop_first'
        b=baselines[ref];neg=totals(ctx['out']['trades'][ref])
        gates[k]={'reference':ref,'net_not_lower':v['net_pp']>=b['net_pp'],
                  'loss_count_20pct_lower':v['losses']<=.8*b['losses'],
                  'negative_pp_20pct_lower':abs(v['negative_pp'])<=.8*abs(neg)}
        gates[k]['pass']=all(gates[k][z] for z in ('net_not_lower','loss_count_20pct_lower','negative_pp_20pct_lower'))
    out={'status':'EXPLORATORY_FIXED_COHORT_NOT_OOS','family':'confirmed_support_loss_after_recovery',
         'pre_registration_sha256':hashlib.sha256((ROOT/'structure_exit_preregistration.json').read_bytes()).hexdigest(),
         'self_tests':4,'comparisons':metrics,'gates':gates,'trades':results,
         'decision':'ADVANCE_TO_INDEPENDENT_VALIDATION' if any(x['pass'] for x in gates.values()) else 'REJECT_FIXED_COHORT_SCREEN_NO_RESCAN',
         'elapsed_seconds':round(time.monotonic()-start,3),
         'limitations':['chosen after inspecting exploratory losses; no untouched OOS',
                       'same original entries; reentry and overlaps not modeled','hourly stop-first; no slippage',
                       'trend branch unchanged; only dip exits investigated']}
    (ROOT/'structure_exit_result.json').write_text(json.dumps(out,indent=2,default=portable))
    print(json.dumps({k:v for k,v in out.items() if k!='trades'},indent=2,default=portable))

if __name__=='__main__':
    import sys
    if '--self-test' in sys.argv:print('support-loss self-tests PASS:',tests())
    else:main()
