# -*- coding: utf-8 -*-
"""
IKINCI TUR VARYANTLAR — DASH 2026-08 ornegi uc yeni soru acti:

1) MACD OKUMASI: DASH 1 gunlukte asil dip barinda (16.08) MACD histogram
   +0.0007 idi, yani "hist<0" sarti dibi SACI TELI KADAR kacirdi; ama MACD
   dif -0.767 (yani "MACD<0.05" birebir okumasi TUTUYORDU). Histogram donus
   barinda zorunlu olarak sifiri keser -> "hist<0" tam donus barini eler.
   dif<0 vs hist<0 vs MACD sarti yok: ucu ayri olculuyor.

2) GEVSEK PENCERE: kullanici "kesisim +-1, 3 alan" derken sartlarin AYNI barda
   saglanmasini kastetmemis olabilir; her sart pencerenin HERHANGI bir barinda
   saglanabilir. DASH 1 gunlukte tam bu oluyor (StochRSI<15 16.08'de,
   RSI>40 17.08'de). Ileriye bakma yok: sinyal bari pencerenin SON bari.

3) RSI BANDI: DASH 4 saatlik dip barinda RSI 42.21 — ne "<=40" ne de belirgin
   ">40". Dogru sart tek tarafli esik degil BANT olabilir. Taranir.
"""
import os, sys, json
import numpy as np
BURASI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, DONEM, ART, DUS
from kesif import Hizli, olcutler
from kural_kullanici import kaydir

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")
KOM = 0.20


def oR(T, m, kac):
    """m, son `kac` barin HERHANGI birinde saglandi mi (0=sadece bu bar)."""
    o = m.copy()
    for k in range(1, kac + 1):
        o = o | kaydir(T, m, k)
    return o


def kur(T, *, kesisim, pencere, srsi_esik, rsi_sart, macd, gevsek):
    """
    kesisim : True/False
    pencere : 0 / 1 / 2  (kesisim bari + kac bar geriye bakilacak)
    rsi_sart: ("<=",50) / (">",40) / ("bant",35,50) / None
    macd    : "hist<0" / "dif<0" / "dif<0.05" / "yok"
    gevsek  : True -> her sart penceredeki HERHANGI barda; False -> hepsi AYNI barda
    """
    K, D, R, W = T.f("srsi_k"), T.f("srsi_d"), T.f("rsi"), T.f("wr")
    dif, hist = T.f("macd_dif"), T.f("macd_hist")
    gec = ~np.isnan(K) & ~np.isnan(R) & ~np.isnan(W) & ~np.isnan(dif)

    s_srsi = (np.fmax(K, D) < srsi_esik) & gec
    s_wr = (W >= -100) & (W <= -75) & gec
    if macd == "hist<0":    s_macd = (hist < 0) & gec
    elif macd == "dif<0":   s_macd = (dif < 0) & gec
    elif macd == "dif<0.05": s_macd = (dif < 0.05) & gec
    else:                   s_macd = gec.copy()
    if rsi_sart is None:            s_rsi = gec.copy()
    elif rsi_sart[0] == "<=":       s_rsi = (R <= rsi_sart[1]) & gec
    elif rsi_sart[0] == ">":        s_rsi = (R > rsi_sart[1]) & gec
    elif rsi_sart[0] == "bant":     s_rsi = (R >= rsi_sart[1]) & (R <= rsi_sart[2]) & gec

    sartlar = [s_srsi, s_wr, s_macd, s_rsi]
    if gevsek:
        birlesik = sartlar[0].copy()
        for s in sartlar[1:]:
            birlesik = birlesik & oR(T, s, pencere)
        birlesik = oR(T, sartlar[0], pencere)
        for s in sartlar[1:]:
            birlesik = birlesik & oR(T, s, pencere)
    else:
        hepsi = sartlar[0]
        for s in sartlar[1:]:
            hepsi = hepsi & s
        birlesik = oR(T, hepsi, pencere)

    if not kesisim:
        return birlesik
    kes = T.f("srsi_kesisim") > 0.5
    return birlesik & oR(T, kes, pencere)


