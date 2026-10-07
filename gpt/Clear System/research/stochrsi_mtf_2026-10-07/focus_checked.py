"""Bounded 5M exit audit; no delivery, no policy selection or production changes."""
import contextlib, io, runpy, time, json, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import numpy as np

ROOT = Path(__file__).parent
with contextlib.redirect_stdout(io.StringIO()):
    ctx = runpy.run_path(str(ROOT / 'exit_compare.py'))
m, summary, END = ctx['m'], ctx['summary'], ctx['END']
m._post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('EXTERNAL WRITE FORBIDDEN'))
m._telegram = m._post
POLICIES = ctx['POLICIES'][:6]
BUDGET_S = 180
DEADLINE = time.monotonic() + BUDGET_S

def validate(a, start, end):
    assert a.ndim == 2 and a.shape[1] == 6 and len(a), 'empty/invalid schema'
    assert a[0, 0] == start and a[-1, 5] == end, 'missing boundary'
    assert np.all(np.diff(a[:, 0]) == 300000), 'missing/duplicate 5M shard'
    assert np.all(a[:, 5] - a[:, 0] == 300000), 'incorrect close timestamp'
    assert np.isfinite(a).all() and np.all(a[:, 1:5] > 0), 'invalid prices'
    assert np.all(a[:, 3] <= np.minimum(a[:, 1], a[:, 4])), 'invalid low'
    assert np.all(a[:, 2] >= np.maximum(a[:, 1], a[:, 4])), 'invalid high'

def fetch(tr):
    s, start = tr['symbol'], int(tr['alim_t'])
    cache = ROOT / 'data' / f'{s}_{start}_5m_focus.npy'
    if cache.exists():
        a = np.load(cache); validate(a, start, END); return a, 0
    cur, rows, calls = start, [], 0
    # The scope is frozen to October screenshot examples. Never extend to full year here.
    assert END - start <= 7 * m.GUN, 'scope exceeds focused request budget'
    while cur < END:
        if time.monotonic() >= DEADLINE or calls >= 3:
            raise TimeoutError('180s total / 3 requests per path budget')
        calls += 1
        r = requests.get(m.BASE_URLS[0] + '/api/v3/klines', params={
            'symbol': s, 'interval': '5m', 'startTime': cur,
            'endTime': END - 1, 'limit': 1000}, timeout=(5, 25))
        r.raise_for_status(); b = r.json()
        if not isinstance(b, list) or not b:
            raise ValueError('empty/unexpected response')
        rows.extend([[float(z[0]), *[float(v) for v in z[1:5]], float(z[0]) + 300000]
                     for z in b if float(z[0]) + 300000 <= END])
        nxt = int(b[-1][0]) + 300000
        if nxt <= cur: raise ValueError('pagination did not advance')
        cur = nxt
    a = np.asarray(rows, float); validate(a, start, END)
    np.save(cache, a)
    return a, calls

def replay(a, P, hours, sells, policy):
    """Stops from previous close; intrabar stop precedes target and close decisions."""
    stop, active, activation, peak = .95 * P, False, None, P
    for row in a:
        ot, o, hi, lo, c, t = row
        if lo <= stop:
            px = min(o, stop)
            return {'exit_t': t, 'price': px, 'reason': 'protect' if active else 'stop',
                    't5': activation, 'net_pct': (px * .999 / (P * 1.001) - 1) * 100}
        if policy == 'fixed_tp5' and hi >= P * 1.05:
            return {'exit_t': t, 'price': P * 1.05, 'reason': 'tp5', 't5': None,
                    'net_pct': (1.05 * .999 / 1.001 - 1) * 100}
        if t not in hours: continue
        # At the hourly close the high of that entire hour is now observable.
        peak = max(peak, hours[t][2])
        if hours[t][2] >= P * 1.05 and not active:
            active, activation = True, t
        if t in sells[95.] or (active and t in sells[80.]):
            return {'exit_t': t, 'price': c, 'reason': 'indicator', 't5': activation,
                    'net_pct': (c * .999 / (P * 1.001) - 1) * 100}
        if active:
            if policy == 'original_stop_first': stop = max(stop, P)
            elif policy == 'cost_floor_net0.1': stop = max(stop, ctx['floor'](P, .1))
            elif policy == 'lock_net2': stop = max(stop, ctx['floor'](P, 2))
            elif policy == 'stair_5_7_10':
                stop = max(stop, ctx['floor'](P, 6 if peak / P >= 1.10 else 4 if peak / P >= 1.07 else 2))
            elif policy == 'trail3_net2': stop = max(stop, ctx['floor'](P, 2), peak * .97)
    return {'exit_t': None, 'price': None, 'reason': 'open', 't5': activation, 'net_pct': None}

