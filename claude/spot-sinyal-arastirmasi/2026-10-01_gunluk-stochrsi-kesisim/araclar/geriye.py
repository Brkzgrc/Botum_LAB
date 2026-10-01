# -*- coding: utf-8 -*-
"""
TERS YON — "yukselisler bu degerlerle mi basliyor?"

Kullanicinin gozlemi GERIYE DONUK: yukselen mum gruplarina bakip baslangic
anindaki degerleri okudu. Bu, su olasiligi olcer:
        P(degerler | yukselis basladi)
Alim karari icin gereken ise TERSIDIR:
        P(yukselis baslayacak | degerler)
Ikisi ayni sey DEGILDIR (taban-oran yanilgisi). Bu dosya IKISINI DE olcer.

"Yukselis baslangici" MEKANIK tanim (ileriye bakar, ama bu BETIMLEYICI bir
istatistik — alim kurali degil):
    - sonraki 30 gunde +%20'ye ULASTI ve bunu -%10'u gormeden ONCE yapti
    - VE bar, son 10 gunun en dusuk KAPANISI (yerel dip)
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, DONEM, ART, DUS
from kural_kullanici import kurul, kaydir
import gosterge1g as g

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")


def yerel_dip(T, pencere=10):
    """Bar, son `pencere` gunun en dusuk kapanisi mi (sembol siniri korunur)."""
    o = np.zeros(len(T.kapanis), dtype=bool)
    bas = 0
    for s in np.unique(T.sym_idx):
        m = T.sym_idx == s
        c = T.kapanis[m].astype(float)
        n = len(c)
        d = np.full(n, False)
        mn = g.kayan_min(c, pencere)
        d = (~np.isnan(mn)) & (c <= mn + 1e-12)
        o[m] = d
    return o


def main():
    T = Tablo()
    j20 = ART.index(20); j10 = ART.index(10); j5 = ART.index(5)
    d10 = DUS.index(10); d5 = DUS.index(5)

    temiz20 = ((T.ILK_ART[:, j20] > 0) &
               ((T.ILK_DUS[:, d10] == 0) | (T.ILK_ART[:, j20] < T.ILK_DUS[:, d10])))
    dip = yerel_dip(T, 10)
    print("yerel dip barlari hazir", flush=True)

    sonuc = {}
    for don, (b, e) in DONEM.items():
        D = T.donem_maske(b, e) & T.tam
        basladi = D & temiz20 & dip          # "yukselis baslangici" kumesi
        kural = kurul(T, pencere=1, srsi="max", macd="hist_neg") & D
        kes = (T.f("srsi_kesisim") > 0.5) & D

        print(f"\n{'='*78}\nDONEM {don}  ({b} -> {e})")
        print(f"  tum barlar                      : {int(D.sum()):,}")
        print(f"  'yukselis baslangici' (temiz+20 & yerel dip): {int(basladi.sum()):,}"
              f"  (tum barlarin %{basladi.sum()/D.sum()*100:.1f}'i)")

        # --- 1) GERIYE DONUK: baslangiclarin kacinda kullanicinin degerleri var
        def oran(maske, alt):
            return float((maske & alt).sum() / max(alt.sum(), 1))

        K, Dd, R, W, H = (T.f("srsi_k"), T.f("srsi_d"), T.f("rsi"),
                          T.f("wr"), T.f("macd_hist"))
        s_srsi = np.fmax(K, Dd) < 15
        s_rsi = R > 40
        s_wr = (W >= -100) & (W <= -75)
        s_macd = H < 0
        tam4 = s_srsi & s_rsi & s_wr & s_macd
        kesi = (T.f("srsi_kesisim") > 0.5)
        tam4_pen = kesi & (tam4 | kaydir(T, tam4, 1))

        print(f"\n  --- GERIYE DONUK: P(sart | yukselis basladi) ---")
        print(f"  {'sart':44s} {'baslangiclarda':>15s} {'TUM barlarda':>14s} {'oran':>7s}")
        satirlar = [
            ("StochRSI(max K,D) < 15", s_srsi),
            ("StochRSI yukari kesisim", kesi),
            ("kesisim +-1 icinde StochRSI<15", kesi & (s_srsi | kaydir(T, s_srsi, 1))),
            ("RSI > 40", s_rsi),
            ("W%R -100..-75", s_wr),
            ("MACD hist < 0", s_macd),
            ("DORT SART birlikte (pencere yok)", tam4),
            ("KULLANICININ TAM KURALI", tam4_pen),
        ]
        g1 = {}
        for ad, m in satirlar:
            a = oran(m, basladi); c = oran(m, D)
            g1[ad] = {"baslangicta": a, "tum_barda": c, "lift": a / c if c > 0 else None}
            print(f"  {ad:44s} {a*100:14.1f}% {c*100:13.1f}% "
                  f"{(a/c if c>0 else float('nan')):6.2f}x")

        # --- 2) ILERIYE DONUK: kuralin verdigi barlarin kaci baslangicmis
        print(f"\n  --- ILERIYE DONUK: P(yukselis basladi | sart) ---")
        print(f"  {'sart':44s} {'n':>8s} {'baslangic orani':>16s}")
        g2 = {}
        for ad, m in satirlar:
            mm = m & D
            if mm.sum() == 0: continue
            p = float((mm & basladi).sum() / mm.sum())
            g2[ad] = {"n": int(mm.sum()), "baslangic_orani": p}
            print(f"  {ad:44s} {int(mm.sum()):8d} {p*100:15.1f}%")
        taban_p = float(basladi.sum() / D.sum())
        print(f"  {'TABAN (rastgele bar)':44s} {int(D.sum()):8d} {taban_p*100:15.1f}%")

        # --- 3) BASLANGICLARIN GERCEK IMZASI (dagilim) ---
        print(f"\n  --- YUKSELIS BASLANGICLARININ GERCEK IMZASI (yuzdelikler) ---")
        print(f"  {'olcu':16s} {'--- baslangic ---':>34s}   {'--- tum bar ---':>34s}")
        print(f"  {'':16s} {'%10':>8s} {'%25':>8s} {'%50':>8s} {'%75':>8s}   "
              f"{'%10':>8s} {'%25':>8s} {'%50':>8s} {'%75':>8s}")
        g3 = {}
        for ad in ["srsi_k", "srsi_min", "rsi", "wr", "macd_hist_n", "kdj_j",
                   "cci", "mfi", "roc10", "roc20", "ema20_uz", "ema200_uz",
                   "zirve100_uz", "dip100_uz", "adx", "atr_y", "bb_b",
                   "hacim_oran", "taker_oran", "ardisik_dusen"]:
            v = T.f(ad)
            a = v[basladi]; c = v[D]
            a = a[~np.isnan(a)]; c = c[~np.isnan(c)]
            if len(a) < 50: continue
            qa = np.percentile(a, [10, 25, 50, 75])
            qc = np.percentile(c, [10, 25, 50, 75])
            g3[ad] = {"baslangic": qa.tolist(), "tum": qc.tolist()}
            print(f"  {ad:16s} " + " ".join(f"{x:8.2f}" for x in qa) + "   "
                  + " ".join(f"{x:8.2f}" for x in qc))
        sonuc[don] = {"geriye": g1, "ileriye": g2, "imza": g3,
                      "taban_baslangic_orani": taban_p,
                      "baslangic_n": int(basladi.sum()), "bar_n": int(D.sum())}

    json.dump(sonuc, open(os.path.join(SON, "geriye.json"), "w"), indent=1, default=float)
    print("\nkaydedildi: sonuclar/geriye.json")


if __name__ == "__main__":
    main()
