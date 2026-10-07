# -*- coding: utf-8 -*-
"""StochRSI çoklu zaman dilimi sinyal sistemi (1h / 4h / 1d). Emir göndermez.

Kurallar: "StochRSI Çoklu Zaman Dilimi Sinyal Sistemi — Uygulama Spesifikasyonu
(v3, 2026-10-02)". Bölüm numaraları (§) o belgeye aittir. Üç parça:
  1. Dip alımı (§4–§7)          2. Yükselişte al (§8)
  3. Piyasa genişliği filtresi (§9, Ek A'daki 74 sembol; yalnız dip alımını kapatır)
Kurallar her sembolde aynıdır; taranan evren evren_kurallari modülünden gelir.
Her sembolde aynı anda tek pozisyon (dip ya da trend, §10).
Kod, belgenin §12 doğrulama değerlerini birebir üretir.

Ayrı modüldür; spot_opportunity_scanner yalnızca saatlik döngüyü başlatır.
Mevcut v11 / TSI+BB mantığına ve panelin çıkış kurallarına dokunmaz.

Panel bağlantısı:
  alım  -> POST /api/signal          (sig_type="stochrsi_mtf", source="stochrsi-mtf")
  satış -> POST /api/position-closed (source filtreli; kapanışı panel DEĞİL bu modül verir)

Durum: her koşuda her coinin işlem geçmişi SIM_BASLA'dan yeniden hesaplanır
(deterministik). Durum dosyası yalnız "neyi zaten gönderdim" bilgisini tutar.
Mumlar diskte önbelleklenir; her saat yalnız yeni kapanan mumlar çekilir.
"""
from __future__ import annotations

import bisect
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import numpy as np
import requests
from numpy.lib.stride_tricks import sliding_window_view as _pencere

import evren_kurallari as EK

SISTEM_ADI = "STOCHRSI_MTF"
SURUM = "v3-2026-10-02"
SIG_TYPE = "stochrsi_mtf"
KAYNAK = "stochrsi-mtf"

H = 3_600_000
ARALIK_MS = {"1h": H, "4h": 4 * H, "1d": 24 * H}


def _ms(y, a, g, s=0):
    return int(datetime(y, a, g, s, tzinfo=timezone.utc).timestamp() * 1000)


# §1 — veri başlangıçları (testte kullanılanlarla aynı; özyinelemeli göstergeler)
VERI_BASLA = {"1h": _ms(2025, 10, 1), "4h": _ms(2025, 6, 1), "1d": _ms(2024, 1, 1)}
# §1 — önerilen en az geçmiş 1h 2.000 / 4h 1.500 / 1d 600 mum. Zorunlu değildir:
# geçmişi kısa coin elindeki veriyle hesaplanır (durumda "kisa_gecmis" olarak sayılır).
ONERILEN_MUM = {"1h": 2000, "4h": 1500, "1d": 600}
# §12 — başlangıç durumu: pozisyon yok, son_çıkış_zamanı = 2025-12-31 21:00 UTC.
SIM_BASLA = _ms(2025, 12, 31, 21)
GUN = 24 * H
CANLI_MUM_N = 300            # §1 — MACD filtreleri: son 300 kapanmış mum + canlı mum

ESIK_ALIM_H4 = 20.0
ESIK_ALIM_G20, ESIK_ALIM_G40 = 20.0, 40.0
SATIS_NORMAL, SATIS_KORUMA, SATIS_GUNLUK = 95.0, 80.0, 70.0
PENCERE_SAAT = 72
BIRLESIM_SAAT = 24
CIFT_SAAT = 24
MACD_ACIKLIK_MAX = 5.0       # %
KORUMA = 1.05                # +%5 -> t5
ZARAR = 0.95                 # -%5
KOMISYON = 0.001             # her bacak

# §8 — yükselişte al
TREND_GUN = 20               # önceki 20 günlük kapanışın en yükseği
TREND_EMA_HIZLI, TREND_EMA_YAVAS = 20, 50
TREND_ZARAR = 0.90           # −%10

# §9 — piyasa genişliği (Ek A; panelin taradığı listeden BAĞIMSIZ, sabit)
GENISLIK_ESIK = 85.0         # >= 85 -> dip alımı yok
GENISLIK_EMA = 50
GENISLIK_ILK_INDEKS = 60     # sembol kendi 61. günlük mumundan itibaren sayılır
GENISLIK_BASLA = _ms(2019, 6, 1)

# §6 Filtre 4 / 5 (v3.1) — yalnız dip alımına uygulanır; canlı mum kullanılmaz
EGIM_EMA, EGIM_GERI, EGIM_ESIK = 50, 5, -0.93      # coin 4h EMA50, 5 mum önceye göre %, < −0,93 -> yok
BTC_RSI_ESIK = 50.0                                 # BTCUSDT 4h RSI(14) < 50 -> yok
EK_A = ("BTC ETH SOL ZEC NEAR XRP QNT SUI MOVR BNB UNI DOGE WLD ENA AAVE AVAX ADA PUMP LINK HYPE "
        "PEPE TAO VTHO TRX LTC ZRO ONDO FET HBAR TRUMP ALICE MEGA NOM NIGHT XLM PENGU BCH GTC 牛来 MARSCOIN "
        "FIL ARB ASTER DOT GRAM SCR XPL DASH SYN JASMY APT TIA OP POL HEI AR ICP ACE ARK INJ "
        "MUBARAK OPN SEI STX ETHFI SUPER DEXE VIRTUAL ALGO WLFI MORPHO ONE DUSK VET").split()

BASE_URLS = ("https://data-api.binance.vision", "https://api.binance.com", "https://api1.binance.com")
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Botum-StochRSI-MTF/1.0"})

PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "").rstrip("/")
PORTFOLIO_TOKEN = os.getenv("PORTFOLIO_TOKEN", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_THREAD_ID = int(os.getenv("STOCHRSI_MTF_THREAD_ID", os.getenv("SIGNAL_THREAD_ID", "2")))
STATE_FILE = os.getenv("STOCHRSI_MTF_STATE_FILE", "/tmp/stochrsi_mtf_state.json")
CACHE_DIR = os.getenv("STOCHRSI_MTF_CACHE_DIR", "/tmp/stochrsi_mtf_mumlar")
ISCI = max(1, min(8, int(os.getenv("STOCHRSI_MTF_WORKERS", "4"))))
TR_TZ = timezone(timedelta(hours=3))

durum = {"status": "BOOT", "surum": SURUM, "son_kosu": None, "evren": 0, "taranan": 0,
         "kisa_gecmis": 0, "acik_pozisyon": [], "hata": 0, "sure_sn": None, "son_hata": None,
         "genislik": None}


# ─── VERİ ────────────────────────────────────────────────────────────────────
def _get(path, params=None):
    son = None
    for n in range(4):
        for base in BASE_URLS:
            try:
                r = HTTP.get(base + path, params=params or {}, timeout=20)
                if r.status_code in (418, 429):
                    son = RuntimeError(f"rate-limit {r.status_code}")
                    time.sleep(2 * (n + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                son = exc
        time.sleep(min(5.0, 0.5 * 2 ** n))
    raise RuntimeError(f"Binance {path}: {son}")


def evren():
    """EVREN_KURALLARI.md — ortak evren_kurallari modülünden. {sembol: {"tick", "min_notional", ...}}."""
    return EK.kripto_evreni(EK.exchange_info_getir(HTTP))[0]


def mumlar(sembol, aralik, simdi_ms=None, onbellek=True, baslangic=None, etiket=""):
    """§1 — yalnız kapanmış mumlar. Satırlar: [açılış, o, h, l, c, KAPANIŞ(=açılış+aralık)].
    Diskteki önbellekten devam eder; yalnız yeni mumlar çekilir."""
    simdi_ms = simdi_ms or int(time.time() * 1000)
    yol = os.path.join(CACHE_DIR, f"{sembol}_{aralik}{etiket}.npy")
    eski = None
    if onbellek and os.path.exists(yol):
        try:
            eski = np.load(yol)
        except Exception:
            eski = None
    ilk = VERI_BASLA[aralik] if baslangic is None else baslangic
    cur = int(eski[-1, 0]) + ARALIK_MS[aralik] if eski is not None and len(eski) else ilk
    yeni = []
    while cur + ARALIK_MS[aralik] <= simdi_ms:
        rows = _get("/api/v3/klines", {"symbol": sembol, "interval": aralik, "startTime": cur, "limit": 1000})
        if not rows:
            break
        yeni += [[float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in rows]
        cur = int(rows[-1][0]) + 1
        if len(rows) < 1000:
            break
    a = np.array(yeni, dtype=float).reshape(-1, 5)
    a = np.c_[a, a[:, 0] + ARALIK_MS[aralik]] if len(a) else np.zeros((0, 6))
    a = a[a[:, 5] <= simdi_ms]
    if eski is not None and len(eski):
        a = np.vstack([eski, a[a[:, 0] > eski[-1, 0]]])
        a = a[a[:, 5] <= simdi_ms]
    if onbellek and len(a):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            np.save(yol + ".tmp.npy", a)
            os.replace(yol + ".tmp.npy", yol)
        except Exception:
            pass
    return a


# ─── §2 GÖSTERGELER (TradingView ile aynı) ──────────────────────────────────
def rsi_wilder(c, n=14):
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    out[n] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    for i in range(n + 1, len(c)):
        au = (au * (n - 1) + up[i - 1]) / n
        ad = (ad * (n - 1) + dn[i - 1]) / n
        out[i] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    return out


def _yuvarlan(x, n, f):
    """Penceresi tamamen geçerli (NaN'sız) barlarda f(pencere); diğerleri NaN."""
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    w = _pencere(x, n)
    ok = ~np.isnan(w).any(axis=1)
    out[n - 1:][ok] = f(w[ok], axis=1)
    return out


def _sma(x, n):
    return _yuvarlan(x, n, np.mean)


def stoch_rsi(r, n=14):
    hi, lo = _yuvarlan(r, n, np.max), _yuvarlan(r, n, np.min)
    with np.errstate(invalid="ignore", divide="ignore"):
        st = 100 * (r - lo) / (hi - lo)
    for i in np.flatnonzero(hi == lo):          # max = min -> bir önceki stoch
        st[i] = st[i - 1] if i > 0 else np.nan
    hizli = _sma(st, 3)
    return hizli, _sma(hizli, 3)


def ema_tv(x, n):
    """İlk n geçerli değerin basit ortalamasıyla başlar, sonra α = 2/(n+1)."""
    out = np.full(len(x), np.nan)
    gecerli = np.flatnonzero(~np.isnan(x))
    if len(gecerli) < n:
        return out
    b = gecerli[0]
    out[b + n - 1] = x[b:b + n].mean()
    a = 2 / (n + 1)
    for i in range(b + n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def macd(c):
    m = ema_tv(c, 12) - ema_tv(c, 26)
    s = ema_tv(m, 9)
    return m, s, m - s


def williams(h, l, c, n=14):
    """§2 — `−100 × (HH14 − kapanış) / (HH14 − LL14)`, HH = LL ise −50. Sonuç 9 ondalığa
    yuvarlanır; tam −75 / −100 olması gereken değer kayan nokta hatasıyla sınırın yanlış
    tarafına düşmez."""
    hh, ll = _yuvarlan(h, n, np.max), _yuvarlan(l, n, np.min)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.round(np.where(hh == ll, -50.0, -100 * (hh - c) / (hh - ll)), 9)


def dusuk_tepe(h, r):
    out = np.zeros(len(h), bool)
    if len(h) <= 20:
        return out
    tepe = _yuvarlan(h, 20, np.max)                      # max(yüksek[i−19..i])
    w = _pencere(r, 20)[:-1]                             # rsi[i−20..i−1], i = 20..
    with np.errstate(invalid="ignore"):
        hepsi_nan = np.isnan(w).all(axis=1)
        rmax = np.where(hepsi_nan, np.nan, np.nanmax(np.where(np.isnan(w), -np.inf, w), axis=1))
        out[20:] = (~hepsi_nan) & ~np.isnan(r[20:]) & (h[20:] >= 0.995 * tepe[20:]) & (r[20:] < rmax)
    return out


def gostergeler(a):
    h, l, c = a[:, 2], a[:, 3], a[:, 4]
    r = rsi_wilder(c)
    k, d = stoch_rsi(r)
    _, _, hist = macd(c)
    return {"t": a[:, 5], "h": h, "l": l, "c": c, "rsi": r, "k": k, "d": d, "hist": hist,
            "wr": williams(h, l, c), "dt": dusuk_tepe(h, r)}


# ─── §3–5 OLAYLAR ────────────────────────────────────────────────────────────
def _yukari(g, c):
    return c >= 1 and g["k"][c - 1] <= g["d"][c - 1] and g["k"][c] > g["d"][c]


def _asagi(g, c):
    return c >= 1 and g["k"][c - 1] >= g["d"][c - 1] and g["k"][c] < g["d"][c]


def _w(dizi, c, e):
    return dizi[c - 1:e + 1]


def _abc(g, c, e):
    """§3 — alım için 3 şart, W(c,e) içinde herhangi bir barda."""
    A = np.any(_w(g["rsi"], c, e) > 30)
    B = np.any(_w(g["hist"], c, e) < 0.05)
    wr = _w(g["wr"], c, e)
    C = np.any((wr >= -100) & (wr <= -75))
    return int(A) + int(B) + int(C)


def _pencereli(g, c, sart):
    """§3 — önce e=c, sağlanmazsa ve c+1 kapanmışsa e=c+1. Döner: e ya da None."""
    for e in (c, c + 1):
        if e >= len(g["c"]):
            break
        if sart(e):
            return e
    return None


def _kesisimler(g, yon):
    k, d = g["k"], g["d"]
    with np.errstate(invalid="ignore"):
        if yon > 0:
            m = (k[:-1] <= d[:-1]) & (k[1:] > d[1:])
        else:
            m = (k[:-1] >= d[:-1]) & (k[1:] < d[1:])
    return np.flatnonzero(m) + 1


def h1_alim(g):
    k, d, r, hs, wr = g["k"], g["d"], g["rsi"], g["hist"], g["wr"]
    yuk = np.zeros(len(k), bool)
    yuk[_kesisimler(g, +1)] = True
    with np.errstate(invalid="ignore"):
        n = (r < 30).astype(int) + (hs < 0.05).astype(int) + ((wr >= -100) & (wr <= -75)).astype(int)
        m = (k < 20) & (d < 20) & ((np.abs(k - d) <= 3) | yuk) & (n >= 2)
    m[0] = False
    return list(g["t"][m])


def mtf_alim(g, esik):
    """H4_ALIM (4h, eşik 20) ve G_ALIM20/40 (1d)."""
    out = []
    for c in _kesisimler(g, +1):
        e = _pencereli(g, c, lambda e: np.any(_w(g["k"], c, e) < esik) and _abc(g, c, e) >= 2)
        if e is not None:
            out.append(g["t"][e])
    return out


def h1_satis(g, esik):
    out = []
    for c in _kesisimler(g, -1):
        if g["k"][c] > esik and g["hist"][c] > 0 and g["hist"][c] < g["hist"][c - 1] and g["dt"][c]:
            out.append((g["t"][c], g["c"][c]))
    return out


def _var(g, c, e, f):
    return any(f(j) for j in range(max(c - 1, 1), e + 1))


def h4_satis(g, esik):
    out = []
    for c in _kesisimler(g, -1):
        def sart(e):
            if not np.any(_w(g["k"], c, e) > esik):
                return False
            n = (_var(g, c, e, lambda j: g["hist"][j] < g["hist"][j - 1])
                 + _var(g, c, e, lambda j: g["rsi"][j] < g["rsi"][j - 1])
                 + _var(g, c, e, lambda j: g["wr"][j - 1] >= -20 and g["wr"][j] < -20)
                 + _var(g, c, e, lambda j: bool(g["dt"][j])))
            return n >= 2
        e = _pencereli(g, c, sart)
        if e is not None:
            out.append((g["t"][e], g["c"][e]))
    return out


def g_satis(g):
    out = []
    for c in _kesisimler(g, -1):
        e = _pencereli(g, c, lambda e: np.any(_w(g["k"], c, e) > SATIS_GUNLUK)
                       and _var(g, c, e, lambda j: g["hist"][j] < g["hist"][j - 1])
                       and _var(g, c, e, lambda j: g["rsi"][j] < g["rsi"][j - 1]))
        if e is not None:
            out.append((g["t"][e], g["c"][e]))
    return out


def satis_cifti(s1, s4, sg):
    """§5 — farklı zaman diliminden önceki bir olayla en fazla 24 saat arayla eşleşen olay."""
    ol = sorted([(t, p, "1h") for t, p in s1] + [(t, p, "4h") for t, p in s4] + [(t, p, "1d") for t, p in sg],
                key=lambda z: z[0])
    out, gorulen = [], set()
    for i, (t, p, tf) in enumerate(ol):
        for t2, _, tf2 in ol[:i]:
            if tf2 != tf and 0 <= t - t2 <= CIFT_SAAT * H:
                if t not in gorulen:
                    out.append({"t": t, "fiyat": p, "tf": f"{tf2} + {tf}"})
                    gorulen.add(t)
                break
    return out


# ─── §6 FİLTRELER (canlı mum) ────────────────────────────────────────────────
def _canli(a_ust, a1, h_ms, periyot):
    kap = a_ust[a_ust[:, 5] <= h_ms][-CANLI_MUM_N:]
    bas = (h_ms // periyot) * periyot
    p = a1[(a1[:, 0] >= bas) & (a1[:, 5] <= h_ms)]
    if len(p):
        kap = np.vstack([kap, [bas, p[0, 1], p[:, 2].max(), p[:, 3].min(), p[-1, 4], bas + periyot]])
    return kap


def filtreler(a1, a4, ag, h_ms, fiyat):
    _, _, hg = macd(_canli(ag, a1, h_ms, 24 * H)[:, 4])
    m4, s4, _ = macd(_canli(a4, a1, h_ms, 4 * H)[:, 4])
    aciklik = hg[-1] / fiyat * 100
    return {"gunluk_macd_acikligi_%": round(float(aciklik), 3), "f1": bool(abs(aciklik) <= MACD_ACIKLIK_MAX),
            "4h_macd": float(m4[-1]), "4h_sinyal": float(s4[-1]), "f2": bool(m4[-1] > s4[-1])}


# ─── §9 PİYASA GENİŞLİĞİ ─────────────────────────────────────────────────────
def genislik_hesapla(gunlukler):
    """§9.2 — {sembol: 1d mumları} -> (kapanış zamanları, n, alt, genişlik %), zamana göre sıralı."""
    sayac = {}
    for a in gunlukler.values():
        if len(a) <= GENISLIK_ILK_INDEKS:
            continue
        e50 = ema_tv(a[:, 4], GENISLIK_EMA)
        for j in range(GENISLIK_ILK_INDEKS, len(a)):
            x = sayac.setdefault(float(a[j, 5]), [0, 0])
            x[0] += 1
            x[1] += int(a[j, 4] < e50[j])
    t = np.array(sorted(sayac), dtype=float)
    n = np.array([sayac[k][0] for k in t], dtype=int)
    alt = np.array([sayac[k][1] for k in t], dtype=int)
    return t, n, alt, 100.0 * alt / np.maximum(n, 1)


def genislik_verisi(simdi_ms=None, onbellek=True):
    """Ek A'daki sembollerin 1d mumları (2019-06-01 ya da listelenme gününden).
    Bir sembol alınamazsa tur DÜŞMEZ: diskteki önbelleği varsa o kullanılır (son mumu eski
    olduğu için o sembol o gün sayılmaz, §9.2), yoksa sembol atlanır. Alınamayanlar
    GENISLIK_ALINAMAYAN'a yazılır."""
    simdi_ms = simdi_ms or int(time.time() * 1000)

    def al(c):
        s = c + "USDT"
        try:
            return mumlar(s, "1d", simdi_ms, onbellek, GENISLIK_BASLA, "_genislik")
        except Exception as exc:
            print(f"[STOCHRSI-MTF] genişlik {s} alınamadı: {exc}", flush=True)
            yol = os.path.join(CACHE_DIR, f"{s}_1d_genislik.npy")
            if onbellek and os.path.exists(yol):
                try:
                    a = np.load(yol)
                    return a[a[:, 5] <= simdi_ms]
                except Exception:
                    pass
            return None

    out = {}
    GENISLIK_ALINAMAYAN.clear()
    with ThreadPoolExecutor(max_workers=ISCI) as havuz:
        for c, a in zip(EK_A, havuz.map(al, EK_A)):
            if a is None or not len(a) or a[-1, 5] < simdi_ms - GUN:
                GENISLIK_ALINAMAYAN.append(c)
            if a is not None and len(a):
                out[c + "USDT"] = a
    return genislik_hesapla(out)


GENISLIK_ALINAMAYAN = []      # son turda güncel günlük mumu alınamayan Ek A sembolleri


def genislik_an(genislik, h_ms):
    """§9.3 — kapanış zamanı <= h olan SON günlük değer: (n, alt, %) ya da None."""
    t, n, alt, pct = genislik
    k = int(np.searchsorted(t, h_ms, side="right")) - 1
    if k < 0:
        return None
    return int(n[k]), int(alt[k]), float(pct[k])


# ─── §6–8, §10 SİMÜLASYON (sembol başına tek pozisyon) ───────────────────────
def _arasi(liste, a, b):
    """a < t <= b olan olaylar."""
    return liste[bisect.bisect_right(liste, a):bisect.bisect_right(liste, b)]


def hesapla(a1, a4, ag, genislik=None, dip=True, trend=True, btc4=None):
    """Bir sembolün işlem listesi. genislik=None -> §9 filtresi kapalı (yalnız §12 aşamaları için).
    dip / trend: §12.6 aşamalarında parçaları ayrı ayrı açıp kapatmak için.
    btc4: BTCUSDT 4h mumları (§6 Filtre 5). Canlıda her zaman verilir."""
    g1, g4, gg = gostergeler(a1), gostergeler(a4), gostergeler(ag)
    ol = {"H1_ALIM": h1_alim(g1), "H4_ALIM": mtf_alim(g4, ESIK_ALIM_H4),
          "G_ALIM20": mtf_alim(gg, ESIK_ALIM_G20), "G_ALIM40": mtf_alim(gg, ESIK_ALIM_G40)}
    s1 = {e: h1_satis(g1, e) for e in (SATIS_NORMAL, SATIS_KORUMA)}
    s4 = {e: h4_satis(g4, e) for e in (SATIS_NORMAL, SATIS_KORUMA)}
    sg = g_satis(gg)
    cift = {e: satis_cifti(s1[e], s4[e], sg) for e in (SATIS_NORMAL, SATIS_KORUMA)}

    t1, hi1, lo1, c1 = a1[:, 5], a1[:, 2], a1[:, 3], a1[:, 4]
    gt, gc = ag[:, 5], ag[:, 4]
    ema20, ema50 = ema_tv(gc, TREND_EMA_HIZLI), ema_tv(gc, TREND_EMA_YAVAS)
    gun_indeks = {float(t): k for k, t in enumerate(gt)}
    t4, ema50_4h = a4[:, 5], ema_tv(a4[:, 4], EGIM_EMA)               # §6 Filtre 4
    if btc4 is not None and len(btc4):
        tb4, rsi_b4 = btc4[:, 5], rsi_wilder(btc4[:, 4])               # §6 Filtre 5

    islemler, son_cikis = [], float(SIM_BASLA)
    i = int(np.searchsorted(t1, son_cikis, side="right"))          # §10: h > son_çıkış_zamanı
    while i < len(t1):
        h, isl = t1[i], None
        # 1) dip alımı (§6)
        if dip:
            a = max(son_cikis, h - PENCERE_SAAT * H)
            x1, y4 = _arasi(ol["H1_ALIM"], a, h), _arasi(ol["H4_ALIM"], a, h)
            if x1 and y4:
                g40, g20 = _arasi(ol["G_ALIM40"], a, h), _arasi(ol["G_ALIM20"], a, h)
                yol = None
                if g40 and any(abs(x - y) <= BIRLESIM_SAAT * H for x in x1 for y in y4):
                    yol = "A"
                elif g20:
                    yol = "B"
                if yol:
                    gn = genislik_an(genislik, h) if genislik is not None else None
                    f3 = genislik is None or (gn is not None and gn[2] < GENISLIK_ESIK)
                    # Filtre 4 — kapanışı <= h olan son 4h mum j: 100 × (EMA50[j] / EMA50[j−5] − 1)
                    j = int(np.searchsorted(t4, h, side="right")) - 1
                    egim = (100 * (ema50_4h[j] / ema50_4h[j - EGIM_GERI] - 1)
                            if j >= EGIM_GERI and not np.isnan(ema50_4h[j - EGIM_GERI]) else np.nan)
                    f4 = bool(egim >= EGIM_ESIK)                         # hesaplanamazsa geçmez
                    # Filtre 5 — BTCUSDT'nin kapanışı <= h olan son 4h mumunun RSI(14)'ü
                    btc_rsi = np.nan
                    if btc4 is not None and len(btc4):
                        jb = int(np.searchsorted(tb4, h, side="right")) - 1
                        btc_rsi = rsi_b4[jb] if jb >= 0 else np.nan
                    f5 = btc4 is None or bool(btc_rsi >= BTC_RSI_ESIK)
                    if f3 and f4 and f5:
                        f = filtreler(a1, a4, ag, h, c1[i])
                        f.update({"coin_4h_ema50_egim_%": round(float(egim), 4),
                                  "btc_4h_rsi": None if np.isnan(btc_rsi) else round(float(btc_rsi), 2)})
                        if f["f1"] and f["f2"]:
                            isl = _cikis(i, t1, hi1, lo1, c1, cift)
                            isl.update({"tip": "dip", "yol": yol, "filtre": f,
                                        "genislik": None if gn is None else {"n": gn[0], "alt": gn[1], "yuzde": round(gn[2], 1)},
                                        "olaylar": {"H1_ALIM": x1, "H4_ALIM": y4, "G_ALIM40": g40, "G_ALIM20": g20}})
        # 2) dip alımı yoksa ve günlük kapanışsa yükselişte al (§8.1)
        if isl is None and trend and h % GUN == 0:
            d = gun_indeks.get(float(h))
            if d is not None and d >= TREND_GUN and not np.isnan(ema50[d]):
                onceki = float(gc[d - TREND_GUN:d].max())
                if gc[d] > onceki and ema20[d] > ema50[d]:
                    isl = _cikis_trend(i, t1, lo1, c1, gt, gc, ema20)
                    isl.update({"tip": "trend", "yol": "trend",
                                "trend": {"kapanis": float(gc[d]), "onceki_20_en_yuksek": onceki,
                                          "ema20": float(ema20[d]), "ema50": float(ema50[d])}})
        if isl is not None:
            isl.update({"alim_t": h, "alim_fiyat": float(c1[i])})
            islemler.append(isl)
            if isl["cikis_t"] is None:
                break
            son_cikis = isl["cikis_t"]
            i = int(np.searchsorted(t1, son_cikis, side="right"))  # aynı saatte yeni alım yok
            continue
        i += 1
    return islemler, ol, cift


def _sonuc(cik, P):
    acik = not np.isfinite(cik[0])
    net = None if acik else (cik[1] * (1 - KOMISYON)) / (P * (1 + KOMISYON)) - 1
    return {"cikis_t": None if acik else cik[0], "cikis_fiyat": None if acik else float(cik[1]),
            "neden": None if acik else cik[2], "net": net, "net_%": None if acik else round(net * 100, 2)}


def _cikis(i, t1, hi1, lo1, c1, cift):
    """§7 — dip pozisyonu satışı."""
    T, P = t1[i], float(c1[i])
    c95 = [c for c in cift[SATIS_NORMAL] if c["t"] > T]
    sinir95 = c95[0]["t"] if c95 else np.inf
    t5 = None
    for j in range(i + 1, len(t1)):
        if t1[j] > sinir95:
            break
        if hi1[j] >= KORUMA * P:
            t5 = (j, t1[j])
            break
    adaylar = []
    if c95:
        adaylar.append((c95[0]["t"], c95[0]["fiyat"], f"satis_cifti_95 ({c95[0]['tf']})"))
    if t5:
        c80 = [c for c in cift[SATIS_KORUMA] if c["t"] > T and c["t"] >= t5[1]]
        if c80:
            adaylar.append((c80[0]["t"], c80[0]["fiyat"], f"satis_cifti_80 ({c80[0]['tf']})"))
    cik = min(adaylar, key=lambda z: z[0]) if adaylar else (np.inf, None, None)
    if t5:
        for j in range(t5[0] + 1, len(t1)):
            if t1[j] >= cik[0]:
                break
            if lo1[j] <= P:
                cik = (t1[j], P, "basa_bas")
                break
    for j in range(i + 1, len(t1)):
        if t1[j] >= cik[0]:
            break
        if lo1[j] <= ZARAR * P:
            cik = (t1[j], ZARAR * P, "zarar_siniri_-5")
            break
    return {"t5": None if not t5 else t5[1], **_sonuc(cik, P)}


def _cikis_trend(i, t1, lo1, c1, gt, gc, ema20):
    """§8.2 — trend pozisyonu satışı: EMA20 altı günlük kapanış ya da −%10."""
    T, P = t1[i], float(c1[i])
    cik = (np.inf, None, None)
    for k in range(int(np.searchsorted(gt, T, side="right")), len(gt)):
        if not np.isnan(ema20[k]) and gc[k] < ema20[k]:
            cik = (gt[k], float(gc[k]), "ema20_alti")
            break
    for j in range(i + 1, len(t1)):
        if t1[j] >= cik[0]:
            break
        if lo1[j] <= TREND_ZARAR * P:
            cik = (t1[j], TREND_ZARAR * P, "zarar_siniri_-10")
            break
    return {"t5": None, **_sonuc(cik, P)}


def _btc4_verisi(simdi_ms):
    """§1 — BTCUSDT 4h mumları (Filtre 5). Alınamazsa önbellek; o da yoksa boş dizi ->
    Filtre 5 hesaplanamaz ve o turda dip alımı yapılmaz (trend ve satışlar etkilenmez)."""
    try:
        return mumlar("BTCUSDT", "4h", simdi_ms)
    except Exception as exc:
        print(f"[STOCHRSI-MTF] BTC 4h alınamadı: {exc}", flush=True)
        yol = os.path.join(CACHE_DIR, "BTCUSDT_4h.npy")
        try:
            a = np.load(yol)
            return a[a[:, 5] <= simdi_ms]
        except Exception:
            return np.zeros((0, 6))


def coin_hesapla(sembol, genislik, simdi_ms=None, onbellek=True, btc4=None):
    """Bir sembolün bütün işlem geçmişi + son kapanmış 1h zamanı + önerilen geçmiş var mı."""
    a = {iv: mumlar(sembol, iv, simdi_ms, onbellek) for iv in ("1h", "4h", "1d")}
    if not len(a["1h"]):
        return [], None, False
    tam = all(len(a[iv]) >= ONERILEN_MUM[iv] for iv in a)
    return hesapla(a["1h"], a["4h"], a["1d"], genislik, btc4=btc4)[0], float(a["1h"][-1, 5]), tam


# ─── PANEL / TELEGRAM ────────────────────────────────────────────────────────
def _utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def _tr(ms):
    return _utc(ms).astimezone(TR_TZ).strftime("%d.%m %H:%M")


def _post(yol, govde):
    if not PORTFOLIO_URL:
        return None
    hd = {"Content-Type": "application/json"}
    if PORTFOLIO_TOKEN:
        hd["Authorization"] = f"Bearer {PORTFOLIO_TOKEN}"
    try:
        return HTTP.post(f"{PORTFOLIO_URL}{yol}", json=govde, headers=hd, timeout=15).status_code
    except Exception as exc:
        print(f"[STOCHRSI-MTF] panel {yol}: {exc}", flush=True)
        return None


def _telegram(metin):
    if not (TELEGRAM_ENABLED and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return False
    pl = {"chat_id": TELEGRAM_CHAT_ID, "text": metin}
    if TELEGRAM_THREAD_ID:
        pl["message_thread_id"] = TELEGRAM_THREAD_ID
    try:
        return HTTP.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=pl, timeout=15).ok
    except Exception:
        return False


def _ondalik(tick):
    if not tick or tick <= 0:
        return 8
    return max(0, min(10, int(round(-np.log10(tick)))))


NEDEN_ETIKET = {"basa_bas": "başa baş", "zarar_siniri_-5": "−%5", "zarar_siniri_-10": "−%10",
                "ema20_alti": "EMA20 altı"}


def _neden_yazi(neden):
    if neden and neden.startswith("satis_cifti"):
        return "satış çifti" + neden[len("satis_cifti_95"):]
    return NEDEN_ETIKET.get(neden, neden)


def _alim_govdesi(sembol, bilgi, isl):
    P = isl["alim_fiyat"]
    tick = bilgi.get("tick") or 0
    od = _ondalik(tick)
    ortak = {"symbol": sembol.replace("USDT", "/USDT"), "entry": P, "signal_price": P,
             "limit_price": round(P + 3 * tick, od),                    # kapanış + 3 × tickSize
             "tp2": None, "tp3": None, "sig_type": SIG_TYPE, "source": KAYNAK, "phase": "sinyal",
             "system": SISTEM_ADI, "system_version": SURUM, "pozisyon_tipi": isl["tip"],
             "tick_size": tick, "min_notional": bilgi.get("min_notional"),
             "alim_zamani_utc": _utc(isl["alim_t"]).isoformat()}
    if isl["tip"] == "trend":                                           # §8 / §11 kayıt
        return {**ortak, "stop": round(TREND_ZARAR * P, od + 1), "tp1": P, "sub_type": "trend",
                "trend": isl["trend"], "cikis_kurali": "EMA20 altı günlük kapanış · −%10 zarar sınırı"}
    ol = {k: [_utc(t).strftime("%Y-%m-%d %H:%M") for t in v] for k, v in isl["olaylar"].items()}
    return {**ortak, "stop": round(ZARAR * P, od + 1), "tp1": round(KORUMA * P, od + 1),
            "sub_type": f"dip · yol {isl['yol']}", "olaylar": ol, "filtreler": isl["filtre"],
            "genislik": isl.get("genislik"),
            "cikis_kurali": "satış çifti (95, +%5 sonrası 80) · +%5 sonrası başa baş · −%5 zarar sınırı"}


_kilit = threading.Lock()
ACIK = {}        # sembol -> açık pozisyon (dakikalık kontrol için; her saatlik turda yenilenir)


def _durum_oku():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _durum_yaz(d):
    try:
        os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception as exc:
        print(f"[STOCHRSI-MTF] durum yazılamadı: {exc}", flush=True)


def _satis_gonder(k, sembol, tip, neden, fiyat, net, t_ms):
    kod = _post("/api/position-closed", {"symbol": sembol.replace("USDT", "/USDT"), "source": KAYNAK,
                                         "reason": neden, "close_price": fiyat, "pnl_pct": net,
                                         "close_time_utc": _utc(t_ms).isoformat()})
    _telegram(f"#{sembol[:-4]} SATIŞ (StochRSI MTF · {tip}) — {_neden_yazi(neden)}\nFiyat: {fiyat:.6g} · "
              f"net %{net:+.2f}\nZaman: {_tr(t_ms)} TR")
    k["satis"] = kod in (200, 404) or not PORTFOLIO_URL
    print(f"[STOCHRSI-MTF] SATIŞ {sembol} {tip} {_utc(t_ms)} {neden} net {net}% panel={kod}", flush=True)


def _bildir(st, sembol, bilgi, islemler):
    """Bir sembolün işlemlerinden panele/Telegram'a gitmemiş olanları gönderir."""
    gonderildi = st.setdefault("gonderildi", {})
    bas = st["canli_baslangic"]
    coin = sembol[:-4]
    for isl in islemler:
        # Her olay KENDİ zamanına göre süzülür: durum dosyası silinip yeniden
        # başlarsa, öncesinde açılmış pozisyonun satışı yine de panele gider.
        if (isl["cikis_t"] or float("inf")) < bas:
            continue
        k = gonderildi.setdefault(f"{sembol}:{int(isl['alim_t'])}", {})
        P, tip = isl["alim_fiyat"], isl["tip"]
        if isl["alim_t"] < bas:
            k["alim"] = True
        if not k.get("alim"):
            kod = _post("/api/signal", _alim_govdesi(sembol, bilgi, isl))
            if tip == "trend":
                tr = isl["trend"]
                ek = (f"Önceki 20 gün en yüksek: {tr['onceki_20_en_yuksek']:.6g} · EMA20 {tr['ema20']:.6g} > "
                      f"EMA50 {tr['ema50']:.6g}\nZarar sınırı (−%10): {TREND_ZARAR * P:.6g} · satış: EMA20 altı kapanış")
            else:
                gn = isl.get("genislik") or {}
                ek = (f"Yol {isl['yol']} · genişlik %{gn.get('yuzde')} ({gn.get('alt')}/{gn.get('n')})\n"
                      f"Zarar sınırı (−%5): {ZARAR * P:.6g} · koruma eşiği (+%5): {KORUMA * P:.6g}")
            _telegram(f"#{coin} ALIM (StochRSI MTF · {tip})\nFiyat: {P}\nZaman: {_tr(isl['alim_t'])} TR\n{ek}")
            k["alim"] = kod in (200, 201, 409) or not PORTFOLIO_URL
            print(f"[STOCHRSI-MTF] ALIM {sembol} {tip} {_utc(isl['alim_t'])} @ {P} panel={kod}", flush=True)
        if isl["t5"] and isl["t5"] < bas:
            k["t5"] = True
        if isl["t5"] and not k.get("t5"):
            _telegram(f"#{coin} kâr koruma devrede (+%5)\n{_tr(isl['t5'])} TR — stop alış fiyatına ({P}) taşındı.")
            k["t5"] = True
        if isl["cikis_t"] is not None and not k.get("satis"):
            _satis_gonder(k, sembol, tip, isl["neden"], isl["cikis_fiyat"], isl["net_%"], isl["cikis_t"])


def _genislik_bildir(st, genislik):
    """§11 — günlük genişlik değeri ve dip alımlarının açık / kapalı durumu (günde bir kez)."""
    t, n, alt, pct = genislik
    if not len(t):
        return
    gun = int(t[-1])
    if st.get("genislik_bildirilen_gun") == gun:
        return
    acik = pct[-1] < GENISLIK_ESIK
    _telegram(f"StochRSI MTF — piyasa genişliği %{pct[-1]:.1f} ({int(alt[-1])}/{int(n[-1])} sembol EMA50 altında)\n"
              f"Dip alımları: {'AÇIK' if acik else 'KAPALI'} (eşik %{GENISLIK_ESIK:g}) · gün {_utc(gun):%d.%m.%Y}")
    st["genislik_bildirilen_gun"] = gun


def tur():
    """Bir saatlik koşu: genişliği güncelle, her sembolün geçmişini yeniden hesapla, yeni olayları bildir."""
    t0 = time.time()
    simdi = int(time.time() * 1000)
    genislik = genislik_verisi(simdi)                                   # §11.1 — önce genişlik
    btc4 = _btc4_verisi(simdi)                                          # §6 Filtre 5
    ev = evren()
    sonuc, hata = {}, 0
    with ThreadPoolExecutor(max_workers=ISCI) as havuz:
        isler = {havuz.submit(coin_hesapla, s, genislik, simdi, True, btc4): s for s in ev}
        for f in as_completed(isler):
            s = isler[f]
            try:
                sonuc[s] = f.result()
            except Exception as exc:
                hata += 1
                print(f"[STOCHRSI-MTF] {s}: {exc}", flush=True)
    with _kilit:
        st = _durum_oku()
        # İlk çalışmada geçmiş işlemler panele basılmaz; yalnız bu andan (2 saat payla) sonrası.
        st.setdefault("canli_baslangic", simdi - 2 * H)
        _genislik_bildir(st, genislik)
        for s in sorted(sonuc):
            _bildir(st, s, ev[s], sonuc[s][0])
        _durum_yaz(st)
        ACIK.clear()
        for s, (isl, son_saat, _) in sonuc.items():
            if isl and isl[-1]["cikis_t"] is None:
                x = isl[-1]
                ACIK[s] = {"anahtar": f"{s}:{int(x['alim_t'])}", "tip": x["tip"], "P": x["alim_fiyat"],
                           "alim_t": x["alim_t"], "t5": x["t5"], "son_saat": son_saat}
    kisa = sum(1 for r in sonuc.values() if not r[2])
    acik = [{"coin": s[:-4], "tip": v["tip"], "alim_utc": _utc(v["alim_t"]).isoformat(), "fiyat": v["P"],
             "t5": bool(v["t5"])} for s, v in sorted(ACIK.items())]
    gn = genislik_an(genislik, simdi)
    durum.update({"status": "RUNNING", "son_kosu": datetime.now(TR_TZ).isoformat(), "son_hata": None,
                  "evren": len(ev), "taranan": len(sonuc), "kisa_gecmis": kisa, "hata": hata,
                  "acik_pozisyon": acik, "sure_sn": round(time.time() - t0, 1),
                  # Değer hesaplanamasa da (ör. hiçbir sembol alınamadı) alınamayan listesi görünür.
                  "genislik": ({"n": None, "alt": None, "yuzde": None, "dip_alimi": "kapalı (genişlik yok)",
                                "alinamayan": list(GENISLIK_ALINAMAYAN)} if gn is None else
                               {"n": gn[0], "alt": gn[1], "yuzde": round(gn[2], 1),
                                "dip_alimi": "açık" if gn[2] < GENISLIK_ESIK else "kapalı",
                                "alinamayan": list(GENISLIK_ALINAMAYAN)})})
    print(f"[STOCHRSI-MTF] tur bitti: evren {len(ev)} · taranan {len(sonuc)} · önerilenden kısa geçmiş {kisa} · "
          f"hata {hata} · açık {len(acik)} · genişlik {durum['genislik']} · {time.time() - t0:.0f} sn", flush=True)


def dakika_kontrol():
    """§11 — pozisyon açıkken dakikalık fiyat kontrolü.
    Dip: başa baş (yalnız t5 kapanmış bir 1h mumda görüldüyse; §7.3 t5 mumundan SONRA) ve −%5.
         Aynı dakikada ikisi birden -> başa baş (§7.5: zarar sınırı ancak daha ERKENSE yerine geçer).
    Trend: yalnız −%10. EMA20 çıkışı yalnız günlük kapanışta, saatlik turda verilir.
    Son kapanmış 1h mumdan sonraki kapanmış 1m mumlara bakılır (öncesini saatlik tur işledi)."""
    simdi = int(time.time() * 1000)
    with _kilit:
        hedef = dict(ACIK)
    if not hedef:
        return

    def cek(sv):
        s, v = sv
        if not v["son_saat"]:
            return s, None
        try:
            return s, _get("/api/v3/klines", {"symbol": s, "interval": "1m", "startTime": int(v["son_saat"]), "limit": 1000})
        except Exception as exc:
            print(f"[STOCHRSI-MTF] dakika {s}: {exc}", flush=True)
            return s, None
    with ThreadPoolExecutor(max_workers=ISCI) as havuz:            # açık pozisyon sayısı yüzleri bulabilir
        mumlar_1m = dict(havuz.map(cek, hedef.items()))
    with _kilit:
        st = _durum_oku()
        gonderildi = st.setdefault("gonderildi", {})
        degisti = False
        for s, v in list(ACIK.items()):
            if ACIK.get(s) is not hedef.get(s):                     # arada saatlik tur yenilediyse atla
                continue
            k = gonderildi.setdefault(v["anahtar"], {})
            rows = mumlar_1m.get(s)
            if k.get("satis") or not rows:
                continue
            P = v["P"]
            for x in rows:
                kapanis = int(x[0]) + 60_000
                if kapanis > simdi:
                    break
                low = float(x[3])
                if v["tip"] == "trend":
                    if low > TREND_ZARAR * P:
                        continue
                    neden, fiyat = "zarar_siniri_-10", TREND_ZARAR * P
                elif v["t5"] and low <= P:
                    neden, fiyat = "basa_bas", P
                elif low <= ZARAR * P:
                    neden, fiyat = "zarar_siniri_-5", ZARAR * P
                else:
                    continue
                net = round(((fiyat * (1 - KOMISYON)) / (P * (1 + KOMISYON)) - 1) * 100, 2)
                _satis_gonder(k, s, v["tip"], neden, fiyat, net, kapanis)
                k["dakika"] = True
                ACIK.pop(s, None)
                degisti = True
                break
        if degisti:
            _durum_yaz(st)


def dongu():
    """Her saat HH:00:05 UTC tam tur (§11); arada her dakika açık pozisyon kontrolü."""
    sonraki = 0.0
    while True:
        if time.time() >= sonraki:
            try:
                tur()
            except Exception as exc:
                durum.update({"status": "ERROR", "son_hata": f"{type(exc).__name__}: {exc}"})
                print(f"[STOCHRSI-MTF] HATA {exc}", flush=True)
            simdi = time.time()
            sonraki = simdi - (simdi % 3600) + 3600 + 5
        else:
            try:
                dakika_kontrol()
            except Exception as exc:
                print(f"[STOCHRSI-MTF] dakika kontrol hatası: {exc}", flush=True)
        time.sleep(max(1.0, min(60.0, sonraki - time.time())))


def baslat():
    threading.Thread(target=dongu, daemon=True, name="stochrsi-mtf").start()
