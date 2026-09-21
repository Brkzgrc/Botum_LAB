# -*- coding: utf-8 -*-
"""SPOT_SCANNER v11 — stateful Binance Spot opportunity scanner.

Detection model validated on the 54-case audit: strong 1D/4H context plus a
controlled 1H reset/rejection profile. 15M remains an entry-timing layer only.
No first-scan entry. Existing output integrations are unchanged.
"""
from __future__ import annotations

import json, logging, math, os, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify

BINANCE = "https://api.binance.com"
TR_TZ = timezone(timedelta(hours=3))
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Botum-SPOT-SCANNER/11.0"})
MAX_WORKERS = max(2, min(10, int(os.getenv("MAX_WORKERS", "6"))))
PYTHON_TOP_N = max(64, min(120, int(os.getenv("VISUAL_TOP_N", "96"))))
PREFILTER_CORE_N = max(48, min(PYTHON_TOP_N, int(os.getenv("PREFILTER_CORE_N", "72"))))
MIN_QUOTE_VOLUME = float(os.getenv("MIN_QUOTE_VOLUME", "0"))
SCAN_INTERVAL_SECONDS = max(300, int(os.getenv("SCAN_INTERVAL_SECONDS", "900")))
WATCH_TTL_HOURS = float(os.getenv("WATCH_TTL_HOURS", "18"))
MAX_SIGNALS_PER_DAY = max(1, min(6, int(os.getenv("MAX_SIGNALS_PER_DAY", "3"))))
FINAL_MIN_QUALITY = float(os.getenv("FINAL_MIN_QUALITY", "72"))
STATE_FILE = os.getenv("SCANNER_STATE_FILE", "/tmp/spot_scanner_state_v11.json")
SCAN_ON_START = os.getenv("SCAN_ON_START", "true").strip().lower() == "true"
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "").rstrip("/")
PORTFOLIO_TOKEN = os.getenv("PORTFOLIO_TOKEN", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_THREAD_ID = int(os.getenv("SIGNAL_THREAD_ID", "2"))
IGNORED_BASES = {"USDT","USDC","BUSD","TUSD","DAI","PAX","HUSD","USDP","GUSD","FDUSD","EUR","TRY","GBP","USD","BRL","RUB","AUD","XUSD","USD1","USDE","BFUSD","USDS","USDD","PYUSD","AEUR","EURI","USTC","FRAX","LUSD","SUSD","USDX","CUSD","OUSD","MUSD","RLUSD","BIDR","IDRT","VAI","PAXG","XAUT","WBTC","WETH","WBNB","BETH","BTCB","HBTC","U"}
LEVERAGED_SUFFIXES = ("UP","DOWN","BULL","BEAR","2L","2S","3L","3S","5L","5S","10L","10S")
CRYPTO_BASES_ENDING_B = {"BNB","DGB","TRB","CKB","SHIB","ARB","BB","YB"}
app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

def now_tr(): return datetime.now(timezone.utc).astimezone(TR_TZ)
def sf(v, default=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception: return default
def pct(new, old): return (new/old-1)*100 if old else 0.0
def clamp(v, lo=0.0, hi=100.0): return max(lo,min(hi,float(v)))

def _get(path, params=None, attempts=4):
    last=None
    for i in range(attempts):
        try:
            r=HTTP.get(BINANCE+path,params=params,timeout=15)
            if r.status_code in (418,429): time.sleep(1.5*(2**i)); continue
            r.raise_for_status(); return r.json()
        except Exception as exc:
            last=exc; time.sleep(.35*(2**i))
    raise RuntimeError(f"Binance API failed {path}: {last}")

def ohlcv(symbol, interval, limit=240):
    rows=_get("/api/v3/klines",{"symbol":symbol,"interval":interval,"limit":limit})
    if not isinstance(rows,list) or len(rows)<80: raise ValueError(f"insufficient candles {symbol} {interval}")
    cols=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
    d=pd.DataFrame(rows,columns=cols)
    for c in ("open","high","low","close","volume","quote_volume","taker_quote"): d[c]=pd.to_numeric(d[c],errors="coerce")
    d["open_time"]=pd.to_datetime(d.open_time,unit="ms",utc=True); d["close_time"]=pd.to_datetime(d.close_time,unit="ms",utc=True)
    if rows and int(rows[-1][6])>=int(time.time()*1000): d=d.iloc[:-1].copy()
    return d.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)

def _rsi(s,n=14):
    delta=s.diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    ag=gain.ewm(alpha=1/n,adjust=False,min_periods=n).mean(); al=loss.ewm(alpha=1/n,adjust=False,min_periods=n).mean(); rs=ag/al.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(50)

def indicators(d):
    x=d.copy(); x["ema20"]=x.close.ewm(span=20,adjust=False).mean(); x["ema50"]=x.close.ewm(span=50,adjust=False).mean(); x["ema200"]=x.close.ewm(span=200,adjust=False).mean(); x["rsi"]=_rsi(x.close)
    lo=x.rsi.rolling(14).min(); hi=x.rsi.rolling(14).max(); raw=100*(x.rsi-lo)/(hi-lo).replace(0,np.nan); x["stoch_k"]=raw.rolling(3).mean().fillna(50); x["stoch_d"]=x.stoch_k.rolling(3).mean().fillna(50)
    e12=x.close.ewm(span=12,adjust=False).mean(); e26=x.close.ewm(span=26,adjust=False).mean(); x["macd"]=e12-e26; x["macd_signal"]=x.macd.ewm(span=9,adjust=False).mean(); x["macd_hist"]=x.macd-x.macd_signal
    pc=x.close.shift(1); tr=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1); x["atr"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); x["vol_ratio"]=x.volume/x.volume.rolling(20).mean().replace(0,np.nan); x["obv"]=(np.sign(x.close.diff()).fillna(0)*x.volume).cumsum(); x["taker_buy_ratio"]=(x.taker_quote/x.quote_volume.replace(0,np.nan)).clip(0,1).fillna(.5)
    return x

