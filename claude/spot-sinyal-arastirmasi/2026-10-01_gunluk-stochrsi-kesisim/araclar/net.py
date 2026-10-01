# -*- coding: utf-8 -*-
"""A3 varyantinin KOMISYON SONRASI islem basi dagilimi (sabit 5/10 gun tutma)."""
import os, sys
import numpy as np
BURASI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BURASI)
from olc import Tablo, DONEM
from kural_kullanici import kurul

KOM = 0.20   # gidis-donus toplam %
T = Tablo()
likit = T.f("quote20") >= 1_000_000
A1 = kurul(T, pencere=1, srsi="max", macd="hist_neg")
A2 = ((np.fmax(T.f("srsi_k"), T.f("srsi_d")) < 15) & (T.f("wr") >= -100)
      & (T.f("wr") <= -75) & (T.f("macd_hist") < 0))
A3 = A2 & (T.f("rsi") <= 40)

print(f"komisyon (gidis+donus): %{KOM}  ·  SABIT tutma suresi, stop/hedef YOK")
print(f"\n{'donem':22s} {'kurulum':26s} {'n':>7s} {'gun':>5s} "
      f"{'net medyan':>11s} {'net ort':>9s} {'kazanan':>8s} {'ay blok t':>10s}")
for don, (b, e) in DONEM.items():
    D = T.donem_maske(b, e) & T.tam & likit
    for ad, m in [("TABAN (tum barlar)", np.ones(len(T.zaman), bool)),
                  ("A1 kullanici TAM kural", A1), ("A3 degerler+RSI<=40", A3)]:
        mm = m & D
        for j, gun in [(0, 5), (1, 10)]:
            r = T.RET[mm, j].astype(float) - KOM
            r = r[~np.isnan(r)]
            if len(r) < 50: continue
            # ay bloklu t (bagimsiz gozlem: ay)
            ay = (T.zaman[mm][~np.isnan(T.RET[mm, j].astype(float))] // 86_400_000 // 30)
            aylar = np.unique(ay)
            ort_ay = np.array([r[ay == a].mean() for a in aylar])
            t = ort_ay.mean()/(ort_ay.std(ddof=1)/np.sqrt(len(ort_ay))) if len(aylar) > 3 else float('nan')
            print(f"{don:22s} {ad:26s} {len(r):7d} {gun:5d} "
                  f"{np.median(r):+10.2f}% {r.mean():+8.2f}% "
                  f"{(r>0).mean()*100:7.1f}% {t:+10.2f}")
    print()
