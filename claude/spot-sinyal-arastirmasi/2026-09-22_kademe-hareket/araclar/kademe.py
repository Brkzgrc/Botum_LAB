# -*- coding: utf-8 -*-
"""KADEME OLCUMU — yukselislerde 4h / 1h / 15m dip yukseltmesi hangi sirayla, kac saat arayla?

Once TESPIT: her yukselisi bul ve uc zaman diliminde donusun ne zaman onaylandigini olc.
Ayirma (kazanan/kaybeden) sonraki adim.
"""
import numpy as np

def yukselis_baslangiclari(t15, h15, l15, c15, artis=15.0, dusus=7.5, pencere=12):
    """Yerel dipten +artis%'e, -dusus%'e inmeden ULASAN hareketler.
    Doner: her yukselis icin (dip_index, dip_zamani, zirve_getiri)."""
    n = len(c15); out = []; i = pencere + 5
    while i < n - 5:
        if l15[i] > np.min(l15[i-pencere:i+1]): i += 1; continue
        g = c15[i]; ust = g*(1+artis/100); alt = g*(1-dusus/100)
        j = i+1; ulasti = False
        while j < n:
            if l15[j] <= alt: break
            if h15[j] >= ust: ulasti = True; break
            j += 1
        if not ulasti: i += 1; continue
        zirve = h15[j]; k = j+1
        while k < n and h15[k] >= zirve*0.925:
            zirve = max(zirve, h15[k]); k += 1
        out.append((i, int(t15[i]), float(zirve/g-1)*100))
        i = max(k, j+1)
    return out

def dip_onayi(t, l, ts, ileriye=48, tut=2):
    """Dibi ICEREN bardan ITIBAREN ileriye dogru: dip yukselten ve TUTAN ilk bar.

    Dibi iceren bar da sayilir — 4h bari dibi icinde barindirip yine de
    onceki bara gore yuksek dip yapabilir (16.09.2026 ornegi).
    Geriye dogru tarama YOK: pencere ucundaki alakasiz dip yukselmelerini
    onay sanma hatasi bu yuzden olusmustu.
    Doner: (bar_zamani, dibe gore saat farki) ya da None.
    """
    i0 = int(np.searchsorted(t, ts, side="right")) - 1   # ts'yi iceren bar
    if i0 < 1: return None
    son = min(len(l)-tut-1, i0+ileriye)
    for i in range(i0, son+1):
        if l[i] <= l[i-1]: continue
        if any(l[i+k] < l[i] for k in range(1, tut+1)): continue
        return int(t[i]), (t[i]-ts)/3600_000.0
    return None

def coin_olc(t15,h15,l15,c15, t1,l1, t4,l4, birik):
    """Her yukselis icin 4h/1h/15m onay zamanlarini biriktir."""
    for i0, ts, kazanc in yukselis_baslangiclari(t15,h15,l15,c15):
        # TUTMA SARTI ESIT: ucunde de 4 SAAT boyunca dip kirilmamali.
        # (Once 15m'de 30dk / 4h'de 4 saat idi -> 15m'ye 8 kat kolaylik,
        #  sira sonucu bu yuzden 15m lehine cikiyordu.)
        o4 = dip_onayi(t4,  l4,  ts, ileriye=6,  tut=1)    # 1 bar  = 4 saat
        o1 = dip_onayi(t1,  l1,  ts, ileriye=24, tut=4)    # 4 bar  = 4 saat
        o15= dip_onayi(t15, l15, ts, ileriye=96, tut=16)   # 16 bar = 4 saat
        if o4 is None or o1 is None or o15 is None: continue
        birik.append({"kazanc": kazanc,
                      "s4": o4[1], "s1": o1[1], "s15": o15[1],
                      "sira": _sira(o4[0], o1[0], o15[0])})

def _sira(a4, a1, a15):
    """hangi zaman dilimi once onayladi"""
    d = sorted([(a4,"4h"), (a1,"1h"), (a15,"15m")])
    return "-".join(x[1] for x in d)

def ozet(B):
    import collections
    if not B: return
    n = len(B)
    print(f"toplam yukselis: {n:,}\n")
    print("=== ONAY SIRASI ===")
    c = collections.Counter(x["sira"] for x in B)
    for s, k in c.most_common():
        print(f"  {s:<14} {k:>7,}  %{100*k/n:.1f}")
    print(f"\n  4h en once (herhangi bir sirada): %{100*sum(1 for x in B if x['s4']<=x['s1'] and x['s4']<=x['s15'])/n:.1f}")
    print(f"  TAM SIRA 4h -> 1h -> 15m         : %{100*c.get('4h-1h-15m',0)/n:.1f}")
    print("\n=== ONAY ZAMANI (yukselisin dibine gore, saat; - = once) ===")
    for ad, k in (("4h","s4"),("1h","s1"),("15m","s15")):
        v = np.array([x[k] for x in B])
        print(f"  {ad:<4} medyan {np.median(v):+6.1f}   %25 {np.percentile(v,25):+6.1f}   %75 {np.percentile(v,75):+6.1f}   once onaylayan %{100*np.mean(v<=0):.0f}")
    print("\n=== GECIKMELER (saat) ===")
    d41 = np.array([x["s1"]-x["s4"] for x in B]); d115 = np.array([x["s15"]-x["s1"] for x in B])
    print(f"  4h -> 1h   medyan {np.median(d41):+5.1f}   (%25 {np.percentile(d41,25):+.1f} / %75 {np.percentile(d41,75):+.1f})")
    print(f"  1h -> 15m  medyan {np.median(d115):+5.1f}   (%25 {np.percentile(d115,25):+.1f} / %75 {np.percentile(d115,75):+.1f})")
