# -*- coding: utf-8 -*-
"""YUKSELIS IMZASI — cikis/stop YOK. Soru: yukselislerin ortak paydasi ne,
ve hangi asamada okunabiliyor?

Aday  = her yerel dip (sonucu ne olursa olsun, SECIM YOK)
Asama = dipten +%0 / +2 / +5 / +8 / +12 / +20 seviyesine ILK ulasilan bar
Hedef = o asamadan itibaren +%10/20/30/40/50'ye ULASTI MI (tek yonlu, stop yok)

Cikti = OLASILIK. "asama +%5'te olcum X ust dilimdeyse, %A'si +%30'a gitmis;
        taban oran %B" — parametre degil, olasilik.
"""
import numpy as np

ASAMA  = (0.0, 2.0, 5.0, 8.0, 12.0, 20.0)     # dipten yuzde kac yukselmisken
HEDEF  = (10.0, 20.0, 30.0, 40.0, 50.0)       # asamadan itibaren hedef
DESIL  = 10
UFUK   = 336                                   # 14 gun (1h bar)

def adaylar(h, l, c, pencere=12):
    """Her yerel dip bir adaydir. Hicbir secim/filtre yok."""
    n = len(c); out = []
    for i in range(pencere+30, n-10):
        if l[i] <= np.min(l[i-pencere:i+1]): out.append(i)
    return out

def asama_barlari(h, c, i0, ufuk=UFUK):
    """Dipten her asamaya ILK ulasilan bar. Ulasilmayan asama None."""
    g = c[i0]; son = min(len(c), i0+ufuk)
    out = {}
    for a in ASAMA:
        if a == 0.0: out[a] = i0; continue
        hedef = g*(1+a/100); bul = None
        for j in range(i0+1, son):
            if h[j] >= hedef: bul = j; break
        out[a] = bul
    return out

def hedefe_ulasti(h, l, c, j, ufuk=UFUK):
    """j barindan itibaren her hedefe ulasti mi + oraya kadarki en kotu geri cekilme."""
    g = c[j]; son = min(len(c), j+ufuk)
    if son <= j+1 or g <= 0: return None
    yuksek = h[j+1:son]; dusuk = l[j+1:son]
    kum_dip = np.minimum.accumulate(dusuk)
    out = {}
    for hd in HEDEF:
        seviye = g*(1+hd/100)
        idx = np.where(yuksek >= seviye)[0]
        if len(idx):
            k = int(idx[0])
            out[hd] = (1, float((kum_dip[k]/g - 1)*100), k+1)   # ulasti, MAE, kac bar
        else:
            out[hd] = (0, float((kum_dip[-1]/g - 1)*100), None)
    return out

# --------------------------------------------------------------- birikim
def bos_birikim(olcum_adlari):
    return {"olcumler": list(olcum_adlari),
            # [asama][olcum][desil][hedef] -> (ulasan, toplam)
            "say": np.zeros((len(ASAMA), len(olcum_adlari), DESIL, len(HEDEF), 2), dtype=np.int64),
            # [asama][hedef] -> (ulasan, toplam)   TABAN
            "taban": np.zeros((len(ASAMA), len(HEDEF), 2), dtype=np.int64),
            # asamaya ULASAN aday sayisi (dipten girmek vs sonra girmek icin)
            "asama_ulasan": np.zeros(len(ASAMA), dtype=np.int64),
            "aday": 0}

def coin_isle(h, l, c, O, birik):
    """O: {olcum_adi: seri}. birik yerinde guncellenir."""
    adlar = birik["olcumler"]
    # coin-ici desil sinirlari (serinin KENDI gecmisine gore)
    SINIR = {}
    for k, ad in enumerate(adlar):
        x = O.get(ad)
        if x is None: continue
        f = x[np.isfinite(x)]
        if len(f) < 500: continue
        SINIR[k] = np.percentile(f, np.arange(10, 100, 10))
    ad_list = adlar
    n = 0
    for i0 in adaylar(h, l, c):
        ab = asama_barlari(h, c, i0)
        birik["aday"] += 1; n += 1
        for ai, a in enumerate(ASAMA):
            j = ab.get(a)
            if j is None or j+2 >= len(c): continue
            birik["asama_ulasan"][ai] += 1
            son = hedefe_ulasti(h, l, c, j)
            if son is None: continue
            for hi, hd in enumerate(HEDEF):
                u = son[hd][0]
                birik["taban"][ai, hi, 0] += u
                birik["taban"][ai, hi, 1] += 1
            for k, sinir in SINIR.items():
                x = O[ad_list[k]]
                if j >= len(x) or not np.isfinite(x[j]): continue
                d = int(np.searchsorted(sinir, x[j]))
                d = min(max(d, 0), DESIL-1)
                for hi, hd in enumerate(HEDEF):
                    birik["say"][ai, k, d, hi, 0] += son[hd][0]
                    birik["say"][ai, k, d, hi, 1] += 1
    return n

def birlestir(a, b):
    a["say"] += b["say"]; a["taban"] += b["taban"]
    a["asama_ulasan"] += b["asama_ulasan"]; a["aday"] += b["aday"]
    return a

def kaydet(b, yol):
    np.savez_compressed(yol, olcumler=np.array(b["olcumler"]), say=b["say"],
                        taban=b["taban"], asama_ulasan=b["asama_ulasan"],
                        aday=np.array([b["aday"]]))

def yukle(yol):
    z = np.load(yol, allow_pickle=False)
    return {"olcumler": [str(x) for x in z["olcumler"]], "say": z["say"],
            "taban": z["taban"], "asama_ulasan": z["asama_ulasan"],
            "aday": int(z["aday"][0])}
