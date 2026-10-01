# -*- coding: utf-8 -*-
"""
OLCUM MOTORU — kurulum (bool maske) -> sonuc + TABAN karsilastirmasi.

Uc ayri taban kullanilir (hepsi raporlanir):
  T1  tum evren barlari              (ham taban)
  T2  AYNI GUN kesit eslemesi        (piyasa rejimi karistirici DEGIL)
  T3  sadece StochRSI yukari kesisimi (ek sartlarin KATKISI ne)

Anlamlilik GUN bazinda: ayni gunun sinyalleri TEK gozlem sayilir
(CLAUDE.md: bar degil OLAY say).
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
VERI   = os.path.join(os.path.dirname(BURASI), "veri")

DONEM = {
    "kesif_2017_2022":    ("2017-08-01", "2023-01-01"),
    "dogrulama_2023_2024": ("2023-01-01", "2025-01-01"),
    "dogrulama_2025_2026": ("2025-01-01", "2026-10-01"),
}

ART = [2.5, 5, 10, 15, 20, 30, 50]
DUS = [2.5, 5, 10, 15, 20]
TEMIZ = [(5, 5), (10, 5), (20, 10)]      # (hedef%, once gorulmemesi gereken dusus%)


class Tablo:
    def __init__(self, yol=None):
        z = np.load(yol or os.path.join(VERI, "tablo_1g.npz"), allow_pickle=False)
        self.z = z
        self.oz_ad = list(z["ozellik"])
        self.OZ = z["OZ"]; self.zaman = z["zaman"]; self.sym_idx = z["sym_idx"]
        self.kapanis = z["kapanis"]
        self.ILK_ART = z["ILK_ART"]; self.ILK_DUS = z["ILK_DUS"]
        self.MFE = z["MFE"]; self.MAE = z["MAE"]; self.RET = z["RET"]
        self.ILERI = z["ILERI"]; self.GENISLIK = z["GENISLIK"]
        self.semboller = list(z["semboller"])
        self.gun = (self.zaman // 86_400_000).astype(np.int32)
        self.tam = self.ILERI >= 30
        self.yil = np.array([int(np.datetime64(int(t) // 1000, "s").astype("datetime64[Y]")
                                 .astype(int)) + 1970 for t in [0]])  # kullanilmiyor

    def f(self, ad):
        return self.OZ[:, self.oz_ad.index(ad)]

    def donem_maske(self, bas, bit):
        b = int(np.datetime64(bas).astype("datetime64[ms]").astype(np.int64))
        e = int(np.datetime64(bit).astype("datetime64[ms]").astype(np.int64))
        return (self.zaman >= b) & (self.zaman < e)


def ozet(T, maske, ad="", min_n=1):
    """maske: bool dizi. Yalnizca 30 gun ileri verisi TAM olan barlar."""
    m = maske & T.tam
    n = int(m.sum())
    if n < min_n:
        return {"ad": ad, "n": n}
    d = {"ad": ad, "n": n, "gun": int(len(np.unique(T.gun[m]))),
         "sembol": int(len(np.unique(T.sym_idx[m])))}
    for i, e in enumerate(ART):
        d[f"ulasti_{e}"] = float((T.ILK_ART[m, i] > 0).mean())
    for i, e in enumerate(DUS):
        d[f"gordu_{e}"] = float((T.ILK_DUS[m, i] > 0).mean())
    for hx, dy in TEMIZ:
        ia = T.ILK_ART[m, ART.index(hx)]
        id_ = T.ILK_DUS[m, DUS.index(dy)]
        temiz = (ia > 0) & ((id_ == 0) | (ia < id_))
        d[f"temiz_{hx}_{dy}"] = float(temiz.mean())
    for j, U in enumerate([5, 10, 20, 30]):
        d[f"mfe{U}"] = float(np.nanmedian(T.MFE[m, j]))
        d[f"mae{U}"] = float(np.nanmedian(T.MAE[m, j]))
        d[f"ret{U}_med"] = float(np.nanmedian(T.RET[m, j]))
        d[f"ret{U}_ort"] = float(np.nanmean(T.RET[m, j]))
    return d


def gun_bazli_test(T, sinyal, havuz, olcut):
    """AYNI GUN kesit eslemesi + gun bazinda eslestirilmis t testi.

    olcut(m) -> her bar icin skaler dizi (orn. temiz 0/1, ya da MFE30)
    Her gun: sinyal ortalamasi - o gunun havuz ortalamasi. Gunler bagimsiz
    gozlem sayilir.
    """
    s = sinyal & T.tam
    h = havuz & T.tam
    if s.sum() == 0:
        return None
    deg = olcut(T)
    gunler = np.unique(T.gun[s])
    farklar, agirlik = [], []
    for gn in gunler:
        ms = s & (T.gun == gn)
        mh = h & (T.gun == gn)
        if mh.sum() < 10:
            continue
        a = np.nanmean(deg[ms]); b = np.nanmean(deg[mh])
        if np.isnan(a) or np.isnan(b):
            continue
        farklar.append(a - b); agirlik.append(int(ms.sum()))
    if len(farklar) < 5:
        return None
    f = np.array(farklar)
    return {
        "gun_sayisi": len(f),
        "sinyal_bar": int(s.sum()),
        "ort_fark": float(f.mean()),
        "medyan_fark": float(np.median(f)),
        "pozitif_gun_orani": float((f > 0).mean()),
        "t": float(f.mean() / (f.std(ddof=1) / np.sqrt(len(f)))) if f.std(ddof=1) > 0 else 0.0,
    }


def olcut_temiz(hx, dy):
    def _o(T):
        ia = T.ILK_ART[:, ART.index(hx)].astype(float)
        id_ = T.ILK_DUS[:, DUS.index(dy)].astype(float)
        return ((ia > 0) & ((id_ == 0) | (ia < id_))).astype(float)
    return _o


def olcut_mfe(U=30):
    j = [5, 10, 20, 30].index(U)
    return lambda T: T.MFE[:, j].astype(float)


def olcut_ret(U=20):
    j = [5, 10, 20, 30].index(U)
    return lambda T: T.RET[:, j].astype(float)


def ay_bootstrap(T, sinyal, taban_deger, olcut, tur=4000, tohum=12345):
    """Ay bloklu bootstrap: sinyal ortalamasi - sabit taban."""
    m = sinyal & T.tam
    if m.sum() < 20:
        return None
    deg = olcut(T)[m]
    ay = (T.zaman[m] // 86_400_000 // 30).astype(np.int64)
    gec = ~np.isnan(deg)
    deg, ay = deg[gec], ay[gec]
    aylar = np.unique(ay)
    if len(aylar) < 6:
        return None
    rng = np.random.default_rng(tohum)
    grup = [deg[ay == a] for a in aylar]
    orn = np.empty(tur)
    for i in range(tur):
        sec = rng.integers(0, len(grup), len(grup))
        orn[i] = np.concatenate([grup[j] for j in sec]).mean()
    return {
        "ort": float(deg.mean()),
        "taban": float(taban_deger),
        "ga_alt": float(np.percentile(orn, 2.5)),
        "ga_ust": float(np.percentile(orn, 97.5)),
        "tabanin_ustunde_kalma": float((orn > taban_deger).mean()),
        "ay_blok": int(len(aylar)),
    }


def yaz(d, baslik=""):
    if baslik:
        print(f"\n{baslik}")
    if d is None:
        print("  (yetersiz ornek)"); return
    if d.get("n", 1) == 0:
        print(f"  {d.get('ad','')}: n=0"); return
    ad = d.get("ad", "")
    print(f"  {ad:38s} n={d['n']:7d} gun={d.get('gun',0):5d} sembol={d.get('sembol',0):4d}")
    print(f"     temiz +5/-5={d['temiz_5_5']*100:5.1f}%  "
          f"+10/-5={d['temiz_10_5']*100:5.1f}%  +20/-10={d['temiz_20_10']*100:5.1f}%")
    print(f"     ulasti +10={d['ulasti_10']*100:5.1f}%  +20={d['ulasti_20']*100:5.1f}%  "
          f"+50={d['ulasti_50']*100:5.1f}%   gordu -10={d['gordu_10']*100:5.1f}%  "
          f"-20={d['gordu_20']*100:5.1f}%")
    print(f"     medyan MFE30={d['mfe30']:6.1f}%  MAE30={d['mae30']:6.1f}%  "
          f"RET10med={d['ret10_med']:6.2f}%  RET20med={d['ret20_med']:6.2f}%  "
          f"RET30ort={d['ret30_ort']:6.2f}%")
