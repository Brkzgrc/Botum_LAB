# -*- coding: utf-8 -*-
"""DASH 2026-08-15 .. 2026-08-30 — 1 GUNLUK ve 4 SAATLIK bar bar inceleme."""
import os, sys, json, urllib.request
from datetime import datetime, timezone
import numpy as np
BURASI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BURASI)
import gosterge1g as g

API = "https://data-api.binance.vision"

def cek(sym, tf, bitis_ms, limit=1000):
    url = f"{API}/api/v3/klines?symbol={sym}&interval={tf}&endTime={bitis_ms-1}&limit={limit}"
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"r"}), timeout=60)
    kl = json.loads(r.read())
    return np.array([[float(k[0]), float(k[1]), float(k[2]), float(k[3]),
                      float(k[4]), float(k[5])] for k in kl])

def ms(s):
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()*1000)

def tablo(sym, tf, bas, bit, bicim="%Y-%m-%d"):
    a = cek(sym, tf, ms("2026-10-01"))
    t, o, h, l, c, v = a[:,0], a[:,1], a[:,2], a[:,3], a[:,4], a[:,5]
    K, D = g.stochrsi(c); R = g.rsi(c,14); W = g.wr(h,l,c,14)
    dif, dea, hist = g.macd(c)
    kes = g.kesisim_yukari(K, D)
    bm, em = ms(bas), ms(bit)
    idx = np.nonzero((t >= bm) & (t < em))[0]

    print(f"\n{'='*132}")
    print(f"{sym}  {tf}  {bas} -> {bit}   ({len(idx)} bar)")
    print(f"{'='*132}")
    print(f"{'zaman':17s} {'kapanis':>9s} {'srsiK':>7s} {'srsiD':>7s} {'kes':>4s} "
          f"{'RSI':>6s} {'W%R':>7s} {'MACDhist':>10s} {'dif':>9s} "
          f"{'<15':>4s} {'W%R✓':>5s} {'H<0':>4s} {'R≤40':>5s} {'R≤50':>5s} {'R>40':>5s}  SINYAL")
    for i in idx:
        s15  = "✓" if max(K[i],D[i]) < 15 else "·"
        swr  = "✓" if (-100 <= W[i] <= -75) else "·"
        sh   = "✓" if hist[i] < 0 else "·"
        r40  = "✓" if R[i] <= 40 else "·"
        r50  = "✓" if R[i] <= 50 else "·"
        ru40 = "✓" if R[i] > 40 else "·"
        kk   = "KES" if kes[i] else ""
        # pencere +-1 icinde <15 var mi
        pen = any(max(K[j],D[j]) < 15 for j in (i-1,i,i+1) if 0 <= j < len(c) and not np.isnan(K[j]))
        kes_pen = any(kes[j] for j in (i-1,i,i+1) if 0 <= j < len(c))
        etiket = []
        if s15=="✓" and swr=="✓" and sh=="✓" and r40=="✓": etiket.append("A3(RSI≤40)")
        if s15=="✓" and swr=="✓" and sh=="✓" and r50=="✓": etiket.append("A5(RSI≤50)")
        if kes_pen and pen and swr=="✓" and sh=="✓" and ru40=="✓": etiket.append("SENIN(RSI>40,kes)")
        if kes_pen and pen and swr=="✓" and sh=="✓" and r50=="✓": etiket.append("YENI(RSI≤50,kes±1)")
        print(f"{datetime.fromtimestamp(t[i]/1000,timezone.utc).strftime(bicim):17s} "
              f"{c[i]:9.3f} {K[i]:7.2f} {D[i]:7.2f} {kk:>4s} {R[i]:6.2f} {W[i]:7.2f} "
              f"{hist[i]:10.4f} {dif[i]:9.4f} {s15:>4s} {swr:>5s} {sh:>4s} "
              f"{r40:>5s} {r50:>5s} {ru40:>5s}  {' + '.join(etiket)}")
    # sonrasinda ne oldu
    son = idx[-1]
    if son+1 < len(c):
        ileri = min(30 if tf=="1d" else 60, len(c)-son-1)
        gir = c[son]
        hh = h[son+1:son+1+ileri].max(); ll = l[son+1:son+1+ileri].min()
        print(f"\n  {bit} sonrasi {ileri} bar: en yuksek {hh:.3f} (+{(hh/gir-1)*100:.1f}%)  "
              f"en dusuk {ll:.3f} ({(ll/gir-1)*100:.1f}%)  son kapanis {c[min(son+ileri,len(c)-1)]:.3f} "
              f"({(c[min(son+ileri,len(c)-1)]/gir-1)*100:+.1f}%)")

tablo("DASHUSDT", "1d", "2026-08-10", "2026-09-05")
tablo("DASHUSDT", "4h", "2026-08-15", "2026-08-31", "%Y-%m-%d %H:%M")
