# -*- coding: utf-8 -*-
"""
ANA TABLO — her (sembol, gunluk bar) icin ozellikler + ILERI YOL PROFILI.

Tasarim ilkesi (2026-09-22 kademe-hareket calismasindan devrali):
  - Cikis kurali VARSAYILMAZ. Her barin sonraki 30 gunluk yolunun tamami
    (hangi gun +%X'e ulasti, hangi gun -%Y'yi gordu) kaydedilir.
    Hedef/stop/temiz-yukselis olculeri SONRADAN bu tablodan turetilir.
  - TABAN her zaman yanda: tablo TUM barlari icerir, sinyal bir bayraktir.
  - Ileriye bakma yok: bar i'nin ozellikleri yalnizca <=i kapanmis barlardan.
"""
import json, os, pickle, sys
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import gosterge1g as g

VERI = os.path.join(os.path.dirname(BURASI), "veri")
UFUK = 30                                      # ileri yol penceresi (gun)
ART_ESIK = np.array([2.5, 5, 10, 15, 20, 30, 50], dtype=float)
DUS_ESIK = np.array([2.5, 5, 10, 15, 20], dtype=float)
MIN_GECMIS = 60                                # sembol basina en az bar

OZELLIK = [
    # --- kullanicinin kuralindaki dogrudan degerler ---
    "srsi_k", "srsi_d", "srsi_min", "srsi_max", "rsi", "wr",
    "macd_dif", "macd_dea", "macd_hist",
    "macd_dif_n", "macd_hist_n",          # fiyata normalize (% olarak)
    # --- diger osilatorler ---
    "kdj_j", "cci", "mfi", "roc5", "roc10", "roc20", "roc60",
    # --- yapi ---
    "ema20_uz", "ema50_uz", "ema200_uz",
    "ema20_50", "ema50_200",
    "zirve100_uz", "dip100_uz",
    "adx", "pdi", "ndi", "atr_y",
    "bb_gen", "bb_b",
    "dip_yukseliyor",
    # --- hacim / akis ---
    "hacim_oran", "islem_oran", "taker_oran", "quote20",
    # --- mum geometrisi ---
    "govde", "alt_fitil", "ust_fitil", "ardisik_dusen",
    # --- donus olaylari (bool 0/1) ---
    "srsi_kesisim", "macd_kesisim", "kdj_kesisim", "ema20_kesisim",
    # --- baglam ---
    "bar_no",
]


def profil(h, l, c, ufuk=UFUK):
    """Her bar icin: ilk hangi gun +%X'e / -%Y'ye ulasildi (0 = hic)."""
    n = len(c)
    ia = np.zeros((n, len(ART_ESIK)), dtype=np.int16)
    id_ = np.zeros((n, len(DUS_ESIK)), dtype=np.int16)
    mfe = np.full((n, 4), np.nan, dtype=np.float32)   # 5/10/20/30 gun
    mae = np.full((n, 4), np.nan, dtype=np.float32)
    ret = np.full((n, 4), np.nan, dtype=np.float32)
    ileri = np.zeros(n, dtype=np.int16)
    zirve_gun = np.zeros(n, dtype=np.int16)
    if n < 2:
        return ia, id_, mfe, mae, ret, ileri, zirve_gun

    hp = g._pencere(h[1:], ufuk)        # row j = h[j+1 .. j+ufuk]
    lp = g._pencere(l[1:], ufuk)
    cp = g._pencere(c[1:], ufuk)
    tam = 0 if hp is None else len(hp)

    UFKA = [5, 10, 20, 30]
    for i in range(n - 1):
        kalan = min(ufuk, n - 1 - i)
        ileri[i] = kalan
        if kalan <= 0:
            continue
        if i < tam:
            hh = hp[i]; ll = lp[i]; cc = cp[i]
        else:
            hh = h[i + 1: i + 1 + kalan]; ll = l[i + 1: i + 1 + kalan]
            cc = c[i + 1: i + 1 + kalan]
        giris = c[i]
        if giris <= 0:
            continue
        kmax = np.maximum.accumulate(hh[:kalan]) / giris - 1.0
        kmin = np.minimum.accumulate(ll[:kalan]) / giris - 1.0
        for j, e in enumerate(ART_ESIK):
            w = np.nonzero(kmax >= e / 100.0)[0]
            ia[i, j] = (w[0] + 1) if len(w) else 0
        for j, e in enumerate(DUS_ESIK):
            w = np.nonzero(kmin <= -e / 100.0)[0]
            id_[i, j] = (w[0] + 1) if len(w) else 0
        for j, U in enumerate(UFKA):
            if kalan >= U:
                mfe[i, j] = kmax[U - 1] * 100
                mae[i, j] = kmin[U - 1] * 100
                ret[i, j] = (cc[U - 1] / giris - 1.0) * 100
        zirve_gun[i] = int(np.argmax(hh[:kalan])) + 1
    return ia, id_, mfe, mae, ret, ileri, zirve_gun


