# -*- coding: utf-8 -*-
"""
KESIF — "dip barlari" icinde hangi 1 GUNLUK ozellik yukselis BASLANGICINI
ayiriyor?

NEDEN DIP-KOSULLU: "yukselis baslangici" tanimi zorunlu olarak YEREL DIP
icerir. Osilatorler (StochRSI<15, W%R<-75, MACD<0) zaten dip bulur.
Bu yuzden "dip bulmak" ile "YUKSELECEK dibi bulmak" ayrilmali:
    havuz = tum yerel dipler
    soru  = bu diplerin icinden yukseleni ayiran ozellik var mi?

Yontem:
  - KESIF donemi: 2017-08 -> 2022-12
  - her ozellik kendi (kesif donemi, dip havuzu) %20/%80 yuzdeliginde kesilir
  - sonuc: temiz +%20/-%10 orani + AYNI-GUN kontrol t degeri
  - 2023-2024 ve 2025-2026 DOKUNULMAZ; aday donduktan sonra tek kosu
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, DONEM, ART, DUS
from kural_kullanici import kurul, kaydir
from geriye import yerel_dip

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")


class Hizli:
    """Gun bazli (ayni-gun kesit) karsilastirma — bincount ile hizli."""
    def __init__(self, T):
        self.T = T
        self.gun_kod = np.unique(T.gun, return_inverse=True)[1].astype(np.int64)
        self.G = self.gun_kod.max() + 1

    def grup_ort(self, maske, deg):
        g = self.gun_kod[maske]; d = deg[maske]
        ok = ~np.isnan(d)
        g, d = g[ok], d[ok]
        s = np.bincount(g, weights=d, minlength=self.G)
        n = np.bincount(g, minlength=self.G)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(n > 0, s / np.where(n == 0, np.nan, n), np.nan), n

    def test(self, sinyal, havuz, deg, min_havuz=10):
        os_, ns = self.grup_ort(sinyal, deg)
        oh, nh = self.grup_ort(havuz, deg)
        ok = (ns > 0) & (nh >= min_havuz)
        f = (os_ - oh)[ok]
        f = f[~np.isnan(f)]
        if len(f) < 5:
            return None
        sd = f.std(ddof=1)
        return {"gun": int(len(f)), "n": int(sinyal.sum()),
                "ort_fark": float(f.mean()), "medyan_fark": float(np.median(f)),
                "poz_gun": float((f > 0).mean()),
                "t": float(f.mean() / (sd / np.sqrt(len(f)))) if sd > 0 else 0.0}


def olcutler(T):
    j20, j10, j5 = ART.index(20), ART.index(10), ART.index(5)
    d10, d5 = DUS.index(10), DUS.index(5)
    t20 = ((T.ILK_ART[:, j20] > 0) &
           ((T.ILK_DUS[:, d10] == 0) | (T.ILK_ART[:, j20] < T.ILK_DUS[:, d10]))).astype(float)
    t10 = ((T.ILK_ART[:, j10] > 0) &
           ((T.ILK_DUS[:, d5] == 0) | (T.ILK_ART[:, j10] < T.ILK_DUS[:, d5]))).astype(float)
    return {"temiz20_10": t20 * 100, "temiz10_5": t10 * 100,
            "mfe30": T.MFE[:, 3].astype(float), "ret20": T.RET[:, 2].astype(float),
            "ret30": T.RET[:, 3].astype(float)}


TARANACAK = [
    "srsi_k", "srsi_min", "srsi_max", "rsi", "wr", "macd_dif_n", "macd_hist_n",
    "kdj_j", "cci", "mfi", "roc5", "roc10", "roc20", "roc60",
    "ema20_uz", "ema50_uz", "ema200_uz", "ema20_50", "ema50_200",
    "zirve100_uz", "dip100_uz", "adx", "pdi", "ndi", "atr_y",
    "bb_gen", "bb_b", "hacim_oran", "islem_oran", "taker_oran", "quote20",
    "govde", "alt_fitil", "ust_fitil", "ardisik_dusen",
]
OLAY = ["srsi_kesisim", "macd_kesisim", "kdj_kesisim", "ema20_kesisim",
        "dip_yukseliyor"]


def main():
    T = Tablo()
    H = Hizli(T)
    OL = olcutler(T)
    dip = yerel_dip(T, 10)
    bas, bit = DONEM["kesif_2017_2022"]
    D = T.donem_maske(bas, bit) & T.tam
    HAVUZ = D & dip
    print(f"KESIF {bas} -> {bit}")
    print(f"  tum bar        : {int(D.sum()):,}")
    print(f"  YEREL DIP havuzu: {int(HAVUZ.sum()):,}  (%{HAVUZ.sum()/D.sum()*100:.1f})")

    print(f"\n{'='*86}\n0) DIP HAVUZUNUN TABANI vs TUM BARLAR")
    yaz(ozet(T, D, "tum barlar"))
    yaz(ozet(T, HAVUZ, "YEREL DIP havuzu"))

    print(f"\n{'='*86}")
    print("1) KULLANICININ SARTLARI — DIP HAVUZU ICINDE (havuz: ayni gunun diger dipleri)")
    K, Dd, R, W, Hh = (T.f("srsi_k"), T.f("srsi_d"), T.f("rsi"),
                       T.f("wr"), T.f("macd_hist"))
    kesi = T.f("srsi_kesisim") > 0.5
    s_srsi = np.fmax(K, Dd) < 15
    s_rsi = R > 40
    s_wr = (W >= -100) & (W <= -75)
    s_macd = Hh < 0
    tam4 = s_srsi & s_rsi & s_wr & s_macd
    adaylar = [
        ("StochRSI<15", s_srsi),
        ("RSI>40", s_rsi),
        ("RSI<=40  (TERSI)", R <= 40),
        ("W%R -100..-75", s_wr),
        ("MACD hist<0", s_macd),
        ("4 SART (kesisim yok)", tam4),
        ("StochRSI yukari kesisim", kesi),
        ("KULLANICI TAM KURAL", kurul(T, pencere=1, srsi="max", macd="hist_neg")),
    ]
    print(f"  {'sart':26s} {'n':>7s} {'temiz20':>8s} {'tabanD':>7s} "
          f"{'fark':>6s} {'aynigun t':>10s} {'MFE30 t':>8s}")
    tabanD = float(np.nanmean(OL["temiz20_10"][HAVUZ]))
    g1 = {}
    for ad, m in adaylar:
        mm = HAVUZ & m
        if mm.sum() < 50:
            print(f"  {ad:26s} {int(mm.sum()):7d}  (yetersiz)"); continue
        v = float(np.nanmean(OL["temiz20_10"][mm]))
        r = H.test(mm, HAVUZ, OL["temiz20_10"])
        rm = H.test(mm, HAVUZ, OL["mfe30"])
        g1[ad] = {"n": int(mm.sum()), "temiz20": v, "taban": tabanD,
                  "t": (r or {}).get("t"), "mfe_t": (rm or {}).get("t")}
        print(f"  {ad:26s} {int(mm.sum()):7d} {v:7.1f}% {tabanD:6.1f}% "
              f"{v-tabanD:+6.1f} {(r or {}).get('t',float('nan')):+10.2f} "
              f"{(rm or {}).get('t',float('nan')):+8.2f}")

    print(f"\n{'='*86}")
    print("2) OZELLIK TARAMASI — dip havuzu, her ozellik kendi %20 / %80 ucunda")
    print(f"  taban (dip havuzu) temiz+20/-10 = {tabanD:.1f}%")
    print(f"\n  {'ozellik':16s} {'uc':>5s} {'esik':>11s} {'n':>7s} {'temiz20':>8s} "
          f"{'fark':>6s} {'aynigun t':>10s} {'MFE30 t':>8s}")
    satir = []
    for ad in TARANACAK:
        v = T.f(ad)
        hv = v[HAVUZ]
        hv = hv[~np.isnan(hv)]
        if len(hv) < 500:
            continue
        p20, p80 = np.percentile(hv, [20, 80])
        for uc, m in (("alt", (v <= p20)), ("ust", (v >= p80))):
            mm = HAVUZ & m & ~np.isnan(v)
            if mm.sum() < 300:
                continue
            o = float(np.nanmean(OL["temiz20_10"][mm]))
            r = H.test(mm, HAVUZ, OL["temiz20_10"])
            rm = H.test(mm, HAVUZ, OL["mfe30"])
            satir.append({"ozellik": ad, "uc": uc,
                          "esik": float(p20 if uc == "alt" else p80),
                          "n": int(mm.sum()), "temiz20": o, "fark": o - tabanD,
                          "t": (r or {}).get("t"), "mfe_t": (rm or {}).get("t")})
    for ad in OLAY:
        v = T.f(ad)
        mm = HAVUZ & (v > 0.5)
        if mm.sum() < 300: continue
        o = float(np.nanmean(OL["temiz20_10"][mm]))
        r = H.test(mm, HAVUZ, OL["temiz20_10"]); rm = H.test(mm, HAVUZ, OL["mfe30"])
        satir.append({"ozellik": ad, "uc": "var", "esik": 1.0, "n": int(mm.sum()),
                      "temiz20": o, "fark": o - tabanD,
                      "t": (r or {}).get("t"), "mfe_t": (rm or {}).get("t")})
    satir.sort(key=lambda x: -(x["t"] or -99))
    for s in satir:
        print(f"  {s['ozellik']:16s} {s['uc']:>5s} {s['esik']:11.3f} {s['n']:7d} "
              f"{s['temiz20']:7.1f}% {s['fark']:+6.1f} {(s['t'] or float('nan')):+10.2f} "
              f"{(s['mfe_t'] or float('nan')):+8.2f}")

    json.dump({"kullanici_sartlari_dip_icinde": g1, "ozellik_taramasi": satir,
               "taban_dip_temiz20": tabanD, "dip_n": int(HAVUZ.sum()),
               "kesif_donemi": [bas, bit]},
              open(os.path.join(SON, "kesif.json"), "w"), indent=1, default=float)
    print(f"\nkaydedildi: sonuclar/kesif.json")
    print(f"\nUYARI: {len(satir)} test yapildi. Bu bir ADAY listesidir, KANIT DEGIL."
          f"\nHukum dokunulmamis donemde (2023-2024, 2025-2026) tek kosuda verilecek.")


if __name__ == "__main__":
    main()
