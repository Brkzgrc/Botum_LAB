# -*- coding: utf-8 -*-
"""
1 GUNLUK kline indirici.
  - bugun islem goren pariteler: data-api.binance.vision REST (hizli)
  - delist olmus pariteler: s3 arsivi (aylik 1d zip) -> hayatta kalma yanliligi yok

Bilinen tuzak (onceki calismadan): Binance arsivinde 2025'ten itibaren zaman
damgasi MIKROSANIYE. Satir bazinda duzeltilir (dizi bazinda DEGIL).
"""
import json, os, io, sys, time, zipfile, csv
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BURASI = os.path.dirname(os.path.abspath(__file__))
VERI   = os.path.join(os.path.dirname(BURASI), "veri")
API    = "https://data-api.binance.vision"
S3     = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BASLA  = 1_483_228_800_000     # 2017-01-01
BITIR  = 1_790_812_800_000     # 2026-10-01 00:00 UTC (bugunun KAPANMAMIS mumu haric)
GUN_MS = 14_400_000


def _ac(url, deneme=5, timeout=60):
    for d in range(deneme):
        try:
            istek = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(istek, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return None
            time.sleep(1.5 * (d + 1) + 0.5 * d * d)
        except Exception:
            time.sleep(1.5 * (d + 1))
    return None


def _ms(t):
    t = int(t)
    if t > 1e14:          # mikrosaniye -> milisaniye
        t //= 1000
    return t


def api_indir(sym):
    """[[acilis_ms, o,h,l,c, hacim, quote_hacim, islem_sayisi, taker_al_quote], ...]"""
    cik, bas = [], BASLA
    while bas < BITIR:
        url = (f"{API}/api/v3/klines?symbol={sym}&interval=4h"
               f"&startTime={bas}&limit=1000")
        ham = _ac(url)
        if ham is None:
            return None
        try:
            kl = json.loads(ham.decode())
        except Exception:
            return None
        if not kl:
            break
        for k in kl:
            t = _ms(k[0])
            if t >= BITIR:
                continue
            cik.append([t, float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                        float(k[5]), float(k[7]), int(k[8]), float(k[9])])
        son = _ms(kl[-1][0])
        if son + GUN_MS <= bas:
            break
        bas = son + GUN_MS
        if len(kl) < 1000:
            break
    return cik


def _s3_liste(sym):
    yollar, tok = [], None
    while True:
        url = (f"{S3}/?list-type=2&prefix=data/spot/monthly/klines/{sym}/4h/"
               f"&max-keys=1000")
        if tok:
            url += "&continuation-token=" + urllib.parse.quote(tok, safe="")
        ham = _ac(url)
        if ham is None:
            return yollar
        metin = ham.decode()
        import re
        for m in re.finditer(r"<Key>([^<]+)</Key>", metin):
            k = m.group(1)
            if k.endswith(".zip"):
                yollar.append(k)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", metin)
        if m and "<IsTruncated>true</IsTruncated>" in metin:
            tok = m.group(1)
        else:
            break
    return sorted(yollar)


def arsiv_indir(sym):
    yollar = _s3_liste(sym)
    if not yollar:
        return None
    satirlar = []
    for yol in yollar:
        ham = _ac(f"{S3}/{yol}")
        if ham is None:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(ham)) as z:
                ad = z.namelist()[0]
                metin = z.read(ad).decode("utf-8", "replace")
        except Exception:
            continue
        for sat in csv.reader(io.StringIO(metin)):
            if not sat or len(sat) < 9:
                continue
            if not sat[0].lstrip("-").replace(".", "").isdigit():
                continue          # baslik satiri (2025+ dosyalarda var)
            try:
                t = _ms(float(sat[0]))
                if t >= BITIR:
                    continue
                satirlar.append([t, float(sat[1]), float(sat[2]), float(sat[3]),
                                 float(sat[4]), float(sat[5]), float(sat[7]),
                                 int(float(sat[8])), float(sat[9])])
            except Exception:
                continue
    satirlar.sort(key=lambda r: r[0])
    # ayni gun tekrar ederse tekille
    temiz, son_t = [], None
    for r in satirlar:
        if r[0] != son_t:
            temiz.append(r); son_t = r[0]
    return temiz


def main():
    ev = json.load(open(os.path.join(VERI, "evren_1g.json")))
    tut = ev["tutulan"]
    canli = ev["canli_mi"]
    print(f"evren {len(tut)} parite  (canli {sum(canli.values())})", flush=True)

    sonuc, hata = {}, []
    sayac = [0]

    def isle(sym):
        v = api_indir(sym) if canli.get(sym) else None
        if not v or len(v) < 360:
            v = arsiv_indir(sym)
        sayac[0] += 1
        if sayac[0] % 50 == 0:
            print(f"  {sayac[0]}/{len(tut)}", flush=True)
        return sym, v

    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, v in ex.map(isle, tut):
            if v and len(v) >= 360:
                sonuc[sym] = v
            else:
                hata.append(sym)

    print(f"\nbasarili {len(sonuc)} / {len(tut)} · yetersiz/hatali {len(hata)}", flush=True)
    if hata:
        print("  " + ", ".join(sorted(hata)[:60]), flush=True)

    import pickle
    yol = os.path.join(VERI, "dort_saat_4h.pkl")
    with open(yol, "wb") as f:
        pickle.dump(sonuc, f, protocol=4)
    print(f"kaydedildi {yol}  {os.path.getsize(yol)/1048576:.1f} MB", flush=True)

    from datetime import datetime, timezone
    toplam_bar = sum(len(v) for v in sonuc.values())
    ilk = min(v[0][0] for v in sonuc.values())
    son = max(v[-1][0] for v in sonuc.values())
    print(f"toplam gunluk bar: {toplam_bar:,}", flush=True)
    print(f"aralik: {datetime.fromtimestamp(ilk/1000, timezone.utc):%Y-%m-%d}"
          f" -> {datetime.fromtimestamp(son/1000, timezone.utc):%Y-%m-%d}", flush=True)


if __name__ == "__main__":
    import urllib.parse
    main()
