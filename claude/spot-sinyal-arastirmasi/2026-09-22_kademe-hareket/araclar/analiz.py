# -*- coding: utf-8 -*-
"""Her olcu icin: KAZANC BUYUKLUGU ve DERIN KAYIP ayri ayri.
Isabet orani BIRINCIL olcut DEGIL (kullanici talebi): +%78 giden islemle
+%20'de duran islem ayni sayilmamali."""
import sys
import numpy as np

z=np.load(sys.argv[1], allow_pickle=True)
AD=list(z["ad"]); SUT=list(z["sut"]); X=z["X"]; P=z["P"]; C=z["C"]; T=z["T"]
si={s:i for i,s in enumerate(SUT)}
tepe=P[:,si["tepe"]]*100
dipp=P[:,si["en_dip"]]*100
mae =P[:,si["mae_tepeye_kadar"]]*100
tbar=P[:,si["tepe_bar"]]

def olc(m):
    if m.sum()<300: return None
    return dict(n=int(m.sum()),
                ort=float(np.mean(tepe[m])), med=float(np.median(tepe[m])),
                b20=100*float(np.mean(tepe[m]>=20)), b50=100*float(np.mean(tepe[m]>=50)),
                b100=100*float(np.mean(tepe[m]>=100)),
                d10=100*float(np.mean(dipp[m]<=-10)), d20=100*float(np.mean(dipp[m]<=-20)),
                temiz=100*float(np.mean((tepe[m]>=20)&(mae[m]>-10))))

T0=olc(np.ones(len(X),bool))
print(f"TABAN — {T0['n']:,} sinyal")
print(f"  tepe yukselis: ort %{T0['ort']:.1f} · medyan %{T0['med']:.1f}")
print(f"  +%20'ye ulasan %{T0['b20']:.1f} · +%50 %{T0['b50']:.1f} · +%100 %{T0['b100']:.1f}")
print(f"  KAYIP: -%10'u goren %{T0['d10']:.1f} · -%20 %{T0['d20']:.1f}")
print(f"  'temiz yukselis' (+%20'ye, once -%10 gormeden): %{T0['temiz']:.1f}")
print(f"  tepeye ulasma suresi: medyan {np.median(tbar):.0f} bar ({np.median(tbar)*4:.0f} saat)")

# --- her olcu, kendi 5'li dilimlerinde
print(f"\n{'='*118}")
print("EN IYI AYIRANLAR — olcunun kendi ust/alt %20'lik dilimi, tabana gore")
print(f"{'olcu':<22}{'dilim':<8}{'n':>7}{'med tepe':>10}{'+%50':>8}{'+%100':>8}{'-%10 gor':>10}{'temiz':>8}{'  <- taban':<12}")
print(f"{'TABAN':<22}{'':<8}{T0['n']:>7}{T0['med']:>9.1f}%{T0['b50']:>7.1f}%{T0['b100']:>7.1f}%{T0['d10']:>9.1f}%{T0['temiz']:>7.1f}%")
print("-"*118)
sonuc=[]
for j,ad in enumerate(AD):
    x=X[:,j]; ok=np.isfinite(x)
    if ok.sum()<2000: continue
    q=np.nanpercentile(x[ok],[20,80])
    for et,m in (("alt %20", ok&(x<=q[0])), ("ust %20", ok&(x>=q[1]))):
        r=olc(m)
        if r: sonuc.append((ad,et,r))
# siralama: temiz yukselis orani (buyukluk + kayip kacinma birlikte)
sonuc.sort(key=lambda a:-a[2]["temiz"])
for ad,et,r in sonuc[:14]:
    print(f"{ad:<22}{et:<8}{r['n']:>7}{r['med']:>9.1f}%{r['b50']:>7.1f}%{r['b100']:>7.1f}%{r['d10']:>9.1f}%{r['temiz']:>7.1f}%")
print("\nKAYBI EN COK KESENLER (-%10 gorme orani en dusuk):")
for ad,et,r in sorted(sonuc,key=lambda a:a[2]["d10"])[:8]:
    print(f"{ad:<22}{et:<8}{r['n']:>7}{r['med']:>9.1f}%{r['b50']:>7.1f}%{r['b100']:>7.1f}%{r['d10']:>9.1f}%{r['temiz']:>7.1f}%")
print("\nEN BUYUK KAZANC GETIRENLER (MEDYAN tepe en yuksek):")
for ad,et,r in sorted(sonuc,key=lambda a:-a[2]["med"])[:8]:
    print(f"{ad:<22}{et:<8}{r['n']:>7}{r['med']:>9.1f}%{r['b50']:>7.1f}%{r['b100']:>7.1f}%{r['d10']:>9.1f}%{r['temiz']:>7.1f}%")
