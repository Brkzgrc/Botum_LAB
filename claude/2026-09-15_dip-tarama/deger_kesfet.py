#!/usr/bin/env python3
# =====================================================================
#  AYARLAR
# =====================================================================
SEMBOLLER   = ["BTCUSDT"]          # birden fazla verilebilir
BASLANGIC   = "10/11/2021"         # gg/aa/yyyy (TR)
BITIS       = "10/11/2022"

# --- "IYI AN" TANIMI -------------------------------------------------
KAZANC      = 4.0      # sonraki pencerede once bu kadar yukselirse
KAYIP       = 3.0      # ama once bu kadar dusmezse  -> IYI AN
PENCERE_S   = 24       # pencere (saat)

GIRIS_TF    = "15m"                # alim burada belirlenir, etiketleme de burada
DESTEK_TF   = ["1h", "4h"]         # teyit / baglam
# =====================================================================
"""DEGER KESFET — "hangi degerler iyi" sorusunu VERIYE sordurur.

Klasik yontem: "su degerleri deneyelim" -> test -> uymadi -> baska deger.
Burada: once "iyi an" objektif etiketlenir (gelecege bakarak), sonra o
anlardaki OZELLIKLER diger tum anlarla karsilastirilir. Degerleri kullanici
vermez; veri soyler. "Hicbir sey bulunamadi" da gecerli bir cevaptir.

ARANAN SEY BELLI DEGIL — o yuzden genis bakiyoruz:
  seviye    : gostergenin degeri
  hareket   : 1 ve 3 bar onceye gore degisim (yukari mi donuyor)
  aralik    : son 50 bardaki goreli konum (sabit esik yerine)
  DURUM     : donuyor mu / donmeye mi hazirlaniyor / hizlaniyor mu / dipte mi
              kesisime yakin mi / kesti mi          <-- "doğru hareket"
  DESTEK    : ayni anda KAC gosterge ayni durumda (KAC_donus, KAC_dipte...)
              ve zaman dilimleri birbirini teyit ediyor mu
  hacim     : ortalamaya gore hacim, hacim trendi, OBV
  oynaklik  : ATR%, bar genisligi
  mum sekli : ust/alt fitil, govde orani
  yapi      : N barlik tepe/dipten uzaklik, ardisik yukselen dipler

BIRLESIM TESTI: tek tek AUC "birlikte olunca" durumunu OLCMEZ. Sonda ayri bir
bolum, gerekcelendirilmis birkac birlesimi (rastgele tarama DEGIL) test eder —
"6+ gosterge ayni anda donuyor", "4h geri cekilmede VE 15m donuyor", ve
kullanicinin 12 ekran goruntusunden cikan kural (RSI<50 & MACD hist<0 &
RSI/KDJ-J/W%R/OBV dorduu birden yukari donmus).

GOSTERGELER (ZEC 23.08.2026 09:00 ile birebir dogrulandi):
  RSI 14 Wilder · StochRSI 14/14/3/3 · KDJ 9/3/3 (J=3K-2D) · W%R 14
  MACD 12/26/9 (hist = dif - dea)

ILERIYE BAKMA: etiket gelecege bakar (dogru — "iyi"nin tanimi bu), ozellikler
sadece o ana kadar KAPANMIS mumlardan hesaplanir.

GURULTU TABANI: etiketler rastgele karistirilip ayni arama tekrarlanir.
100+ ozellik arasindan EN IYIYI secmenin sans payi boyle olculur. Bir bulgu
ancak bu tabanin USTUNDEYSE gercektir. Bu kontrol olmadan gurultu, bulgu
gibi gorunur — bu projede tam olarak bu oldu (CLAUDE.md, 2026-07-30).

DOGRULANDI (sentetik veriyle, 3 senaryo):
  A) saf rastgele          -> hicbir ozellik/birlesim tabani asmadi   (en iyi 0.105 / taban 0.143)
  B) ekilen SEVIYE sinyali -> bulundu                                 (0.370 / taban 0.096)
  C) ekilen BIRLESIM       -> birlesim testi ates etti (A'da 0, C'de 1)
  + ust zaman dilimi hizalamasi nedensel (Binance k[6]=KAPANIS zamani kullanilir)
"""
import json, os, pickle, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

TR = timezone(timedelta(hours=3))
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]
SURE = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
CACHE = "kesfet_cache"


