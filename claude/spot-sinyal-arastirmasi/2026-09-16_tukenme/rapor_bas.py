# -*- coding: utf-8 -*-
"""IMZA RAPORU — olasilik tablolari. Parametre yok."""
import os, sys, json
import numpy as np
KOK = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KOK)
import imza
B = imza.yukle(os.path.join(KOK, "birikim.npz"))
try: bitti = len(json.load(open(os.path.join(KOK,"durum.json")))["bitti"])
except Exception: bitti = 0
A, H = imza.ASAMA, imza.HEDEF
print(f"islenen coin-donem: {bitti}   toplam aday (yerel dip): {B['aday']:,}\n")

print("=== 1. GIRIS ASAMASI: dipten ne kadar sonra girmek daha iyi? ===")
print("   (satir = dipten yuzde kac yukselmisken girdin, sutun = oradan +X%'e ulasma olasiligi)")
print(f"   {'asama':<10}{'ulasan aday':>13}" + "".join(f"{'+'+str(int(x))+'%':>9}" for x in H))
for ai, a in enumerate(A):
    n = B["asama_ulasan"][ai]
    hucre = []
    for hi in range(len(H)):
        u, t = B["taban"][ai, hi]
        hucre.append(f"{100*u/t:.1f}%" if t >= 30 else "-")
    print(f"   +%{a:<8.0f}{n:>13,}" + "".join(f"{x:>9}" for x in hucre))

print("\n=== 2. YUKSELISIN IMZASI ===")
print("   Her asamada, her olcumun her dilimi icin +X%'e ulasma olasiligi.")
print("   Tabandan en cok SAPAN olcumler (en az 400 ornek):\n")
olc = B["olcumler"]
for ai, a in enumerate(A):
    for hi, hd in enumerate(H):
        tu, tt = B["taban"][ai, hi]
        if tt < 300: continue
        taban = tu/tt
        sat = []
        for k in range(len(olc)):
            for d in range(imza.DESIL):
                u, t = B["say"][ai, k, d, hi]
                if t < 400: continue
                p = u/t
                # binom standart hata ile kaba z
                se = (taban*(1-taban)/t)**0.5
                z = (p-taban)/se if se > 0 else 0
                sat.append((z, p, t, olc[k], d))
        if not sat: continue
        sat.sort(reverse=True)
        if abs(sat[0][0]) < 3: continue
        print(f"  --- asama +%{a:.0f}  ->  hedef +%{hd:.0f}   (taban %{100*taban:.1f}, n={tt:,})")
        tm = imza.mae_medyan(B["mae_taban"][ai])
        print(f"        {'olasilik':>9}{'kat':>7}{'z':>6}{'GERI CEKILME':>14}{'n':>8}   olcum")
        for z, p, t, ad, d in sat[:6]:
            kat = p/taban if taban > 0 else 0
            k = olc.index(ad)
            m = imza.mae_medyan(B["mae"][ai, k, d])
            bedel = f"-%{m:.0f}" if m is not None else "?"
            uyari = ""
            if m is not None and tm is not None and m > tm*1.25: uyari = "  <- BEDELI DE BUYUK"
            print(f"        %{100*p:8.1f}{kat:>7.2f}{z:>+6.1f}{bedel:>14}{t:>8,}   {ad} dilim {d+1}/10{uyari}")
        print(f"        (taban geri cekilme medyani: -%{tm:.0f})" if tm is not None else "")
        print()
