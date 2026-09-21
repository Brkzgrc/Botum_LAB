import json, math, time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from pathlib import Path

START_MS=1767225600000
END_MS=1790035199000
SPLIT_MS=1782864000000
COST=0.002
EXCLUDE={"USDT","USDC","TUSD","USDP","FDUSD","BUSD","DAI","EURI","EUR","TRY","GBP","BRL","AUD","BIDR","AEUR","USD1","USDE","USDS","USTC","FRAX","RLUSD","BFUSD","XUSD"}
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"; OUT.mkdir(exist_ok=True)

def get(path,params=None,retries=6):
    url="https://data-api.binance.vision"+path
    if params:url+="?"+urlencode(params)
    for n in range(retries):
        try:
            with urlopen(Request(url,headers={"User-Agent":"Botum-LAB-research"}),timeout=30) as r:return json.loads(r.read())
        except Exception:
            if n==retries-1:raise
            time.sleep(2**n)

def universe():
    x=get("/api/v3/exchangeInfo"); z=[]
    for s in x["symbols"]:
        b=s["baseAsset"]
        if s["quoteAsset"]!="USDT" or s["status"]!="TRADING" or not s.get("isSpotTradingAllowed",False):continue
        if b in EXCLUDE:continue
        if s["symbol"].endswith(("UPUSDT","DOWNUSDT","BULLUSDT","BEARUSDT")):continue
        z.append(s["symbol"])
    return sorted(set(z))

def klines(sym,intv):
    rows=[]; cur=START_MS
    while cur<=END_MS:
        x=get("/api/v3/klines",{"symbol":sym,"interval":intv,"startTime":cur,"endTime":END_MS,"limit":1000})
        if not x:break
        rows+=x; nxt=x[-1][0]+1
        if nxt<=cur:break
        cur=nxt; time.sleep(.02)
    return rows

def ema(a,n):
    if not a:return []
    k=2/(n+1); v=a[0]; out=[]
    for x in a:v=x*k+v*(1-k);out.append(v)
    return out
def mean(a):return sum(a)/len(a) if a else 0
def sd(a):
    m=mean(a);return math.sqrt(mean([(x-m)**2 for x in a])) if a else 0

def prep(rows):
    o=[float(x[1]) for x in rows];h=[float(x[2]) for x in rows];l=[float(x[3]) for x in rows];c=[float(x[4]) for x in rows]
    v=[float(x[5]) for x in rows];q=[float(x[7]) for x in rows]
    e20=ema(c,20);e50=ema(c,50);e12=ema(c,12);e26=ema(c,26)
    mac=[a-b for a,b in zip(e12,e26)];sig=ema(mac,9);hist=[a-b for a,b in zip(mac,sig)]
    tr=[h[0]-l[0]]
    for i in range(1,len(c)):tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
    atr=ema(tr,14);obv=[0.]
    for i in range(1,len(c)):obv.append(obv[-1]+(v[i] if c[i]>c[i-1] else -v[i] if c[i]<c[i-1] else 0))
    fs=[]
    for i in range(80,len(c)-80):
        # Motion is measured as a sequence, not as a dip/oversold state.
        lows=[min(l[i-23:i-15]),min(l[i-15:i-7]),min(l[i-7:i+1])]
        hl1=lows[1]/lows[0]-1;hl2=lows[2]/lows[1]-1
        hi=max(h[i-24:i])
        d0=(hi-c[i-8])/c[i-8];d1=(hi-c[i-4])/c[i-4];d2=(hi-c[i])/c[i]
        approach=(d0-d2)
        # pullback decay: recent downside excursion versus prior excursion
        pb_old=(max(h[i-16:i-8])-min(l[i-16:i-8]))/c[i]
        pb_new=(max(h[i-8:i])-min(l[i-8:i]))/c[i]
        pb_decay=pb_new/(pb_old or 1)
        # resistance pressure: touches near rolling resistance in last 12h
        tol=.012
        touches=sum(1 for x in h[i-11:i+1] if (hi-x)/hi<=tol)
        # flow/momentum evolution normalized cross-coin
        obv1=(obv[i-4]-obv[i-8])/(abs(obv[i-8])+1)
        obv2=(obv[i]-obv[i-4])/(abs(obv[i-4])+1)
        obv_acc=obv2-obv1
        mh1=(hist[i-4]-hist[i-8])/(atr[i]+1e-12);mh2=(hist[i]-hist[i-4])/(atr[i]+1e-12)
        mac_acc=mh2-mh1
        rv_old=mean(q[i-15:i-7])/(mean(q[i-31:i-15]) or 1)
        rv_new=mean(q[i-7:i+1])/(mean(q[i-23:i-7]) or 1)
        rv_traj=rv_new-rv_old
        bw_old=4*sd(c[i-39:i-19])/(mean(c[i-39:i-19]) or 1)
        bw_new=4*sd(c[i-19:i+1])/(mean(c[i-19:i+1]) or 1)
        compression=bw_new/(bw_old or 1)
        fs.append(dict(i=i,t=rows[i][0],hl1=hl1,hl2=hl2,approach=approach,dist=(hi-c[i])/c[i],
          pb=pb_decay,touches=touches,obva=obv_acc,maca=mac_acc,rvt=rv_traj,comp=compression,
          es=e20[i]/e20[i-8]-1,trend=c[i]/e50[i]-1,atr=atr[i]))
    return dict(rows=rows,o=o,h=h,l=l,c=c,f=fs)

