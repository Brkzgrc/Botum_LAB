# -*- coding: utf-8 -*-
"""
EVREN KURUCU — Binance Spot USDT pariteleri, 1 GUNLUK arastirma icin.

CLAUDE.md "Spot Universe Filtering" kuralina uygun:
  - Korlemesine substring eslesmesi YOK.
  - "UP/DOWN/BULL/BEAR" filtresi SADECE onek gercek bir Binance varligi ise
    ve parite bugun SPOT'ta islem GORMUYORSA uygulanir (tum leveraged token
    2021'de delist edildi). SYRUP ("SYR" varlik degil), JUP ("J" varlik degil)
    bu yuzden KORUNUR.
  - Stablecoin ve fiat listeleri ACIK yazildi, tahmin yok.
  - Elenen ve KORUNAN siniri gecen her sembol rapora yazilir (denetlenebilir).
"""
import json, os, sys, re
import urllib.request

BURASI = os.path.dirname(os.path.abspath(__file__))
VERI   = os.path.join(os.path.dirname(BURASI), "veri")
ESKI_EVREN = os.path.join(os.path.dirname(os.path.dirname(BURASI)),
                          "veri", "binance_evren_delist_dahil.json")

API = "https://data-api.binance.vision"

# --- ACIK LISTELER (tahmin yok, elle yazildi) -------------------------------
STABLE = {
    "USDT","USDC","BUSD","TUSD","USDP","PAX","PAXG_NO","DAI","FDUSD","UST",
    "USTC","SUSD","GUSD","USDS","USDSB","VAI","USDD","FRAX","LUSD","EURI",
    "PYUSD","AEUR","USD1","USDE","USDE_NO","XUSD","USDJ","MUSD","CUSD",
    "USDQ","EURQ","USDG","RLUSD","USDF","USDX","DUSD","OUSD","USDB","FUSD",
}
# not: PAXG = altin tokeni, stablecoin DEGIL -> listede yok (korunur)

FIAT = {
    "EUR","GBP","AUD","TRY","BRL","RUB","NGN","UAH","ZAR","BIDR","IDRT",
    "PLN","RON","CZK","JPY","MXN","COP","ARS","VND","KRW","CHF","CAD",
    "INR","THB","HUF","SEK","NOK","DKK","NZD","SGD","HKD","AED","SAR",
}

SONEK = ("UP","DOWN","BULL","BEAR")

# Binance tokenize HISSE/ETF urunleri (xStocks: AAPLB, NVDAB, SPYB, TSLAB...).
# Kripto spot varligi DEGIL -> arastirma kapsami disinda.
# Tespit METADATA ile: exchangeInfo permissionSets icinde bu izin grubu.
# ONEMLI: "BUSDT ile bitiyor" gibi substring testi KULLANILMAZ — o test
# ARBUSDT, BNBUSDT, SHIBUSDT, QNTUSDT, DGBUSDT, TRBUSDT, CKBUSDT gibi GERCEK
# coinleri de yakalar (tam kacinilmasi gereken false positive).
TOKENIZE_HISSE_IZNI = "TRD_GRP_261"


