# -*- coding: utf-8 -*-
"""
GUNCEL SINYALLER — son kapanmis gunluk bara (2026-09-30) gore.

Bu bir TAVSIYE DEGIL. Amaci: ILERIYE DONUK (hindsight'siz) bir izleme listesi
olusturmak; ilerideki oturumlarda gercek forward kanit olarak kullanilmak uzere.
Sonuclar henuz YOK (30 gunluk ufuk dolmadi).
"""
import os, sys, json
from datetime import datetime, timezone
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo
from kesif import olcutler
from geriye import yerel_dip
from formasyon import formasyonlar

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")
ILGI = ["A1 kullanici TAM kural", "A3 A2 + RSI<=40 (ters)",
        "B2 dip + derin deger", "B5 dip + ADX ust%20 + PDI ust%20"]


def main():
    T = Tablo()
    E = json.load(open(os.path.join(SON, "formasyon_kesif.json")))["esikler"]
    F = formasyonlar(T, E, yerel_dip(T, 10))
    likit = T.f("quote20") >= 1_000_000
    sem = list(np.load(os.path.join(os.path.dirname(BURASI), "veri", "tablo_1g.npz"),
                       allow_pickle=False)["semboller"])

    son_gun = T.zaman.max()
    print(f"son kapanmis gunluk bar: "
          f"{datetime.fromtimestamp(son_gun/1000, timezone.utc):%Y-%m-%d} (UTC)\n")

    cikti = {"olusturuldu": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "son_kapanis_gunu": datetime.fromtimestamp(son_gun/1000, timezone.utc)
                                 .strftime("%Y-%m-%d"),
             "not": "Ileriye donuk izleme listesi. Sonuc YOK. Tavsiye degil.",
             "listeler": {}}

    for gun_geri, etiket in [(0, "SON GUN (2026-09-30)"), (7, "SON 7 GUN")]:
        esik = son_gun - gun_geri * 86_400_000
        pencere = T.zaman >= esik
        print(f"{'='*96}\n{etiket}")
        for ad in ILGI:
            m = F[ad] & pencere & likit
            idx = np.nonzero(m)[0]
            print(f"\n  {ad}  — likit, {len(idx)} sinyal")
            if len(idx) == 0:
                continue
            kay = []
            for i in idx:
                kay.append({
                    "sembol": str(sem[T.sym_idx[i]]),
                    "tarih": datetime.fromtimestamp(T.zaman[i]/1000, timezone.utc)
                             .strftime("%Y-%m-%d"),
                    "kapanis": float(T.kapanis[i]),
                    "srsi_k": float(T.f("srsi_k")[i]), "srsi_d": float(T.f("srsi_d")[i]),
                    "rsi": float(T.f("rsi")[i]), "wr": float(T.f("wr")[i]),
                    "macd_hist_n": float(T.f("macd_hist_n")[i]),
                    "ema200_uz": float(T.f("ema200_uz")[i]),
                    "zirve100_uz": float(T.f("zirve100_uz")[i]),
                    "adx": float(T.f("adx")[i]),
                    "quote20_mUSDT": round(float(T.f("quote20")[i]) / 1e6, 2),
                })
            kay.sort(key=lambda r: -r["quote20_mUSDT"])
            print(f"    {'sembol':14s} {'tarih':11s} {'kapanis':>12s} {'srsiK':>6s} "
                  f"{'RSI':>6s} {'W%R':>7s} {'ema200%':>8s} {'zirve%':>7s} {'ADX':>5s} {'hacimM$':>8s}")
            for r in kay[:25]:
                print(f"    {r['sembol']:14s} {r['tarih']:11s} {r['kapanis']:12.6g} "
                      f"{r['srsi_k']:6.1f} {r['rsi']:6.1f} {r['wr']:7.1f} "
                      f"{r['ema200_uz']:8.1f} {r['zirve100_uz']:7.1f} {r['adx']:5.1f} "
                      f"{r['quote20_mUSDT']:8.1f}")
            if len(kay) > 25:
                print(f"    ... +{len(kay)-25} tane daha (JSON'da)")
            cikti["listeler"][f"{etiket}|{ad}"] = kay

    json.dump(cikti, open(os.path.join(SON, "guncel_izleme_20261001.json"), "w"),
              indent=1, ensure_ascii=False)
    print(f"\nkaydedildi: sonuclar/guncel_izleme_20261001.json")


if __name__ == "__main__":
    main()
