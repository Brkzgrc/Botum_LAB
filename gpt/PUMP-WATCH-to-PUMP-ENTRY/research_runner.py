import json, math, time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from pathlib import Path

START_MS=1767225600000
END_MS=1790035199000
COST=0.002
FORCE_INCLUDE={"JUP","SYRUP"}
EXCLUDE={"USDT","USDC","TUSD","USDP","FDUSD","BUSD","DAI","EURI","EUR","TRY","GBP","BRL","AUD","BIDR","AEUR","USD1","USDE","USDS","USTC","FRAX","RLUSD","BFUSD","XUSD"}

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"
OUT.mkdir(exist_ok=True)

def get(path, params=None, retries=6):
    url="https://api.binance.com"+path
    if params: url+="?"+urlencode(params)
    for n in range(retries):
        try:
            with urlopen(Request(url,headers={"User-Agent":"Botum-LAB-research"}),timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            if n==retries-1: raise
            time.sleep(2**n)

def universe():
    x=get("/api/v3/exchangeInfo")
    out=[]
    for s in x["symbols"]:
        b=s["baseAsset"]
        if s["quoteAsset"]!="USDT" or s["status"]!="TRADING" or not s.get("isSpotTradingAllowed",False): continue
        if b not in FORCE_INCLUDE and b in EXCLUDE: continue
        if s["symbol"].endswith(("UPUSDT","DOWNUSDT","BULLUSDT","BEARUSDT")): continue
        out.append(s["symbol"])
    return sorted(set(out))

def klines(symbol, interval, start=START_MS, end=END_MS):
    rows=[]; cur=start
    while cur<=end:
        x=get("/api/v3/klines",{"symbol":symbol,"interval":interval,"startTime":cur,"endTime":end,"limit":1000})
        if not x: break
        rows.extend(x)
        nxt=x[-1][0]+1
        if nxt<=cur: break
        cur=nxt
        time.sleep(.025)
    return rows

def ema(a,n):
    if not a:return []
    k=2/(n+1); v=a[0]; z=[]
    for x in a: v=x*k+v*(1-k); z.append(v)
    return z

def mean(a): return sum(a)/len(a) if a else float("nan")
def std(a):
    if not a:return float("nan")
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))

def features(rows):
    o=[float(x[1]) for x in rows]; h=[float(x[2]) for x in rows]; l=[float(x[3]) for x in rows]
    c=[float(x[4]) for x in rows]; v=[float(x[5]) for x in rows]; q=[float(x[7]) for x in rows]
    e20=ema(c,20); e50=ema(c,50)
    ef=ema(c,12); es=ema(c,26); mac=[a-b for a,b in zip(ef,es)]; sg=ema(mac,9); hist=[a-b for a,b in zip(mac,sg)]
    obv=[0.0]
    for i in range(1,len(c)): obv.append(obv[-1]+(v[i] if c[i]>c[i-1] else -v[i] if c[i]<c[i-1] else 0))
    tr=[h[0]-l[0]]
    for i in range(1,len(c)): tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
    atr=ema(tr,14)
    z=[]
    for i in range(60,len(c)-20):
        vol20=mean(q[i-19:i+1]); rvol=mean(q[i-2:i+1])/(vol20 or 1)
        prev_hi=max(h[i-12:i]); dist=(prev_hi-c[i])/c[i]
        low_old=min(l[i-11:i-5]); low_new=min(l[i-5:i+1]); hl=low_new/(low_old or low_new)-1
        r0=(max(h[i-11:i-5])-min(l[i-11:i-5]))/c[i]
        r1=(max(h[i-5:i+1])-min(l[i-5:i+1]))/c[i]
        contract=r1/(r0 or 1)
        obvs=(obv[i]-obv[i-6])/(abs(obv[i-6])+1)
        obva=((obv[i]-obv[i-3])-(obv[i-3]-obv[i-6]))/(abs(obv[i-6])+1)
        hs=(hist[i]-hist[i-3])/(atr[i]+1e-12)
        bw=4*std(c[i-19:i+1])/(mean(c[i-19:i+1]) or 1)
        bwp=4*std(c[i-25:i-5])/(mean(c[i-25:i-5]) or 1)
        z.append(dict(i=i,t=rows[i][0],rvol=rvol,dist=dist,hl=hl,contract=contract,obvs=obvs,obva=obva,
                      hs=hs,bwch=bw/(bwp or 1),es=e20[i]/e20[i-6]-1,trend=c[i]/e50[i]-1,atr=atr[i]))
    return dict(rows=rows,o=o,h=h,l=l,c=c,f=z)