def api(path, params=None):
    q = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    err = None
    for host in HOSTS:
        for _ in range(3):
            try:
                with urllib.request.urlopen(f"{host}{path}?{q}", timeout=30) as r:
                    return json.loads(r.read())
            except Exception as e:
                err = e; time.sleep(0.4)
    raise RuntimeError(f"{path}: {type(err).__name__} {err}")


def mumlar(sym, itv, bas, bit):
    """(close_time, open, high, low, close, volume)"""
    os.makedirs(CACHE, exist_ok=True)
    yol = os.path.join(CACHE, f"{sym}_{itv}_{bas}_{bit}.pkl")
    if os.path.exists(yol):
        with open(yol, "rb") as f: return pickle.load(f)
    out, cur = [], bas - 400 * SURE[itv]
    while cur < bit:
        raw = api("/api/v3/klines", {"symbol": sym, "interval": itv,
                                     "startTime": int(cur), "endTime": int(bit), "limit": 1000})
        if not raw: break
        out += [(int(k[6]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]))
                for k in raw]
        yeni = int(raw[-1][0]) + SURE[itv]
        if yeni <= cur or len(raw) < 1000: break
        cur = yeni; time.sleep(0.08)
    a = tuple(np.array([r[i] for r in out], dtype=np.int64 if i == 0 else np.float64)
              for i in range(6))
    with open(yol, "wb") as f: pickle.dump(a, f)
    return a


# ── gostergeler (ZEC 23.08.2026 09:00 ile birebir dogrulandi) ───────
def _ema(v, n):
    a = 2.0 / (n + 1.0); o = np.empty_like(v); o[0] = v[0]
    for i in range(1, len(v)): o[i] = a * v[i] + (1 - a) * o[i - 1]
    return o


def _sma(v, n):
    c = np.cumsum(np.insert(v, 0, 0.0)); o = (c[n:] - c[:-n]) / n
    return np.concatenate([np.array([v[:i + 1].mean() for i in range(n - 1)]), o])


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


def _roll(v, n, ismin):
    o = np.full(len(v), np.nan)
    if len(v) == 0: return o
    for i in range(min(n - 1, len(v))):
        w = v[:i + 1]; w = w[~np.isnan(w)]
        if len(w): o[i] = w.min() if ismin else w.max()
    if len(v) >= n:
        vv = np.where(np.isnan(v), np.inf if ismin else -np.inf, v)
        sw = np.lib.stride_tricks.sliding_window_view(vv, n)
        r = sw.min(axis=1) if ismin else sw.max(axis=1)
        o[n - 1:] = np.where(np.isinf(r), np.nan, r)
    return o


def _kaydir(v, k):
    """np.roll SARMALIYOR (son eleman basa geliyor) -> bastaki k elemani NaN yap.
    Yoksa dizinin sonundaki deger basina sizip sahte bilgi uretir."""
    o = np.roll(v, k).astype(float)
    o[:k] = np.nan
    return o


def _gecmis_ort(v, n):
    """SADECE GECMISE bakan hareketli ortalama.
    np.convolve(mode='same') ORTALANMIS pencere kullanir ve GELECEGI GORUR —
    bir kez bu hataya dusuldu, rastgele veride bile AUC 0.65 uretti."""
    c = np.cumsum(np.insert(np.nan_to_num(v), 0, 0.0))
    o = np.full(len(v), np.nan)
    o[n - 1:] = (c[n:] - c[:-n]) / n
    return o


def _konum(v, n=50):
    """son n bardaki goreli konum (0=dip, 100=tepe) — sabit esigin alternatifi"""
    lo = _roll(v, n, True); hi = _roll(v, n, False); rng = hi - lo
    return np.where(rng > 0, (v - lo) / np.where(rng > 0, rng, 1) * 100, 50.0)


