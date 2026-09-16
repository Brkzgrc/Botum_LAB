# -*- coding: utf-8 -*-
"""ORTUSME v2 — canli evren filtresi + her tarama aninda en iyi 96 + gunde 3 sinir."""
import os, pickle, sys, time, json
import numpy as np
KOK=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,KOK)
import ortusme as O          # olcum(), gunluk(), at()
VD=os.path.join(KOK,"veri_dogrulama"); V1=os.path.join(KOK,"veri_1h")
ET=sys.argv[1] if len(sys.argv)>1 else "2025-2026"
MIN_Q=72.0; CORE_N=72; TOP_N=96; GUNLUK_MAX=3

IGN={'USDT','USDC','BUSD','TUSD','DAI','PAX','HUSD','USDP','GUSD','FDUSD','EUR','TRY','GBP','USD',
     'BRL','RUB','AUD','XUSD','USD1','USDE','BFUSD','USDS','USDD','PYUSD','AEUR','EURI','USTC','FRAX',
     'LUSD','SUSD','USDX','CUSD','OUSD','MUSD','RLUSD','BIDR','IDRT','VAI','PAXG','XAUT','WBTC','WETH',
     'WBNB','BETH','BTCB','HBTC','U'}
LEV=('UP','DOWN','BULL','BEAR','2L','2S','3L','3S','5L','5S','10L','10S')
OKB={'BNB','DGB','TRB','CKB','SHIB','ARB','BB','YB'}
def canli_evrende(sym):
    b=sym[:-4]
    return not (b in IGN or (b.endswith(LEV) and b not in OKB))

def on_eleme_seri(m1):
    """canli _prefilter() puani + seed, 1h izgarada seri olarak"""
    p=m1["p"]; e20=m1["e20"]; e50=m1["e50"]; r=m1["rsi"]; k=m1["k"]; d=m1["d"]
    k0=m1["kprev"]; kmin3=m1["kmin3"]; mh=m1["hist"]; mh0=m1["histprev"]
    obv=m1["obv"]>=m1["obv3"]; near=m1["nh20"]; ret3=m1["ret3"]
    hc=m1["hc6"]; hl=m1["hl6"]; de20=m1["de20"]
    ret6=np.concatenate([np.full(6,np.nan),(p[6:]/p[:-6]-1)*100])
    reset=(k<=75)|(kmin3<=30); turn=(k>d)&(k>k0)
    s=(np.where(p>=e50,18,0)+np.where(p>=e20,12,5)
       +np.where((r>=45)&(r<=88),12,np.where((r>=38)&(r<=92),5,0))
       +np.where(reset,13,np.where(turn,8,0))
       +np.where(mh>mh0,10,np.where(mh>0,5,0))
       +np.where(obv,10,0)+7      # vol_ratio>=.8 varsayimi -> 7 (hacim var)
       +np.where(near<=7,7,np.where(near<=12,3,0))
       +5                          # taker>=.50 notr
       +np.where(np.nan_to_num(ret6)>3,4,0)).astype(float)
    s-=np.where((ret3>14)&(k>85)&(de20>15),18,0)
    seed=((p>=e50)&(r>=38)&(r<=90)&(reset|turn)&(ret3>=-7)&(ret3<=10)) | \
         ((p>=e20)&(r>=45)&(r<=88)&(hc>=3)&(hl>=3)&(near<=6)&(ret3>=-1)&(ret3<=9))
    return np.nan_to_num(s,nan=-999.0), np.nan_to_num(seed.astype(float))

def coin_yukle(sym):
    vv=pickle.load(open(os.path.join(VD,f"{sym}__{ET}.pkl"),"rb"))
    h1=pickle.load(open(os.path.join(V1,f"{sym}__{ET}.pkl"),"rb"))
    t15,h15,l15,c15,v15=vv["15m"]; t4,h4,l4,c4,v4=vv["4h"]
    if len(t15)<400 or len(t4)<300: return None
    t1,h1a,l1a,c1a=h1[:4]; v1a=h1[4] if len(h1)>4 else np.ones(len(t1))
    if len(t1)<300: return None
    td,hd,ld,cd,vd=O.gunluk(t4,h4,l4,c4,v4)
    if len(td)<220: return None
    return {"m15":O.olcum(t15,h15,l15,c15,v15),"m4":O.olcum(t4,h4,l4,c4,v4),
            "m1":O.olcum(t1,h1a,l1a,c1a,v1a),"md":O.olcum(td,hd,ld,cd,vd)}

