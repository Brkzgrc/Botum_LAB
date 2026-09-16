#!/usr/bin/env python3
# =====================================================================
#  BURAYI DOLDUR — F5'e bas
# =====================================================================
SEMBOL = "ZECUSDT"
ZAMAN  = "23/08/2026 08:00"      # TR saati (UTC+3) — senin ekranindaki an
# =====================================================================
"""GOSTERGE DOGRULAMA

Amac: benim hesapladigim RSI / StochRSI / KDJ / W%R / MACD degerlerinin
senin ekraninda gordugun rakamlarla ayni cikip cikmadigini kontrol etmek.

Tutmuyorsa ustune kurulacak her sey yanlis olur. O yuzden once bu.

Formuller (standart):
  RSI(14)        Wilder
  StochRSI(14,3,3)  rsi'nin 14'luk stokastigi, %K=SMA3, %D=SMA3(%K)
  KDJ(9,3,3)     RSV=(C-LLV9)/(HHV9-LLV9)*100; K=2/3*Kprev+1/3*RSV;
                 D=2/3*Dprev+1/3*K;  J=3K-2D
  W%R(14)        (HHV14-C)/(HHV14-LLV14)*-100
  MACD(12,26,9)  dif=EMA12-EMA26; dea=EMA9(dif); hist=dif-dea
"""
import json, sys, urllib.request
from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]


def kline(sym, itv, bitis_ms, adet=500):
    err = None
    for host in HOSTS:
        u = f"{host}/api/v3/klines?symbol={sym}&interval={itv}&endTime={int(bitis_ms)}&limit={adet}"
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            err = e
    sys.exit(f"Veri alinamadi ({sym} {itv}): {type(err).__name__} {err}")


def ema(v, n):
    a = 2.0 / (n + 1.0); out = [v[0]]
    for x in v[1:]: out.append(a * x + (1 - a) * out[-1])
    return out


def sma(v, n):
    out = []
    for i in range(len(v)):
        out.append(sum(v[max(0, i - n + 1):i + 1]) / min(i + 1, n))
    return out


def rsi_wilder(c, n=14):
    g = [0.0]; l = [0.0]
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]
        g.append(max(ch, 0.0)); l.append(max(-ch, 0.0))
    ag = sum(g[1:n + 1]) / n; al = sum(l[1:n + 1]) / n
    out = [None] * n
    out.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + l[i]) / n
        out.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return out


def hesapla(h, l, c):
    r = rsi_wilder(c)
    # StochRSI(14,3,3)
    ham = []
    for i in range(len(r)):
        w = [x for x in r[max(0, i - 13):i + 1] if x is not None]
        if r[i] is None or len(w) < 14: ham.append(None); continue
        lo, hi = min(w), max(w)
        ham.append(0.0 if hi == lo else (r[i] - lo) / (hi - lo) * 100)
    ok = [x for x in ham if x is not None]
    k = sma(ok, 3); dd = sma(k, 3)
    # KDJ(9,3,3)
    K = D = 50.0
    for i in range(len(c)):
        w = max(0, i - 8)
        hh, ll = max(h[w:i + 1]), min(l[w:i + 1])
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        K = (2 / 3) * K + (1 / 3) * rsv
        D = (2 / 3) * D + (1 / 3) * K
    J = 3 * K - 2 * D
    # W%R(14)
    hh, ll = max(h[-14:]), min(l[-14:])
    wr = 0.0 if hh == ll else (hh - c[-1]) / (hh - ll) * -100
    # MACD(12,26,9)
    e12, e26 = ema(c, 12), ema(c, 26)
    dif = [a - b for a, b in zip(e12, e26)]
    dea = ema(dif, 9)
    return dict(rsi=r[-1], srsi_k=k[-1], srsi_d=dd[-1], kdj_k=K, kdj_d=D, kdj_j=J,
                wr=wr, dif=dif[-1], dea=dea[-1], hist=dif[-1] - dea[-1])