def gostergeler(o, h, l, c, hac):
    r = _rsi(c)
    lo = _roll(r, 14, True); hi = _roll(r, 14, False); rng = hi - lo
    ham = np.nan_to_num(np.where(rng > 0, (r - lo) / np.where(rng > 0, rng, 1) * 100, 0.0))
    sk = _sma(ham, 3); sd = _sma(sk, 3)
    hh9 = _roll(h, 9, False); ll9 = _roll(l, 9, True)
    rsv = np.where(hh9 > ll9, (c - ll9) / np.where(hh9 > ll9, hh9 - ll9, 1) * 100, 50.0)
    K = np.empty(len(c)); D = np.empty(len(c)); K[0] = D[0] = 50.0
    for i in range(1, len(c)):
        K[i] = (2 / 3) * K[i - 1] + (1 / 3) * rsv[i]
        D[i] = (2 / 3) * D[i - 1] + (1 / 3) * K[i]
    hh14 = _roll(h, 14, False); ll14 = _roll(l, 14, True)
    wr = np.where(hh14 > ll14, (hh14 - c) / np.where(hh14 > ll14, hh14 - ll14, 1) * -100, 0.0)
    dif = _ema(c, 12) - _ema(c, 26); dea = _ema(dif, 9)
    e20 = _ema(c, 20); e50 = _ema(c, 50)
    # oynaklik / sekil / yapi / hacim
    pc = np.roll(c, 1); pc[0] = c[0]      # ATR icin ilk barda kendi kapanisi (dogru)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = _ema(tr, 14)
    govde = np.abs(c - o); genislik = np.maximum(h - l, 1e-12)
    hac_ort = _sma(hac, 20)
    obv = np.cumsum(np.sign(np.diff(c, prepend=c[0])) * hac)
    return {
        "OBV": obv,
        "RSI": r, "StochRSI_K": sk, "StochRSI_D": sd,
        "KDJ_K": K, "KDJ_D": D, "KDJ_J": 3 * K - 2 * D, "WR": wr,
        "MACD_hist": dif - dea, "MACD_dif": dif,
        "MA20_uzaklik": (c - e20) / e20 * 100, "MA50_uzaklik": (c - e50) / e50 * 100,
        "ATR_yuzde": atr / np.maximum(c, 1e-12) * 100,
        "bar_genislik": genislik / np.maximum(c, 1e-12) * 100,
        "ust_fitil": (h - np.maximum(o, c)) / genislik,
        "alt_fitil": (np.minimum(o, c) - l) / genislik,
        "govde_orani": govde / genislik,
        "hacim_orani": hac / np.maximum(hac_ort, 1e-12),
        "hacim_egim": (_sma(hac, 5) - _sma(hac, 20)) / np.maximum(_sma(hac, 20), 1e-12),
        "tepe20_uzaklik": (c - _roll(h, 20, False)) / c * 100,
        "dip20_uzaklik": (c - _roll(l, 20, True)) / c * 100,
        "yukselen_dip": _gecmis_ort((l > _kaydir(l, 1)).astype(float), 6),
    }


#  DURUM ozellikleri — "deger" degil "ne yapiyor":
#    donuyor      : su an yukari dondu (v > v-1 iken v-1 <= v-2)
#    hazirlaniyor : hala dusuyor AMA yavasliyor (donmeye hazirlanma)
#    hizlaniyor   : yukselis ivmeleniyor
#    dipte        : son N barin en alt %20'sinde
#    kesisime_yakin: iki cizgi birbirine yaklasiyor ve aralari dar
#    kesti        : son k barda yukari kesti
def _donuyor(v):
    return ((v > _kaydir(v, 1)) & (_kaydir(v, 1) <= _kaydir(v, 2))).astype(float)


def _hazirlaniyor(v):
    """dususte ama dusus yavasliyor — donmeden onceki hal"""
    d1 = v - _kaydir(v, 1); d2 = _kaydir(v, 1) - _kaydir(v, 2)
    return ((d1 < 0) & (d2 < 0) & (d1 > d2)).astype(float)


def _hizlaniyor(v):
    d1 = v - _kaydir(v, 1); d2 = _kaydir(v, 1) - _kaydir(v, 2)
    return ((d1 > 0) & (d1 > d2)).astype(float)


def _dipte(v, n=30):
    return (_konum(v, n) <= 20).astype(float)


def _kesisime_yakin(a, b, n=20):
    """|a-b| dar VE daraliyor — kesisime hazirlanma"""
    fark = np.abs(a - b)
    dar = _konum(fark, n) <= 25
    daraliyor = fark < _kaydir(fark, 1)
    return (dar & daraliyor).astype(float)