def net(T, m, D, j=0):
    mm = m & D
    r = T.RET[mm, j].astype(float) - KOM
    r = r[~np.isnan(r)]
    if len(r) < 50:
        return None
    ay = (T.zaman[mm][~np.isnan(T.RET[mm, j].astype(float))] // 86_400_000 // 30)
    aylar = np.unique(ay)
    oa = np.array([r[ay == a].mean() for a in aylar])
    t = oa.mean() / (oa.std(ddof=1) / np.sqrt(len(oa))) if len(aylar) > 3 else float("nan")
    return {"n": len(r), "medyan": float(np.median(r)), "kazanan": float((r > 0).mean() * 100),
            "ay_t": float(t)}


def main():
    # argv[1] verilirse o tablo kullanilir (orn. veri/tablo_4h.npz)
    tablo_yolu = sys.argv[1] if len(sys.argv) > 1 else None
    etiket_izgara = sys.argv[2] if len(sys.argv) > 2 else "1 GUNLUK"
    T = Tablo(tablo_yolu); H = Hizli(T); OL = olcutler(T)
    print(f"IZGARA: {etiket_izgara}   tablo: {tablo_yolu or 'veri/tablo_1g.npz'}")
    print(f"bar: {len(T.zaman):,}  sembol: {len(T.semboller)}")
    from datetime import datetime, timezone
    print(f"aralik: {datetime.fromtimestamp(T.zaman.min()/1000,timezone.utc):%Y-%m-%d}"
          f" -> {datetime.fromtimestamp(T.zaman.max()/1000,timezone.utc):%Y-%m-%d}")
    likit = T.f("quote20") >= 1_000_000

    VAR = {
        # --- kullanicinin ORIJINAL kurali, uc MACD okumasiyla ---
        "O1 orijinal (kes, RSI>40, hist<0)":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=(">", 40), macd="hist<0", gevsek=False),
        "O2 orijinal ama MACD dif<0":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=(">", 40), macd="dif<0", gevsek=False),
        "O3 orijinal ama MACD dif<0.05 (birebir)":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=(">", 40), macd="dif<0.05", gevsek=False),
        "O4 orijinal, GEVSEK pencere, dif<0":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=(">", 40), macd="dif<0", gevsek=True),
        "O5 orijinal, GEVSEK pencere 2, dif<0":
            dict(kesisim=True, pencere=2, srsi_esik=15, rsi_sart=(">", 40), macd="dif<0", gevsek=True),
        # --- KULLANICININ YENI ONERISI: RSI<=50, kesisim +-1 ---
        "Y1 YENI (kes±1, RSI≤50, hist<0)":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=("<=", 50), macd="hist<0", gevsek=False),
        "Y2 YENI ama MACD dif<0":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=("<=", 50), macd="dif<0", gevsek=False),
        "Y3 YENI, GEVSEK pencere, dif<0":
            dict(kesisim=True, pencere=1, srsi_esik=15, rsi_sart=("<=", 50), macd="dif<0", gevsek=True),
        "Y4 YENI, GEVSEK pencere 2, dif<0":
            dict(kesisim=True, pencere=2, srsi_esik=15, rsi_sart=("<=", 50), macd="dif<0", gevsek=True),
        "Y5 YENI, KESISIM YOK, dif<0":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("<=", 50), macd="dif<0", gevsek=False),
        # --- A3 (benim bulundugum) ve MACD okumasi varyantlari ---
        "A3 (kes yok, RSI≤40, hist<0)":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("<=", 40), macd="hist<0", gevsek=False),
        "A3b (kes yok, RSI≤40, dif<0)":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("<=", 40), macd="dif<0", gevsek=False),
        "A3c (kes yok, RSI≤40, MACD yok)":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("<=", 40), macd="yok", gevsek=False),
        # --- RSI BANT fikri ---
        "R1 kes yok, RSI 35-50, dif<0":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("bant", 35, 50), macd="dif<0", gevsek=False),
        "R2 kes yok, RSI 40-50, dif<0":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("bant", 40, 50), macd="dif<0", gevsek=False),
        "R3 kes yok, RSI≤50, dif<0":
            dict(kesisim=False, pencere=0, srsi_esik=15, rsi_sart=("<=", 50), macd="dif<0", gevsek=False),
    }

    M = {ad: kur(T, **p) for ad, p in VAR.items()}
    cikti = {}
    for et, suz in [("LIKIT (>=1M USDT/gun)", likit)]:
        for don, (b, e) in DONEM.items():
            D = T.donem_maske(b, e) & T.tam & suz
            rol = "KESIF" if don.startswith("kesif") else "DOGRULAMA"
            tb = net(T, np.ones(len(T.zaman), bool), D)
            tb20 = float(np.nanmean(OL["temiz20_10"][D]))
            print(f"\n{'='*118}")
            print(f"{don}  [{rol}]  {et}   havuz n={int(D.sum()):,}")
            print(f"  TABAN: 5g net medyan {tb['medyan']:+.2f}%  kazanan {tb['kazanan']:.1f}%  "
                  f"ay t {tb['ay_t']:+.2f}  ·  temiz+20/-10 {tb20:.1f}%")
            print(f"  {'varyant':42s} {'n':>6s} {'5g net med':>11s} {'kazanan':>8s} "
                  f"{'ay t':>6s} {'temiz20':>8s} {'aynigun t':>10s}")
            for ad in VAR:
                d = net(T, M[ad], D)
                if d is None:
                    print(f"  {ad:42s} {int((M[ad]&D).sum()):6d}  (yetersiz)"); continue
                v20 = float(np.nanmean(OL["temiz20_10"][M[ad] & D]))
                r = H.test(M[ad] & D, D, OL["temiz20_10"])
                isaret = ""
                if d["medyan"] > tb["medyan"] and d["kazanan"] > tb["kazanan"]: isaret = " <<"
                print(f"  {ad:42s} {d['n']:6d} {d['medyan']:+10.2f}% {d['kazanan']:7.1f}% "
                      f"{d['ay_t']:+6.2f} {v20:7.1f}% {(r or {}).get('t',float('nan')):+10.2f}{isaret}")
                cikti[f"{don}|{ad}"] = {**d, "temiz20": v20, "aynigun_t": (r or {}).get("t"),
                                        "taban_medyan": tb["medyan"], "taban_kazanan": tb["kazanan"],
                                        "taban_temiz20": tb20}
    ek = "_4h" if (tablo_yolu and "4h" in tablo_yolu) else ""
    json.dump(cikti, open(os.path.join(SON, f"varyant2{ek}.json"), "w"), indent=1, default=float)
    print(f"\nkaydedildi: sonuclar/varyant2{ek}.json")
    print("\n'<<' = hem 5g net medyan hem kazanan orani tabanin ustunde")


if __name__ == "__main__":
    main()
