# -*- coding: utf-8 -*-
"""SIKISMA TESPITI

Tanim (kullanicinin tarifi):
  Fiyat belirli bir aralikta sikisir. Aralik ne kadar dar ve bu ne kadar UZUN
  surerse, tepki o kadar buyuk beklenir. Tepkinin YONU belirsizdir.
  Ust TF'de gorulmezse alt TF'e bakilir; TF kuculdukce cikis hizlanmali.

Iki olcu:
  darlik    = (son n mumun en yuksegi - en dusugu) / fiyat
              kendi gecmisinin yuzdelik dilimi olarak (olceksiz, esiksiz)
  sure      = darlik kac BAR'dir kendi %33 diliminin altinda kalmis

Nedensel: her an icin yalnizca o ana kadar KAPANMIS mumlar.
"""
import numpy as np, pickle, bisect

# her TF icin "aralik" penceresi: kullanicinin tarifine gore
#   gunluk 4-5 gun -> 5 bar;  4h icin ~ayni takvim suresi -> 30 bar;  vs.
PENCERE = {"15m": 20, "1h": 24, "4h": 30, "1d": 5}

def _darlik_serisi(h, l, c, n):
    d = np.full(len(c), np.nan)
    for i in range(n-1, len(c)):
        hh = h[i-n+1:i+1].max(); ll = l[i-n+1:i+1].min()
        d[i] = (hh-ll)/c[i]*100 if c[i] else np.nan
    return d

class Sikisma:
    def __init__(self, ham):
        """ham: {tf: [[o,h,l,c,v,kapanis_ms], ...]}"""
        self.d = {}
        for tf, rows in ham.items():
            if tf not in PENCERE: continue
            a = np.array(rows, dtype=float)
            h,l,c,kt = a[:,1],a[:,2],a[:,3],a[:,5]
            n = PENCERE[tf]
            dar = _darlik_serisi(h,l,c,n)
            v = a[:,4]
            # hacim: son n barin ortalamasi / onceki 4n barin ortalamasi (olceksiz)
            hac = np.full(len(c), np.nan)
            for i in range(5*n, len(c)):
                yak = v[i-n+1:i+1].mean(); uzak = v[i-5*n+1:i-n+1].mean()
                hac[i] = yak/uzak if uzak > 0 else np.nan
            gecerli = dar[~np.isnan(dar)]
            if len(gecerli) < 50: continue
            esik = float(np.percentile(gecerli, 33))      # kendi gecmisi, sonuca bakmaz
            # sure: kac bardir esigin altinda
            sure = np.zeros(len(dar))
            for i in range(len(dar)):
                if np.isnan(dar[i]) or dar[i] > esik: sure[i] = 0
                else: sure[i] = (sure[i-1] if i else 0) + 1
            # yuzdelik: darligin kendi gecmisindeki yeri
            sirali = np.sort(gecerli)
            yuzde = np.full(len(dar), np.nan)
            ok = ~np.isnan(dar)
            yuzde[ok] = np.searchsorted(sirali, dar[ok]) / len(sirali) * 100
            self.d[tf] = {"kt":kt,"dar":dar,"sure":sure,"yuzde":yuzde,"esik":esik,"c":c,"hac":hac}

    def _i(self, tf, ms):
        return bisect.bisect_left(self.d[tf]["kt"], ms) - 1

    def olc(self, tf, ms):
        if tf not in self.d: return None
        i = self._i(tf, ms)
        if i < PENCERE[tf]: return None
        x = self.d[tf]
        if np.isnan(x["yuzde"][i]): return None
        return {"darlik_yuzde": float(x["yuzde"][i]),   # 0=en dar, 100=en genis
                "sikisma_bar":  int(x["sure"][i]),
                "aralik_pct":   float(x["dar"][i]),
                "hacim_orani":  float(x["hac"][i]) if not np.isnan(x["hac"][i]) else None}

    def durum(self, tf, ms):
        """SIKISIK / NORMAL / GENIS + sikisma suresi."""
        o = self.olc(tf, ms)
        if o is None: return None
        if o["darlik_yuzde"] <= 33: d = "SIKISIK"
        elif o["darlik_yuzde"] >= 67: d = "GENIS"
        else: d = "NORMAL"
        return d, o["sikisma_bar"], o["aralik_pct"]

    def en_ust_sikisik_tf(self, ms, sira=("1d","4h","1h","15m")):
        """Kullanicinin kurali: once ust TF'e bak, yoksa alt TF'e in."""
        for tf in sira:
            r = self.durum(tf, ms)
            if r and r[0] == "SIKISIK":
                return tf, r[1], r[2]
        return None, 0, None
