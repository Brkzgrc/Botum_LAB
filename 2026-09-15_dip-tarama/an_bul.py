#!/usr/bin/env python3
# =====================================================================
#  SENIN EKRANINDA GORDUGUN RAKAMLAR — buraya yaz
# =====================================================================
SEMBOL   = "ZECUSDT"
YAKLASIK = "23/08/2026 08:00"     # TR saati, yaklasik olsun yeter
TF       = "1h"                   # bu rakamlar hangi grafikten: "15m" / "1h" / "4h"

GOZLENEN = {
    "rsi":      48.57,
    "srsi_k":    1.63,
    "srsi_d":    0.75,
    "kdj_k":    17.60,
    "kdj_d":    22.85,
    "kdj_j":     7.12,
    "wr":      -84.31,
    "dif":       9.12,
    "dea":      18.53,
}
ARAMA_SAAT = 6        # yaklasik saatin +/- bu kadar saati taranir
ADIM_DK    = 5        # kac dakikada bir denensin
# =====================================================================
"""HANGI DAKIKADA BU RAKAMLAR CIKIYOR?

Gosterge formullerim dogru mu, yoksa sadece saat mi kaymis — onu ayirir.
Yaklasik saatin etrafini dakika dakika tarar, senin yazdigin rakamlara en
cok uyan ani bulur.

  * Bir an COK iyi tutuyorsa  -> formuller dogru, sadece saat farkliymis.
  * Hicbir an tutmuyorsa      -> formullerde gercek bir fark var, duzeltiriz.
"""
import json, sys, urllib.request
from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]
SURE = {"15m": 900_000, "1h": 3600_000, "4h": 4 * 3600_000}


def kline(sym, itv, bas, bit, limit=1000):
    err = None
    for host in HOSTS:
        u = (f"{host}/api/v3/klines?symbol={sym}&interval={itv}"
             f"&startTime={int(bas)}&endTime={int(bit)}&limit={limit}")
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            err = e
    sys.exit(f"Veri alinamadi: {type(err).__name__} {err}")


def ema(v, n):
    a = 2.0 / (n + 1.0); o = [v[0]]
    for x in v[1:]: o.append(a * x + (1 - a) * o[-1])
    return o


def sma(v, n):
    return [sum(v[max(0, i - n + 1):i + 1]) / min(i + 1, n) for i in range(len(v))]


def rsi_w(c, n=14):
    g = [0.0]; l = [0.0]
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]; g.append(max(ch, 0.0)); l.append(max(-ch, 0.0))
    ag = sum(g[1:n + 1]) / n; al = sum(l[1:n + 1]) / n
    o = [None] * n + [100.0 if al == 0 else 100 - 100 / (1 + ag / al)]
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + l[i]) / n
        o.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return o


def hesapla(h, l, c):
    r = rsi_w(c)
    ham = []
    for i in range(len(r)):
        w = [x for x in r[max(0, i - 13):i + 1] if x is not None]
        if r[i] is None or len(w) < 14: ham.append(None); continue
        lo, hi = min(w), max(w)
        ham.append(0.0 if hi == lo else (r[i] - lo) / (hi - lo) * 100)
    ok = [x for x in ham if x is not None]
    k = sma(ok, 3); dd = sma(k, 3)
    K = D = 50.0
    for i in range(len(c)):
        w = max(0, i - 8); hh, ll = max(h[w:i + 1]), min(l[w:i + 1])
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        K = (2 / 3) * K + (1 / 3) * rsv; D = (2 / 3) * D + (1 / 3) * K
    hh, ll = max(h[-14:]), min(l[-14:])
    wr = 0.0 if hh == ll else (hh - c[-1]) / (hh - ll) * -100
    e12, e26 = ema(c, 12), ema(c, 26); dif = [a - b for a, b in zip(e12, e26)]
    dea = ema(dif, 9)
    return dict(rsi=r[-1], srsi_k=k[-1], srsi_d=dd[-1], kdj_k=K, kdj_d=D, kdj_j=3 * K - 2 * D,
                wr=wr, dif=dif[-1], dea=dea[-1], hist=dif[-1] - dea[-1])


yak = datetime.strptime(YAKLASIK, "%d/%m/%Y %H:%M").replace(tzinfo=TR)
mrk = int(yak.astimezone(timezone.utc).timestamp() * 1000)
gen = ARAMA_SAAT * 3600_000
per = SURE[TF]

print(f"{SEMBOL}  {TF}  —  {YAKLASIK} TR etrafinda +/-{ARAMA_SAAT} saat taraniyor...\n")
ana = kline(SEMBOL, TF, mrk - gen - 400 * per, mrk + gen)
ince = kline(SEMBOL, "1m", mrk - gen - 60_000, mrk + gen)
if not ana or not ince:
    sys.exit("Veri gelmedi. Sembol/tarih dogru mu?")

sonuc = []
t = mrk - gen
while t <= mrk + gen:
    kap = [r for r in ana if int(r[6]) <= t]
    if len(kap) < 60:
        t += ADIM_DK * 60_000; continue
    h = [float(r[2]) for r in kap]; l = [float(r[3]) for r in kap]; c = [float(r[4]) for r in kap]
    bas = int(kap[-1][6]) + 1
    parca = [r for r in ince if bas <= int(r[0]) and int(r[6]) <= t]
    if parca:                                   # o an ACIK olan mumun olusmus kismi
        h.append(max(float(r[2]) for r in parca))
        l.append(min(float(r[3]) for r in parca))
        c.append(float(parca[-1][4]))
    g = hesapla(h, l, c)
    olcek = {"rsi": 100, "srsi_k": 100, "srsi_d": 100, "kdj_k": 100, "kdj_d": 100,
             "kdj_j": 100, "wr": 100, "dif": max(1e-9, abs(GOZLENEN.get("dif", 1))),
             "dea": max(1e-9, abs(GOZLENEN.get("dea", 1)))}
    fark = sum(abs(g[k] - v) / olcek[k] for k, v in GOZLENEN.items() if k in g)
    sonuc.append((fark, t, g))
    t += ADIM_DK * 60_000

sonuc.sort(key=lambda x: x[0])
print("EN IYI 5 AN")
print("=" * 96)
for fark, t, g in sonuc[:5]:
    ts = datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(TR)
    print(f"\n### {ts:%d.%m.%Y %H:%M} TR    uyusmazlik puani: {fark:.3f}  (0 = birebir)")
    print("     %-10s %10s %10s %9s" % ("gosterge", "sen", "ben", "fark"))
    for k, v in GOZLENEN.items():
        print("     %-10s %10.2f %10.2f %+9.2f" % (k, v, g[k], g[k] - v))

en = sonuc[0][0]
print("\n" + "=" * 96)
if en < 0.25:
    print("SONUC: Formuller DOGRU. Fark sadece saatteydi.")
elif en < 0.60:
    print("SONUC: Yakin ama tam degil. Bir gosterge farkli hesaplaniyor olabilir.")
else:
    print("SONUC: Hicbir an tutmadi. Formullerde gercek bir fark var.")
print("Yukaridaki 'fark' sutununda en buyuk sapma hangi gostergedeyse, sorun orada.")
if len(sys.argv) <= 1:
    input("\nKapatmak icin Enter...")