def _swings(d,wing=2,lookback=80):
    x=d.tail(lookback).reset_index(drop=True); highs=[]; lows=[]
    for i in range(wing,len(x)-wing):
        w=x.iloc[i-wing:i+wing+1]
        if x.high.iloc[i]>=w.high.max(): highs.append(float(x.high.iloc[i]))
        if x.low.iloc[i]<=w.low.min(): lows.append(float(x.low.iloc[i]))
    return highs[-8:],lows[-8:]

def snap(d,label):
    x=indicators(d); a=x.iloc[-1]; b=x.iloc[-2]; p=sf(a.close); highs,lows=_swings(x); atr=sf(a.atr); c6=x.close.tail(6).to_numpy(); l6=x.low.tail(6).to_numpy(); rg=max(0.0,sf(a.high)-sf(a.low))
    upper=(sf(a.high)-max(sf(a.open),sf(a.close)))/rg if rg else 0.0; lower=(min(sf(a.open),sf(a.close))-sf(a.low))/rg if rg else 0.0
    return {"tf":label,"price":p,"bar_id":int(pd.Timestamp(a.open_time).timestamp()),"ret3":pct(p,sf(x.close.iloc[-4])),"ret6":pct(p,sf(x.close.iloc[-7])),"ret24":pct(p,sf(x.close.iloc[-25])),"ema20":sf(a.ema20),"ema50":sf(a.ema50),"ema200":sf(a.ema200),"ema20_slope":pct(sf(a.ema20),sf(x.ema20.iloc[-4])),"ema50_slope":pct(sf(a.ema50),sf(x.ema50.iloc[-4])),"dist_ema20":pct(p,sf(a.ema20)),"dist_ema50":pct(p,sf(a.ema50)),"rsi":sf(a.rsi),"stoch_k":sf(a.stoch_k),"stoch_d":sf(a.stoch_d),"stoch_k_prev":sf(b.stoch_k),"stoch_min3":sf(x.stoch_k.tail(3).min()),"macd_hist":sf(a.macd_hist),"macd_hist_prev":sf(b.macd_hist),"vol_ratio":sf(a.vol_ratio,1),"obv_up":sf(a.obv)>=sf(x.obv.iloc[-6]),"obv_fast_up":sf(a.obv)>=sf(x.obv.iloc[-3]),"taker_buy_ratio":sf(x.taker_buy_ratio.tail(3).mean(),.5),"higher_closes6":int(sum(c6[i]>c6[i-1] for i in range(1,len(c6)))),"higher_lows6":int(sum(l6[i]>=l6[i-1] for i in range(1,len(l6)))),"near_high20_pct":max(0.0,-pct(p,sf(x.high.tail(20).max()))),"prev_high6":sf(x.high.iloc[-7:-1].max()),"atr_pct":100*atr/p if p else 0,"upper_wick":upper,"lower_wick":lower,"supports":sorted([v for v in lows if v<p],reverse=True)[:4],"resistances":sorted([v for v in highs if v>p])[:4]}

@dataclass
class Candidate:
    symbol:str; base:str; qv:float; rank:float; snapshot:dict[str,Any]; decision:dict[str,Any]

def universe():
    ex=_get("/api/v3/exchangeInfo"); ticks=_get("/api/v3/ticker/24hr"); tm={x.get("symbol"):x for x in ticks if isinstance(x,dict)}; out=[]
    for it in ex.get("symbols",[]):
        sym=it.get("symbol",""); base=it.get("baseAsset","")
        if it.get("quoteAsset")!="USDT" or it.get("status")!="TRADING" or it.get("isSpotTradingAllowed") is False: continue
        if base in IGNORED_BASES or (base.endswith(LEVERAGED_SUFFIXES) and base not in CRYPTO_BASES_ENDING_B): continue
        qv=sf((tm.get(sym) or {}).get("quoteVolume"))
        if qv>=MIN_QUOTE_VOLUME: out.append((sym,qv))
    return out

def _prefilter(symbol,qv):
    try:
        x=indicators(ohlcv(symbol,"1h",220)); a=x.iloc[-1]; b=x.iloc[-2]; p=sf(a.close); r=sf(a.rsi); sk=sf(a.stoch_k); sd=sf(a.stoch_d); sk0=sf(b.stoch_k); mh=sf(a.macd_hist); mh0=sf(b.macd_hist); e20=sf(a.ema20); e50=sf(a.ema50); vr=sf(a.vol_ratio,1); ret3=pct(p,sf(x.close.iloc[-4])); ret6=pct(p,sf(x.close.iloc[-7])); obv=sf(a.obv)>=sf(x.obv.iloc[-6]); high20=sf(x.high.tail(20).max()); near=max(0,-pct(p,high20)); taker=sf(x.taker_buy_ratio.tail(3).mean(),.5); c=x.close.tail(6).to_numpy(); l=x.low.tail(6).to_numpy(); hc=sum(c[i]>c[i-1] for i in range(1,len(c))); hl=sum(l[i]>=l[i-1] for i in range(1,len(l)))
        reset=sk<=75 or sf(x.stoch_k.tail(3).min())<=30; turn=sk>sd and sk>sk0
        score=(18 if p>=e50 else 0)+(12 if p>=e20 else 5)+(12 if 45<=r<=88 else 5 if 38<=r<=92 else 0)+(13 if reset else 8 if turn else 0)+(10 if mh>mh0 else 5 if mh>0 else 0)+(10 if obv else 0)+(7 if vr>=.8 else 3)+(7 if near<=7 else 3 if near<=12 else 0)+(5 if taker>=.50 else 0)+(4 if ret6>3 else 0)
        retrigger_seed=p>=e50 and 38<=r<=90 and (reset or turn) and -7<=ret3<=10
        pressure_seed=p>=e20 and 45<=r<=88 and hc>=3 and hl>=3 and near<=6 and -1<=ret3<=9 and (taker>=.50 or obv)
        seed="RETRIGGER" if retrigger_seed else "PRESSURE" if pressure_seed else ""
        if ret3>14 and sk>85 and pct(p,e20)>15: score-=18
        return symbol,qv,round(score,2),seed
    except Exception: return None