def sembol_isle(ham):
    """ham: [[t,o,h,l,c,vol,quote,trades,taker_quote], ...] -> (ozellikler, profil)"""
    a = np.asarray(ham, dtype=float)
    t = a[:, 0].astype(np.int64)
    o, h, l, c = a[:, 1], a[:, 2], a[:, 3], a[:, 4]
    v, q, tr, tq = a[:, 5], a[:, 6], a[:, 7], a[:, 8]
    n = len(c)
    if n < MIN_GECMIS:
        return None

    K, D = g.stochrsi(c)
    R = g.rsi(c, 14)
    W = g.wr(h, l, c, 14)
    dif, dea, hist = g.macd(c)
    Jk, Jd, J = g.kdj(h, l, c)
    CCI = g.cci(h, l, c, 20)
    MFI = g.mfi(h, l, c, v, 14)
    A, PDI, NDI = g.adx(h, l, c, 14)
    ATR = g.atr(h, l, c, 14)
    _, _, _, bbg, bbb = g.bollinger(c, 20, 2.0)
    e20, e50, e200 = g.ema(c, 20), g.ema(c, 50), g.ema(c, 200)

    guv = lambda x: np.where((x == 0) | np.isnan(x), np.nan, x)

    z100 = g.kayan_max(h, 100)
    d100 = g.kayan_min(l, 100)
    d5 = g.kayan_min(l, 5)
    d5_onc = np.roll(d5, 5); d5_onc[:5] = np.nan

    aralik = guv(h - l)
    dusen = (c < np.roll(c, 1)).astype(float); dusen[0] = 0.0
    ard = np.zeros(n)
    for i in range(1, n):
        ard[i] = ard[i - 1] + 1 if dusen[i] else 0.0

    oz = {
        "srsi_k": K, "srsi_d": D,
        "srsi_min": np.fmin(K, D), "srsi_max": np.fmax(K, D),
        "rsi": R, "wr": W,
        "macd_dif": dif, "macd_dea": dea, "macd_hist": hist,
        "macd_dif_n": dif / guv(c) * 100, "macd_hist_n": hist / guv(c) * 100,
        "kdj_j": J, "cci": CCI, "mfi": MFI,
        "roc5": g.roc(c, 5), "roc10": g.roc(c, 10),
        "roc20": g.roc(c, 20), "roc60": g.roc(c, 60),
        "ema20_uz": c / guv(e20) * 100 - 100,
        "ema50_uz": c / guv(e50) * 100 - 100,
        "ema200_uz": c / guv(e200) * 100 - 100,
        "ema20_50": (e20 - e50) / guv(c) * 100,
        "ema50_200": (e50 - e200) / guv(c) * 100,
        "zirve100_uz": c / guv(z100) * 100 - 100,
        "dip100_uz": c / guv(d100) * 100 - 100,
        "adx": A, "pdi": PDI, "ndi": NDI,
        "atr_y": ATR / guv(c) * 100,
        "bb_gen": bbg * 100, "bb_b": bbb * 100,
        "dip_yukseliyor": (d5 > d5_onc).astype(float),
        "hacim_oran": v / guv(g.kayan_ort(v, 20)),
        "islem_oran": tr / guv(g.kayan_ort(tr, 20)),
        "taker_oran": tq / guv(q),
        "quote20": g.kayan_ort(q, 20),
        "govde": (c - o) / aralik,
        "alt_fitil": (np.minimum(o, c) - l) / aralik,
        "ust_fitil": (h - np.maximum(o, c)) / aralik,
        "ardisik_dusen": ard,
        "srsi_kesisim": g.kesisim_yukari(K, D).astype(float),
        "macd_kesisim": g.kesisim_yukari(dif, dea).astype(float),
        "kdj_kesisim": g.kesisim_yukari(Jk, Jd).astype(float),
        "ema20_kesisim": g.kesisim_yukari(c, e20).astype(float),
        "bar_no": np.arange(n, dtype=float),
    }
    ia, id_, mfe, mae, ret, ileri, zg = profil(h, l, c)
    return t, c, oz, ia, id_, mfe, mae, ret, ileri, zg


