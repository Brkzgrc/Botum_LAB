# -*- coding: utf-8 -*-
"""
4 SAATLIK tablo — gunluk tabloyla AYNI olcutler, ayni yol profili mantigi.
Ufuk 180 bar = 30 gun (gunluk calismayla birebir karsilastirilabilir).
profil() VEKTORLESTIRILDI (4.7M bar, Python dongusu cok yavas olurdu).
"""
import json, os, pickle, sys
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import gosterge1g as g
from tablo import OZELLIK, ART_ESIK, DUS_ESIK

VERI = os.path.join(os.path.dirname(BURASI), "veri")
UFUK = 180                 # 180 x 4h = 30 gun
UFKA = [30, 60, 120, 180]  # 5 / 10 / 20 / 30 gun
MIN_GECMIS = 360
PARCA = 3000               # bellek icin dilim


def profil_vek(h, l, c, ufuk=UFUK):
    n = len(c)
    ia = np.zeros((n, len(ART_ESIK)), dtype=np.int16)
    id_ = np.zeros((n, len(DUS_ESIK)), dtype=np.int16)
    mfe = np.full((n, 4), np.nan, dtype=np.float32)
    mae = np.full((n, 4), np.nan, dtype=np.float32)
    ret = np.full((n, 4), np.nan, dtype=np.float32)
    ileri = np.zeros(n, dtype=np.int16)
    zirve = np.zeros(n, dtype=np.int16)
    if n < ufuk + 2:
        return ia, id_, mfe, mae, ret, ileri, zirve

    hp = g._pencere(h[1:], ufuk)          # satir i = h[i+1 .. i+ufuk]
    lp = g._pencere(l[1:], ufuk)
    cp = g._pencere(c[1:], ufuk)
    tam = len(hp)
    ileri[:tam] = ufuk
    for i in range(tam, n - 1):
        ileri[i] = n - 1 - i

    for b0 in range(0, tam, PARCA):
        b1 = min(b0 + PARCA, tam)
        gir = c[b0:b1][:, None]
        with np.errstate(invalid="ignore", divide="ignore"):
            kmax = np.maximum.accumulate(hp[b0:b1], axis=1) / gir - 1.0
            kmin = np.minimum.accumulate(lp[b0:b1], axis=1) / gir - 1.0
        for j, e in enumerate(ART_ESIK):
            v = kmax >= e / 100.0
            var = v.any(axis=1)
            ia[b0:b1, j] = np.where(var, v.argmax(axis=1) + 1, 0)
        for j, e in enumerate(DUS_ESIK):
            v = kmin <= -e / 100.0
            var = v.any(axis=1)
            id_[b0:b1, j] = np.where(var, v.argmax(axis=1) + 1, 0)
        for j, U in enumerate(UFKA):
            mfe[b0:b1, j] = kmax[:, U - 1] * 100
            mae[b0:b1, j] = kmin[:, U - 1] * 100
            with np.errstate(invalid="ignore", divide="ignore"):
                ret[b0:b1, j] = (cp[b0:b1, U - 1] / c[b0:b1] - 1.0) * 100
        zirve[b0:b1] = hp[b0:b1].argmax(axis=1) + 1

    # kuyruk (tam pencere olmayan barlar): sadece ia/id_ kismi, ret NaN kalir
    for i in range(tam, n - 1):
        kalan = n - 1 - i
        if kalan <= 0 or c[i] <= 0:
            continue
        kmax = np.maximum.accumulate(h[i+1:i+1+kalan]) / c[i] - 1.0
        kmin = np.minimum.accumulate(l[i+1:i+1+kalan]) / c[i] - 1.0
        for j, e in enumerate(ART_ESIK):
            w = np.nonzero(kmax >= e / 100.0)[0]
            ia[i, j] = (w[0] + 1) if len(w) else 0
        for j, e in enumerate(DUS_ESIK):
            w = np.nonzero(kmin <= -e / 100.0)[0]
            id_[i, j] = (w[0] + 1) if len(w) else 0
        zirve[i] = int(np.argmax(h[i+1:i+1+kalan])) + 1
    return ia, id_, mfe, mae, ret, ileri, zirve