def prefilter_candidates():
    uni=universe(); rows=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fs=[ex.submit(_prefilter,s,q) for s,q in uni]
        for f in as_completed(fs):
            r=f.result()
            if r: rows.append(r)
    rows.sort(key=lambda z:z[2],reverse=True); selected=list(rows[:PREFILTER_CORE_N]); seen={r[0] for r in selected}
    for r in rows[PREFILTER_CORE_N:]:
        if len(selected)>=PYTHON_TOP_N: break
        if r[3] and r[0] not in seen: selected.append(r); seen.add(r[0])
    if len(selected)<PYTHON_TOP_N:
        for r in rows[PREFILTER_CORE_N:]:
            if len(selected)>=PYTHON_TOP_N: break
            if r[0] not in seen: selected.append(r); seen.add(r[0])
    return [(s,q,score) for s,q,score,_ in selected],len(uni)

def _load_state():
    try:
        with open(STATE_FILE,encoding="utf-8") as f: d=json.load(f); return d if isinstance(d,dict) else {}
    except Exception: return {}
def _save_state(d):
    try:
        os.makedirs(os.path.dirname(STATE_FILE) or ".",exist_ok=True); tmp=STATE_FILE+".tmp"
        with open(tmp,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
        os.replace(tmp,STATE_FILE)
    except Exception as exc: print(f"[STATE] {exc}",flush=True)
def _clean_watch(state):
    now=time.time(); watch=state.setdefault("watch",{}); dead=[s for s,r in watch.items() if now-sf((r or {}).get("first_seen",0))>WATCH_TTL_HOURS*3600]
    for s in dead: watch.pop(s,None)
def _daily_room(state):
    day=now_tr().strftime("%Y-%m-%d")
    if state.get("signal_day")!=day: state["signal_day"]=day; state["signal_count"]=0
    return max(0,MAX_SIGNALS_PER_DAY-int(state.get("signal_count",0)))

def btc_regime():
    try:
        h=snap(ohlcv("BTCUSDT","1h"),"1H"); f=snap(ohlcv("BTCUSDT","4h"),"4H")
        if h["ret3"]<=-3 or f["ret3"]<=-6: return "RED"
        if h["ret3"]<-.9 or f["macd_hist"]<f["macd_hist_prev"]: return "YELLOW"
        return "GREEN"
    except Exception: return "YELLOW"

def evaluate(symbol,qv,pre_rank,regime,prior):
    day=snap(ohlcv(symbol,"1d"),"1D"); four=snap(ohlcv(symbol,"4h"),"4H"); one=snap(ohlcv(symbol,"1h"),"1H"); fast=snap(ohlcv(symbol,"15m"),"15M"); live=sf(_get("/api/v3/ticker/price",{"symbol":symbol}).get("price")) or one["price"]
    prior_phase=(prior or {}).get("phase"); prior_bar=int(sf((prior or {}).get("last_bar_15m"),0))

    day_trend=day["price"]>=day["ema20"] and day["ema20_slope"]>=-.8 and day["rsi"]>=50
    four_trend=four["price"]>=four["ema50"] and four["ema50_slope"]>=-.2 and four["rsi"]>=45
    one_structure=one["price"]>=one["ema50"] and one["rsi"]>=38
    one_reset=one["stoch_k"]<=75 or one["stoch_min3"]<=30
    one_turn=one["stoch_k"]>one["stoch_d"] and one["stoch_k"]>one["stoch_k_prev"]
    one_mom=one["macd_hist"]>one["macd_hist_prev"] or one["obv_fast_up"] or one_turn

    # Six broad, rounded audit features. 5/6 was materially more selective than v10
    # while keeping useful coverage in both halves of the 54-case sample.
    audit_score=sum((
        four["dist_ema50"]>=6.0,
        four["ema20_slope"]>=1.0,
        one["dist_ema50"]>=2.0,
        one["upper_wick"]>=0.22,
        one["stoch_k"]<=75.0,
        day["rsi"]>=62.0,
    ))
    audit_balanced=day_trend and four_trend and one_structure and audit_score>=5
    audit_strict=day_trend and four_trend and four["dist_ema50"]>=6.0 and one["dist_ema50"]>=2.0 and one["upper_wick"]>=0.22 and one["stoch_k"]<=75.0

    fast_turn=fast["stoch_k"]>fast["stoch_d"] and fast["stoch_k"]>fast["stoch_k_prev"] and fast["rsi"]>=40
    fast_confirm=fast_turn and (fast["macd_hist"]>fast["macd_hist_prev"] or fast["obv_fast_up"]) and fast["price"]>=fast["ema20"]*.995

    pressure=day_trend and four_trend and audit_score>=4 and one["price"]>=one["ema20"] and one["ema20_slope"]>0 and one["rsi"]>=50 and one["higher_closes6"]>=3 and one["higher_lows6"]>=3 and one["near_high20_pct"]<=4.5
    fast_break=fast["price"]>=fast["prev_high6"]*.998 and fast["rsi"]>=48 and (fast["macd_hist"]>fast["macd_hist_prev"] or fast["obv_fast_up"])
    # REVIZE: yalnız RETRIGGER yolu kapanır; PRESSURE yolu korunur.
    retrigger=audit_balanced and one_reset and one["near_high20_pct"]<=1.0

    first_price=sf((prior or {}).get("first_price"),live); chase=pct(live,first_price) if first_price else 0
    structural_break=(day["price"]<day["ema50"] and four["price"]<four["ema50"]) or (four["price"]<four["ema50"] and one["price"]<one["ema50"] and four["ema50_slope"]<0)
    blowoff=one["ret3"]>14 and one["stoch_k"]>85 and one["dist_ema20"]>15
    chased=chase>8 and not one_reset

    q=32+audit_score*8+(8 if one_turn else 0)+(7 if one_mom else 0)+(8 if fast_confirm else 0)+(8 if audit_strict else 0)
    pq=24+audit_score*8+(20 if pressure else 0)+(16 if fast_break else 0)+(5 if one["taker_buy_ratio"]>=.52 else 0)
    if regime=="RED": q-=5; pq-=5
    quality=clamp(max(q if retrigger else 0,pq if pressure else 0)); decision="REDDET"; phase="NONE"; kind="NONE"; why="Yeterli kurulum yok"

    if not structural_break and not blowoff and not chased:
        if pressure:
            decision="TETIK_BEKLE"; phase="PRESSURE"; kind="PRESSURE"; why="Güçlü üst zaman yapısı; momentum devam tetiği izleniyor"
        if retrigger:
            decision="TETIK_BEKLE"; phase="COOLING" if not one_turn else "ARMED"; kind="RETRIGGER"; why="Güçlü 1D/4H yapı + ölçülmüş 1H reset/rejection; yeniden tetik izleniyor"
        observed_new_bar=bool(prior and fast["bar_id"]>prior_bar)
        eligible_history=bool(prior and observed_new_bar and prior_phase in {"COOLING","ARMED","PRESSURE","FORMING"})
        retrigger_ready=retrigger and one_mom and fast_confirm
        pressure_ready=pressure and fast_break
        if eligible_history and quality>=FINAL_MIN_QUALITY and (retrigger_ready or pressure_ready):
            decision="ALIM_ADAYI"; phase="ENTRY"; kind="RETRIGGER" if retrigger_ready and q>=pq else "PRESSURE"; why="İzleme sonrası yeni kapalı 15M mumda giriş tetiği doğrulandı"
        elif decision=="REDDET" and day_trend and four_trend and audit_score>=3:
            decision="TETIK_BEKLE"; phase="FORMING"; kind="FORMING"; why="Üst zaman yapısı var; yeterli 1H kalite puanı oluşması bekleniyor"
    if structural_break: decision="REDDET"; phase="BROKEN"; kind="NONE"; why="Üst zaman yapısı bozulmuş"
    if blowoff or chased: decision="REDDET"; phase="LATE"; kind="NONE"; why="1H hareketi gerçek blow-off/chase bölgesinde"

    ss={"symbol":symbol,"live_price":live,"1d":day,"4h":four,"1h":one,"15m":fast,"btc_regime":regime}; dd={"decision":decision,"confidence":round(quality,1),"state":phase,"setup_kind":kind,"why_now":why,"risk_flags":(["BTC sert baskı altında"] if regime=="RED" else [])}; return Candidate(symbol,symbol[:-4],qv,quality+min(8,max(0,pre_rank-55)*.25),ss,dd)

def levels(c):
    p=sf(c.snapshot["live_price"]); h=c.snapshot["1h"]; f=c.snapshot["4h"]; sups=[sf(x) for x in h["supports"]+f["supports"] if 0<sf(x)<p]; ress=sorted(set(sf(x) for x in h["resistances"]+f["resistances"] if sf(x)>p)); support=max(sups) if sups else min(h["ema20"],h["ema50"],p*.96); stop=support*.975; tp1=next((r for r in ress if pct(r,p)>=2.5),p*1.035); tp2=next((r for r in ress if r>tp1 and pct(r,p)>=5),max(tp1*1.02,p*1.055)); return {"price":p,"support":support,"stop":stop,"tp1":tp1,"tp2":tp2}

def discover(state):
    pre,total=prefilter_candidates(); regime=btc_regime(); watch=state.setdefault("watch",{}); out=[]
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,6)) as ex:
        fs={ex.submit(evaluate,s,q,r,regime,watch.get(s)):s for s,q,r in pre}
        for f in as_completed(fs):
            try: out.append(f.result())
            except Exception as exc: print(f"[SCAN] {fs[f]}: {exc}",flush=True)
    out.sort(key=lambda c:c.rank,reverse=True); return [c for c in out if c.decision["decision"]=="ALIM_ADAYI"],[c for c in out if c.decision["decision"]=="TETIK_BEKLE"],{"universe":total,"evaluated":len(out),"btc_regime":regime}