def tetik(C,i,j1,j4,jd):
    F=O.at(C["m15"],i); Q=O.at(C["m4"],j4); D=O.at(C["md"],jd); Ox=O.at(C["m1"],j1)
    if np.isnan(Q["k"]) or np.isnan(Ox["k"]) or np.isnan(D["rsi"]): return 0.0,False
    day=D["p"]>=D["e20"] and D["e20s"]>=-.8 and D["rsi"]>=50
    four=Q["p"]>=Q["e50"] and Q["e50s"]>=-.2 and Q["rsi"]>=45
    if not(day and four): return 0.0,False
    st=Ox["p"]>=Ox["e50"] and Ox["rsi"]>=38
    reset=Ox["k"]<=75 or Ox["kmin3"]<=30
    turn=Ox["k"]>Ox["d"] and Ox["k"]>Ox["kprev"]
    mom=Ox["hist"]>Ox["histprev"] or Ox["obv"]>=Ox["obv3"] or turn
    a=int(Q["de50"]>=6.0)+int(Q["e20s"]>=1.0)+int(Ox["de50"]>=2.0)+int(Ox["upw"]>=0.22)+int(Ox["k"]<=75.0)+int(D["rsi"]>=62.0)
    bal=st and a>=5
    strict=Q["de50"]>=6.0 and Ox["de50"]>=2.0 and Ox["upw"]>=0.22 and Ox["k"]<=75.0
    ft=F["k"]>F["d"] and F["k"]>F["kprev"] and F["rsi"]>=40
    fc=ft and (F["hist"]>F["histprev"] or F["obv"]>=F["obv3"]) and F["p"]>=F["e20"]*.995
    press=a>=4 and Ox["p"]>=Ox["e20"] and Ox["e20s"]>0 and Ox["rsi"]>=50 and Ox["hc6"]>=3 and Ox["hl6"]>=3 and Ox["nh20"]<=4.5
    fb=F["p"]>=F["ph6"]*.998 and F["rsi"]>=48 and (F["hist"]>F["histprev"] or F["obv"]>=F["obv3"])
    retr=bal and reset
    sb=(D["p"]<D["e50"] and Q["p"]<Q["e50"]) or (Q["p"]<Q["e50"] and Ox["p"]<Ox["e50"] and Q["e50s"]<0)
    bo=Ox["ret3"]>14 and Ox["k"]>85 and Ox["de20"]>15
    if sb or bo: return 0.0,False
    q =32+a*8+(8 if turn else 0)+(7 if mom else 0)+(8 if fc else 0)+(8 if strict else 0)
    pq=24+a*8+(20 if press else 0)+(16 if fb else 0)
    qual=max(0,min(100,max(q if retr else 0, pq if press else 0)))
    return qual,((retr and mom and fc) or (press and fb))

def main():
    syms=[f.split("__")[0] for f in os.listdir(VD) if f.endswith(f"__{ET}.pkl")]
    syms=[s for s in syms if os.path.exists(os.path.join(V1,f"{s}__{ET}.pkl")) and canli_evrende(s)]
    syms.sort()
    print(f"{ET} — canli evren filtresinden gecen: {len(syms)} coin",flush=True)
    C={}; t0=time.time()
    for n,s in enumerate(syms,1):
        try:
            c=coin_yukle(s)
            if c: C[s]=c
        except Exception: pass
        if n%100==0: print(f"  yukleme {n}/{len(syms)} {time.time()-t0:.0f}sn",flush=True)
    syms=[s for s in syms if s in C]
    print(f"  verisi tam: {len(syms)}",flush=True)
    # ortak 1h izgarasi
    t1_all=np.unique(np.concatenate([C[s]["m1"]["t"] for s in syms]))
    SK=np.full((len(syms),len(t1_all)),-999.0); SD=np.zeros((len(syms),len(t1_all)))
    for a,s in enumerate(syms):
        sc,sd=on_eleme_seri(C[s]["m1"])
        idx=np.searchsorted(t1_all,C[s]["m1"]["t"])
        SK[a,idx]=sc; SD[a,idx]=sd
    print(f"  on eleme matrisi: {SK.shape}",flush=True)
    # her saat icin en iyi 96
    secim={}
    for h in range(len(t1_all)):
        col=SK[:,h]
        if (col>-999).sum()<10: continue
        order=np.argsort(-col)
        sel=[a for a in order[:CORE_N] if col[a]>-999]
        ss=set(sel)
        for a in order[CORE_N:]:
            if len(sel)>=TOP_N: break
            if col[a]>-999 and SD[a,h] and a not in ss: sel.append(a); ss.add(a)
        for a in order[CORE_N:]:
            if len(sel)>=TOP_N: break
            if col[a]>-999 and a not in ss: sel.append(a); ss.add(a)
        secim[h]=sel
    print(f"  {len(secim)} tarama saati",flush=True)
    # 15dk izgarada tara
    t15_all=np.unique(np.concatenate([C[s]["m15"]["t"] for s in syms]))
    olay=[]
    for ti,ts in enumerate(t15_all):
        h=np.searchsorted(t1_all,ts,side="right")-1
        sel=secim.get(h)
        if not sel: continue
        for a in sel:
            s=syms[a]; c=C[s]
            i=np.searchsorted(c["m15"]["t"],ts,side="right")-1
            if i<400 or c["m15"]["t"][i]!=ts: continue
            j1=np.searchsorted(c["m1"]["t"],ts,side="right")-1
            j4=np.searchsorted(c["m4"]["t"],ts,side="right")-1
            jd=np.searchsorted(c["md"]["t"],ts,side="right")-1
            if j1<60 or j4<60 or jd<220: continue
            q,ok=tetik(c,i,j1,j4,jd)
            if ok and q>=MIN_Q: olay.append((int(ts),s,q))
        if ti%5000==0: print(f"  tarama {ti}/{len(t15_all)}  {len(olay)} aday  {time.time()-t0:.0f}sn",flush=True)
    olay.sort()
    # gunde 3 + ayni coinde 24 saat tekrar yok
    canli={}; gun=None; sayac=0; son={}
    for ts,s,q in olay:
        g=(ts+3*3600_000)//86400000
        if g!=gun: gun=g; sayac=0
        if sayac>=GUNLUK_MAX: continue
        if ts-son.get(s,-10**15)<24*3600_000: continue
        canli.setdefault(s,[]).append(ts); son[s]=ts; sayac+=1
    nc=sum(len(v) for v in canli.values())
    print(f"\nCANLI sinyal (evren+top96+gunde3): {nc}  ({len(canli)} coin)",flush=True)
    json.dump(canli,open(os.path.join(KOK,f"canli2_{ET}.json"),"w"))

if __name__=="__main__": main()
