# -*- coding: utf-8 -*-
"""4h -> 1h -> 15m TEYIT SISTEMI

4h'de dip bulunur, 1h teyit bekler, 15m teyit bekler, giris 15m teyidinde.
Her kademenin katki yapip yapmadigini gormek icin UC KOL birden olculur:
   A) sadece 4h        B) 4h + 1h        C) 4h + 1h + 15m (tam sistem)
"""
import numpy as np
import donus   # 6 gosterge donus sartlari (macd rsi kdj wr stochrsi obv)

SART_MIN   = 2      # her TF'de en az kac donus sarti
DIP_PENCERE= 12     # 4h dip: son 12 barin en dibi
DIP_YAS    = 3      # dip son kac bar icinde olmus olmali (dip=BAGLAM, donus=TETIK)
BEKLE_1H   = 5      # 4h sonrasi 1h teyidi icin kac bar
BEKLE_15M  = 20     # 1h teyidi sonrasi 15m icin kac bar

def _teyit(t, say, c, bas_ts, kac_bar):
    """bas_ts'den sonra kac_bar icinde SART_MIN sarti saglayan ilk bar.
    say ONCEDEN hesaplanir (her sinyalde bastan hesaplamak koşuyu kilitliyordu)."""
    i0 = int(np.searchsorted(t, bas_ts, side="right"))
    for i in range(i0, min(i0+kac_bar, len(t))):
        if say[i] >= SART_MIN:
            return i, int(t[i]), float(c[i])
    return None

def yol_sonuc(t, h, l, c, giris_i, giris, hedef, stop, ufuk=672):
    """hedefe mi once ulasti stopa mi? Ayrica en kotu geri cekilme."""
    ust = giris*(1+hedef/100); alt = giris*(1-stop/100)
    son = min(len(c), giris_i+1+ufuk)
    dip = giris
    for j in range(giris_i+1, son):
        dip = min(dip, l[j])
        if l[j] <= alt: return 0, (dip/giris-1)*100
        if h[j] >= ust: return 1, (dip/giris-1)*100
    return -1, (dip/giris-1)*100

def coin_tara(d15, d1, d4, birik, hedefler=((10,5),(20,10),(30,15))):
    t15,h15,l15,c15,v15 = d15
    t1 ,h1 ,l1 ,c1 ,v1  = d1
    t4 ,h4 ,l4 ,c4 ,v4  = d4
    if len(t4) < 60 or len(t1) < 200 or len(t15) < 500: return
    _, say4,  _ = donus.sartlar(h4,  l4,  c4,  v4)
    _, say1,  _ = donus.sartlar(h1,  l1,  c1,  v1)
    _, say15, _ = donus.sartlar(h15, l15, c15, v15)
    son_giris = -1
    for i in range(DIP_PENCERE+30, len(t4)):
        # --- 4h SINYAL: dip BAGLAMI + donus TETIGI
        # Dibin tam oldugu barda gosterge henuz donmemis olur (olculdu: 72 dipten
        # 70'inde sifir sart). O yuzden dip son DIP_YAS bar icinde aranir,
        # tetik su anki barda istenir.
        if say4[i] < SART_MIN: continue
        if not any(l4[j] <= np.min(l4[j-DIP_PENCERE:j+1])
                   for j in range(max(DIP_PENCERE, i-DIP_YAS), i+1)): continue
        if t4[i] <= son_giris: continue
        kayit = {"t4": int(t4[i])}
        # A kolu: 4h'nin kendi kapanisindan gir
        kayit["A"] = (i, float(c4[i]), t4, h4, l4, c4)
        # B kolu: 1h teyidi
        b = _teyit(t1, say1, c1, t4[i], BEKLE_1H)
        kayit["B"] = b
        # C kolu: 15m teyidi (1h teyidinden SONRA)
        cc = _teyit(t15, say15, c15, b[1], BEKLE_15M) if b else None
        kayit["C"] = cc
        r = {"t4": int(t4[i])}
        for ad, arm in (("A", ("4h", i, c4[i])), ("B", ("1h",)+(b[:1]+(b[2],) if b else ())),
                        ("C", ("15m",)+(cc[:1]+(cc[2],) if cc else ()))):
            if len(arm) < 3: r[ad] = None; continue
            tf = arm[0]; gi = arm[1]; gp = arm[2]
            tt,hh,ll,ccx = (t4,h4,l4,c4) if tf=="4h" else ((t1,h1,l1,c1) if tf=="1h" else (t15,h15,l15,c15))
            uf = {"4h":168,"1h":672,"15m":2688}[tf]
            r[ad] = {"giris": gp,
                     "sonuc": {f"{hd}/{st}": yol_sonuc(tt,hh,ll,ccx,gi,gp,hd,st,uf)
                               for hd,st in hedefler}}
        birik.append(r)
        if cc: son_giris = cc[1]
        elif b: son_giris = b[1]
        else:  son_giris = int(t4[i])
