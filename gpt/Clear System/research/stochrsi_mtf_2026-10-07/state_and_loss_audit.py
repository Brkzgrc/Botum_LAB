"""Offline original-code state regression and conservative pre-exit loss diagnosis."""
import contextlib, io, json, runpy, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).parent
with contextlib.redirect_stdout(io.StringIO()):
    ctx = runpy.run_path(str(ROOT/'exit_compare.py'))
m, summary = ctx['m'], ctx['summary']
baseline = ctx['out']['trades']['original_stop_first']

def state_regression():
    """Run actual minute and hourly loops with in-memory state and controlled data."""
    start = m._ms(2026,10,7,16); now = (start + 120000) / 1000
    key = f'BTCUSDT:{start-m.H}'
    state = {'canli_baslangic':start-2*m.H,'gonderildi':{key:{'alim':True}}}
    x = {'alim_t':start-m.H, 'alim_fiyat':100., 'tip':'dip', 't5':None,
         'cikis_t':None, 'yol':'A'}
    v = {'anahtar':key,'tip':'dip','P':100.,'alim_t':x['alim_t'], 't5':None,'son_saat':start}
    # Save every patched field; no external calls and no state files are written.
    names = ('_durum_oku','_durum_yaz','_get','_satis_gonder','genislik_verisi',
             '_btc4_verisi','evren','coin_hesapla','_post','_telegram')
    originals = {n:getattr(m,n) for n in names}
    old_time = time.time; old_open = dict(m.ACIK)
    try:
        time.time = lambda: now
        m._durum_oku = lambda: state
        m._durum_yaz = lambda s: None
        m._get = lambda *args,**kwargs:[[start,'100','101','94','95']]
        m._post = lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('unexpected write'))
        m._telegram = m._post
        def record_close(k,s,tip,reason,price,net,t):
            k.update(satis=True,close_t=t,close_price=price,reason=reason)
        m._satis_gonder = record_close
        m.ACIK.clear(); m.ACIK['BTCUSDT'] = v
        with contextlib.redirect_stdout(io.StringIO()): m.dakika_kontrol()
        after_minute = 'BTCUSDT' in m.ACIK
        assert state['gonderildi'][key]['satis'] and not after_minute
        m.genislik_verisi = lambda *args:tuple(np.array([]) for _ in range(4))
        m._btc4_verisi = lambda *args:np.zeros((0,6))
        m.evren = lambda:{'BTCUSDT':{}}
        m.coin_hesapla = lambda *args:([x],start,True)
        # Actual _bildir sees alim/satis already sent; it should make zero delivery calls.
        with contextlib.redirect_stdout(io.StringIO()): m.tur()
        after_hour = 'BTCUSDT' in m.ACIK
        assert after_hour, 'source behavior changed; investigate'
        # Source says closed in persistent state, but its rebuilt open list says open.
        return {'status':'REPRODUCED_SOURCE_STATE_DIVERGENCE','minute_removed_open':not after_minute,
                'persistent_closed_flag':state['gonderildi'][key]['satis'],
                'hourly_reintroduced_same_key':after_hour,
                'external_calls':0,'state_file_writes':0,
                'scope':'actual minute/hour loops with stub market/replay inputs; not observed live incident'}
    finally:
        time.time = old_time
        for n,v in originals.items():setattr(m,n,v)
        m.ACIK.clear();m.ACIK.update(old_open)

def profiles():
    trades = []
    originals = {(x['symbol'],x['alim_t']):x for x in summary['trades']}
    for x in baseline:
        if x['net_pct'] is None:continue
        orig = originals[x['symbol'],x['entry_t']]
        a = np.load(ROOT/'data'/f"{x['symbol']}_1h_strategy.npy")
        T, E, P = x['entry_t'],x['exit_t'],orig['alim_fiyat']
        strict = a[(a[:,5]>T)&(a[:,5]<E)]
        inclusive = a[(a[:,5]>T)&(a[:,5]<=E)]
        vals = {name:float((path[:,col].max() / P - 1)*100) if len(path) else None
                for name,path,col in [('mfe_before_exit_bar_pct',strict,2),('mfe_upper_bound_pct',inclusive,2)]}
        vals['mae_before_exit_bar_pct'] = float((strict[:,3].min()/P-1)*100) if len(strict) else None
        peak = vals['mfe_before_exit_bar_pct']
        trades.append({**x, **vals, 'duration_hours':(E-T)/m.H,
                       'valid_t5':bool(orig['t5'] and orig['t5']<=E),
                       'source_ghost_t5':bool(orig['t5'] and orig['t5']>E),
                       'pre_exit_positive_close':bool(len(strict) and np.any(strict[:,4]>P)),
                       'pre_exit_cost_covered_close':bool(len(strict) and np.any(strict[:,4]>P*1.001/.999)),
                       'pre_exit_5pct_proven':bool(peak is not None and peak>=5),
                       'pre_exit_5pct_possible':bool(vals['mfe_upper_bound_pct'] is not None and vals['mfe_upper_bound_pct']>=5)})
    losses = [x for x in trades if x['net_pct']<0]
    def group(xs):
        return {'n':len(xs),'net_pp':sum(x['net_pct'] for x in xs),
                'worst_pct':min((x['net_pct'] for x in xs),default=None),
                'mfe_lower_mean_pct':float(np.mean([x['mfe_before_exit_bar_pct'] for x in xs if x['mfe_before_exit_bar_pct'] is not None])) if any(x['mfe_before_exit_bar_pct'] is not None for x in xs) else None,
                'positive_closed_bar':sum(x['pre_exit_positive_close'] for x in xs),
                'cost_covered_closed_bar':sum(x['pre_exit_cost_covered_close'] for x in xs)}
    gains = sorted((x['net_pct'] for x in trades if x['net_pct']>0),reverse=True)
    groups = {'all_losses':group(losses),
              'proven_5pct_before_exit':group([x for x in losses if x['pre_exit_5pct_proven']]),
              'no_proven_5pct':group([x for x in losses if not x['pre_exit_5pct_proven']]),
              'protected_losses':group([x for x in losses if x['protected']]),
              'unprotected_losses':group([x for x in losses if not x['protected']])}
    return {'groups':groups,'top3_gain_share_pct':sum(gains[:3])/sum(gains)*100,
            't5_after_exit_closed_dip_count':sum(x['source_ghost_t5'] for x in trades),
            'trades':trades,'limitations':['exclude exit-hour extremes from proven peak because stop can occur intrabar',
                                        'no intrabar timing claims from 1H OHLC','not full universe or OOS',
                                        'these are corrected fixed-cohort exits; source reentry effects not included']}

if __name__ == '__main__':
    started = time.monotonic()
    out = {'status':'OFFLINE_CAUSAL_AUDIT','state_test':state_regression(), 'loss_diagnosis':profiles(),
           'source_sha256':summary['source_sha256'], 'data_window':summary['window']}
    out['elapsed_seconds'] = round(time.monotonic()-started,3)
    (ROOT/'state_and_loss_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({**out,'loss_diagnosis':{k:v for k,v in out['loss_diagnosis'].items() if k!='trades'}},indent=2))
