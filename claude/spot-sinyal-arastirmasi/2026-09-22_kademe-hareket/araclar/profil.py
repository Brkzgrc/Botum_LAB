# -*- coding: utf-8 -*-
"""SINYAL SONRASI YOL PROFILI — stop YOK, sabit pencere YOK.

Amac: varsayim koymadan "sinyalden sonra ne oluyor" sorusunu olcmek.
  1) k bar sonra: o ana kadarki EN YUKSEK ve EN DUSUK (yuzde)
  2) once dusup SONRA yukselenler: kac tanesi? (stoplu olcum bunlari kaybediyor)
  3) asil yukselis kac bar sonra basliyor? -> bekleme suresi BURADAN cikar
"""
import numpy as np
import donus

# k degerleri bar cinsinden; 15m icin 96 bar = 1 gun, 2688 = 28 gun
KLER = {
 "15m": [4, 8, 16, 32, 96, 192, 384, 672, 1344, 2688],
 "1h" : [1, 2,  4,  8, 24,  48,  96, 168,  336,  672],
 "4h" : [1, 1,  1,  2,  6,  12,  24,  42,   84,  168],
}
ETIKET = ["1sa","2sa","4sa","8sa","1g","2g","4g","1hf","2hf","4hf"]
SOGUMA = {"4h":6, "1h":24, "15m":96}   # 24 saat

def tara(d, itv, N, kutu):
    t,h,l,c,v = d
    if len(t) < 400: return
    _, say, _ = donus.sartlar(h,l,c,v)
    kl = KLER[itv]; mx = kl[-1]; sg = SOGUMA[itv]
    n = len(t); sonr = -10**9
    for i in range(60, n-1):
        if say[i] < N or i-sonr < sg: continue
        sonr = i
        g = c[i]
        sh = h[i+1:i+1+mx]; sl = l[i+1:i+1+mx]
        if len(sh) < 8: continue
        rmax = np.maximum.accumulate(sh)/g - 1.0
        rmin = np.minimum.accumulate(sl)/g - 1.0
        up = [float(rmax[min(k,len(rmax))-1]) for k in kl]
        dn = [float(rmin[min(k,len(rmin))-1]) for k in kl]
        # ilk -%5'i gorme ani ve ONDAN SONRAKI en yuksek
        d5 = np.where(rmin <= -0.05)[0]
        if len(d5):
            j = int(d5[0])
            sonra = float(rmax[-1]) if j+1 >= len(rmax) else float(np.max(sh[j+1:])/g - 1.0)
        else:
            j = -1; sonra = float('nan')
        # +%5'i ilk gorme ani (kac bar sonra hareket basliyor)
        u5 = np.where(rmax >= 0.05)[0]
        kutu.append((up, dn, j, sonra, int(u5[0])+1 if len(u5) else -1, len(sh)))

def rapor(itv, N, kutu):
    if not kutu: print(f"{itv} >={N}: sinyal yok"); return
    UP = np.array([x[0] for x in kutu]); DN = np.array([x[1] for x in kutu])
    print(f"\n--- {itv}  >= {N} sart   ({len(kutu):,} sinyal) ---")
    print(f"  {'':<10}" + "".join(f"{e:>9}" for e in ETIKET))
    for ad, A, fn in (("medyan EN YUKSEK", UP, np.median), ("medyan EN DUSUK", DN, np.median)):
        print(f"  {ad:<18}" + "".join(f"{100*fn(A[:,k]):>8.1f}%" for k in range(len(ETIKET))))
    for esik in (0.10, 0.20, 0.30):
        o = [100*np.mean(UP[:,k] >= esik) for k in range(len(ETIKET))]
        print(f"  +%{int(esik*100)}'a ulasan   " + "".join(f"{x:>8.1f}%" for x in o))
    dustu = np.array([x[2] for x in kutu]) >= 0
    sonra = np.array([x[3] for x in kutu])
    print(f"\n  once -%5 gorenler: {dustu.sum():,} / {len(kutu):,}  (%{100*dustu.mean():.0f})")
    if dustu.sum():
        s = sonra[dustu]; s = s[~np.isnan(s)]
        for esik in (0.10, 0.20, 0.30):
            print(f"    bunlarin %{100*np.mean(s>=esik):.1f}'i -%5'ten SONRA +%{int(esik*100)}'a ulasti")
    bas = np.array([x[4] for x in kutu]); bas = bas[bas > 0]
    if len(bas):
        q = np.percentile(bas, [25,50,75,90])
        print(f"  +%5'e ilk ulasma (bar): medyan {q[1]:.0f} · %25 {q[0]:.0f} · %75 {q[2]:.0f} · %90 {q[3]:.0f}"
              f"   (hic ulasmayan %{100*(1-len(bas)/len(kutu)):.0f})")