def _payload(c):
    lv=levels(c); p=lv["price"]; stop_pct=max(0,pct(p,lv["stop"])); target_pct=max(0,pct(lv["tp1"],p)); rr=target_pct/stop_pct if stop_pct else 0
    return {"symbol":c.symbol.replace("USDT","/USDT"),"entry":round(p,10),"limit_price":round(p,10),"signal_price":round(p,10),"stop":round(lv["stop"],10),"tp1":round(lv["tp1"],10),"tp2":round(lv["tp2"],10),"tp3":None,"sig_type":"spot_opportunity","sub_type":"","source":"spot-scanner","phase":"manual_review","target_pct":round(target_pct,2),"stop_pct":round(stop_pct,2),"rr":round(rr,2),"setup":c.decision["state"],"setup_kind":c.decision["setup_kind"],"score":c.decision["confidence"],"btc_regime":c.snapshot["btc_regime"]}

def _send_portfolio(c):
    if not PORTFOLIO_URL: return ""
    h={"Content-Type":"application/json"}
    if PORTFOLIO_TOKEN: h["Authorization"]=f"Bearer {PORTFOLIO_TOKEN}"
    try:
        r=HTTP.post(f"{PORTFOLIO_URL}/api/signal",json=_payload(c),headers=h,timeout=15); return "ok" if r.status_code in (200,201,409) else ""
    except Exception: return ""

