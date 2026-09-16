#!/usr/bin/env python3
# =====================================================================
#  AYARLAR
# =====================================================================
BASLANGIC   = "01/01/2025"     # gg/aa/yyyy  (TR)
BITIS       = "01/10/2026"
EVREN_LIMIT = 0                # 0 = tum USDT spot evreni; 50 yazarsan en likit 50 coin
TARAMA_DK   = 15               # kac dakikada bir taransin — CANLI SISTEM 15 DK (900sn)
GUNLUK_MAX_SINYAL = 0          # 0 = sinirsiz (arastirma).  3 = canlidaki gibi (MAX_SIGNALS_PER_DAY)

# --- KURAL (ZEC 23.08.2026 09:00 ornegimden turetildi) ----------------
# 4 SAAT: trend GUCLU olsun ama StochRSI dipte olsun (= yukselen trendde geri cekilme)
K4_RSI_MIN      = 60.0     # 4H RSI bunun ustunde  (ZEC: 70.34)
K4_SRSI_MAX     = 15.0     # 4H StochRSI bunun altinda (ZEC: 2.41)
# 1 SAAT: giris zamanlamasi — osilatorler dipte
K1_RSI_MAX      = 55.0     # (ZEC: 48.57)
K1_SRSI_MAX     = 10.0     # (ZEC: 1.63)
K1_KDJ_J_MAX    = 15.0     # (ZEC: 7.12)
K1_WR_MAX       = -75.0    # (ZEC: -84.31)
K1_MACD_NEGATIF = True     # MACD histogrami negatif olsun (ZEC: -9.42)
# 15 DAKIKA: teyit
K15_RSI_MAX     = 50.0     # (ZEC: 33.00)
K15_SRSI_MAX    = 20.0     # (ZEC: 1.11)
K15_WR_MAX      = -70.0    # (ZEC: -76.83)
# --- CIKIS (canli portfolio_tracker kurallari) ------------------------
TRAIL_PCT       = 2.5
EXPIRE_H        = 24
KOMISYON        = 0.2
PARA            = 2500
AYNI_COIN_TEKRAR_SAAT = 24     # ayni coinde bu sure gecmeden yeni sinyal alma
# =====================================================================
"""DIP TARAMA — kullanicinin kendi alim mantigiyla SIFIRDAN sinyal uretir.

Mevcut spot_opportunity_scanner'a DOKUNMAZ. Ayri, bagimsiz bir tarama.

Fark: mevcut scanner "hareket baslamis mi" diye bakar (4H StochRSI medyani 73,
islemlerin %0'i 4H MA20 altinda). Bu tarama "yukselen trendde geri cekilme
bitmis mi" diye bakar — 4H guclu ama StochRSI dipte, 1H/15M osilatorler tukenmis.

Gostergeler ZEC 23.08.2026 09:00 ile BIREBIR dogrulandi (9 gostergenin 9'u).
Seviye mantigi (stop/tp1) scanner'in levels() fonksiyonuyla birebir ayni.

=====================================================================
CANLI SISTEMDEN FARKLAR — bilerek yapilan secimler, gizli degil
=====================================================================
  1. TARAMA SIKLIGI
     canli : SCAN_INTERVAL_SECONDS = 900  (15 dakika)
     burada: TARAMA_DK ayari, VARSAYILAN 15 (canliyla ayni)
     60 yaparsan saatin icinde olusan kurulumlarin 3/4'unu kacirirsin.

  2. GUNLUK SINYAL SINIRI
     canli : MAX_SIGNALS_PER_DAY = 3  (tum evren icin toplam)
     burada: GUNLUK_MAX_SINYAL, VARSAYILAN 0 = sinirsiz
     * 0  -> "bu kuralin kenari var mi" sorusunu olcer (daha cok veri, temiz istatistik)
     * 3  -> "canlida ne olurdu" sorusunu olcer (gunde en fazla 3 islem)
     Ikisi FARKLI sorular. Arastirma icin 0, dagitim karari icin 3.

  3. DERIN ANALIZ EDILEN COIN SAYISI
     canli : ucuz bir 1H on-eleme puaniyla en iyi PYTHON_TOP_N=96 parite secilir,
             sadece onlar derin analize girer
     burada: on-eleme YOK, evrendeki her parite taranir
     Yani bu tarama canlinin gormedigi adaylari da gorur. Kural canliya
     eklenecekse on-eleme de hesaba katilmali.

  4. KALITE ESIGI
     canli : FINAL_MIN_QUALITY = 72 (scanner'in kendi puani)
     burada: yok — kullanicinin kurali onun yerine geciyor

  5. AYNI COIN TEKRARI
     canli : watch state makinesi (WATCH_TTL_HOURS=18) + ayni sembolde acik
             pozisyon varsa yeni sinyal reddi
     burada: AYNI_COIN_TEKRAR_SAAT basit bekleme suresi (yaklasiklama)

  6. GIRIS FIYATI
     canli : /api/v3/ticker/price (anlik)
     burada: o ana kadar kapanmis son 15dk mumunun kapanisi (ileriye bakmamak icin)
=====================================================================
"""
import json, os, pickle, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import numpy as np