def main():
    with open(os.path.join(VERI, "gunluk_1d.pkl"), "rb") as f:
        veri = pickle.load(f)
    print(f"sembol: {len(veri)}", flush=True)

    semboller = sorted(veri)
    parcalar = []
    atlanan = []
    for si, sym in enumerate(semboller):
        r = sembol_isle(veri[sym])
        if r is None:
            atlanan.append(sym); continue
        t, c, oz, ia, id_, mfe, mae, ret, ileri, zg = r
        n = len(t)
        M = np.empty((n, len(OZELLIK)), dtype=np.float32)
        for j, ad in enumerate(OZELLIK):
            M[:, j] = oz[ad]
        parcalar.append((si, sym, t, c.astype(np.float32), M,
                         ia, id_, mfe, mae, ret, ileri, zg))
        if (si + 1) % 100 == 0:
            print(f"  {si+1}/{len(semboller)}", flush=True)

    print(f"islenen {len(parcalar)} · atlanan (bar<{MIN_GECMIS}) {len(atlanan)}", flush=True)

    sym_idx = np.concatenate([np.full(len(p[2]), p[0], dtype=np.int16) for p in parcalar])
    zaman   = np.concatenate([p[2] for p in parcalar])
    kapanis = np.concatenate([p[3] for p in parcalar])
    OZ      = np.concatenate([p[4] for p in parcalar], axis=0)
    ILK_ART = np.concatenate([p[5] for p in parcalar], axis=0)
    ILK_DUS = np.concatenate([p[6] for p in parcalar], axis=0)
    MFE     = np.concatenate([p[7] for p in parcalar], axis=0)
    MAE     = np.concatenate([p[8] for p in parcalar], axis=0)
    RET     = np.concatenate([p[9] for p in parcalar], axis=0)
    ILERI   = np.concatenate([p[10] for p in parcalar])
    ZIRVE   = np.concatenate([p[11] for p in parcalar])

    # --- piyasa genisligi: o gun yukselen sembol orani ---
    gunluk_ret = np.full(len(kapanis), np.nan, dtype=np.float32)
    bas = 0
    for p in parcalar:
        n = len(p[2]); c = p[3].astype(float)
        r = np.full(n, np.nan)
        r[1:] = c[1:] / np.where(c[:-1] == 0, np.nan, c[:-1]) - 1
        gunluk_ret[bas:bas + n] = r
        bas += n
    tekil_gun, ters = np.unique(zaman, return_inverse=True)
    poz = np.zeros(len(tekil_gun)); say = np.zeros(len(tekil_gun))
    gec = ~np.isnan(gunluk_ret)
    np.add.at(poz, ters[gec], (gunluk_ret[gec] > 0).astype(float))
    np.add.at(say, ters[gec], 1.0)
    genislik = np.where(say >= 20, poz / np.where(say == 0, np.nan, say), np.nan)
    GENISLIK = genislik[ters].astype(np.float32)

    print(f"\ntoplam bar: {len(zaman):,}", flush=True)
    yol = os.path.join(VERI, "tablo_1g.npz")
    np.savez_compressed(
        yol, sym_idx=sym_idx, zaman=zaman, kapanis=kapanis, OZ=OZ,
        ILK_ART=ILK_ART, ILK_DUS=ILK_DUS, MFE=MFE, MAE=MAE, RET=RET,
        ILERI=ILERI, ZIRVE=ZIRVE, GENISLIK=GENISLIK, gunluk_ret=gunluk_ret,
        ozellik=np.array(OZELLIK), semboller=np.array([p[1] for p in parcalar]),
        sym_sira=np.array(semboller),
        art_esik=ART_ESIK, dus_esik=DUS_ESIK, ufuk=np.array([UFUK]),
    )
    print(f"kaydedildi {yol}  {os.path.getsize(yol)/1048576:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
