# -*- coding: utf-8 -*-
"""BTC durum tespiti: YATAY / YUKSELIS / DUSUS.

Olcu: verimlilik orani (efficiency ratio)
    |son - ilk| / toplam katedilen yol
  0'a yakin -> testere, hicbir yere varmamis  -> YATAY
  1'e yakin -> duz bir cizgide gitmis         -> TREND (yon = net getirinin isareti)

Esikler BTC'nin KENDI gecmisinden (%33/%67 dilim). Islem sonuclarina BAKMAZ.
Nedensel: her an icin yalnizca o ana kadar KAPANMIS mumlar kullanilir.
"""
import numpy as np, pickle, bisect

PENCERE = {"15m": 8, "1h": 12, "4h": 12, "1d": 7}   # 2sa / 12sa / 2gun / 1hafta

def verimlilik(c):
    yol = np.abs(np.diff(c)).sum()
    return 0.0 if yol == 0 else abs(c[-1]-c[0]) / yol

class BTC:
    def __init__(self, yol="btc.pkl"):
        ham = pickle.load(open(yol,"rb"))
        self.d = {}
        for tf, rows in ham.items():
            a = np.array(rows, dtype=float)
            self.d[tf] = {"c": a[:,3], "h": a[:,1], "l": a[:,2], "kt": a[:,5]}
        self.esik = self._esikler()

    def _seri(self, tf, ms):
        """ms aninda KAPANMIS son mumun indeksi."""
        kt = self.d[tf]["kt"]
        i = bisect.bisect_left(kt, ms) - 1
        return i

    def olc(self, tf, ms):
        n = PENCERE[tf]; i = self._seri(tf, ms)
        if i < n: return None
        c = self.d[tf]["c"][i-n+1:i+1]
        return {"ver": verimlilik(c), "getiri": (c[-1]/c[0]-1)*100}

    def _esikler(self):
        """BTC'nin kendi gecmisindeki verimlilik dagiliminin %33/%67 dilimleri."""
        e = {}
        for tf, n in PENCERE.items():
            c = self.d[tf]["c"]
            v = [verimlilik(c[i-n+1:i+1]) for i in range(n, len(c))]
            e[tf] = (float(np.percentile(v,33)), float(np.percentile(v,67)))
        return e

    def durum(self, tf, ms):
        """Uc durum. Esik BTC'nin kendi %33 dilimi - islem sonuclarina bakmaz."""
        o = self.olc(tf, ms)
        if o is None: return None
        dus, _ = self.esik[tf]
        if o["ver"] <= dus: return "YATAY"
        return "YUKSELIS" if o["getiri"] > 0 else "DUSUS"

    def ozet(self, ms):
        return {tf: self.durum(tf, ms) for tf in PENCERE}