TR = timezone(timedelta(hours=3))
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]
IGNORED = {"USDT","USDC","BUSD","TUSD","DAI","PAX","HUSD","USDP","GUSD","FDUSD","EUR","TRY","GBP",
           "USD","BRL","RUB","AUD","XUSD","USD1","USDE","BFUSD","USDS","USDD","PYUSD","AEUR","EURI",
           "USTC","FRAX","LUSD","SUSD","USDX","CUSD","OUSD","MUSD","RLUSD","BIDR","IDRT","VAI",
           "PAXG","XAUT","WBTC","WETH","WBNB","BETH","BTCB","HBTC","U"}
KALDIRACLI = ("UP","DOWN","BULL","BEAR","2L","2S","3L","3S","5L","5S","10L","10S")
B_ISTISNA = {"BNB","DGB","TRB","CKB","SHIB","ARB","BB","YB"}
SURE = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}
CACHE = "dip_cache"


def api(path, params=None, deneme=3):
    q = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    err = None
    for host in HOSTS:
        for _ in range(deneme):
            try:
                with urllib.request.urlopen(f"{host}{path}?{q}" if q else f"{host}{path}", timeout=30) as r:
                    return json.loads(r.read())
            except Exception as e:
                err = e; time.sleep(0.4)
    raise RuntimeError(f"{path}: {type(err).__name__} {err}")


def evren():
    ex = api("/api/v3/exchangeInfo"); tk = api("/api/v3/ticker/24hr")
    hac = {x["symbol"]: float(x.get("quoteVolume", 0)) for x in tk if isinstance(x, dict)}
    out = []
    for it in ex.get("symbols", []):
        s, b = it.get("symbol", ""), it.get("baseAsset", "")
        if it.get("quoteAsset") != "USDT" or it.get("status") != "TRADING": continue
        if it.get("isSpotTradingAllowed") is False: continue
        if b in IGNORED or (b.endswith(KALDIRACLI) and b not in B_ISTISNA): continue
        out.append((s, hac.get(s, 0.0)))
    out.sort(key=lambda x: -x[1])
    return [s for s, _ in (out[:EVREN_LIMIT] if EVREN_LIMIT else out)]


def mumlar(sym, itv, bas, bit):
    os.makedirs(CACHE, exist_ok=True)
    yol = os.path.join(CACHE, f"{sym}_{itv}_{bas}_{bit}.pkl")
    if os.path.exists(yol):
        with open(yol, "rb") as f: return pickle.load(f)
    out, cur = [], bas - 300 * SURE[itv]        # gosterge isinmasi icin geriden basla
    while cur < bit:
        raw = api("/api/v3/klines", {"symbol": sym, "interval": itv,
                                     "startTime": int(cur), "endTime": int(bit), "limit": 1000})
        if not raw: break
        out += [(int(k[6]), float(k[2]), float(k[3]), float(k[4])) for k in raw]
        yeni = int(raw[-1][0]) + SURE[itv]
        if yeni <= cur or len(raw) < 1000: break
        cur = yeni; time.sleep(0.08)
    a = (np.array([r[0] for r in out], dtype=np.int64),
         np.array([r[1] for r in out], dtype=np.float64),
         np.array([r[2] for r in out], dtype=np.float64),
         np.array([r[3] for r in out], dtype=np.float64))
    with open(yol, "wb") as f: pickle.dump(a, f)
    return a


