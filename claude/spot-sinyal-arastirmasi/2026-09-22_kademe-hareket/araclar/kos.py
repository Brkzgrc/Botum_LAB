# -*- coding: utf-8 -*-
import os, sys, pickle, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kademe
G="/tmp/claude-0/-home-user-Botum/3e092c90-6fa5-51e5-9584-2428d75342cd/scratchpad/gecmis"
VESKI=f"{G}/veri"; VD=f"{G}/veri_dogrulama"; V1=f"{G}/veri_1h"; V19=f"{G}/veri_2019"

def yukle(s, era):
    if era=="2019-2020":
        d={i:pickle.load(open(f"{V19}/{s}__{i}.pkl","rb")) for i in ("15m","1h","4h")}
        return (d["15m"][0],d["15m"][1],d["15m"][2],d["15m"][3], d["1h"][0],d["1h"][2], d["4h"][0],d["4h"][2])
    if era=="2021-2022":
        d=pickle.load(open(f"{VESKI}/{s}.pkl","rb"))
        return (d["15m"][0],d["15m"][1],d["15m"][2],d["15m"][3], d["1h"][0],d["1h"][2], d["4h"][0],d["4h"][2])
    v=pickle.load(open(f"{VD}/{s}__{era}.pkl","rb")); h1=pickle.load(open(f"{V1}/{s}__{era}.pkl","rb"))
    return (v["15m"][0],v["15m"][1],v["15m"][2],v["15m"][3], h1[0],h1[2], v["4h"][0],v["4h"][2])

def semboller(era):
    if era=="2019-2020":
        s={f.split("__")[0] for f in os.listdir(V19)}
        return sorted(x for x in s if all(os.path.exists(f"{V19}/{x}__{i}.pkl") for i in ("15m","1h","4h")))
    if era=="2021-2022": return sorted(f[:-4] for f in os.listdir(VESKI) if f.endswith(".pkl"))
    return sorted(f.split("__")[0] for f in os.listdir(VD)
                  if f.endswith(f"__{era}.pkl") and os.path.exists(f"{V1}/{f.split('__')[0]}__{era}.pkl"))

if __name__=="__main__":
    era=sys.argv[1]; lim=int(sys.argv[2]) if len(sys.argv)>2 else 0
    syms=semboller(era)
    if lim: syms=syms[:lim]
    B=[]; t0=time.time(); n=0
    for s in syms:
        n+=1
        try: kademe.coin_olc(*yukle(s,era), B)
        except Exception: pass
        if n%100==0: print(f"  {n}/{len(syms)}  {len(B):,} yukselis  {time.time()-t0:.0f}sn", flush=True)
    print(f"\n{'='*60}\n{era}  ({len(syms)} coin)\n{'='*60}")
    kademe.ozet(B)
    json.dump(B, open(f"sonuc_{era}.json","w"))
