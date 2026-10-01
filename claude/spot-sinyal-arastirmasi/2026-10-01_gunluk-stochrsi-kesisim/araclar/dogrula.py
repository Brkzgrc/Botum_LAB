# -*- coding: utf-8 -*-
"""
DOGRULAMA — dondurulmus esiklerle, dokunulmamis iki donemde TEK KOSU.
Esik/ozellik/formasyon DEGISTIRILMEZ. (formasyon_kesif.json'daki esikler)

Iki ayri soru ayri ayri raporlanir:
  HAM   : sinyalin kendi mutlak sonucu (pratikte onemli olan — nakitte beklemek
          de bir secenek oldugu icin "ayni gunun digerlerini gecmek" sart degil)
  AYNIGUN: ayni gun, ayni piyasada secim kalitesi (karistirici-arindirilmis)
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, DONEM, ART, DUS
from kesif import Hizli, olcutler
from geriye import yerel_dip
from formasyon import formasyonlar

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")
SECILEN = ["A1 kullanici TAM kural", "A2 kesisim YOK, RSI>40 YOK",
           "A3 A2 + RSI<=40 (ters)", "A4 kesisim + TEYIT (srsi<30, c>ema20)",
           "B2 dip + derin deger", "B3 dip + KDJ kesisimi",
           "B5 dip + ADX ust%20 + PDI ust%20",
           "C2 EMA20 kirilimi + StochRSI dipten cikmis",
           "C4 yukselen dip + EMA20 ustu + hacim"]


def satir(T, H, OL, mm, HAVUZ, tb):
    n = int(mm.sum())
    if n < 60:
        return None
    t20 = H.test(mm, HAVUZ, OL["temiz20_10"])
    tmf = H.test(mm, HAVUZ, OL["mfe30"])
    return {
        "n": n,
        "temiz20": float(np.nanmean(OL["temiz20_10"][mm])),
        "temiz20_taban": tb["temiz20_10"],
        "temiz10": float(np.nanmean(OL["temiz10_5"][mm])),
        "temiz10_taban": tb["temiz10_5"],
        "mfe30_med": float(np.nanmedian(OL["mfe30"][mm])),
        "mfe30_med_taban": tb["mfe30_med"],
        "ret20_med": float(np.nanmedian(OL["ret20"][mm])),
        "ret20_med_taban": tb["ret20_med"],
        "ret30_med": float(np.nanmedian(OL["ret30"][mm])),
        "ret30_med_taban": tb["ret30_med"],
        "t20": (t20 or {}).get("t"), "mfe_t": (tmf or {}).get("t"),
        "gun": (t20 or {}).get("gun"),
    }


def tabanlar(OL, HAVUZ):
    return {"temiz20_10": float(np.nanmean(OL["temiz20_10"][HAVUZ])),
            "temiz10_5": float(np.nanmean(OL["temiz10_5"][HAVUZ])),
            "mfe30_med": float(np.nanmedian(OL["mfe30"][HAVUZ])),
            "ret20_med": float(np.nanmedian(OL["ret20"][HAVUZ])),
            "ret30_med": float(np.nanmedian(OL["ret30"][HAVUZ]))}


def bas(ad, d):
    if d is None:
        print(f"  {ad:42s} (yetersiz ornek)"); return
    print(f"  {ad:42s} {d['n']:6d} "
          f"{d['temiz20']:6.1f}/{d['temiz20_taban']:<5.1f} "
          f"{d['temiz10']:6.1f}/{d['temiz10_taban']:<5.1f} "
          f"{d['mfe30_med']:6.1f}/{d['mfe30_med_taban']:<5.1f} "
          f"{d['ret20_med']:+6.2f}/{d['ret20_med_taban']:<+6.2f} "
          f"{(d['t20'] if d['t20'] is not None else float('nan')):+6.2f}")


def main():
    T = Tablo(); H = Hizli(T); OL = olcutler(T)
    dip = yerel_dip(T, 10)
    E = json.load(open(os.path.join(SON, "formasyon_kesif.json")))["esikler"]
    F = formasyonlar(T, E, dip)
    likit = T.f("quote20") >= 1_000_000

    print("DONDURULMUS ESIKLER (kesif doneminden, DEGISTIRILMEDI):")
    for k, v in E.items():
        print(f"  {k:14s} p20={v['p20']:12.4f}  p80={v['p80']:12.4f}")

    cikti = {"esikler": E}
    for etiket, suz in [("TUM EVREN", np.ones(len(T.zaman), bool)),
                        ("LIKIT (>=1M USDT/gun)", likit)]:
        print(f"\n{'#'*104}\n### {etiket}")
        for don, (b, e) in DONEM.items():
            D = T.donem_maske(b, e) & T.tam & suz
            tb = tabanlar(OL, D)
            print(f"\n{'='*104}")
            etik = "KESIF (arama burada yapildi)" if don.startswith("kesif") \
                   else "DOGRULAMA (dokunulmamis)"
            print(f"{don}  {b} -> {e}   [{etik}]   havuz n={int(D.sum()):,}")
            print(f"  {'formasyon':42s} {'n':>6s} {'temiz20/tb':>12s} "
                  f"{'temiz10/tb':>12s} {'MFEmed/tb':>12s} {'RET20med/tb':>14s} {'t20':>6s}")
            bk = {}
            for ad in SECILEN:
                d = satir(T, H, OL, F[ad] & D, D, tb)
                bas(ad, d); bk[ad] = d
            cikti[f"{etiket}|{don}"] = {"taban": tb, "sonuc": bk}

    json.dump(cikti, open(os.path.join(SON, "dogrulama.json"), "w"),
              indent=1, default=float)
    print(f"\nkaydedildi: sonuclar/dogrulama.json")


if __name__ == "__main__":
    main()