def self_test():
    empty = {95.: set(), 80.: set()}
    # Later +5 must not activate a position stopped beforehand.
    a = np.array([[0,100,102,94,101,300000], [300000,101,108,100,107,600000]], float)
    z = replay(a, 100, {600000:a[1]}, {95.:{300000},80.:set()}, 'original_stop_first')
    assert z['price'] == 95 and z['t5'] is None
    # High-triggered protection cannot be used retroactively in the activation candle.
    a = np.array([[0,100,108,99,107,300000], [300000,107,107,101,103,600000]], float)
    z = replay(a, 100, {300000:a[0]}, empty, 'lock_net2')
    assert z['exit_t'] == 600000 and abs(z['net_pct']-2) < 1e-10
    # Gap below known stop uses open; same candle target and stop is pessimistic stop-first.
    a = np.array([[0,90,106,89,100,300000]], float)
    z = replay(a, 100, {}, empty, 'fixed_tp5'); assert z['price'] == 90
    # Cross-hour activation does not happen at first 5M high; it waits for close.
    a = np.array([[0,100,108,99,107,300000], [300000,107,107,99,100,600000]], float)
    z = replay(a, 100, {600000:np.array([0,100,108,99,100,600000])}, empty, 'original_stop_first')
    assert z['exit_t'] is None and z['t5'] == 600000
    return 4

def one(tr):
    a, calls = fetch(tr); s = tr['symbol']; P = tr['alim_fiyat']
    arrays = {iv:np.load(ROOT/'data'/f'{s}_{iv}_strategy.npy') for iv in ('1h','4h','1d')}
    gs = {iv:m.gostergeler(x) for iv,x in arrays.items()}
    sells = {e:{z['t'] for z in m.satis_cifti(m.h1_satis(gs['1h'],e),m.h4_satis(gs['4h'],e),m.g_satis(gs['1d']))}
             for e in (95.,80.)}
    hours = {row[5]:row for row in arrays['1h']}
    results = {p:replay(a,P,hours,sells,p) for p in POLICIES}
    # Exclude the exit 5M bar: its high may occur after a stop hit inside the bar.
    ex = results['original_stop_first']['exit_t'] or END
    strict = a[a[:,5] < ex]; inclusive = a[a[:,5] <= ex]
    return {'symbol':s, 'entry_t':tr['alim_t'], 'original_hourly_exit_t':tr['cikis_t'],
            'source_original_net_pct':tr['net_%'], 'candles':len(a), 'requests':calls,
            'coverage_pct':100, 'mfe_before_exit_bar_pct':float((strict[:,2].max()/P-1)*100) if len(strict) else None,
            'mfe_including_exit_bar_upper_bound_pct':float((inclusive[:,2].max()/P-1)*100),
            'policies':results}

def main():
    start = time.monotonic(); tests = self_test()
    selected = [x for x in summary['trades'] if x['tip']=='dip' and x['symbol'] in
                ('LUMIAUSDT','MIRAUSDT','TSTUSDT') and x['alim_t'] >= m._ms(2026,10,1)]
    assert len(selected) == 3, 'unexpected focused cohort'
    out = {'status':'REAL_5M_FIXED_COHORT_DIAGNOSTIC', 'tests_passed':tests, 'budget_seconds':BUDGET_S,
           'expected_paths':len(selected), 'errors':[], 'results':[], 'not_oos':True,
           'activation':'closed 1H; stops only subsequent 5M bars', 'source_sha256':summary['source_sha256'],
           'cost':'each leg 0.10%; net=exit*0.999/(entry*1.001)-1; spread/slippage not modeled',
           'limitations':['fixed original entries; no reentry modeling', '5M stop-first; intrabar/tick order still ambiguous',
                          'MFE before exit bar is lower bound, exit-bar-inclusive high is upper bound']}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(one,tr):tr for tr in selected}
        for f in as_completed(futures):
            tr = futures[f]
            try: out['results'].append(f.result())
            except Exception as exc:
                out['errors'].append({'symbol':tr['symbol'],'start':tr['alim_t'],'end':END,
                                      'reason':f'{type(exc).__name__}: {exc}'})
    out['results'].sort(key=lambda x:x['symbol'])
    out['missing_paths'] = len(selected) - len(out['results'])
    if out['missing_paths']: out['status'] = 'INCOMPLETE_DO_NOT_PROMOTE'
    out['elapsed_seconds'] = round(time.monotonic()-start,3)
    (ROOT/'focus_checked.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if out['errors']: raise SystemExit(1)

if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv: print('self-test PASS:',self_test())
    else: main()
