# -*- coding: utf-8 -*-
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profil, kos2
if __name__=="__main__":
    era=sys.argv[1]; lim=int(sys.argv[2]) if len(sys.argv)>2 else 0
    syms=kos2.semboller(era)
    if lim: syms=syms[:lim]
    ISLER=[("15m",3),("15m",4),("1h",3),("4h",3)]
    K={x:[] for x in ISLER}
    t0=time.time()
    for n,s in enumerate(syms,1):
        try:
            a15,a1,a4=kos2.yukle(s,era); dd={"15m":a15,"1h":a1,"4h":a4}
            for itv,N in ISLER: profil.tara(dd[itv],itv,N,K[(itv,N)])
        except Exception: pass
        if n%25==0: print(f"  {n}/{len(syms)}  {time.time()-t0:.0f}sn", flush=True)
    print(f"\n{'='*100}\n{era} ({len(syms)} coin) — SINYAL SONRASI YOL PROFILI · stop YOK · pencere YOK\n{'='*100}")
    for itv,N in ISLER: profil.rapor(itv,N,K[(itv,N)])