def getir(yol):
    istek = urllib.request.Request(API + yol, headers={"User-Agent": "research/1.0"})
    with urllib.request.urlopen(istek, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    bilgi = getir("/api/v3/exchangeInfo")
    semboller = bilgi["symbols"]
    print(f"exchangeInfo: {len(semboller)} sembol", flush=True)

    # --- bugun SPOT'ta islem goren USDT pariteleri ---
    canli_usdt = {}
    tum_base = set()
    for s in semboller:
        tum_base.add(s["baseAsset"])
        izin = set()
        for ps in s.get("permissionSets") or []:
            izin |= set(ps)
        izin |= set(s.get("permissions") or [])
        if s["quoteAsset"] != "USDT":
            continue
        canli_usdt[s["symbol"]] = {
            "base": s["baseAsset"],
            "durum": s["status"],
            "spot": bool(s.get("isSpotTradingAllowed")),
            "izin": sorted(izin),
        }
    print(f"USDT paritesi (exchangeInfo): {len(canli_usdt)}", flush=True)

    # --- arsiv listesi (delist olanlar dahil, onceki calismadan) ---
    eski = json.load(open(ESKI_EVREN))
    arsiv_tum = set(eski["tum_usdt"])
    print(f"arsiv USDT paritesi (delist dahil): {len(arsiv_tum)}", flush=True)

    aday = sorted(arsiv_tum | set(canli_usdt))
    print(f"birlesik aday: {len(aday)}", flush=True)

    # --- bilinen varlik kumesi: exchangeInfo base'leri + arsiv base'leri ---
    # arsiv base'i = sembolden "USDT" sonekini at
    arsiv_base = {s[:-4] for s in arsiv_tum if s.endswith("USDT")}
    bilinen_varlik = tum_base | arsiv_base

    tut, at = [], []
    korunan_sonekli = []      # sonek tasiyip da KORUNANLAR (denetim icin)

    for sym in aday:
        if not sym.endswith("USDT"):
            at.append((sym, "USDT paritesi degil")); continue
        base = canli_usdt.get(sym, {}).get("base") or sym[:-4]
        canli = sym in canli_usdt and canli_usdt[sym]["durum"] == "TRADING" \
                and canli_usdt[sym]["spot"]
        izin = set(canli_usdt.get(sym, {}).get("izin") or [])

        if TOKENIZE_HISSE_IZNI in izin:
            at.append((sym, f"tokenize hisse/ETF ({TOKENIZE_HISSE_IZNI} izni)")); continue
        if "LEVERAGED" in izin:
            at.append((sym, "exchangeInfo LEVERAGED izni")); continue
        if base in STABLE:
            at.append((sym, "stablecoin (acik liste)")); continue
        if base in FIAT:
            at.append((sym, "fiat (acik liste)")); continue

        # leveraged token: sonek + onek gercek varlik + bugun SPOT'ta YOK
        lev = False
        for sk in SONEK:
            if base.endswith(sk) and len(base) > len(sk) + 1:
                onek = base[: -len(sk)]
                if onek in bilinen_varlik and not canli:
                    lev = True
                    at.append((sym, f"leveraged token (onek '{onek}' gercek varlik, "
                                    f"bugun SPOT'ta yok)"))
                break
        if lev:
            continue

        # sonek tasiyor ama leveraged sayilmadi -> kayda gec
        for sk in SONEK:
            if base.endswith(sk) and len(base) > len(sk) + 1:
                onek = base[: -len(sk)]
                korunan_sonekli.append({
                    "sembol": sym, "base": base, "sonek": sk, "onek": onek,
                    "onek_varlik_mi": onek in bilinen_varlik,
                    "bugun_spot": canli,
                })
                break

        tut.append(sym)

    print(f"\nTUTULAN: {len(tut)}   ELENEN: {len(at)}", flush=True)
    print(f"sonek tasiyip KORUNAN: {len(korunan_sonekli)}", flush=True)
    for k in korunan_sonekli:
        print(f"  KORUNDU {k['sembol']:14s} base={k['base']:10s} sonek={k['sonek']:5s} "
              f"onek={k['onek']:8s} onek_varlik={k['onek_varlik_mi']} spot={k['bugun_spot']}",
              flush=True)

    print("\n--- ELENENLER (sebep bazinda) ---", flush=True)
    from collections import defaultdict
    grup = defaultdict(list)
    for s, sebep in at:
        grup[sebep.split("(")[0].strip()].append(s)
    for sebep, liste in sorted(grup.items()):
        print(f"  {sebep}: {len(liste)}", flush=True)
        print(f"     {', '.join(sorted(liste))}", flush=True)

    cikti = {
        "olusturuldu": "2026-10-01",
        "kaynak": ["data-api.binance.vision/exchangeInfo",
                   "veri/binance_evren_delist_dahil.json (arsiv, delist dahil)"],
        "kural": {
            "quote": "USDT",
            "stablecoin_listesi": sorted(STABLE),
            "fiat_listesi": sorted(FIAT),
            "leveraged_kurali": "base UP/DOWN/BULL/BEAR ile bitiyor VE onek "
                                "gercek Binance varligi VE bugun SPOT'ta islem "
                                "gormuyor -> leveraged. Aksi halde KORUNUR.",
            "tokenize_hisse_kurali": f"exchangeInfo permissionSets icinde "
                                     f"{TOKENIZE_HISSE_IZNI} -> tokenize hisse/ETF, elenir",
            "substring_korlemesi": "YOK",
        },
        "tutulan": tut,
        "elenen": [{"sembol": s, "sebep": r} for s, r in at],
        "sonek_tasiyip_korunan": korunan_sonekli,
        "canli_mi": {s: (s in canli_usdt and canli_usdt[s]["durum"] == "TRADING")
                     for s in tut},
    }
    yol = os.path.join(VERI, "evren_1g.json")
    os.makedirs(VERI, exist_ok=True)
    json.dump(cikti, open(yol, "w"), indent=1)
    print(f"\nkaydedildi: {yol}", flush=True)


if __name__ == "__main__":
    main()
