#!/usr/bin/env python3
# =====================================================================
#  BURAYI DOLDUR — F5'e bas, baska hicbir sey sormaz.
# =====================================================================
SEMBOL       = "LSKUSDT"
GIRIS_SAATI  = "10/09/2026 00:12"     # TR saati (UTC+3)
GIRIS        = 0.1159
STOP         = 0.1003275
TP1          = 0.1199565

TRAIL_PCT    = 2.5      # TP1 sonrasi trailing: zirveden %2.5 geri cekilince cikis
EXPIRE_H     = 24       # TP1 gorulmezse 24 saatte kapat (TP1 sonrasi sure sinirisi YOK)
KOMISYON     = 0.2      # al + sat toplam %
PARA         = 2500     # kac dolarla girdigini varsayalim
TUM_DAKIKALAR = False   # True yaparsan her dakikayi tek tek yazar
# =====================================================================

import json, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]


def cek(sym, bas_ms, bit_ms):
    """Binance'ten 1 dakikalik mumlar. Tek cagrida max 1000 -> sayfalanir."""
    out, cur, hata = [], bas_ms, None
    while cur < bit_ms:
        raw = None
        for host in HOSTS:
            url = (f"{host}/api/v3/klines?symbol={sym}&interval=1m"
                   f"&startTime={cur}&endTime={bit_ms}&limit=1000")
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    raw = json.loads(r.read())
                break
            except Exception as e:
                hata = e
        if raw is None:
            sys.exit(f"Binance'ten veri alinamadi: {type(hata).__name__} {hata}")
        if not raw:
            break
        # [open_time, open, high, low, close, volume, close_time, ...]
        out += [(int(k[0]), float(k[2]), float(k[3]), float(k[4])) for k in raw]
        yeni = int(raw[-1][0]) + 60_000
        if yeni <= cur or len(raw) < 1000:
            break
        cur = yeni
        time.sleep(0.15)
    return out


def saat(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(TR).strftime("%d.%m.%Y %H:%M")


def yuzde(p):
    return (p / GIRIS - 1) * 100


dt = datetime.strptime(GIRIS_SAATI, "%d/%m/%Y %H:%M").replace(tzinfo=TR)
t0 = int(dt.astimezone(timezone.utc).timestamp() * 1000)

print("=" * 78)
print(f"{SEMBOL}   giris {GIRIS_SAATI} (TR)   fiyat {GIRIS:g}   para {PARA}$")
print(f"stop {STOP:g} ({yuzde(STOP):+.2f}%)   TP1 {TP1:g} ({yuzde(TP1):+.2f}%)   "
      f"trailing %{TRAIL_PCT}")
print("=" * 78)

mumlar = cek(SEMBOL, t0, t0 + 14 * 24 * 3600_000)     # en fazla 14 gun ileri bak
if not mumlar:
    sys.exit("Veri gelmedi. Sembol adini ve tarihi kontrol et.")
print(f"{len(mumlar)} adet 1 dakikalik mum cekildi: {saat(mumlar[0][0])} - {saat(mumlar[-1][0])}\n")

bitis_ms = t0 + EXPIRE_H * 3600_000
zirve = GIRIS
tp1_gorundu = False
sonuc = None
olaylar = []

for ot, yuksek, dusuk, kapanis in mumlar:
    if not tp1_gorundu:
        if dusuk <= STOP:
            sonuc = ("STOP'A DEGDI", STOP, ot); break
        if yuksek >= TP1:
            tp1_gorundu = True
            zirve = max(zirve, yuksek)
            olaylar.append((ot, f"TP1 GORULDU ({TP1:g}) -> trailing basladi, sure sinirisi kalkti"))
        elif ot >= bitis_ms:
            sonuc = ("24 SAAT DOLDU", kapanis, ot); break

    if tp1_gorundu and sonuc is None:
        eski = zirve
        zirve = max(zirve, yuksek)
        trail = max(GIRIS, zirve * (1 - TRAIL_PCT / 100))
        if zirve > eski:
            olaylar.append((ot, f"yeni zirve {zirve:.8g} ({yuzde(zirve):+.2f}%)  "
                                f"-> trailing {trail:.8g} ({yuzde(trail):+.2f}%)"))
        if kapanis <= trail:
            sonuc = ("TRAILING", trail, ot); break

    if TUM_DAKIKALAR:
        tr_ = max(GIRIS, zirve * (1 - TRAIL_PCT / 100)) if tp1_gorundu else STOP
        print(f"{saat(ot)}  yuksek {yuksek:<12.8g} dusuk {dusuk:<12.8g} "
              f"kapanis {kapanis:<12.8g} zirve {zirve:<12.8g} cikis-seviyesi {tr_:.8g}")

if not TUM_DAKIKALAR:
    print("ONEMLI ANLAR")
    print("-" * 78)
    for ot, m in olaylar:
        print(f"  {saat(ot)}   {m}")
    if not olaylar:
        print("  (TP1 hic gorulmedi)")

print("\n" + "=" * 78)
if sonuc is None:
    print("Pozisyon 14 gunluk veride hala kapanmadi.")
    print(f"Su anki zirve: {zirve:.8g} ({yuzde(zirve):+.2f}%)")
    sys.exit(0)

sebep, cikis, ct = sonuc
brut = yuzde(cikis)
net = brut - KOMISYON
print(f"CIKIS       : {saat(ct)}   ({(ct - t0) / 3600000:.1f} saat sonra)")
print(f"SEBEP       : {sebep}")
print(f"CIKIS FIYATI: {cikis:.8g}")
print(f"EN YUKSEK   : {zirve:.8g}  ({yuzde(zirve):+.2f}%)")
print("-" * 78)
print(f"BRUT        : {brut:+.2f}%")
print(f"KOMISYON    : -{KOMISYON:.2f}%")
print(f"NET         : {net:+.2f}%")
print(f"PARA        : {PARA}$  ->  {PARA * (1 + net / 100):.2f}$   ({PARA * net / 100:+.2f}$)")
print("=" * 78)

if sebep == "TRAILING":
    print("\nNOT: Yukaridaki hesap, trailing seviyesinden tam olarak satabildigini")
    print("varsayar (Binance'te o seviyede bekleyen emir varsa boyle olur).")
    print("Emir yoksa sistem 5 dakikada bir bakar; o anki fiyat daha asagida")
    print("olabilir. Farki gormek icin TUM_DAKIKALAR = True yapip cikis")
    print("anindaki kapanis fiyatlarina bak.")

if len(sys.argv) <= 1:
    input("\nKapatmak icin Enter...")
