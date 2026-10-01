# -*- coding: utf-8 -*-
"""
FORMASYON ARAMASI — "baska yukselis formasyonlari var mi?"

Kullanicinin sorusu: kendi buldugu kuruluma BENZER ama farkli ozellik/deger,
ya da BASKA bir yukselis formasyonu bulunabilir mi?

Onceki calismanin (2026-09-15_hareket-tespiti) en net bulgusu: 1 saatlik
izgarada "YAPI calisiyor, OSILATOR calismiyor". Bu yuzden aranan formasyonlarin
yarisi YAPI/SUREKLILIK (trend icinde geri cekilme, EMA dizilimi, sikisma
kirilimi), yarisi DIP-DONUS varyantidir.

Esikler KESIF doneminde (2017-08 -> 2022-12) hesaplanir, JSON'a DONDURULUR;
dogrulama bu dondurulmus sayilarla tek kosuda yapilir.
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, DONEM, ART, DUS
from kural_kullanici import kurul, kaydir
from kesif import Hizli, olcutler
from geriye import yerel_dip

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")


def esikler(T, havuz, ozellikler, yuzdeler=(20, 80)):
    cik = {}
    for ad in ozellikler:
        v = T.f(ad)
        h = v[havuz]; h = h[~np.isnan(h)]
        if len(h) < 500: continue
        p = np.percentile(h, yuzdeler)
        cik[ad] = {f"p{int(y)}": float(x) for y, x in zip(yuzdeler, p)}
    return cik


def formasyonlar(T, E, dip):
    """E: dondurulmus esik sozlugu. Doner: {ad: bool maske}"""
    f = T.f
    g = lambda ad, p: E[ad][p]
    kesi = f("srsi_kesisim") > 0.5
    gecerli = ~np.isnan(f("ema200_uz")) & ~np.isnan(f("adx")) & ~np.isnan(f("srsi_k"))

    F = {}

    # --- A) KULLANICININ FIKRININ VARYANTLARI ---
    F["A1 kullanici TAM kural"] = kurul(T, pencere=1, srsi="max", macd="hist_neg")
    F["A2 kesisim YOK, RSI>40 YOK"] = (
        (np.fmax(f("srsi_k"), f("srsi_d")) < 15) &
        (f("wr") >= -100) & (f("wr") <= -75) & (f("macd_hist") < 0))
    F["A3 A2 + RSI<=40 (ters)"] = F["A2 kesisim YOK, RSI>40 YOK"] & (f("rsi") <= 40)
    F["A4 kesisim + TEYIT (srsi<30, c>ema20)"] = (
        kesi & (np.fmax(f("srsi_k"), f("srsi_d")) < 30) &
        (f("rsi") > 45) & (f("ema20_uz") > 0))

    # --- B) DIP-DONUS, kesifteki en iyi eksenler ---
    F["B1 dip + ADX ust%20"] = dip & (f("adx") >= g("adx", "p80"))
    F["B2 dip + derin deger"] = dip & (f("ema200_uz") <= g("ema200_uz", "p20")) & \
                                (f("zirve100_uz") <= g("zirve100_uz", "p20"))
    F["B3 dip + KDJ kesisimi"] = dip & (f("kdj_kesisim") > 0.5)
    F["B4 dip + taker ust%20 + hacim>1"] = dip & (f("taker_oran") >= g("taker_oran", "p80")) & \
                                           (f("hacim_oran") >= 1.0)
    F["B5 dip + ADX ust%20 + PDI ust%20"] = dip & (f("adx") >= g("adx", "p80")) & \
                                            (f("pdi") >= g("pdi", "p80"))

    # --- C) YAPI / SUREKLILIK (onceki calismanin yonu) ---
    F["C1 trend ici geri cekilme"] = (
        (f("ema20_50") > 0) & (f("ema50_200") > 0) &
        (f("ema20_uz") <= 0) & (f("ema20_uz") >= -8) &
        (f("adx") >= 20) & (f("roc20") > 0))
    F["C2 EMA20 kirilimi + StochRSI dipten cikmis"] = (
        (f("ema20_kesisim") > 0.5) & (f("srsi_min") >= 20) & (f("srsi_min") <= 60) &
        (f("macd_hist") > 0))
    F["C3 sikisma + hacimli yesil mum"] = (
        (f("bb_gen") <= g("bb_gen", "p20")) & (f("govde") >= 0.3) &
        (f("hacim_oran") >= 1.5) & (f("roc5") > 0))
    F["C4 yukselen dip + EMA20 ustu + hacim"] = (
        (f("dip_yukseliyor") > 0.5) & (f("ema20_uz") > 0) & (f("hacim_oran") >= 1.2))
    F["C5 MACD kesisimi + trend yukari"] = (
        (f("macd_kesisim") > 0.5) & (f("ema50_200") > 0) & (f("adx") >= 20))
    F["C6 C1 + taker ust%20"] = F["C1 trend ici geri cekilme"] & \
                                (f("taker_oran") >= g("taker_oran", "p80"))

    return {k: (v & gecerli) for k, v in F.items()}


def rapor(T, H, OL, F, HAVUZ, baslik, tabanad="tum barlar"):
    print(f"\n{'='*100}\n{baslik}")
    tb = {k: float(np.nanmean(OL[k][HAVUZ])) for k in OL}
    print(f"  TABAN ({tabanad}, n={int(HAVUZ.sum()):,}): "
          f"temiz20={tb['temiz20_10']:.1f}%  temiz10={tb['temiz10_5']:.1f}%  "
          f"MFE30med={np.nanmedian(OL['mfe30'][HAVUZ]):.1f}%  "
          f"RET20ort={tb['ret20']:.2f}%")
    print(f"\n  {'formasyon':38s} {'n':>7s} {'gun':>5s} {'temiz20':>8s} {'fark':>6s} "
          f"{'t20':>7s} {'MFEt':>6s} {'RET20t':>7s} {'RET20ort':>9s}")
    cik = {}
    for ad, m in F.items():
        mm = m & HAVUZ
        n = int(mm.sum())
        if n < 100:
            print(f"  {ad:38s} {n:7d}  (yetersiz)"); continue
        v = float(np.nanmean(OL["temiz20_10"][mm]))
        r20 = H.test(mm, HAVUZ, OL["temiz20_10"])
        rmf = H.test(mm, HAVUZ, OL["mfe30"])
        rrt = H.test(mm, HAVUZ, OL["ret20"])
        cik[ad] = {"n": n, "gun": (r20 or {}).get("gun"), "temiz20": v,
                   "fark": v - tb["temiz20_10"], "t20": (r20 or {}).get("t"),
                   "mfe_t": (rmf or {}).get("t"), "ret20_t": (rrt or {}).get("t"),
                   "ret20_ort": float(np.nanmean(OL["ret20"][mm]))}
        print(f"  {ad:38s} {n:7d} {(r20 or {}).get('gun',0):5d} {v:7.1f}% "
              f"{v-tb['temiz20_10']:+6.1f} {(r20 or {}).get('t',float('nan')):+7.2f} "
              f"{(rmf or {}).get('t',float('nan')):+6.2f} "
              f"{(rrt or {}).get('t',float('nan')):+7.2f} "
              f"{np.nanmean(OL['ret20'][mm]):+9.2f}%")
    return {"taban": tb, "formasyonlar": cik}


def main():
    T = Tablo(); H = Hizli(T); OL = olcutler(T)
    dip = yerel_dip(T, 10)
    bas, bit = DONEM["kesif_2017_2022"]
    D = T.donem_maske(bas, bit) & T.tam

    # --- esikleri KESIF doneminde hesapla ve DONDUR ---
    gerekli = ["adx", "pdi", "ema200_uz", "zirve100_uz", "taker_oran", "bb_gen"]
    E = esikler(T, D, gerekli)
    print("DONDURULAN ESIKLER (kesif donemi 2017-08..2022-12, tum barlar):")
    for k, v in E.items():
        print(f"  {k:14s} p20={v['p20']:12.4f}  p80={v['p80']:12.4f}")

    F = formasyonlar(T, E, dip)
    sonuc = {"esikler": E, "kesif_donemi": [bas, bit]}
    sonuc["kesif"] = rapor(T, H, OL, F, D,
                           f"KESIF DONEMI {bas} -> {bit} · havuz: AYNI GUNUN TUM COINLERI")

    json.dump(sonuc, open(os.path.join(SON, "formasyon_kesif.json"), "w"),
              indent=1, default=float)
    print(f"\nkaydedildi: sonuclar/formasyon_kesif.json")
    print("\nUYARI: 15 formasyon x 4 olcut = 60 test. ADAY listesi, KANIT DEGIL.")


if __name__ == "__main__":
    main()