def sembol_isle(ham):
    import tablo as T1
    a = np.asarray(ham, dtype=float)
    if len(a) < MIN_GECMIS:
        return None
    t = a[:, 0].astype(np.int64)
    o, h, l, c = a[:, 1], a[:, 2], a[:, 3], a[:, 4]
    v, q, tr, tq = a[:, 5], a[:, 6], a[:, 7], a[:, 8]
    # ozellikler: gunluk tabloyla AYNI fonksiyon (tablo.sembol_isle'nin ozellik kismi)
    r = T1.sembol_isle(ham)       # kendi profilini de hesaplar, onu atacagiz
    if r is None:
        return None
    _t, _c, oz, *_ = r
    ia, id_, mfe, mae, ret, ileri, zirve = profil_vek(h, l, c)
    return t, c, oz, ia, id_, mfe, mae, ret, ileri, zirve


def main():
    with open(os.path.join(VERI, "dort_saat_4h.pkl"), "rb") as f:
        veri = pickle.load(f)
    print(f"sembol: {len(veri)}", flush=True)
    semboller = sorted(veri)
    parcalar, atlanan = [], []
    for si, sym in enumerate(semboller):
        r = sembol_isle(veri[sym])
        if r is None:
            atlanan.append(sym); continue
        t, c, oz, ia, id_, mfe, mae, ret, ileri, zv = r
        n = len(t)
        M = np.empty((n, len(OZELLIK)), dtype=np.float32)
        for j, ad in enumerate(OZELLIK):
            M[:, j] = oz[ad]
        parcalar.append((si, sym, t, c.astype(np.float32), M, ia, id_, mfe, mae, ret, ileri, zv))
        if (si + 1) % 50 == 0:
            print(f"  {si+1}/{len(semboller)}", flush=True)

    print(f"islenen {len(parcalar)} · atlanan {len(atlanan)}", flush=True)
    sym_idx = np.concatenate([np.full(len(p[2]), p[0], dtype=np.int16) for p in parcalar])
    zaman = np.concatenate([p[2] for p in parcalar])
    kapanis = np.concatenate([p[3] for p in parcalar])
    OZ = np.concatenate([p[4] for p in parcalar], axis=0)
    ILK_ART = np.concatenate([p[5] for p in parcalar], axis=0)
    ILK_DUS = np.concatenate([p[6] for p in parcalar], axis=0)
    MFE = np.concatenate([p[7] for p in parcalar], axis=0)
    MAE = np.concatenate([p[8] for p in parcalar], axis=0)
    RET = np.concatenate([p[9] for p in parcalar], axis=0)
    ILERI = np.concatenate([p[10] for p in parcalar])
    ZIRVE = np.concatenate([p[11] for p in parcalar])
    print(f"toplam 4h bar: {len(zaman):,}", flush=True)

    yol = os.path.join(VERI, "tablo_4h.npz")
    np.savez_compressed(yol, sym_idx=sym_idx, zaman=zaman, kapanis=kapanis, OZ=OZ,
        ILK_ART=ILK_ART, ILK_DUS=ILK_DUS, MFE=MFE, MAE=MAE, RET=RET, ILERI=ILERI,
        ZIRVE=ZIRVE, GENISLIK=np.zeros(len(zaman), np.float32),
        gunluk_ret=np.zeros(len(zaman), np.float32),
        ozellik=np.array(OZELLIK), semboller=np.array([p[1] for p in parcalar]),
        sym_sira=np.array(semboller), art_esik=ART_ESIK, dus_esik=DUS_ESIK,
        ufuk=np.array([UFUK]))
    print(f"kaydedildi {yol}  {os.path.getsize(yol)/1048576:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