def _send_telegram(c):
    if not TELEGRAM_ENABLED or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    lv=levels(c); text=f"#{c.base} SPOT ADAYI\nFiyat: {lv['price']}\nStop: {lv['stop']}\nTP1: {lv['tp1']}\nTP2: {lv['tp2']}\nKalite: %{c.decision['confidence']:.0f}"; payload={"chat_id":TELEGRAM_CHAT_ID,"text":text}
    if TELEGRAM_THREAD_ID: payload["message_thread_id"]=TELEGRAM_THREAD_ID
    try: return HTTP.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",json=payload,timeout=15).ok
    except Exception: return False

runtime={"status":"BOOT","version":"v11","outputs_enabled":bool(PORTFOLIO_URL),"last_scan":None,"symbols":0,"evaluated":0,"watching":0,"signals":0,"btc_regime":None,"last_error":None}
def scan_cycle():
    runtime.update({"status":"SCANNING","signals":0,"last_error":None}); state=_load_state(); _clean_watch(state)
    try:
        finals,waits,stats=discover(state); watch=state.setdefault("watch",{}); now=time.time()
        for c in waits:
            rec=watch.get(c.symbol) or {"first_seen":now,"first_price":c.snapshot["live_price"],"observations":0,"last_bar_15m":0}; bar=c.snapshot["15m"]["bar_id"]
            if int(sf(rec.get("last_bar_15m"),0)) and bar>int(sf(rec.get("last_bar_15m"),0)): rec["observations"]=int(sf(rec.get("observations",0)))+1
            rec.update({"updated_at":now,"phase":c.decision["state"],"setup_kind":c.decision["setup_kind"],"price":c.snapshot["live_price"],"score":c.decision["confidence"],"last_bar_15m":bar}); watch[c.symbol]=rec
        room=_daily_room(state); selected=finals[:room]; emitted=0
        for c in selected:
            lv=levels(c); print(f"[FINAL CANDIDATE] {c.symbol} {c.decision['setup_kind']} q={c.decision['confidence']} entry={lv['price']} stop={lv['stop']} tp1={lv['tp1']} tp2={lv['tp2']}",flush=True)
            if True:
                portfolio_ok=bool(_send_portfolio(c)); telegram_ok=bool(_send_telegram(c)); ok=portfolio_ok or telegram_ok
                if ok: state["signal_count"]=int(state.get("signal_count",0))+1; watch.pop(c.symbol,None); emitted+=1
        _save_state(state); runtime.update({"status":"RUNNING","last_scan":now_tr().isoformat(),"symbols":stats["universe"],"evaluated":stats["evaluated"],"watching":len(watch),"signals":emitted,"btc_regime":stats["btc_regime"]}); print(f"[SCAN DONE] evren={stats['universe']} evaluated={stats['evaluated']} watch={len(watch)} final={len(selected)} sent={emitted} BTC={stats['btc_regime']}",flush=True)
    except Exception as exc:
        runtime.update({"status":"ERROR","last_error":f"{type(exc).__name__}: {exc}","last_scan":now_tr().isoformat()}); _save_state(state); print(f"[SCAN ERROR] {exc}",flush=True)

def scan_loop():
    if not SCAN_ON_START: time.sleep(SCAN_INTERVAL_SECONDS)
    while True: scan_cycle(); time.sleep(SCAN_INTERVAL_SECONDS)
@app.route("/")
def index(): return jsonify({"service":"SPOT_SCANNER",**runtime})
@app.route("/health")
def health(): return jsonify(runtime),200

# ---- Yerel tarihsel replay: aşağıdaki bölüm canlı tarayıcıyı başlatmaz. ----
import sys
scanner = sys.modules[__name__]
#!/usr/bin/env python
"""Local Portfolio-style replay (v5). Run from this folder; writes a JSON report.

v4 -> v5 (tarama/karar mantığı aynı; hız + hata düzeltmeleri):
  1) signal_features NameError düzeltildi. v4'te bu hata sessizce yutuluyor, HİÇ pozisyon açılmıyordu.
  2) hist(): her çağrıda tüm tabloyu süzüp kopyalamak yerine searchsorted + iloc dilimi.
  3) snap() ve _prefilter() sonuçları, o zaman diliminde yeni mum kapanana kadar önbellekten gelir
     (1D/4H/1H göstergeleri her 15 dakikada baştan hesaplanmaz).
  4) _swings numpy ile hesaplanır (aynı sonuç).
  5) evaluate()'in kesin REDDET döneceği coinlerde (1D/4H trend yok, audit<3, yapı bozuk, blow-off) evaluate() çağrılmaz.
  6) Sessiz except'ler sayılır; özet ekrana ve JSON'a yazılır.
  7) İndirilen mumlar bt_cache klasörüne kaydedilir; aynı tarih aralığı tekrar indirilmez (--no-cache ile kapatılır).
  8) Henüz kapanmamış mum veriye alınmaz ve tarama şimdiki zamanı geçmez.
  9) 80 kapalı mumu olmayan tek bir coin artık tüm adımı iptal etmez; yalnız o coin atlanır.
"""
import argparse, json, os, pickle, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from numpy.lib.stride_tricks import sliding_window_view

