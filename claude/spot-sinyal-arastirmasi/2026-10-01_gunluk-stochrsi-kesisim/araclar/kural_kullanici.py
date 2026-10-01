# -*- coding: utf-8 -*-
"""
KULLANICININ 1 GUNLUK KURALI — tanim, belirsizlik varyantlari, taban, ablasyon.

Kullanicinin ifadesi (2026-10-01):
    1 gunluk grafikte
      StochRSI KESISIM aninda (kesisim oncesi / kesisim / kesisim sonrasi = 3 alan)
        StochRSI < 15                  (KESIN sart)
      RSI > 40
      MACD < 0.05
      Williams %R -100 ile -75 arasi

ACIK BELIRSIZLIKLER (sessizce varsayilmadi, hepsi AYRI AYRI olculuyor):
  B1  "StochRSI < 15" hangi cizgi?  max(K,D) / min(K,D) / sadece K
  B2  "MACD < 0.05" MUTLAK bir sayi; MACD fiyat olcegine baglidir.
      BTC'de (fiyat ~100.000) MACD yuzlerle ifade edilir, 0.05 esigi
      ANLAMSIZDIR. Olcek-bagimsiz okumalar ayri ayri test edilir.
  B3  "kesisim +-1" penceresi: kesisim sonrasi bari kullanmak GELECEGE
      bakmaktir; bu durumda sinyal bari BIR GUN ILERI atilir (gecikmeli giris).
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, gun_bazli_test, olcut_temiz, olcut_mfe, \
                olcut_ret, ay_bootstrap, DONEM, ART, DUS


def kaydir(T, x, k):
    """x'i k bar ileri kaydir (k=1 -> bar i'de bar i-1'in degeri). Sembol siniri korunur."""
    o = np.roll(x, k)
    ayni = np.roll(T.sym_idx, k) == T.sym_idx
    if x.dtype == bool:
        o = o & ayni
    else:
        o = np.where(ayni, o, np.nan)
    if k > 0:
        o[:k] = False if x.dtype == bool else np.nan
    return o


def macd_sarti(T, yorum):
    dif = T.f("macd_dif"); hist = T.f("macd_hist"); difn = T.f("macd_dif_n")
    if yorum == "yok":
        return np.ones(len(dif), dtype=bool)
    if yorum == "hist_neg":
        return hist < 0
    if yorum == "dif_neg":
        return dif < 0
    if yorum == "difn_0.05":           # dif, fiyatin %0.05'inden kucuk
        return difn < 0.05
    if yorum == "difn_1.0":            # ~"5$ bir coinde MACD<0.05"
        return difn < 1.0
    if yorum == "mutlak_0.05":         # birebir okuma (olcek bagimli)
        return dif < 0.05
    raise ValueError(yorum)


def srsi_sarti(T, yorum, esik=15.0):
    K, D = T.f("srsi_k"), T.f("srsi_d")
    if yorum == "max":  return np.fmax(K, D) < esik     # IKISI de altinda
    if yorum == "min":  return np.fmin(K, D) < esik     # en az biri altinda
    if yorum == "k":    return K < esik
    raise ValueError(yorum)


def kurul(T, pencere=1, srsi="max", macd="hist_neg",
          srsi_esik=15.0, rsi_esik=40.0, wr_alt=-100.0, wr_ust=-75.0,
          kesisim_sarti=True):
    """Kullanicinin kurali. Doner: sinyal bari bool maskesi (ILERIYE BAKMA YOK)."""
    sart = (srsi_sarti(T, srsi, srsi_esik)
            & (T.f("rsi") > rsi_esik)
            & (T.f("wr") >= wr_alt) & (T.f("wr") <= wr_ust)
            & macd_sarti(T, macd))
    sart = sart & ~np.isnan(T.f("srsi_k")) & ~np.isnan(T.f("rsi")) & ~np.isnan(T.f("wr"))

    if not kesisim_sarti:
        return sart

    kes = T.f("srsi_kesisim") > 0.5
    if pencere == 0:
        return kes & sart
    if pencere == 1:                      # kesisim oncesi VEYA kesisim bari
        return kes & (sart | kaydir(T, sart, 1))
    if pencere == 2:                      # +-1: kesisim sonrasi -> sinyal 1 gun GECIKIR
        a = kes & (sart | kaydir(T, sart, 1))
        b = kaydir(T, kes, 1) & sart      # onceki bar kesisim, bu barda sart saglandi
        return a | b
    raise ValueError(pencere)


def main():
    T = Tablo()
    print(f"tablo: {len(T.zaman):,} gunluk bar · {len(T.semboller)} sembol", flush=True)
    from datetime import datetime, timezone
    print(f"aralik: {datetime.fromtimestamp(T.zaman.min()/1000,timezone.utc):%Y-%m-%d}"
          f" -> {datetime.fromtimestamp(T.zaman.max()/1000,timezone.utc):%Y-%m-%d}", flush=True)
    print(f"30 gun ileri verisi TAM olan bar: {int(T.tam.sum()):,}", flush=True)

    bas, bit = DONEM["kesif_2017_2022"]
    D = T.donem_maske(bas, bit)
    print(f"\n{'='*78}\nKESIF DONEMI {bas} -> {bit} : {int((D&T.tam).sum()):,} bar")
    likit = T.f("quote20") >= 1_000_000
    print(f"  likit (20g ort quote hacim >= 1.000.000 USDT): {int((D&T.tam&likit).sum()):,} bar")

    print(f"\n{'='*78}\n1) TABANLAR (kesif donemi)")
    yaz(ozet(T, D, "T1 TUM BARLAR (ham taban)"))
    yaz(ozet(T, D & likit, "T1-likit TUM BARLAR likit"))
    kes = T.f("srsi_kesisim") > 0.5
    yaz(ozet(T, D & kes, "T3 sadece StochRSI yukari kesisimi"))

    print(f"\n{'='*78}\n2) KULLANICININ KURALI — belirsizlik varyantlari (kesif donemi)")
    print("   (pencere 1 = kesisim oncesi veya kesisim bari)")
    sonuc = {}
    for srsi in ["max", "min", "k"]:
        for macd in ["yok", "hist_neg", "dif_neg", "difn_0.05", "difn_1.0", "mutlak_0.05"]:
            m = kurul(T, pencere=1, srsi=srsi, macd=macd)
            o = ozet(T, D & m, f"srsi={srsi:3s} macd={macd:12s}")
            sonuc[(srsi, macd)] = o
            if o["n"] >= 30:
                yaz(o)
            else:
                print(f"  {o['ad']:38s} n={o['n']:7d}  (yetersiz)")

    print(f"\n{'='*78}\n3) PENCERE VARYANTI (srsi=max, macd=hist_neg)")
    for p in [0, 1, 2]:
        m = kurul(T, pencere=p, srsi="max", macd="hist_neg")
        yaz(ozet(T, D & m, f"pencere={p}"))
    m = kurul(T, kesisim_sarti=False, srsi="max", macd="hist_neg")
    yaz(ozet(T, D & m, "KESISIM SARTI YOK (sadece degerler)"))

    json.dump({f"{k[0]}|{k[1]}": v for k, v in sonuc.items()},
              open(os.path.join(os.path.dirname(BURASI), "sonuclar",
                                "kesif_varyantlar.json"), "w"), indent=1)
    print("\nkaydedildi: sonuclar/kesif_varyantlar.json")


if __name__ == "__main__":
    main()
