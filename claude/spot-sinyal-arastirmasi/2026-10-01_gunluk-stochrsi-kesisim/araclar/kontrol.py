# -*- coding: utf-8 -*-
"""
AYNI-GUN KESIT KONTROLU + ABLASYON + REJIM KIRILIMI.

Neden gerekli: kullanicinin kurali fiyat DUSERKEN atesliyor. Ham taban
(tum barlar) 2017 ve 2021 boga kosularini da icerir. Ham tabanla
karsilastirmak kurali haksiz yere cezalandirir.

Dogru soru: "AYNI GUN, ayni piyasada, bu kuralin sectigi coinler o gunun
            diger coinlerinden iyi mi?"
"""
import os, sys, json
import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
from olc import Tablo, ozet, yaz, gun_bazli_test, olcut_temiz, olcut_mfe, \
                olcut_ret, ay_bootstrap, DONEM, ART, DUS, TEMIZ
from kural_kullanici import kurul, kaydir

SON = os.path.join(os.path.dirname(BURASI), "sonuclar")

OLCUTLER = [
    ("temiz +20/-10", olcut_temiz(20, 10), 100),
    ("temiz +10/-5",  olcut_temiz(10, 5),  100),
    ("MFE30",         olcut_mfe(30),         1),
    ("RET20",         olcut_ret(20),         1),
    ("RET30",         olcut_ret(30),         1),
]


def kontrol_tablosu(T, sinyal, havuz, baslik):
    print(f"\n  {baslik}")
    print(f"  {'olcut':16s} {'gun':>5s} {'sinyal':>7s} {'ort fark':>10s} "
          f"{'medyan':>9s} {'poz.gun':>8s} {'t':>7s}")
    cik = {}
    for ad, f, ols in OLCUTLER:
        r = gun_bazli_test(T, sinyal, havuz, f)
        if r is None:
            print(f"  {ad:16s} (yetersiz)"); continue
        cik[ad] = r
        print(f"  {ad:16s} {r['gun_sayisi']:5d} {r['sinyal_bar']:7d} "
              f"{r['ort_fark']*ols:+10.3f} {r['medyan_fark']*ols:+9.3f} "
              f"{r['pozitif_gun_orani']*100:7.1f}% {r['t']:+7.2f}")
    return cik


def main():
    T = Tablo()
    likit = T.f("quote20") >= 1_000_000
    hepsi = np.ones(len(T.zaman), dtype=bool)
    tumsonuc = {}

    # kullanicinin kurali, en iyi pencere (1), olcek-bagimsiz MACD okumasi
    ANA = dict(pencere=1, srsi="max", macd="hist_neg")

    for don, (b, e) in DONEM.items():
        D = T.donem_maske(b, e)
        m = kurul(T, **ANA) & D
        print(f"\n{'='*78}")
        print(f"DONEM {don}  ({b} -> {e})")
        yaz(ozet(T, D, "  taban: tum barlar"))
        yaz(ozet(T, m, "  kullanici kurali"))
        tumsonuc[don] = {
            "taban": ozet(T, D, "taban"),
            "kural": ozet(T, m, "kural"),
            "ayni_gun_tum": kontrol_tablosu(T, m, D, "AYNI-GUN KONTROL (havuz: o gunun tum coinleri)"),
        }
        kes = (T.f("srsi_kesisim") > 0.5) & D
        tumsonuc[don]["ayni_gun_kesisim"] = kontrol_tablosu(
            T, m, kes, "AYNI-GUN KONTROL (havuz: o gunun StochRSI kesisimleri)")

    # ---------------- ABLASYON (kesif donemi) ----------------
    b, e = DONEM["kesif_2017_2022"]
    D = T.donem_maske(b, e)
    print(f"\n{'='*78}\nABLASYON — her sart tek tek CIKARILINCA ne oluyor (kesif donemi)")
    K, Dd = T.f("srsi_k"), T.f("srsi_d")
    kes = T.f("srsi_kesisim") > 0.5
    gec = ~np.isnan(K) & ~np.isnan(T.f("rsi")) & ~np.isnan(T.f("wr")) & ~np.isnan(T.f("macd_hist"))
    parcalar = {
        "srsi<15": np.fmax(K, Dd) < 15,
        "rsi>40":  T.f("rsi") > 40,
        "wr[-100,-75]": (T.f("wr") >= -100) & (T.f("wr") <= -75),
        "macd_hist<0": T.f("macd_hist") < 0,
    }
    adlar = list(parcalar)

    def birlestir(secili):
        s = gec.copy()
        for a in secili:
            s &= parcalar[a]
        return kes & (s | kaydir(T, s, 1))

    tam = birlestir(adlar)
    yaz(ozet(T, tam & D, "TAM KURAL (4 sart)"))
    ablasyon = {}
    for a in adlar:
        kalan = [x for x in adlar if x != a]
        m = birlestir(kalan) & D
        o = ozet(T, m, f"'{a}' CIKARILDI")
        yaz(o); ablasyon[f"-{a}"] = o
    print("\n  --- her sart TEK BASINA (+ kesisim) ---")
    for a in adlar:
        m = birlestir([a]) & D
        o = ozet(T, m, f"sadece '{a}'")
        yaz(o); ablasyon[f"only {a}"] = o
    tumsonuc["ablasyon_kesif"] = ablasyon

    # ---------------- YIL YIL ----------------
    print(f"\n{'='*78}\nYIL YIL (kullanici kurali vs o yilin tabani)")
    m_tum = kurul(T, **ANA)
    print(f"  {'yil':6s} {'n':>6s} {'kural t20/10':>13s} {'taban t20/10':>13s} "
          f"{'kural MFE30':>12s} {'taban MFE30':>12s} {'aynigun t':>10s}")
    yillar = {}
    for y in range(2017, 2027):
        Dy = T.donem_maske(f"{y}-01-01", f"{y+1}-01-01")
        my = m_tum & Dy
        if (my & T.tam).sum() < 25:
            continue
        ok = ozet(T, my, "k"); ot = ozet(T, Dy, "t")
        r = gun_bazli_test(T, my, Dy, olcut_temiz(20, 10))
        yillar[y] = {"n": ok["n"], "kural": ok, "taban": ot,
                     "aynigun_t": (r or {}).get("t")}
        print(f"  {y:6d} {ok['n']:6d} {ok['temiz_20_10']*100:12.1f}% "
              f"{ot['temiz_20_10']*100:12.1f}% {ok['mfe30']:11.1f}% {ot['mfe30']:11.1f}% "
              f"{(r or {}).get('t', float('nan')):+10.2f}")
    tumsonuc["yil_yil"] = yillar

    # ---------------- LIKIT ALT KUME ----------------
    print(f"\n{'='*78}\nLIKIT ALT KUME (20g ort quote hacim >= 1M USDT), kesif donemi")
    yaz(ozet(T, D & likit, "taban likit"))
    yaz(ozet(T, kurul(T, **ANA) & D & likit, "kural likit"))
    kontrol_tablosu(T, kurul(T, **ANA) & D & likit, D & likit, "AYNI-GUN KONTROL likit")

    json.dump(tumsonuc, open(os.path.join(SON, "kontrol.json"), "w"), indent=1, default=float)
    print(f"\nkaydedildi: sonuclar/kontrol.json")


if __name__ == "__main__":
    main()