def _kesti(a, b, k=3):
    """son k barda a, b'yi YUKARI kesti"""
    ust = (a > b).astype(float)
    onceki = np.zeros_like(ust)
    for i in range(1, k + 1):
        onceki = np.maximum(onceki, np.nan_to_num(_kaydir((a <= b).astype(float), i)))
    return (ust * onceki)


def ozellikler(g, onek):
    """seviye + hareket + aralik + DURUM + gostergeler arasi DESTEK"""
    o = {}
    for k, v in g.items():
        o[f"{onek}{k}"] = v
        o[f"{onek}{k}_hrk1"] = v - _kaydir(v, 1)
        o[f"{onek}{k}_hrk3"] = v - _kaydir(v, 3)
        o[f"{onek}{k}_arlk"] = _konum(v, 50)
    # cizgiler arasi iliski
    o[f"{onek}SK_eksi_SD"] = g["StochRSI_K"] - g["StochRSI_D"]
    o[f"{onek}J_eksi_K"] = g["KDJ_J"] - g["KDJ_K"]
    o[f"{onek}KDJ_K_eksi_D"] = g["KDJ_K"] - g["KDJ_D"]
    o[f"{onek}SRSI_kesisime_yakin"] = _kesisime_yakin(g["StochRSI_K"], g["StochRSI_D"])
    o[f"{onek}KDJ_kesisime_yakin"] = _kesisime_yakin(g["KDJ_K"], g["KDJ_D"])
    o[f"{onek}SRSI_kesti"] = _kesti(g["StochRSI_K"], g["StochRSI_D"])
    o[f"{onek}KDJ_kesti"] = _kesti(g["KDJ_K"], g["KDJ_D"])
    o[f"{onek}MACD_kesisime_yakin"] = _kesisime_yakin(g["MACD_dif"], g["MACD_dif"] - g["MACD_hist"])
    o[f"{onek}MACD_kesti"] = _kesti(g["MACD_dif"], g["MACD_dif"] - g["MACD_hist"])
    # her gosterge icin DURUM
    ANA = ("RSI", "StochRSI_K", "KDJ_J", "WR", "MACD_hist", "OBV")
    for k in ANA:
        o[f"{onek}{k}_donus"] = _donuyor(g[k])
        o[f"{onek}{k}_hazir"] = _hazirlaniyor(g[k])
        o[f"{onek}{k}_hizlan"] = _hizlaniyor(g[k])
        o[f"{onek}{k}_dipte"] = _dipte(g[k])
    # DESTEK: kac gosterge ayni anda ayni durumda
    for durum in ("donus", "hazir", "hizlan", "dipte"):
        o[f"{onek}KAC_{durum}"] = sum(o[f"{onek}{k}_{durum}"] for k in ANA)
    return o


def etiketle(h, l, c, kazanc, kayip, pencere_s, tf):
    """Sadece KARAR VERILEN barlar etiketlenir:
         1 = once +kazanc% geldi   (yukari kazandi)
         0 = once -kayip% geldi    (asagi kazandi)
        -1 = pencerede hicbiri olmadi -> ANALIZ DISI

    NEDEN 'hicbiri' disarida:
      Iceride birakilirsa OYNAKLIK sahte bir ayirt edicilik uretir — yuksek
      oynaklikta fiyat herhangi bir esige daha cok deger, 'iyi' orani artar.
      Ama bu YON bilgisi degil, alim karari icin faydasiz. Testte gorundu:
      tamamen rastgele veride ATR_yuzde AUC 0.585 cikiyordu.
      Sadece karar verilen barlara bakilinca oynaklik avantaji yok olur,
      geriye yalnizca gercek yon bilgisi kalir."""
    n = len(c); ileri = max(1, int(pencere_s * 3_600_000 / SURE[tf]))
    y = np.full(n, -1, dtype=np.int8)
    for i in range(n - 1):
        son = min(n - 1, i + ileri)
        if son <= i: break
        hedef = c[i] * (1 + kazanc / 100.0); dip = c[i] * (1 - kayip / 100.0)
        for j in range(i + 1, son + 1):
            if l[j] <= dip: y[i] = 0; break
            if h[j] >= hedef: y[i] = 1; break
    return y