COLS=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
# Bu araştırmanın evreni: aktif USDT spot pariteleri, stable/fiat hariç.
# JUP/SYRUP dahil; WBTC/PAXG/XAUT dahil.
RESEARCH_EXCLUDED_BASES = {
    "BFUSD", "EUR", "EURI", "FDUSD", "FRAX", "RLUSD", "TUSD", "U",
    "USD1", "USDC", "USDE", "USDP", "USDS", "USTC", "XUSD",
}

def research_universe():
    exchange = requests.get(BINANCE + "/api/v3/exchangeInfo", timeout=30).json()
    symbols = []
    for item in exchange.get("symbols", []):
        if (
            item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
            and item.get("isSpotTradingAllowed") is not False
            and item.get("baseAsset") not in RESEARCH_EXCLUDED_BASES
        ):
            symbols.append(item["symbol"])
    return sorted(set(symbols))
API="https://api.binance.com/api/v3/klines"
LOOKBACK={"15m":18,"1h":20,"4h":60,"1d":320}
LIMITS={"15m":1000,"1h":260,"4h":260,"1d":260}
CACHE_DIR=Path(__file__).resolve().parent/"bt_cache"

def as_frame(rows):
    d=pd.DataFrame(rows,columns=COLS)
    for c in ("open","high","low","close","volume","quote_volume","taker_quote"): d[c]=pd.to_numeric(d[c],errors="coerce")
    d.open_time=pd.to_datetime(d.open_time,unit="ms",utc=True); d.close_time=pd.to_datetime(d.close_time,unit="ms",utc=True)
    return d.dropna(subset=["open","high","low","close","volume"]).drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)

def fetch(symbol, interval, start, end):
    rows=[]; cur=int(start.timestamp()*1000); finish=int(end.timestamp()*1000); http=requests.Session()
    while cur<finish:
        r=http.get(API,params={"symbol":symbol,"interval":interval,"startTime":cur,"endTime":finish-1,"limit":1000},timeout=30); r.raise_for_status(); batch=r.json()
        if not batch: break
        rows.extend(batch); nxt=int(batch[-1][6])+1
        if nxt<=cur: break
        cur=nxt
        if len(batch)==1000: time.sleep(.04)
    if not rows: raise RuntimeError(f"{symbol} {interval}: mum verisi yok")
    return as_frame(rows)

def load_symbol(symbol,start,end,use_cache=True):
    """(symbol, {tf: DataFrame}, önbellekten_mi). Henüz kapanmamış mum atılır."""
    path=CACHE_DIR/f"{symbol}_{start:%Y%m%d}_{end:%Y%m%d}.pkl"
    if use_cache and path.exists():
        try:
            with open(path,"rb") as f: return symbol,pickle.load(f),True
        except Exception: pass
    now=pd.Timestamp.now(tz="UTC"); out={}
    for tf in LIMITS:
        d=fetch(symbol,tf,start-pd.Timedelta(days=LOOKBACK[tf]),end)
        out[tf]=d[d.close_time<now].reset_index(drop=True)
    if use_cache:
        try:
            CACHE_DIR.mkdir(exist_ok=True); tmp=path.with_suffix(".tmp")
            with open(tmp,"wb") as f: pickle.dump(out,f)
            os.replace(tmp,path)
        except Exception as e: print("[CACHE]",e)
    return symbol,out,False

def close_position(p,bar,now):
    """Portfolio kuralı: TP1 öncesi stop/24s expiry, TP1 sonrası peak-%2.5 trailing."""
    high,low,close=float(bar.high),float(bar.low),float(bar.close); p["peak"]=max(p["peak"],high)
    if not p["tp1_hit"] and low<=p["stop"]: return "loss",p["stop"]
    if not p["tp1_hit"] and high>=p["tp1"]: p["tp1_hit"]=True
    if p["tp1_hit"]:
        trail=max(p["entry"],p["peak"]*.975)
        if close<=trail: return "win",trail
    if not p["tp1_hit"] and now>=p["expiry"]: return "expired",close
    return None,None

def jsonable(value):
    """numpy/pandas sayılarını JSON'un anlayacağı normal sayılara dönüştür."""
    if isinstance(value, dict): return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [jsonable(v) for v in value]
    if hasattr(value, "item"):
        try: return value.item()
        except Exception: pass
    if isinstance(value, float) and (pd.isna(value) or value in (float("inf"),float("-inf"))): return None
    return value

def _dt64(ts): return pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).to_datetime64()

def fast_swings(d,wing=2,lookback=80):
    """scanner._swings ile aynı sonuç; iloc döngüsü yerine numpy pencere."""
    x=d.tail(lookback); h=x.high.to_numpy(dtype=float); l=x.low.to_numpy(dtype=float); w=2*wing+1
    if len(h)<w: return [],[]
    hc=h[wing:len(h)-wing]; lc=l[wing:len(l)-wing]
    highs=hc[hc>=sliding_window_view(h,w).max(axis=1)].tolist(); lows=lc[lc<=sliding_window_view(l,w).min(axis=1)].tolist()
    return highs[-8:],lows[-8:]

