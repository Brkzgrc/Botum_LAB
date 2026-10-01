# -*- coding: utf-8 -*-
"""KISA UFUK — kullanici "cogu an yukselis yasiyor" derken kisa siciramayi
kastetmis olabilir. 1-3-5-10 gunluk ufukta ADALET kontrolu."""
import os, sys, json
import numpy as np
BURASI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BURASI)
from olc import Tablo, DONEM, ART, DUS
from kesif import Hizli
from kural_kullanici import kurul

T = Tablo(); H = Hizli(T)
likit = T.f("quote20") >= 1_000_000
A1 = kurul(T, pencere=1, srsi="max", macd="hist_neg")
A2 = ((np.fmax(T.f("srsi_k"), T.f("srsi_d")) < 15) & (T.f("wr") >= -100)
      & (T.f("wr") <= -75) & (T.f("macd_hist") < 0))
A3 = A2 & (T.f("rsi") <= 40)
j25, j5, j10 = ART.index(2.5), ART.index(5), ART.index(10)

def olc(m, ad, D):
    mm = m & D
    n = int(mm.sum())
    if n < 50: print(f"  {ad:34s} n={n} (yetersiz)"); return
    r = {}
    for etiket, j, gun in [("+2.5% / 3g", j25, 3), ("+2.5% / 5g", j25, 5),
                           ("+5% / 5g", j5, 5), ("+5% / 10g", j5, 10),
                           ("+10% / 10g", j10, 10)]:
        a = T.ILK_ART[mm, j]
        r[etiket] = float(((a > 0) & (a <= gun)).mean()) * 100
    # 1-5-10 gunluk medyan getiri (RET dizisi 5/10/20/30)
    m5 = float(np.nanmedian(T.RET[mm, 0])); m10 = float(np.nanmedian(T.RET[mm, 1]))
    print(f"  {ad:34s} {n:7d} " + " ".join(f"{r[k]:9.1f}%" for k in r)
          + f" {m5:+8.2f}% {m10:+8.2f}%")

print(f"{'':36s} {'n':>7s} {'+2.5/3g':>10s} {'+2.5/5g':>10s} {'+5/5g':>10s} "
      f"{'+5/10g':>10s} {'+10/10g':>10s} {'RET5med':>9s} {'RET10med':>9s}")
for don, (b, e) in DONEM.items():
    for et, suz in [("TUM", np.ones(len(T.zaman), bool)), ("LIKIT", likit)]:
        D = T.donem_maske(b, e) & T.tam & suz
        print(f"\n--- {don}  [{et}] ---")
        olc(np.ones(len(T.zaman), bool), "TABAN (tum barlar)", D)
        olc(A1, "A1 kullanici TAM kural", D)
        olc(A2, "A2 degerler (kesisim/RSI yok)", D)
        olc(A3, "A3 A2 + RSI<=40", D)
        for olcut, ad in [(T.ILK_ART[:, j25].astype(float), "")]:
            pass
        # ayni-gun kontrol: +5% / 5 gun
        deg = (((T.ILK_ART[:, j5] > 0) & (T.ILK_ART[:, j5] <= 5)).astype(float)) * 100
        for m, ad in [(A1, "A1"), (A2, "A2"), (A3, "A3")]:
            r = H.test(m & D, D, deg)
            if r: print(f"      aynigun kontrol (+5%/5g) {ad}: ort fark "
                        f"{r['ort_fark']:+6.2f} puan, t={r['t']:+5.2f}, gun={r['gun']}")