def auc(d, e):
    m = ~np.isnan(d) & ~np.isinf(d)
    d = d[m]; e = e[m]
    p = (e == 1).sum(); q = (e == 0).sum()
    if p < 10 or q < 10: return np.nan
    _, ters, sayim = np.unique(d, return_inverse=True, return_counts=True)
    sira = np.empty(len(d)); sira[np.argsort(d, kind="mergesort")] = np.arange(1, len(d) + 1)
    top = np.zeros(len(sayim)); np.add.at(top, ters, sira)
    sira = (top / sayim)[ters]
    return (sira[e == 1].sum() - p * (p + 1) / 2) / (p * q)


def main():
    b = datetime.strptime(BASLANGIC, "%d/%m/%Y").replace(tzinfo=TR)
    e = datetime.strptime(BITIS, "%d/%m/%Y").replace(tzinfo=TR)
    bas, bit = [int(x.astimezone(timezone.utc).timestamp() * 1000) for x in (b, e)]
    print("=" * 100)
    print(f"DEGER KESFET   {BASLANGIC} - {BITIS}   ({', '.join(SEMBOLLER)})")
    print("=" * 100)
    print(f'"IYI AN": sonraki {PENCERE_S} saatte ONCE +%{KAZANC} gorulsun, bunu yapmadan'
          f' once -%{KAYIP} gorulmesin.')
    print(f'GIRIS: {GIRIS_TF} barlari   DESTEK: {", ".join(DESTEK_TF)}')
    print()

    adlar = None; X = {}; Y = []; AY = []
    for sym in SEMBOLLER:
        try:
            t0, o0, h0, l0, c0, v0 = mumlar(sym, GIRIS_TF, bas, bit)
            ust = {}
            for tf in DESTEK_TF:
                ust[tf] = mumlar(sym, tf, bas, bit)
        except Exception as ex:
            print(f"  ! {sym} atlandi: {ex}"); continue
        if len(c0) < 500:
            print(f"  ! {sym} yetersiz veri ({len(c0)} bar)"); continue

        oz = ozellikler(gostergeler(o0, h0, l0, c0, v0), "")
        gecerli = (np.arange(len(c0)) >= 80)
        for tf in DESTEK_TF:
            tu, ou, hu, lu, cu, vu = ust[tf]
            gu = ozellikler(gostergeler(ou, hu, lu, cu, vu), f"{tf}_")
            iu = np.searchsorted(tu, t0, side="right") - 1      # o ana kadar KAPANMIS ust bar
            gecerli &= (iu >= 60)
            iuc = np.clip(iu, 0, len(cu) - 1)
            for k, v in gu.items(): oz[k] = v[iuc]
            # zaman dilimleri birbirini destekliyor mu
            oz[f"destek_{tf}_ikisi_dipte"] = ((oz["StochRSI_K_arlk"] < 25) &
                                              (gu[f"{tf}_StochRSI_K_arlk"][iuc] < 25)).astype(float)
            oz[f"destek_{tf}_ikisi_donuyor"] = ((oz["StochRSI_K_hrk1"] > 0) &
                                                (gu[f"{tf}_StochRSI_K_hrk1"][iuc] > 0)).astype(float)

        y = etiketle(h0, l0, c0, KAZANC, KAYIP, PENCERE_S, GIRIS_TF)
        gecerli &= (y >= 0) & (t0 >= bas) & (t0 <= bit)
        if gecerli.sum() < 200:
            print(f"  ! {sym} yetersiz etiketli bar"); continue
        if adlar is None:
            adlar = list(oz); X = {k: [] for k in adlar}
        for k in adlar: X[k].append(oz[k][gecerli])
        Y.append(y[gecerli])
        AY.append(np.array([datetime.fromtimestamp(x / 1000, tz=TR).strftime("%Y-%m")
                            for x in t0[gecerli]]))
        print(f"  {sym}: {int(gecerli.sum())} kararli bar, yukari oran %{100*y[gecerli].mean():.1f}")

    if not Y: sys.exit("veri yok")
    Y = np.concatenate(Y); AY = np.concatenate(AY)
    X = {k: np.concatenate(v) for k, v in X.items()}
    toplam = len(Y); iyi = int(Y.sum())
    print(f"\nTOPLAM {toplam} KARARLI bar · {iyi} yukari kazandi (%{100*iyi/toplam:.1f})"
          f" · {len(adlar)} ozellik")
    print("  (pencerede ne hedef ne stop goren barlar analiz disi — oynakligin sahte")
    print("   ayirt edicilik uretmesini engellemek icin)")
    if iyi < 50: sys.exit("iyi an cok az — KAZANC dusur veya PENCERE artir")

    # ── AUC ──────────────────────────────────────────────────────────
    gercek = {}
    for k in adlar:
        a = auc(X[k], Y)
        if not np.isnan(a): gercek[k] = a
    en_iyi_gercek = max(abs(v - 0.5) for v in gercek.values())

    # ── GURULTU TABANI (aile duzeyinde) ──────────────────────────────
    #  Her permutasyonda TUM ozelliklerin EN IYISI alinir — cunku gercek
    #  aramada da en iyiyi seciyoruz. Tek ozelligin tabani cok dusuk kalir.
    #  BLOK karistirma: bitisik barlar hem ayni ust-zaman-dilimi degerlerini
    #  paylasir hem de etiketleri ust uste binen pencerelerden gelir. Tek tek
    #  karistirmak bu bagimliligi yok eder ve tabani OLDUGUNDAN DAR gosterir
    #  (testte rastgele veride sahte 'anlamli' bulgular uretti). Bu yuzden
    #  etiketler hafta buyuklugunde bloklar halinde karistirilir.
    BLOK = max(1, int(7 * 24 * 3_600_000 / SURE[GIRIS_TF]))       # ~1 hafta
    print(f"\nGurultu tabani olculuyor (etiketler {BLOK} barlik BLOKLAR halinde"
          f" karistiriliyor, 100 tur)...", flush=True)
    rng = np.random.default_rng(20260912)
    bloklar = [np.arange(i, min(i + BLOK, len(Y))) for i in range(0, len(Y), BLOK)]
    sahte_en_iyi = []
    for tur in range(100):
        sira_b = rng.permutation(len(bloklar))
        yk = np.concatenate([Y[bloklar[i]] for i in sira_b])
        if len(yk) < len(Y): yk = np.concatenate([yk, Y[len(yk):]])
        yk = yk[:len(Y)]
        en = 0.0
        for k in adlar:
            a = auc(X[k], yk)
            if not np.isnan(a): en = max(en, abs(a - 0.5))
        sahte_en_iyi.append(en)
        if (tur + 1) % 25 == 0: print(f"   {tur+1}/100", flush=True)
    taban = float(np.percentile(sahte_en_iyi, 95))

    print("\n" + "=" * 100)
    print("SONUC")
    print("=" * 100)
    print(f"  En iyi gercek ayirt edicilik : |AUC-0.50| = {en_iyi_gercek:.3f}")
    print(f"  Gurultu tabani (%95)         : |AUC-0.50| = {taban:.3f}")
    print(f"  -> {len(adlar)} ozellik arasindan en iyiyi secerken, SIFIR bilgi olsa bile")
    print(f"     tesadufen {taban:.3f} kadar bir ayirt edicilik cikabiliyor.")
    print()
    if en_iyi_gercek <= taban:
        print("  >>> HICBIR OZELLIK GURULTU TABANINI ASMADI.")
        print("      Bu donemde, bu ozelliklerle 'iyi an' ayirt EDILEMIYOR.")
        print("      Igne bu samanlikta degil — baska bir yere bakmak gerek.")
    else:
        print("  >>> Tabani asan ozellikler var (asagida *). Ama tek bir donemde")
        print("      bulundular; dokunulmamis baska bir donemde dogrulanmadan kullanilmaz.")

    print("\n" + "=" * 100)
    print("%-30s %7s %4s | %-22s | %-22s" % ("ozellik", "AUC", "", "IYI anlarda", "DIGER anlarda"))
    print("%-30s %7s %4s | %7s %7s %7s | %7s %7s %7s" %
          ("", "", "", "%25", "medyan", "%75", "%25", "medyan", "%75"))
    print("-" * 100)
    sira = sorted(gercek.items(), key=lambda kv: -abs(kv[1] - 0.5))
    anlamli = []
    for k, a in sira[:30]:
        v = X[k]; m = ~np.isnan(v) & ~np.isinf(v)
        p = v[m & (Y == 1)]; q = v[m & (Y == 0)]
        yildiz = " *" if abs(a - 0.5) > taban else "  "
        if abs(a - 0.5) > taban: anlamli.append((k, a))
        print("%-30s %7.3f %s| %7.1f %7.1f %7.1f | %7.1f %7.1f %7.1f" %
              (k, a, yildiz, np.percentile(p, 25), np.median(p), np.percentile(p, 75),
               np.percentile(q, 25), np.median(q), np.percentile(q, 75)))

    if anlamli:
        print("\n" + "=" * 100)
        print("VERIDEN CIKAN ESIKLER (sadece tabani asan ozellikler)")
        print(f"  taban iyi oran: %{100*Y.mean():.1f}")
        print("=" * 100)
        for k, a in anlamli[:8]:
            v = X[k]; m = ~np.isnan(v) & ~np.isinf(v); vv = v[m]; yy = Y[m]
            en = None
            for qq in np.arange(5, 100, 5):
                esik = np.percentile(vv, qq)
                for yon, sec in (("<=", vv <= esik), (">=", vv >= esik)):
                    if sec.sum() < max(50, 0.03 * len(vv)): continue
                    oran = yy[sec].mean()
                    if en is None or oran > en[0]: en = (oran, yon, esik, int(sec.sum()))
            if en:
                print("  %-30s %s %9.2f  ->  iyi oran %%%.1f  (%d bar)"
                      % (k, en[1], en[2], 100 * en[0], en[3]))

    # aylik istikrar — bulgular tek bir aydan mi geliyor
    if anlamli:
        print("\n" + "=" * 100)
        print("AYLIK ISTIKRAR (en iyi ozellik, ay ay AUC)")
        print("=" * 100)
        k = anlamli[0][0]
        for ay in sorted(set(AY)):
            m = AY == ay
            if m.sum() < 100 or Y[m].sum() < 10: continue
            a = auc(X[k][m], Y[m])
            if not np.isnan(a):
                print("   %s  AUC %.3f  (%d bar, %d iyi)" % (ay, a, m.sum(), int(Y[m].sum())))

    # ── BIRLESIM TESTI ────────────────────────────────────────────────
    #  Tek tek AUC, "birlikte olunca" durumunu olcmez. Kullanicinin tarif
    #  ettigi sey bir BIRLESIM: degerler degil, ayni anda donen gostergeler.
    #  Burada birkac gerekcelendirilmis birlesim test edilir (rastgele tarama
    #  DEGIL) ve ayni blok-permutasyon tabaniyla karsilastirilir.
    def var(k):
        return X[k] if k in X else None

    birlesimler = []
    def ekle(ad2, m):
        if m is not None and m.sum() >= 50: birlesimler.append((ad2, m))

    try:
        ekle("12 ornekten cikan kural: RSI<50 & MACD<0 & RSI/J/WR/OBV hepsi donuyor",
             (var("RSI") < 50) & (var("MACD_hist") < 0) &
             (var("RSI_donus") > 0) & (var("KDJ_J_donus") > 0) &
             (var("WR_donus") > 0) & (var("OBV_donus") > 0))
        for esik in (3, 4, 5, 6):
            ekle(f"15m: {esik}+ gosterge ayni anda donuyor", var("KAC_donus") >= esik)
        ekle("15m: 3+ dipte VE 3+ donuyor",
             (var("KAC_dipte") >= 3) & (var("KAC_donus") >= 3))
        ekle("15m: KDJ kesisime yakin VE 3+ donuyor",
             (var("KDJ_kesisime_yakin") > 0) & (var("KAC_donus") >= 3))
        ekle("15m: StochRSI yukari kesti VE 3+ donuyor",
             (var("SRSI_kesti") > 0) & (var("KAC_donus") >= 3))
        if var("1h_KAC_donus") is not None:
            ekle("15m 4+ donuyor VE 1h 3+ donuyor",
                 (var("KAC_donus") >= 4) & (var("1h_KAC_donus") >= 3))
            ekle("15m 3+ dipte VE 1h 3+ dipte VE 15m 3+ donuyor",
                 (var("KAC_dipte") >= 3) & (var("1h_KAC_dipte") >= 3) & (var("KAC_donus") >= 3))
        if var("4h_KAC_dipte") is not None:
            ekle("4h 3+ dipte (geri cekilme) VE 15m 4+ donuyor",
                 (var("4h_KAC_dipte") >= 3) & (var("KAC_donus") >= 4))
    except Exception as ex:
        print("  ! birlesim kurulamadi:", ex)

    if birlesimler:
        print("\n" + "=" * 100)
        print("BIRLESIM TESTI — gostergeler BIRLIKTE bakildiginda")
        print("=" * 100)
        print("  Tek tek AUC 'birlikte' durumunu olcmez. Asagidakiler gerekcelendirilmis")
        print("  birlesimler (rastgele tarama degil).")
        # blok-permutasyon tabani: bos etiketle bu birlesimlerin EN IYISI ne verir
        print("  Gurultu tabani olculuyor...", flush=True)
        #  Birlesimlerin bar sayilari cok farkli (50 ile binlerce arasi).
        #  Ham orani karsilastirmak kucuk birlesimlere haksiz avantaj verir
        #  (az barda oran cok oynar). Bu yuzden her birlesim KENDI bar
        #  sayisina gore olculur, sonra ailenin en iyisi alinir.
        p0 = float(Y.mean())

        def _z(oran, n):
            se = (p0 * (1 - p0) / max(n, 1)) ** 0.5
            return (oran - p0) / se if se > 0 else 0.0

        sahte_en = []
        for tur in range(200):
            sira_b = rng.permutation(len(bloklar))
            yk = np.concatenate([Y[bloklar[i]] for i in sira_b])[:len(Y)]
            if len(yk) < len(Y): yk = np.concatenate([yk, Y[len(yk):]])
            sahte_en.append(max(_z(yk[m].mean(), int(m.sum())) for _, m in birlesimler))
        z_taban = float(np.percentile(sahte_en, 95))
        print(f"\n  taban oran (hicbir bilgi yokken): %{100*p0:.1f}")
        print(f"  {len(birlesimler)} birlesim deneniyor. Bos etiketle bile en iyisi tesadufen")
        print(f"  taban orandan {z_taban:.2f} standart sapma yukari cikabiliyor —")
        print(f"  bir birlesim ancak BUNU asarsa gercektir.\n")
        print("  %-56s %6s %8s %9s  %s" % ("birlesim", "bar", "yukari", "gerekli", ""))
        print("  " + "-" * 98)
        bul = []
        for ad2, m in sorted(birlesimler, key=lambda x: -_z(float(Y[x[1]].mean()), int(x[1].sum()))):
            n_ = int(m.sum()); oran = float(Y[m].mean())
            gerek = p0 + z_taban * (p0 * (1 - p0) / max(n_, 1)) ** 0.5
            hkm = "ANLAMLI" if oran > gerek else ""
            if oran > gerek: bul.append((ad2, oran, n_))
            print("  %-56s %6d %7.1f%% %8.1f%%  %s" % (ad2[:56], n_, 100 * oran, 100 * gerek, hkm))
        if not bul:
            print("\n  >>> Hicbir birlesim tabani asmadi. Gostergeler birlikte bakildiginda da")
            print("      bu donemde 'iyi an'i ayirt etmiyor.")
        else:
            print(f"\n  >>> {len(bul)} birlesim tabani asti — dokunulmamis bir donemde dogrulanmali.")

    ad = f"deger_kesfet_{BASLANGIC.replace('/','')}_{BITIS.replace('/','')}_{datetime.now():%Y%m%d_%H%M}.json"
    with open(ad, "w", encoding="utf-8") as f:
        json.dump({"tanim": {"KAZANC": KAZANC, "KAYIP": KAYIP, "PENCERE_S": PENCERE_S,
                             "giris_tf": GIRIS_TF, "destek_tf": DESTEK_TF,
                             "semboller": SEMBOLLER, "donem": [BASLANGIC, BITIS]},
                   "bar": int(toplam), "iyi_an": int(iyi), "ozellik_sayisi": len(adlar),
                   "gurultu_tabani": taban, "en_iyi_gercek": en_iyi_gercek,
                   "anlamli": [{"ozellik": k, "auc": float(a)} for k, a in anlamli],
                   "birlesim": ([{"kural": k, "oran": float(o), "bar": n_} for k, o, n_ in bul]
                                if birlesimler else []),
                   "birlesim_z_taban": (z_taban if birlesimler else None),
                   "tum_auc": [{"ozellik": k, "auc": float(a)} for k, a in sira]},
                  f, ensure_ascii=False, indent=1)
    print(f"\nkayit: {ad}")


if __name__ == "__main__":
    main()
    if len(sys.argv) <= 1:
        input("\nKapatmak icin Enter...")