class Replay:
    """Kesim anına kadar kapanmış mum dilimleri + snap/_prefilter önbelleği."""
    def __init__(self,data,orig_snap,orig_prefilter):
        self.data=data; self.orig_snap=orig_snap; self.orig_prefilter=orig_prefilter
        self.times={s:{tf:d.close_time.dt.tz_localize(None).to_numpy() for tf,d in x.items()} for s,x in data.items()}
        self.closes={s:x["15m"].close.to_numpy(dtype=float) for s,x in data.items()}
        self.cut=None; self.snap_cache={}; self.pre_cache={}; self.stats=Counter(); self.tag_frames=True
    def set_cutoff(self,ts): self.cut=_dt64(ts)
    def index(self,symbol,interval,cut=None):
        return int(np.searchsorted(self.times[symbol][interval],self.cut if cut is None else cut,side="right"))
    def hist(self,symbol,interval,limit=240):
        idx=self.index(symbol,interval); out=self.data[symbol][interval].iloc[max(0,idx-limit):idx].reset_index(drop=True)
        if len(out)<80: raise ValueError("yetersiz kapanmis mum")
        if self.tag_frames: out.attrs["bt_key"]=(symbol,interval,limit,idx)
        return out
    def price(self,symbol):
        idx=self.index(symbol,"15m")
        return float(self.closes[symbol][idx-1]) if min(idx,240)>=80 else None
    def snap(self,d,label):
        # anahtar çıkarılır: attrs dolu kalırsa pandas her ara Series'te deepcopy yapıp indicators()'ı yavaşlatıyor
        key=d.attrs.pop("bt_key",None)
        if key is None: return self.orig_snap(d,label)
        slot=(key[0],key[1],key[2],label); hit=self.snap_cache.get(slot)
        if hit is not None and hit[0]==key[3]: self.stats["snap_hit"]+=1; return hit[1]
        self.stats["snap_calc"]+=1; res=self.orig_snap(d,label); self.snap_cache[slot]=(key[3],res); return res
    def prefilter(self,symbol):
        idx=self.index(symbol,"1h"); hit=self.pre_cache.get(symbol)
        if hit is not None and hit[0]==idx: return hit[1]
        self.tag_frames=False
        try: res=self.orig_prefilter(symbol,1_000_000_000)
        finally: self.tag_frames=True
        self.pre_cache[symbol]=(idx,res); return res

def evaluate_gate(symbol):
    """False ise scanner.evaluate() kesin REDDET döner, bu yüzden çağrılmaz (15M snap hesabı atlanır).
    Koşullar evaluate() ile birebir aynıdır: TETIK_BEKLE/ALIM_ADAYI için day_trend+four_trend, audit_score>=3,
    structural_break ve blowoff olmaması şart. evaluate() değişirse burası da güncellenmeli."""
    day=scanner.snap(scanner.ohlcv(symbol,"1d"),"1D"); four=scanner.snap(scanner.ohlcv(symbol,"4h"),"4H")
    day_trend=day["price"]>=day["ema20"] and day["ema20_slope"]>=-.8 and day["rsi"]>=50
    four_trend=four["price"]>=four["ema50"] and four["ema50_slope"]>=-.2 and four["rsi"]>=45
    if not (day_trend and four_trend): return False
    one=scanner.snap(scanner.ohlcv(symbol,"1h"),"1H")
    audit_score=sum((four["dist_ema50"]>=6.0,four["ema20_slope"]>=1.0,one["dist_ema50"]>=2.0,one["upper_wick"]>=0.22,one["stoch_k"]<=75.0,day["rsi"]>=62.0))
    structural_break=(day["price"]<day["ema50"] and four["price"]<four["ema50"]) or (four["price"]<four["ema50"] and one["price"]<one["ema50"] and four["ema50_slope"]<0)
    blowoff=one["ret3"]>14 and one["stoch_k"]>85 and one["dist_ema20"]>15
    return audit_score>=3 and not structural_break and not blowoff

def signal_features(symbol):
    """Sinyal anında, yalnız o ana kadar kapanmış mumlardan çıkarılan snapshot."""
    return jsonable({
        "15m":scanner.snap(scanner.ohlcv(symbol,"15m",260),"15M"),
        "1h":scanner.snap(scanner.ohlcv(symbol,"1h",260),"1H"),
        "4h":scanner.snap(scanner.ohlcv(symbol,"4h",260),"4H"),
        "1d":scanner.snap(scanner.ohlcv(symbol,"1d",260),"1D"),
    })