def watch(f,p):
    # Deliberately no RSI/Stoch oversold requirement: this is continuation/pressure detection.
    score=0
    score+=f["hl2"]>=p["hl"]
    score+=f["approach"]>=p["approach"] and f["dist"]<=p["dist"]
    score+=f["pb"]<=p["pb"]
    score+=f["touches"]>=p["touches"]
    score+=f["obva"]>0
    score+=f["maca"]>=p["maca"]
    score+=f["rvt"]>=p["rvt"]
    score+=f["comp"]<=p["comp"]
    return score>=p["need"] and f["es"]>0 and f["trend"]>-0.06

def evaluate(ds,p,start,end):
    tr=[]
    for sym,d in ds.items():
        last=-999
        for f in d["f"]:
            if f["t"]<start or f["t"]>end or f["i"]-last<12 or not watch(f,p):continue
            ei=f["i"]+1; entry=d["o"][ei]
            # WATCH quality labels: forward MFE/MAE and +10/+15/+20; not pretending WATCH itself is final entry.
            endi=min(ei+73,len(d["c"]))
            hh=max(d["h"][ei:endi]);ll=min(d["l"][ei:endi])
            mfe=hh/entry-1;mae=ll/entry-1
            tr.append((sym,f["t"],mfe,mae));last=f["i"]
    n=len(tr)
    if not n:return dict(n=0)
    return dict(n=n,unique=len(set(x[0] for x in tr)),per_day=n/((end-start)/86400000+1),
      mfe_avg=mean([x[2] for x in tr]),mfe_med=sorted(x[2] for x in tr)[n//2],mae_avg=mean([x[3] for x in tr]),
      hit10=mean([x[2]>=.10 for x in tr]),hit15=mean([x[2]>=.15 for x in tr]),hit20=mean([x[2]>=.20 for x in tr]),
      false5=mean([x[2]<.05 for x in tr]),trades=tr)

def main():
    syms=universe();print("UNIVERSE",len(syms),flush=True)
    ds={}
    for k,s in enumerate(syms,1):
        try:
            r=klines(s,"1h")
            if len(r)>=300:ds[s]=prep(r)
        except Exception as e:print("FAIL",s,e,flush=True)
        if k%20==0:print("LOADED",k,len(ds),flush=True)
    grid=[]
    for hl in (0,.002,.005):
      for ap in (.005,.015,.03):
       for dist in (.015,.03,.05):
        for pb in (.7,.9,1.1):
         for touches in (2,3):
          for maca in (-.03,0,.03):
           for rvt in (-.1,0,.1):
            for comp in (.8,1.0,1.2):
             for need in (5,6,7):
              grid.append(dict(hl=hl,approach=ap,dist=dist,pb=pb,touches=touches,maca=maca,rvt=rvt,comp=comp,need=need))
    ranked=[]
    for p in grid:
        r=evaluate(ds,p,START_MS,SPLIT_MS-1)
        if r.get("n",0)>=50:
            score=(r["hit10"]*2+r["hit15"]*2+r["hit20"]-r["false5"])*math.sqrt(r["n"])
            ranked.append((score,p,{k:v for k,v in r.items() if k!="trades"}))
    ranked.sort(reverse=True,key=lambda x:x[0])
    finals=[]
    for score,p,trn in ranked[:60]:
        va=evaluate(ds,p,SPLIT_MS,END_MS);full=evaluate(ds,p,START_MS,END_MS)
        finals.append(dict(params=p,train=trn,validation={k:v for k,v in va.items() if k!="trades"},
          full={k:v for k,v in full.items() if k!="trades"}))
    finals.sort(key=lambda x:(x["validation"].get("hit10",0)*2+x["validation"].get("hit15",0)*2+x["validation"].get("hit20",0)-x["validation"].get("false5",1))*math.sqrt(max(1,x["validation"].get("n",0))),reverse=True)
    payload={"generated_utc":datetime.now(timezone.utc).isoformat(),"phase":"2 - 1H motion WATCH discovery",
      "period":["2026-01-01","2026-09-21"],"split":"2026-07-01","universe":len(syms),"loaded":len(ds),
      "note":"WATCH quality research only; forward highs/lows are labels, not entries. No dip/oversold requirement.",
      "top":finals[:25]}
    (OUT/"phase2_1h_motion_watch.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(json.dumps(payload["top"][:5],indent=2),flush=True)

if __name__=="__main__":main()