# ── gostergeler (ZEC ile birebir dogrulandi) ─────────────────────────
def _ema(v, n):
    a = 2.0 / (n + 1.0); o = np.empty_like(v); o[0] = v[0]
    for i in range(1, len(v)): o[i] = a * v[i] + (1 - a) * o[i - 1]
    return o


def _sma(v, n):
    c = np.cumsum(np.insert(v, 0, 0.0))
    o = (c[n:] - c[:-n]) / n
    bas = np.array([v[:i + 1].mean() for i in range(n - 1)])
    return np.concatenate([bas, o])


def _rsi(c, n=14):
    d = np.diff(c, prepend=c[0]); g = np.clip(d, 0, None); l = np.clip(-d, 0, None)
    o = np.full(len(c), np.nan)
    if len(c) <= n: return o
    ag = g[1:n + 1].mean(); al = l[1:n + 1].mean()
    o[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + l[i]) / n
        o[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return o


def _roll(v, n, fn):
    o = np.full(len(v), np.nan)
    for i in range(len(v)):
        w = v[max(0, i - n + 1):i + 1]
        w = w[~np.isnan(w)]
        if len(w): o[i] = fn(w)
    return o


def gostergeler(h, l, c):
    r = _rsi(c)
    lo = _roll(r, 14, np.min); hi = _roll(r, 14, np.max)
    rng = hi - lo
    ham = np.where(rng > 0, (r - lo) / np.where(rng > 0, rng, 1) * 100, 0.0)
    ham = np.nan_to_num(ham, nan=0.0)
    sk = _sma(ham, 3); sd = _sma(sk, 3)
    hh9 = _roll(h, 9, np.max); ll9 = _roll(l, 9, np.min)
    rsv = np.where(hh9 > ll9, (c - ll9) / np.where(hh9 > ll9, hh9 - ll9, 1) * 100, 50.0)
    K = np.empty(len(c)); D = np.empty(len(c)); K[0] = D[0] = 50.0
    for i in range(1, len(c)):
        K[i] = (2 / 3) * K[i - 1] + (1 / 3) * rsv[i]
        D[i] = (2 / 3) * D[i - 1] + (1 / 3) * K[i]
    J = 3 * K - 2 * D
    hh14 = _roll(h, 14, np.max); ll14 = _roll(l, 14, np.min)
    wr = np.where(hh14 > ll14, (hh14 - c) / np.where(hh14 > ll14, hh14 - ll14, 1) * -100, 0.0)
    dif = _ema(c, 12) - _ema(c, 26); dea = _ema(dif, 9)
    return dict(rsi=r, sk=sk, sd=sd, kdj_k=K, kdj_d=D, kdj_j=J, wr=wr, hist=dif - dea)


def swing_seviye(h, l, c, i, fiyat):
    """scanner levels(): 1H+4H swing dip/tepeler -> stop = destek*0.975, tp1 = ilk direnc >= +%2.5"""
    b = max(0, i - 79)
    H, L = h[b:i + 1], l[b:i + 1]
    tepe, dip = [], []
    for j in range(2, len(H) - 2):
        if H[j] >= H[j - 2:j + 3].max(): tepe.append(float(H[j]))
        if L[j] <= L[j - 2:j + 3].min(): dip.append(float(L[j]))
    p = float(c[i])
    return (sorted([v for v in dip[-8:] if v < p], reverse=True)[:4],
            sorted([v for v in tepe[-8:] if v > p])[:4])


def son_idx(kapanislar, t):
    """t anina kadar KAPANMIS son mumun indeksi (ileriye bakma yok)."""
    i = np.searchsorted(kapanislar, t, side="right") - 1
    return i if i >= 0 else None


def coin_tara(sym, bas_ms, bit_ms):
    """Bir coin icin tum tarama adimlarini gez, kurala uyan anlarda sinyal uret."""
    try:
        t15, h15, l15, c15 = mumlar(sym, "15m", bas_ms, bit_ms)
        t1h, h1h, l1h, c1h = mumlar(sym, "1h", bas_ms, bit_ms)
        t4h, h4h, l4h, c4h = mumlar(sym, "4h", bas_ms, bit_ms)
    except Exception as e:
        return [], f"{sym}: veri hatasi {type(e).__name__}"
    if len(c1h) < 120 or len(c15) < 120 or len(c4h) < 60:
        return [], f"{sym}: yetersiz mum"
    g15 = gostergeler(h15, l15, c15)
    g1h = gostergeler(h1h, l1h, c1h)
    g4h = gostergeler(h4h, l4h, c4h)

    sinyaller = []; son_sinyal = -1
    adim = TARAMA_DK * 60_000
    t = bas_ms - (bas_ms % adim) + adim
    while t <= bit_ms:
        if son_sinyal > 0 and (t - son_sinyal) < AYNI_COIN_TEKRAR_SAAT * 3600_000:
            t += adim; continue
        i4 = son_idx(t4h, t); i1 = son_idx(t1h, t); i5 = son_idx(t15, t)
        if i4 is None or i1 is None or i5 is None or i1 < 60 or i5 < 60 or i4 < 30:
            t += adim; continue
        # --- KURAL ---
        if not (g4h["rsi"][i4] >= K4_RSI_MIN and g4h["sk"][i4] <= K4_SRSI_MAX):
            t += adim; continue
        if not (g1h["rsi"][i1] <= K1_RSI_MAX and g1h["sk"][i1] <= K1_SRSI_MAX
                and g1h["kdj_j"][i1] <= K1_KDJ_J_MAX and g1h["wr"][i1] <= K1_WR_MAX
                and (g1h["hist"][i1] < 0 if K1_MACD_NEGATIF else True)):
            t += adim; continue
        if not (g15["rsi"][i5] <= K15_RSI_MAX and g15["sk"][i5] <= K15_SRSI_MAX
                and g15["wr"][i5] <= K15_WR_MAX):
            t += adim; continue
        # --- seviyeler (scanner levels() ile ayni) ---
        fiyat = float(c15[i5])
        s1, r1 = swing_seviye(h1h, l1h, c1h, i1, fiyat)
        s4, r4 = swing_seviye(h4h, l4h, c4h, i4, fiyat)
        sup = [v for v in s1 + s4 if 0 < v < fiyat]
        res = sorted({v for v in r1 + r4 if v > fiyat})
        destek = max(sup) if sup else fiyat * 0.96
        stop = destek * 0.975
        tp1 = next((x for x in res if (x - fiyat) / fiyat * 100 >= 2.5), fiyat * 1.035)
        sinyaller.append(dict(s=sym, t=int(t), giris=fiyat, stop=stop, tp1=tp1,
                              r4_rsi=float(g4h["rsi"][i4]), r4_srsi=float(g4h["sk"][i4]),
                              r1_rsi=float(g1h["rsi"][i1]), r1_srsi=float(g1h["sk"][i1]),
                              r1_j=float(g1h["kdj_j"][i1]), r1_wr=float(g1h["wr"][i1]),
                              r15_rsi=float(g15["rsi"][i5]), r15_srsi=float(g15["sk"][i5])))
        son_sinyal = t
        t += adim
    return sinyaller, None


def cikis(sig, t15, h15, l15, c15):
    """Canli portfolio_tracker kurallari: stop / TP1 / TP1 sonrasi %2.5 trailing / 24h."""
    i0 = np.searchsorted(t15, sig["t"], side="left")
    giris, stop, tp1 = sig["giris"], sig["stop"], sig["tp1"]
    limit = sig["t"] + EXPIRE_H * 3600_000
    zirve = giris; tp1_gordu = False
    for i in range(i0, len(c15)):
        hi, lo, cl, ct = h15[i], l15[i], c15[i], t15[i]
        if not tp1_gordu:
            if lo <= stop:
                return ("stop", stop, int(ct), zirve)
            if hi >= tp1:
                tp1_gordu = True
            elif ct >= limit:
                return ("sure", float(cl), int(ct), zirve)
        if tp1_gordu:
            zirve = max(zirve, float(hi))
            tr = max(giris, zirve * (1 - TRAIL_PCT / 100))
            if cl <= tr:
                return ("trailing", tr, int(ct), zirve)
    return ("acik", float(c15[-1]), int(t15[-1]), zirve)


def main():
    b = datetime.strptime(BASLANGIC, "%d/%m/%Y").replace(tzinfo=TR)
    e = datetime.strptime(BITIS, "%d/%m/%Y").replace(tzinfo=TR)
    bas_ms = int(b.astimezone(timezone.utc).timestamp() * 1000)
    bit_ms = int(e.astimezone(timezone.utc).timestamp() * 1000)
    print("=" * 90)
    print(f"DIP TARAMA   {BASLANGIC} - {BITIS}   tarama araligi {TARAMA_DK}dk")
    print("=" * 90)
    print("KURAL:  4H RSI>=%.0f ve StochRSI<=%.0f  |  1H RSI<=%.0f StochRSI<=%.0f J<=%.0f W%%R<=%.0f MACD<0"
          % (K4_RSI_MIN, K4_SRSI_MAX, K1_RSI_MAX, K1_SRSI_MAX, K1_KDJ_J_MAX, K1_WR_MAX))
    print("        15M RSI<=%.0f StochRSI<=%.0f W%%R<=%.0f" % (K15_RSI_MAX, K15_SRSI_MAX, K15_WR_MAX))
    print("SIKLIK: %d dk  (canli sistem 15 dk)   gunluk sinir: %s  (canli 3)"
          % (TARAMA_DK, GUNLUK_MAX_SINYAL if GUNLUK_MAX_SINYAL else "yok"))
    print()
    ev = evren()
    print(f"evren: {len(ev)} parite\n")

    tum, hatalar, bitti = [], [], 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sig, hata in ex.map(lambda s: coin_tara(s, bas_ms, bit_ms), ev):
            bitti += 1
            if hata: hatalar.append(hata)
            tum += sig
            if bitti % 25 == 0:
                print(f"  {bitti}/{len(ev)} coin  |  {len(tum)} sinyal  |  {time.time()-t0:.0f}sn", flush=True)
    print(f"\ntarama bitti: {len(tum)} sinyal, {len(hatalar)} coin atlandi ({time.time()-t0:.0f}sn)\n")
    if not tum:
        print("HIC SINYAL YOK. Kural cok siki — esikleri gevsetip tekrar dene.")
        return

    tum.sort(key=lambda x: x["t"])
    if GUNLUK_MAX_SINYAL:
        # canlidaki MAX_SIGNALS_PER_DAY: gun basina TOPLAM sinyal siniri (tum evren)
        onceki = len(tum); sayac = {}; secilen = []
        for sg in tum:
            gun = datetime.fromtimestamp(sg["t"] / 1000, tz=TR).strftime("%Y-%m-%d")
            if sayac.get(gun, 0) >= GUNLUK_MAX_SINYAL: continue
            sayac[gun] = sayac.get(gun, 0) + 1; secilen.append(sg)
        tum = secilen
        print(f"gunluk sinir ({GUNLUK_MAX_SINYAL}/gun): {onceki} -> {len(tum)} sinyal\n")
    print("cikislar hesaplaniyor...")
    kapali = []
    for sig in tum:
        try:
            t15, h15, l15, c15 = mumlar(sig["s"], "15m", bas_ms, bit_ms + 7 * 24 * 3600_000)
        except Exception:
            continue
        sebep, fiyat, ct, zirve = cikis(sig, t15, h15, l15, c15)
        brut = (fiyat / sig["giris"] - 1) * 100
        kapali.append({**sig, "sebep": sebep, "cikis": fiyat, "ct": ct,
                       "net": brut - KOMISYON, "zirve_pct": (zirve / sig["giris"] - 1) * 100})

    kap = [k for k in kapali if k["sebep"] != "acik"]
    print("\n" + "=" * 90)
    print("SONUC")
    print("=" * 90)
    print(f"  sinyal          : {len(kapali)}")
    print(f"  kapanan         : {len(kap)}")
    if not kap: return
    net = np.array([k["net"] for k in kap])
    print(f"  kazanan / kaybeden : {(net>0).sum()} / {(net<=0).sum()}   "
          f"(%{100*(net>0).mean():.0f} kazanma)")
    print(f"  islem basina ort : {net.mean():+.2f}%")
    for sb in ("trailing", "stop", "sure"):
        g = [k["net"] for k in kap if k["sebep"] == sb]
        if g: print(f"     {sb:9s}: {len(g):4d} islem, ort {np.mean(g):+.2f}%")
    # sirali tek-lot
    para = PARA; bos = None; eq = [para]
    for k in sorted(kap, key=lambda x: x["t"]):
        if bos is not None and k["t"] < bos: continue
        para *= (1 + k["net"] / 100); bos = k["ct"]; eq.append(para)
    eq = np.array(eq); z = np.maximum.accumulate(eq)
    print(f"\n  {PARA}$ ile SIRAYLA ({len(eq)-1} islem):")
    print(f"     bitis        : {para:.0f}$   ({(para/PARA-1)*100:+.1f}%)")
    print(f"     en kotu dusus: {(eq/z-1).min()*100:.1f}%")
    print(f"     en buyuk tek kayip: {net.min():.1f}%")

    tmp = f"dip_tarama_{BASLANGIC.replace('/','')}_{BITIS.replace('/','')}_{datetime.now():%Y%m%d_%H%M}"
    kural = {k: v for k, v in globals().items() if k.startswith(("K4_", "K1_", "K15_", "TRAIL", "EXPIRE"))}
    with open(tmp + ".json", "w", encoding="utf-8") as f:
        json.dump({"kural": kural, "islemler": kapali}, f, ensure_ascii=False, indent=1)
    html_rapor(tmp + ".html", kural, kap, eq)
    print(f"\n  kayit: {tmp}.json  ve  {tmp}.html")


def _yil(ms):
    return datetime.fromtimestamp(ms / 1000, tz=TR).year


def html_rapor(yol, kural, kap, eq):
    def esc(x):
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def sirali_hesap(liste):
        para = PARA; bos = None; e = [para]; al = []
        for k in sorted(liste, key=lambda x: x["t"]):
            if bos is not None and k["t"] < bos: continue
            para *= (1 + k["net"] / 100); bos = k["ct"]; e.append(para); al.append(k["net"])
        e = np.array(e); z = np.maximum.accumulate(e)
        al = np.array(al) if al else np.array([0.0])
        return dict(bitis=para, n=len(al), dd=float((e / z - 1).min() * 100),
                    ort=float(al.mean()), wr=float((al > 0).mean() * 100), enkotu=float(al.min()))

    yillar = sorted({_yil(k["t"]) for k in kap})
    h = ["<!doctype html><meta charset='utf-8'><title>Dip Tarama</title>",
         "<style>body{font:14px system-ui;margin:22px;background:#0f1418;color:#dbe4ea}",
         "h1{font-size:1.25rem}h2{font-size:.95rem;color:#7fd1e8;margin-top:26px}",
         "table{border-collapse:collapse;margin:8px 0;font-size:.78rem}",
         "th,td{border:1px solid #2a3540;padding:4px 8px;text-align:right}",
         "th{background:#1a232b;color:#9fb4c4}td:first-child,th:first-child{text-align:left}",
         ".i{color:#2ecc71}.k{color:#e74c3c}.n{color:#8a9aa8;font-size:.72rem}</style>",
         "<h1>Dip Tarama</h1>",
         f"<p class=n>{esc(BASLANGIC)} - {esc(BITIS)} &nbsp;|&nbsp; tarama {TARAMA_DK}dk &nbsp;|&nbsp; "
         f"evren {'tumu' if not EVREN_LIMIT else EVREN_LIMIT} parite &nbsp;|&nbsp; {PARA}$ sirali tek lot</p>"]
    h.append("<h2>Kural</h2><table><tr><th>parametre</th><th>deger</th></tr>")
    for k, v in kural.items():
        h.append(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>")
    h.append("</table>")

    h.append("<h2>Donemlere gore</h2><table><tr><th>donem</th><th>islem</th><th>ort net</th>"
             "<th>kazanma</th><th>2500$ -&gt;</th><th>en kotu dusus</th><th>en buyuk tek kayip</th></tr>")
    satirlar = [("TUMU", kap)] + [(str(y), [k for k in kap if _yil(k["t"]) == y]) for y in yillar]
    for ad2, liste in satirlar:
        if len(liste) < 2: continue
        r = sirali_hesap(liste)
        cls = "i" if r["bitis"] > PARA else "k"
        h.append(f"<tr><td>{esc(ad2)}</td><td>{len(liste)}</td><td>{r['ort']:+.2f}%</td>"
                 f"<td>{r['wr']:.0f}%</td><td class={cls}>{r['bitis']:.0f}$</td>"
                 f"<td>{r['dd']:.1f}%</td><td>{r['enkotu']:.1f}%</td></tr>")
    h.append("</table>")

    h.append("<h2>Cikis sebepleri</h2><table><tr><th>sebep</th><th>islem</th><th>ortalama</th><th>toplam</th></tr>")
    for sb in ("trailing", "stop", "sure"):
        g = [k["net"] for k in kap if k["sebep"] == sb]
        if not g: continue
        cls = "i" if np.mean(g) > 0 else "k"
        h.append(f"<tr><td>{esc(sb)}</td><td>{len(g)}</td>"
                 f"<td class={cls}>{np.mean(g):+.2f}%</td><td>{np.sum(g):+.1f}</td></tr>")
    h.append("</table>")

    net = np.array([k["net"] for k in kap]); srt = np.sort(net)[::-1]
    h.append("<h2>Kar yogunlasmasi</h2><table><tr><th>durum</th><th>toplam puan</th></tr>")
    h.append(f"<tr><td>tum islemler ({len(net)})</td><td>{net.sum():+.1f}</td></tr>")
    for kk in (1, 3, 5, 10):
        if kk < len(srt):
            h.append(f"<tr><td>en iyi {kk} islem cikarilirsa</td><td>{net.sum()-srt[:kk].sum():+.1f}</td></tr>")
    h.append(f"<tr><td>medyan islem</td><td>{np.median(net):+.2f}%</td></tr></table>")
    h.append("<p class=n>Toplam, en iyi birkac islem cikarilinca eksiye donuyorsa kar birkac "
             "sansli isleme bagimli demektir — oynaklik yuksek, daha cok islem gerekir.</p>")

    h.append("<h2>Islemler</h2><table><tr><th>coin</th><th>giris</th><th>cikis</th><th>sebep</th>"
             "<th>net</th><th>zirve</th><th>4H RSI</th><th>4H SRSI</th><th>1H RSI</th>"
             "<th>1H SRSI</th><th>1H J</th><th>1H W%R</th></tr>")
    for k in sorted(kap, key=lambda x: x["t"]):
        g = datetime.fromtimestamp(k["t"] / 1000, tz=TR).strftime("%d.%m.%y %H:%M")
        c = datetime.fromtimestamp(k["ct"] / 1000, tz=TR).strftime("%d.%m %H:%M")
        cls = "i" if k["net"] > 0 else "k"
        h.append(f"<tr><td>{esc(k['s'])}</td><td>{g}</td><td>{c}</td><td>{esc(k['sebep'])}</td>"
                 f"<td class={cls}>{k['net']:+.2f}%</td><td>{k['zirve_pct']:.1f}%</td>"
                 f"<td>{k['r4_rsi']:.0f}</td><td>{k['r4_srsi']:.1f}</td><td>{k['r1_rsi']:.0f}</td>"
                 f"<td>{k['r1_srsi']:.1f}</td><td>{k['r1_j']:.1f}</td><td>{k['r1_wr']:.0f}</td></tr>")
    h.append("</table>")
    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n".join(h))


if __name__ == "__main__":
    main()
    if len(sys.argv) <= 1:
        input("\nKapatmak icin Enter...")
