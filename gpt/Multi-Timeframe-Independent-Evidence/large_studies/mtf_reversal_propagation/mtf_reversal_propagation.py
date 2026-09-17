from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

SYMBOL = "BTCUSDT"
FETCH_START = pd.Timestamp("2023-12-01", tz="UTC")
START = pd.Timestamp("2024-01-01", tz="UTC")
SPLIT = pd.Timestamp("2026-01-01", tz="UTC")
END = pd.Timestamp("2026-09-18", tz="UTC")
BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]


def get_json(path, params, timeout=30):
    last = None
    for base in BASE_URLS:
        try:
            r = requests.get(base + path, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json(), base
            last = RuntimeError(f"{base} HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            last = e
    raise RuntimeError(f"all Binance transports failed: {last}")


def fetch_15m(start, end):
    rows, used = [], set()
    cur = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000) - 1
    while cur <= end_ms:
        data, base = get_json("/api/v3/klines", {
            "symbol": SYMBOL, "interval": "15m", "startTime": cur,
            "endTime": end_ms, "limit": 1000,
        })
        used.add(base)
        if not data:
            break
        rows.extend(data)
        nxt = int(data[-1][0]) + 15 * 60 * 1000
        if nxt <= cur:
            break
        cur = nxt
        if len(data) < 1000:
            break
        time.sleep(0.03)
    cols = ["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
    d = pd.DataFrame(rows, columns=cols).drop_duplicates("open_time").sort_values("open_time")
    for c in ["open","high","low","close","volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d.open_time, unit="ms", utc=True)
    d = d.set_index("time")[["open","high","low","close","volume"]]
    d.attrs["transports"] = sorted(used)
    return d


def rsi(s, n=14):
    d = s.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100/(1+rs)
    return out.where(~((au == 0) & (ad == 0)), 50.0)


def indicators(df):
    x = df.copy()
    x["rsi"] = rsi(x.close)
    e12 = x.close.ewm(span=12, adjust=False).mean(); e26 = x.close.ewm(span=26, adjust=False).mean()
    x["macd"] = e12-e26; x["macd_signal"] = x.macd.ewm(span=9, adjust=False).mean(); x["macd_hist"] = x.macd-x.macd_signal
    ll9=x.low.rolling(9).min(); hh9=x.high.rolling(9).max(); rsv=100*(x.close-ll9)/(hh9-ll9).replace(0,np.nan)
    x["kdj_k"]=rsv.ewm(alpha=1/3,adjust=False).mean(); x["kdj_d"]=x.kdj_k.ewm(alpha=1/3,adjust=False).mean(); x["kdj_j"]=3*x.kdj_k-2*x.kdj_d; x["kdj_spread"]=x.kdj_k-x.kdj_d
    ll14=x.low.rolling(14).min(); hh14=x.high.rolling(14).max(); x["wpr"]=-100*(hh14-x.close)/(hh14-ll14).replace(0,np.nan)
    sign=np.sign(x.close.diff()).fillna(0); x["obv"]=(sign*x.volume).cumsum()
    rrmin=x.rsi.rolling(14).min(); rrmax=x.rsi.rolling(14).max(); x["stoch_raw"]=100*(x.rsi-rrmin)/(rrmax-rrmin).replace(0,np.nan)
    x["stoch_k"]=x.stoch_raw.rolling(3).mean(); x["stoch_d"]=x.stoch_k.rolling(3).mean(); x["stoch_spread"]=x.stoch_k-x.stoch_d
    for c in ["rsi","macd_hist","kdj_j","kdj_spread","wpr","obv","stoch_k","stoch_spread"]:
        x[c+"_d1"]=x[c].diff(); x[c+"_d3"]=x[c].diff(3)
    rng=(x.high-x.low).replace(0,np.nan); body=(x.close-x.open).abs()
    x["body_frac"]=body/rng; x["close_loc"]=(x.close-x.low)/rng; x["lower_wick"]=(np.minimum(x.open,x.close)-x.low)/rng
    x["hammer"]=(x.lower_wick>=0.5)&(x.body_frac<=0.4)&(x.close_loc>=0.55)
    prev_bear=x.close.shift(1)<x.open.shift(1)
    x["bull_engulf"]=(x.close>x.open)&prev_bear&(x.open<=x.close.shift(1))&(x.close>=x.open.shift(1))
    x["higher_low"]=x.low>x.low.shift(1); x["higher_high"]=x.high>x.high.shift(1)
    prev8=x.low.shift(1).rolling(8).min(); x["sweep_reclaim"]=(x.low<prev8)&(x.close>prev8)
    x["reclaim_prev_high"]=x.close>x.high.shift(1)
    x["structure"] = x.hammer | x.bull_engulf | x.sweep_reclaim | x.reclaim_prev_high | (x.higher_low & x.higher_high)

    # Movement only. Absolute oscillator values are never gates.
    fam = pd.DataFrame(index=x.index)
    fam["RSI"] = np.sign(x.rsi_d1.fillna(0)) + np.sign(x.rsi_d3.fillna(0))
    fam["MACD"] = np.sign(x.macd_hist_d1.fillna(0)) + np.sign(x.macd_hist_d3.fillna(0))
    fam["KDJ"] = np.sign(x.kdj_j_d1.fillna(0)) + np.sign(x.kdj_spread_d1.fillna(0))
    fam["WPR"] = np.sign(x.wpr_d1.fillna(0)) + np.sign(x.wpr_d3.fillna(0))
    fam["OBV"] = np.sign(x.obv_d1.fillna(0)) + np.sign(x.obv_d3.fillna(0))
    fam["STOCH"] = np.sign(x.stoch_k_d1.fillna(0)) + np.sign(x.stoch_spread_d1.fillna(0))
    x["motion_pos"]=(fam>0).sum(axis=1); x["motion_neg"]=(fam<0).sum(axis=1); x["motion_net"]=x.motion_pos-x.motion_neg
    x["motion_rise"]=x.motion_pos.diff(); x["net_rise"]=x.motion_net.diff()
    x["turn4"]=(x.motion_pos>=4)&((x.motion_pos.shift(1)<4)|(x.motion_rise>=2))
    x["turn5"]=(x.motion_pos>=5)&((x.motion_pos.shift(1)<5)|(x.motion_rise>=2))
    return x


def resample(df, rule):
    return df.resample(rule, origin="epoch", label="left", closed="left").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum")).dropna()


def completed_to_15m(tf, delta, base_index, prefix):
    z = tf.copy(); z.index = z.index + delta
    cols=["motion_pos","motion_net","motion_rise","turn4","turn5","structure","higher_low","higher_high","sweep_reclaim","reclaim_prev_high","bull_engulf","hammer"]
    z=z[[c for c in cols if c in z.columns]].rename(columns={c:f"{prefix}_{c}" for c in cols if c in z.columns})
    return z.reindex(base_index, method="ffill")


def since_event(mask, max_bars):
    idx=np.arange(len(mask)); last=np.where(mask.fillna(False).to_numpy(), idx, -10**9); last=np.maximum.accumulate(last)
    return pd.Series((idx-last)<=max_bars, index=mask.index)


def compress(mask, cooldown_bars=16):
    a=mask.fillna(False).to_numpy(); out=np.zeros(len(a),dtype=bool); last=-10**9
    for i,v in enumerate(a):
        if v and i-last>cooldown_bars:
            out[i]=True; last=i
    return pd.Series(out,index=mask.index)


def forward_metrics(base):
    close=base.close.to_numpy(); high=base.high.to_numpy(); low=base.low.to_numpy(); n=len(base)
    out=pd.DataFrame(index=base.index)
    for h in [3,6,12,24]:
        b=h*4
        ret=np.full(n,np.nan); mfe=np.full(n,np.nan); mae=np.full(n,np.nan)
        for i in range(n-b):
            p=close[i]; ret[i]=(close[i+b]/p-1)*100
            mfe[i]=(np.nanmax(high[i+1:i+b+1])/p-1)*100
            mae[i]=(np.nanmin(low[i+1:i+b+1])/p-1)*100
        out[f"ret_{h}h"]=ret; out[f"mfe_{h}h"]=mfe; out[f"mae_{h}h"]=mae
    return out


def eval_events(name, mask, fm, split_name):
    idx=mask[mask].index.intersection(fm.index)
    d=fm.loc[idx].dropna(subset=["ret_12h","mfe_12h","mae_12h"])
    if len(d)==0: return {"candidate":name,"split":split_name,"n":0}
    r={"candidate":name,"split":split_name,"n":int(len(d))}
    for h in [3,6,12,24]:
        rr=d[f"ret_{h}h"]; r[f"mean_ret_{h}h"]=float(rr.mean()); r[f"median_ret_{h}h"]=float(rr.median()); r[f"win_{h}h"]=float((rr>0).mean()*100)
    r["mean_mfe_12h"]=float(d.mfe_12h.mean()); r["mean_mae_12h"]=float(d.mae_12h.mean()); r["mfe_gt_1_12h"]=float((d.mfe_12h>=1).mean()*100); r["ret_gt_1_12h"]=float((d.ret_12h>=1).mean()*100)
    # Bootstrap CI for mean 12h return.
    rng=np.random.default_rng(42); arr=d.ret_12h.to_numpy(); means=[]
    for _ in range(1000): means.append(rng.choice(arr,size=len(arr),replace=True).mean())
    r["mean_ret_12h_ci_low"],r["mean_ret_12h_ci_high"]=map(float,np.quantile(means,[.025,.975]))
    return r


def nearest_lag(event_index, other_index, max_hours):
    if len(other_index)==0: return []
    other=np.array(other_index.view("i8")); out=[]; lim=max_hours*3600*1e9
    for t in event_index.view("i8"):
        j=np.searchsorted(other,t); cand=[]
        if j<len(other): cand.append(other[j])
        if j>0: cand.append(other[j-1])
        if not cand: out.append(np.nan); continue
        q=min(cand,key=lambda v:abs(v-t)); out.append((q-t)/3.6e12 if abs(q-t)<=lim else np.nan)
    return out


def main():
    base=fetch_15m(FETCH_START,END)
    transports=base.attrs.get("transports",[])
    base=base[(base.index>=FETCH_START)&(base.index<END)]
    tf15=indicators(base); tf1=indicators(resample(base,"1h")); tf4=indicators(resample(base,"4h"))
    a1=completed_to_15m(tf1,pd.Timedelta(hours=1),tf15.index,"h1")
    a4=completed_to_15m(tf4,pd.Timedelta(hours=4),tf15.index,"h4")
    z=tf15.join(a1).join(a4)
    z=z[(z.index>=START)&(z.index<END)].copy()
    fm=forward_metrics(z[["open","high","low","close","volume"]])

    # Context is movement improvement, never an oscillator level.
    for m in [2,3,4]:
        z[f"h4_ctx{m}"]=(z.h4_motion_pos>=m)&((z.h4_motion_rise>=0)|(z.h4_motion_net>z.h4_motion_net.shift(16)))
    z["trig4"]=(z.motion_pos>=4)&((z.turn4)|(z.motion_rise>=1))
    z["trig5"]=(z.motion_pos>=5)&((z.turn5)|(z.motion_rise>=1))
    z["trig4s"]=z.trig4&z.structure; z["trig5s"]=z.trig5&z.structure

    h1_turn4 = z.h1_turn4.fillna(False) & (z.index.minute==0)
    h1_turn5 = z.h1_turn5.fillna(False) & (z.index.minute==0)
    h4_turn4 = z.h4_turn4.fillna(False) & ((z.index.hour%4)==0) & (z.index.minute==0)
    recent_h1_2h=since_event(h1_turn4,8); recent_h1_4h=since_event(h1_turn4,16); recent_h4_16h=since_event(h4_turn4,64)

    candidates={}
    for ctx in [2,3,4]:
        for trig in ["trig4","trig4s","trig5","trig5s"]:
            candidates[f"CTX{ctx}+{trig}"]=z[f"h4_ctx{ctx}"]&z[trig]
            candidates[f"CTX{ctx}+{trig}+H1recent2h"]=z[f"h4_ctx{ctx}"]&z[trig]&recent_h1_2h
            candidates[f"CTX{ctx}+{trig}+H1recent4h"]=z[f"h4_ctx{ctx}"]&z[trig]&recent_h1_4h
            candidates[f"H4turn16h+H1turn4h+{trig}"]=recent_h4_16h&recent_h1_4h&z[trig]

    # Entry on 1H confirmation after a recent 15m trigger: tests 15M -> 1H propagation explicitly.
    for trig in ["trig4s","trig5s"]:
        recent_trig=since_event(z[trig],12)  # prior 3h
        candidates[f"{trig}_then_H1turn4_entryH1"] = recent_trig & h1_turn4 & z.h4_ctx3

    rows=[]; event_masks={}
    for name,raw in candidates.items():
        m=compress(raw,16); event_masks[name]=m
        train=m&(m.index<SPLIT); test=m&(m.index>=SPLIT)
        rows.append(eval_events(name,train,fm,"train_2024_2025")); rows.append(eval_events(name,test,fm,"holdout_2026"))
    stats=pd.DataFrame(rows)

    # Baseline: every 4h snapshot, independent of setup.
    base_mask=pd.Series((z.index.minute==0)&((z.index.hour%4)==0),index=z.index)
    rows_base=[eval_events("BASELINE_4H_SNAPSHOTS",base_mask&(z.index<SPLIT),fm,"train_2024_2025"),eval_events("BASELINE_4H_SNAPSHOTS",base_mask&(z.index>=SPLIT),fm,"holdout_2026")]
    stats=pd.concat([stats,pd.DataFrame(rows_base)],ignore_index=True)

    # Select on train only; validate exact rule on 2026.
    tr=stats[(stats.split=="train_2024_2025")&(stats.candidate!="BASELINE_4H_SNAPSHOTS")&(stats.n>=40)].copy()
    tr["score"] = tr.mean_ret_12h + 0.35*tr.mean_mfe_12h + 0.15*tr.mean_mae_12h + 0.01*(tr.win_12h-50)
    champion = tr.sort_values("score",ascending=False).iloc[0].candidate if len(tr) else None

    # Sequence order / lead-lag around independent turn events.
    ev15=z.index[z.turn4.fillna(False)&z.structure.fillna(False)]
    ev1=z.index[h1_turn4]
    ev4=z.index[h4_turn4]
    lag1=nearest_lag(ev15,ev1,4); lag4=nearest_lag(ev15,ev4,12)
    seq=pd.DataFrame({"t15":ev15,"lag_to_nearest_1h_hours":lag1,"lag_to_nearest_4h_hours":lag4})
    seq["order"] = np.where((seq.lag_to_nearest_1h_hours>0)&(seq.lag_to_nearest_4h_hours>seq.lag_to_nearest_1h_hours),"15m->1h->4h",
                    np.where((seq.lag_to_nearest_4h_hours<0)&(seq.lag_to_nearest_1h_hours<0),"4h/1h before 15m",
                    np.where((seq.lag_to_nearest_1h_hours<0)&(seq.lag_to_nearest_4h_hours>0),"1h->15m->4h","mixed")))
    seq_stats=seq.order.value_counts(dropna=False).rename_axis("order").reset_index(name="n")
    seq_stats["pct"]=100*seq_stats.n/seq_stats.n.sum()

    # Strong-rise coverage by holdout candidate: top decile 12h return anchors, spaced 6h apart.
    hold=fm.loc[(fm.index>=SPLIT)&(fm.index<END)].copy(); q=float(hold.ret_12h.quantile(.90)); strong=(hold.ret_12h>=q)
    strong=compress(strong,24); strong_idx=strong[strong].index
    coverage=[]
    for name,m in event_masks.items():
        sig=m[m].index
        covered=0; leads=[]
        for t in strong_idx:
            prev=sig[(sig>=t-pd.Timedelta(hours=6))&(sig<=t)]
            if len(prev): covered+=1; leads.append((t-prev[-1]).total_seconds()/3600)
        coverage.append({"candidate":name,"strong_rise_anchors":len(strong_idx),"covered":covered,"coverage_pct":100*covered/max(1,len(strong_idx)),"median_lead_h":float(np.median(leads)) if leads else np.nan})
    coverage=pd.DataFrame(coverage)

    stats.to_csv(OUT/"candidate_stats.csv",index=False)
    seq.to_csv(OUT/"sequence_events.csv",index=False); seq_stats.to_csv(OUT/"sequence_order_stats.csv",index=False); coverage.to_csv(OUT/"strong_rise_coverage.csv",index=False)

    if champion:
        cm=event_masks[champion]; ev=z.loc[cm,["open","high","low","close","motion_pos","motion_net","structure","h1_motion_pos","h4_motion_pos"]].join(fm)
        ev.to_csv(OUT/"champion_events.csv")
        holdrow=stats[(stats.candidate==champion)&(stats.split=="holdout_2026")].iloc[0].to_dict()
        trainrow=stats[(stats.candidate==champion)&(stats.split=="train_2024_2025")].iloc[0].to_dict()
    else: holdrow={}; trainrow={}

    baseline_hold=stats[(stats.candidate=="BASELINE_4H_SNAPSHOTS")&(stats.split=="holdout_2026")].iloc[0].to_dict()
    topcov=coverage.sort_values(["coverage_pct","median_lead_h"],ascending=[False,True]).head(5).to_dict("records")
    summary={"symbol":SYMBOL,"period":[str(START),str(END)],"split":str(SPLIT),"transports":transports,"candidate_count":len(candidates),"champion_train_selected":champion,"train":trainrow,"holdout":holdrow,"baseline_holdout":baseline_hold,"sequence_orders":seq_stats.to_dict("records"),"strong_rise_top_decile_threshold_12h_ret_pct":q,"top_coverage_candidates":topcov}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    def f(x,k,nd=2):
        try:return f"{float(x.get(k,np.nan)):.{nd}f}"
        except:return "—"
    lines=[]
    lines.append("# BTC Multi-Timeframe Reversal Propagation — Large Historical Study\n")
    lines.append("Setup seçiminde sabit RSI/KDJ/W%R/StochRSI seviyeleri kullanılmadı. Tüm adaylar göstergelerin yönü, eğim değişimi, spread değişimi, OBV hareketi ve göreli fiyat/mum yapısından üretildi. Sabit yüzde eşikleri yalnızca SONUCU ölçmek için kullanılır.\n")
    lines.append(f"Dönem: {START.date()} → {END.date()} | keşif: 2024-2025 | kör holdout: 2026 | aday kural: {len(candidates)}\n")
    lines.append("## Keşif verisinde seçilen aday\n")
    lines.append(f"**{champion}**\n")
    if champion:
        lines.append(f"Keşif n={int(trainrow.get('n',0))}; 12s ort. getiri {f(trainrow,'mean_ret_12h')}%; win {f(trainrow,'win_12h')}%; MFE {f(trainrow,'mean_mfe_12h')}%; MAE {f(trainrow,'mean_mae_12h')}%.\n")
        lines.append(f"2026 holdout n={int(holdrow.get('n',0))}; 3s/6s/12s/24s ort. getiriler {f(holdrow,'mean_ret_3h')} / {f(holdrow,'mean_ret_6h')} / {f(holdrow,'mean_ret_12h')} / {f(holdrow,'mean_ret_24h')}%. 12s win {f(holdrow,'win_12h')}%; MFE>=1% {f(holdrow,'mfe_gt_1_12h')}%; ort. MFE {f(holdrow,'mean_mfe_12h')}%; ort. MAE {f(holdrow,'mean_mae_12h')}%.\n")
        lines.append(f"12s ortalama getiri bootstrap %95 GA: [{f(holdrow,'mean_ret_12h_ci_low')}, {f(holdrow,'mean_ret_12h_ci_high')}].\n")
    lines.append("## 2026 baseline\n")
    lines.append(f"Her 4 saatte bir kör snapshot: n={int(baseline_hold.get('n',0))}; 12s ort. getiri {f(baseline_hold,'mean_ret_12h')}%; win {f(baseline_hold,'win_12h')}%; MFE {f(baseline_hold,'mean_mfe_12h')}%; MAE {f(baseline_hold,'mean_mae_12h')}%.\n")
    lines.append("## Dönüş bilgisinin zaman dilimleri arasında yayılma sırası\n")
    for _,r in seq_stats.iterrows(): lines.append(f"- {r['order']}: {int(r['n'])} olay ({r['pct']:.1f}%)")
    lines.append("\nBu sıra analizi bağımsız hareket-dönüş event'lerinin en yakın 1H/4H event'leriyle zaman farkına bakar; setup kuralı değildir.\n")
    lines.append("## Güçlü yükseliş kapsaması\n")
    lines.append(f"2026'daki 12 saatlik ileri getirinin üst %10'luk dilimi güçlü-yükseliş anchor'ı olarak tanımlandı (eşik sonuç dağılımından gelir: {q:.2f}%). Bir setup'ın anchor'dan önceki 6 saatte görünme oranı ölçüldü.\n")
    for r in topcov: lines.append(f"- {r['candidate']}: kapsama {r['coverage_pct']:.1f}% | medyan öncülük {r['median_lead_h']:.2f}s")
    lines.append("\n## Yorumlama kuralı\n")
    lines.append("Bu test tek bir tarih örneğini ezberlemiyor. Aday, yalnız 2024-2025 verisinde seçildi ve 2026'ya değişmeden taşındı. Holdout sonucu baseline'dan anlamlı biçimde iyi değilse setup doğrulanmış sayılmayacak. İyiyse sıradaki adım BTC dışı coinlerde aynı hareket mantığını, sembol kimliğini özellik yapmadan sınamaktır.\n")
    (OUT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))

if __name__ == "__main__":
    main()