def main():
    a=argparse.ArgumentParser(description="Current scanner + Portfolio exit-rule replay (v5)")
    a.add_argument("--start",default="2026-01-01"); a.add_argument("--end",default=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"))
    a.add_argument("--symbols",type=int,default=0,help="0=tum arastirma evreni; pozitif deger ilk N pariteyi sinirlar"); a.add_argument("--output",default="backtest_result.json")
    a.add_argument("--no-cache",action="store_true",help="bt_cache klasörünü kullanma, veriyi yeniden indir")
    args=a.parse_args(); start=pd.Timestamp(args.start,tz="UTC"); end=pd.Timestamp(args.end,tz="UTC")+pd.Timedelta(days=1)
    names=research_universe(); names=names if args.symbols<=0 else names[:args.symbols]; data={}; from_cache=0
    print(f"[EVREN] aktif USDT spot, stable/fiat haric: {len(names)}",flush=True)
    print(f"[INDIRME] {len(names)} coin | {start.date()} -> {end.date()}")
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs=[pool.submit(load_symbol,s,start,end,not args.no_cache) for s in names]
        for i,j in enumerate(as_completed(jobs),1):
            try: s,x,hit=j.result(); data[s]=x; from_cache+=hit
            except Exception as e: print("[ATLA]",e)
            if i%10==0 or i==len(jobs): print(f"[INDIRME] {i}/{len(jobs)} kullanilabilir={len(data)} onbellekten={from_cache}")
    active=[s for s in names if s!="BTCUSDT" and s in data]
    if "BTCUSDT" not in data or not active: raise SystemExit("Yeterli veri indirilemedi.")

    R=Replay(data,scanner.snap,scanner._prefilter); prices={}; errors=Counter(); examples={}
    def err(stage,e):
        k=f"{stage}:{type(e).__name__}"; errors[k]+=1
        if k not in examples: examples[k]=str(e)[:200]; print(f"[HATA] {k}: {examples[k]} (bu turun sonraki tekrarlari sadece sayilir)",flush=True)
    old={n:getattr(scanner,n) for n in ("ohlcv","_get","snap","_swings")}
    def get(path,params=None,attempts=4):
        if path=="/api/v3/ticker/price": return {"price":str(prices.get((params or {}).get("symbol"),0))}
        return old["_get"](path,params,attempts)
    def prep(ts):
        R.set_cutoff(ts); prices.clear()
        for s in active+["BTCUSDT"]:
            p=R.price(s)
            if p is not None: prices[s]=p
    def selected():
        rows=[x for x in map(R.prefilter,active) if x]
        rows.sort(key=lambda x:x[2],reverse=True); return [(s,q,r) for s,q,r,_ in rows[:scanner.PYTHON_TOP_N]]

    watch={}; positions={}; closed=[]; daily={}
    last=min(end,pd.Timestamp.now(tz="UTC"))
    steps=pd.date_range(start.ceil("15min"),(last-pd.Timedelta(minutes=15)).floor("15min"),freq="15min",tz="UTC")
    scanner.ohlcv,scanner._get,scanner.snap,scanner._swings=R.hist,get,R.snap,fast_swings
    t0=time.time()
    try:
      for n,ts in enumerate(steps,1):
        ts64=_dt64(ts)
        for s in list(positions):
            i=R.index(s,"15m",ts64)
            if i==0: continue
            why,price=close_position(positions[s],data[s]["15m"].iloc[i-1],ts)
            if why:
                p=positions.pop(s)
                record={k:v for k,v in p.items() if k!="expiry"}
                record.update({"symbol":s,"exit_time":ts.isoformat(),"exit":round(float(price),10),"close_reason":why,"close_pct":round((float(price)/p["entry"]-1)*100,2),"peak_pct":round((p["peak"]/p["entry"]-1)*100,2)})
                closed.append(record)
        try:
            prep(ts); regime=scanner.btc_regime(); finals=[]; waits=[]
            for s,q,r in selected():
                try:
                    if not evaluate_gate(s): R.stats["gate_skip"]+=1; continue
                    c=scanner.evaluate(s,q,r,regime,watch.get(s))
                    if c.decision["decision"]=="ALIM_ADAYI": finals.append(c)
                    elif c.decision["decision"]=="TETIK_BEKLE": waits.append(c)
                except Exception as e: err("evaluate",e)
            for c in waits: watch[c.symbol]={"first_seen":ts.timestamp(),"first_price":c.snapshot["live_price"],"observations":0,"last_bar_15m":int(c.snapshot["15m"]["bar_id"]),"phase":c.decision["state"],"setup_kind":c.decision["setup_kind"],"updated_at":ts.timestamp()}
            key=ts.strftime("%Y-%m-%d"); room=max(0,scanner.MAX_SIGNALS_PER_DAY-daily.get(key,0))
            for c in sorted(finals,key=lambda x:x.rank,reverse=True)[:room]:
                if c.symbol in positions: continue
                lv=scanner.levels(c); entry,stop,tp1=map(float,(lv["price"],lv["stop"],lv["tp1"]))
                if not stop<entry<tp1: continue
                try: feats=signal_features(c.symbol)
                except Exception as e: err("features",e); feats={}
                daily[key]=daily.get(key,0)+1; watch.pop(c.symbol,None)
                positions[c.symbol]={"entry_time":ts.isoformat(),"entry":entry,"stop":stop,"tp1":tp1,"peak":entry,"tp1_hit":False,"expiry":ts+pd.Timedelta(hours=24),"setup_kind":c.decision["setup_kind"],"score":round(float(c.decision["confidence"]),2),"btc_regime":regime,"features":feats}
        except Exception as e: err("adim",e)
        if n%192==0 or n==len(steps):
            el=time.time()-t0; eta=el/n*(len(steps)-n)
            print(f"[TARAMA] {n}/{len(steps)} kapanan={len(closed)} acik={len(positions)} hata={sum(errors.values())} gecen={el/60:.1f}dk kalan~{eta/60:.1f}dk",flush=True)
    finally:
        for k,v in old.items(): setattr(scanner,k,v)
    elapsed=time.time()-t0
    groups={k:[x for x in closed if x["close_reason"]==k] for k in ("win","loss","expired")}
    result={"period":{"start":start.isoformat(),"end":end.isoformat()},"summary":{"closed":len(closed),**{k:len(v) for k,v in groups.items()},"win_rate_pct":round(100*len(groups["win"])/len(closed),2) if closed else 0,"net_pct_sum":round(sum(x["close_pct"] for x in closed),2),"win_pct_sum":round(sum(x["close_pct"] for x in groups["win"]),2),"loss_pct_sum":round(sum(x["close_pct"] for x in groups["loss"]),2),"expired_pct_sum":round(sum(x["close_pct"] for x in groups["expired"]),2)},"trades":closed,"open_at_end":[{"symbol":s,**{**p,"expiry":p["expiry"].isoformat()}} for s,p in positions.items()],
            "diagnostics":{"scan_minutes":round(elapsed/60,2),"steps":len(steps),"coins":len(active),"errors":dict(errors),"error_examples":examples,"trend_gate_skipped":R.stats["gate_skip"],"snap_calculated":R.stats["snap_calc"],"snap_from_cache":R.stats["snap_hit"]},
            "limits":["Guncel coin evreni kullanilir.","Bu bugunku scannerin tarihsel replayidir.","Ayni 15dk mumda TP1/stop sirasi belirsizse stop onceligi uygulanir."]}
    Path(args.output).write_text(json.dumps(jsonable(result),ensure_ascii=False,indent=2),encoding="utf-8")
    if errors:
        print("[HATALAR]")
        for k,v in errors.most_common(): print(f"  {k} x{v} | ornek: {examples[k]}")
    print(f"[SURE] tarama {elapsed/60:.1f} dk")
    print(json.dumps(result["summary"],ensure_ascii=False)); print("JSON:",args.output)
if __name__=="__main__": main()