def signal(f,p):
    return (f["rvol"]>=p["rvol"] and f["dist"]<=p["dist"] and f["hl"]>=p["hl"] and
            f["contract"]<=p["contract"] and f["obvs"]>p["obvs"] and f["hs"]>=p["hs"] and
            f["es"]>0 and f["trend"]>p["trend"] and f["bwch"]<=p["bwch"])

def test(ds,p,start,end):
    trades=[]
    for sym,d in ds.items():
        last=-999
        for f in d["f"]:
            if f["t"]<start or f["t"]>end or f["i"]-last<6 or not signal(f,p): continue
            ei=f["i"]+1; entry=d["o"][ei]
            swing=min(d["l"][max(0,f["i"]-6):f["i"]+1])
            stop=max(entry*.88,min(entry*.94,swing-.25*f["atr"]))
            tp=entry*(1+p["tp"])
            ret=None
            for j in range(ei,min(ei+13,len(d["c"]))):
                hs=d["h"][j]>=tp; ss=d["l"][j]<=stop
                if hs and ss: ret=stop/entry-1-COST; break
                if ss: ret=stop/entry-1-COST; break
                if hs: ret=tp/entry-1-COST; break
            if ret is None:
                j=min(ei+12,len(d["c"])-1); ret=d["c"][j]/entry-1-COST
            trades.append((sym,f["t"],ret)); last=f["i"]
    n=len(trades); wins=[x[2] for x in trades if x[2]>0]; losses=[x[2] for x in trades if x[2]<=0]
    gp=sum(wins); gl=-sum(losses)
    return dict(n=n,wr=len(wins)/n if n else 0,pnl=sum(x[2] for x in trades),avg=sum(x[2] for x in trades)/n if n else 0,
                pf=gp/gl if gl else 99, trades=trades)

def main():
    syms=universe()
    print("UNIVERSE",len(syms),"JUP", "JUPUSDT" in syms,"SYRUP","SYRUPUSDT" in syms,flush=True)
    ds={}
    for k,s in enumerate(syms,1):
        try:
            r=klines(s,"4h")
            if len(r)>=150: ds[s]=features(r)
        except Exception as e: print("FAIL",s,e,flush=True)
        if k%20==0: print("LOADED",k,len(ds),flush=True)
    params=[]
    for rv in (.75,.9,1.05,1.2):
      for di in (.015,.03,.05):
       for hl in (0,.004,.008):
        for co in (.65,.8,1.0):
         for hs in (-.05,.05,.15):
          for bw in (.8,1.0,1.2):
           for tp in (.08,.12,.16):
            params.append(dict(rvol=rv,dist=di,hl=hl,contract=co,obvs=0,hs=hs,trend=-.08,bwch=bw,tp=tp))
    split=1782864000000 # 2026-07-01 UTC
    ranked=[]
    for p in params:
        r=test(ds,p,START_MS,split-1)
        if r["n"]>=35:
            score=r["avg"]*min(r["pf"],4)*math.sqrt(r["n"])
            ranked.append((score,p,{k:v for k,v in r.items() if k!="trades"}))
    ranked.sort(key=lambda x:x[0],reverse=True)
    finals=[]
    for score,p,tr in ranked[:40]:
        va=test(ds,p,split,END_MS); full=test(ds,p,START_MS,END_MS)
        finals.append(dict(params=p,train=tr,validation={k:v for k,v in va.items() if k!="trades"},
                           full={k:v for k,v in full.items() if k!="trades"}))
    finals.sort(key=lambda x:(x["validation"]["avg"]*min(x["validation"]["pf"],4)*math.sqrt(max(1,x["validation"]["n"]))),reverse=True)
    payload={"generated_utc":datetime.now(timezone.utc).isoformat(),"universe":len(syms),"loaded":len(ds),
             "period":["2026-01-01","2026-09-21"],"entry":"next 4h candle open","cost":COST,"top":finals[:20]}
    (OUT/"phase1_4h_motion_search.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(json.dumps(payload["top"][:5],indent=2),flush=True)

if __name__=="__main__": main()

# workflow trigger: 2026-09-21 phase1