dt = datetime.strptime(ZAMAN, "%d/%m/%Y %H:%M").replace(tzinfo=TR)
ms = int(dt.astimezone(timezone.utc).timestamp() * 1000)
print("=" * 74)
print(f"{SEMBOL}   {ZAMAN} (TR)  =  {dt.astimezone(timezone.utc):%d.%m.%Y %H:%M} (UTC)")
print("=" * 74)
print("Bu rakamlari kendi ekranindakiyle karsilastir.\n")

# Senin ekraninda o an ACIK olan mum da gorunuyor (or. 4 saatlikte 07:00 mumu,
# 08:00'da 1 saatlik kismi olusmus). Scanner da acik mumu kullanir. O yuzden
# acik mumu 15 dakikaliklardan kurup son bar olarak ekliyoruz.
ham15 = kline(SEMBOL, "15m", ms, 500)
bar15 = [r for r in ham15 if int(r[6]) <= ms]

def acik_mum(sinir_ms):
    """sinir_ms'ten (acik mumun baslangici) su ana kadar olusan kismi bar."""
    parca = [r for r in bar15 if int(r[0]) >= sinir_ms]
    if not parca: return None
    return [max(float(r[2]) for r in parca),      # high
            min(float(r[3]) for r in parca),      # low
            float(parca[-1][4])]                  # close

SURE = {"15m": 900_000, "1h": 3600_000, "4h": 4 * 3600_000, "1d": 24 * 3600_000}
for itv, ad in (("15m", "15 DAKIKA"), ("1h", "1 SAAT"), ("4h", "4 SAAT"), ("1d", "GUNLUK")):
    raw = kline(SEMBOL, itv, ms)
    kapali = [r for r in raw if int(r[6]) <= ms]        # o ana kadar KAPANMIS mumlar
    if len(kapali) < 60:
        print(f"--- {ad}: yeterli mum yok ({len(kapali)})"); continue
    h = [float(r[2]) for r in kapali]; l = [float(r[3]) for r in kapali]; c = [float(r[4]) for r in kapali]
    # acik mum var mi? (son kapanistan sonra zaman gectiyse)
    acik_bas = int(kapali[-1][6]) + 1
    kismi = acik_mum(acik_bas) if (ms - acik_bas) >= 60_000 else None
    if kismi:
        h.append(kismi[0]); l.append(kismi[1]); c.append(kismi[2])
    g = hesapla(h, l, c)
    son = datetime.fromtimestamp(acik_bas / 1000, tz=timezone.utc).astimezone(TR) if kismi \
          else datetime.fromtimestamp(int(kapali[-1][6]) / 1000, tz=timezone.utc).astimezone(TR)
    etiket = (f"ACIK mum {son:%d.%m %H:%M} TR baslangicli, su anki fiyat {c[-1]:g}" if kismi
              else f"son kapali mum {son:%d.%m %H:%M} TR, kapanis {c[-1]:g}")
    print(f"--- {ad}   ({etiket})")
    print(f"      RSI           : {g['rsi']:.2f}")
    print(f"      StochRSI  K/D : {g['srsi_k']:.2f} / {g['srsi_d']:.2f}")
    print(f"      KDJ     K/D/J : {g['kdj_k']:.2f} / {g['kdj_d']:.2f} / {g['kdj_j']:.2f}")
    print(f"      W%R           : {g['wr']:.2f}")
    print(f"      MACD dif/dea  : {g['dif']:.4f} / {g['dea']:.4f}   hist: {g['hist']:.4f}")
    print()

print("NOT: 4 saat ve gunlukte ACIK mum kullanildi (senin ekranindaki gibi),")
print("15 dakikalik mumlardan kuruldu. 15dk ve 1 saat 08:00'da tam sinirda")
print("oldugu icin onlar zaten kapali. Hepsinin tutmasi gerekir.")
if len(sys.argv) <= 1:
    input("\nKapatmak icin Enter...")
