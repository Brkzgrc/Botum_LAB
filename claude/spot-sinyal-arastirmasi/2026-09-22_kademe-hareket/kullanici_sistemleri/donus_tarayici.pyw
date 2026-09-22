# -*- coding: utf-8 -*-
"""
donus_tarayici.py — Spot piyasa "düşüşten yükselişe dönüş" tarayıcısı (GUI)
===========================================================================
API anahtarı GEREKMEZ. Binance public uç noktalarını kullanır.

MANTIK
------
• Evren   : Binance SPOT, USDT pariteleri. Stablecoin + fiat pariteler dışlanır,
            kaldıraçlı token'lar (UP/DOWN/BULL/BEAR) dışlanır.
• Zaman   : 1d, 4h, 1h, 15m  (geniş → dar)
• İndikatör: RSI, MACD, Stoch RSI, KDJ, OBV, Williams %R
• Skorlama: HER İNDİKATÖR BAĞIMSIZ puanlanır  →  (RSI)+(MACD)+(KDJ)+…
            Önce her indikatör kendi başına -1..+1 arası "dönüş skoru" üretir,
            sonra zaman dilimi skoru = indikatör skorlarının ağırlıklı ortalaması,
            en son toplam skor = zaman dilimlerinin ağırlıklı birleşimi.
• Çerçeve : 1d ve 4h = KONTROL/İZİN çerçevesi (bozuksa aday elenir/geri düşer)
            1h        = TEYİT çerçevesi
            15m       = TETİK / son karar çerçevesi

Çalıştırma:
    python donus_tarayici.py

Not: Bu bir karar-destek tarama aracıdır, yatırım tavsiyesi değildir.
"""

import csv
import html
import json
import os
import queue
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# =============================================================================
#  AYARLAR
# =============================================================================

SUNUCULAR = [
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://data-api.binance.vision",
]

ZAMAN_DILIMLERI = ["1d", "4h", "1h", "15m"]

# Sıralama skoru ağırlıkları.
# 15 dakika ÖLÇÜM zaman dilimi DEĞİL — alım yeri tespit çerçevesidir; bu yüzden
# sıralama skoruna girmez (ağırlık 0), huninin son adımı olarak kapı görevi görür.
TF_AGIRLIK = {"1d": 0.30, "4h": 0.35, "1h": 0.35, "15m": 0.0}

# İndikatör ağırlıkları (tümü bağımsız hesaplanır, birleşimde ağırlıklanır)
IND_AGIRLIK = {
    "RSI": 1.0,
    "MACD": 1.2,
    "StochRSI": 1.0,
    "KDJ": 1.0,
    "OBV": 1.1,
    "Williams%R": 0.9,
    "EMA20/50": 0.9,      # destekleyici — tek başına karar verdirmez
    "Yapı LL/HL": 1.1,    # fiyatın kendi kanıtı (dip/tepe yapısı)
    "Hacim/Pump": 1.2,    # hacim patlaması + "zaten kaçmış mı" (veriyle ölçüldü)
}

INDIKATORLER = list(IND_AGIRLIK.keys())

# Zaman dilimine göre ağırlık: StochRSI en hızlı tepki veren gösterge olduğu
# için dar zaman dilimlerinde (tetik) baskın; MACD ve OBV yavaş tepki verdiği
# için geniş zaman dilimlerinde (çerçeve) baskın.
IND_AGIRLIK_TF = {
    "1d":  {"RSI": 1.2, "MACD": 1.3, "StochRSI": 0.9, "KDJ": 0.9, "OBV": 1.3,
            "Williams%R": 0.7, "EMA20/50": 0.9, "Yapı LL/HL": 1.2, "Hacim/Pump": 1.0},
    "4h":  {"RSI": 1.1, "MACD": 1.2, "StochRSI": 1.1, "KDJ": 1.0, "OBV": 1.2,
            "Williams%R": 0.8, "EMA20/50": 1.0, "Yapı LL/HL": 1.3, "Hacim/Pump": 1.2},
    "1h":  {"RSI": 1.0, "MACD": 1.1, "StochRSI": 1.3, "KDJ": 1.1, "OBV": 1.1,
            "Williams%R": 0.9, "EMA20/50": 1.0, "Yapı LL/HL": 1.2, "Hacim/Pump": 1.3},
    # 15dk: alım yeri tespiti. Yapı burada gecikmeli/gürültülü olduğu için hafif.
    "15m": {"RSI": 1.0, "MACD": 0.9, "StochRSI": 1.5, "KDJ": 1.2, "OBV": 1.0,
            "Williams%R": 1.0, "EMA20/50": 1.1, "Yapı LL/HL": 0.7, "Hacim/Pump": 1.1},
}

# Pencere/sütun ölçüleri, ayarlar ve izleme listesi burada saklanır
AYAR_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "donus_tarayici_ayarlar.json")

# İzleme listesi AYRI dosyada tutulur: pencere/sütun ayarlarıyla birlikte
# yazılmaz, atomik kaydedilir ve her değişiklikten önce yedeklenir.
IZLEME_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "donus_tarayici_izleme.json")
YEDEK_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "izleme_yedek")

# Uygulama hangi ekranda açılsın?
#   "mouse"  → imlecin bulunduğu ekranın ortası
#   "1", "2" → o numaralı ekranın ortası (1 = ana ekran, sonra soldan sağa)
#   "kayitli"→ en son kapatıldığı konum
ACILIS_EKRANI = "mouse"

CANLI_ARALIK = 10      # izleme listesi fiyat yenileme (saniye)
SKOR_ARALIK = 300      # izleme listesi indikatör skoru yenileme (saniye)

TARIH_BICIM = "%d-%m-%Y %H:%M"

# ÇIKIŞ PLANI — 78 coin / 500 gün / 772 gerçek sinyal, 5 DAKİKALIK mumlarla
# simüle edildi (giriş: sinyal mumu kapandıktan sonraki ilk mumun açılışı).
#
#   stop 4×ATR altı · hedef 8×ATR üstü
#   → %42.6 kazanan · net beklenti +%1.58 · kâr faktörü 1.45
#   → ortalama kazanç +%11.99 · ortalama zarar -%6.15
#
# NEDEN TAKİP EDEN STOP YOK: 1 saatlik mumla ölçüldüğünde TP1+takip planları
# daha iyi görünüyordu, ama o ölçüm yanlıydı — kaba mum, takip stopunu
# tetikleyen mum-içi geri çekilmeleri gizliyor. 5 dakikalık mumla:
#   takip 0.6 ATR: +%1.52 → +%0.87   ·   takip %5: +%1.51 → +%1.07
#   sabit 4/8    : +%1.59 → +%1.58   (sabit hedef bu yanlılıktan etkilenmiyor)
# Sabit hedef hem daha yüksek beklenti veriyor hem ölçümü güvenilir.
STOP_ATR = 4.0
HEDEF_ATR = 8.0

# Oluşan (henüz kapanmamış) mum hesaba katılsın mı?
#   True  → VARSAYILAN: grafikte gördüğünle aynı; 1G'deki 24 saatlik gecikmeyi
#           kaldırır, ama mum kapanana kadar değerler oynamaya devam eder
#   False → sadece kapanmış mumlar (backtest saflığı, ileriye bakma yok)
# Arayüzdeki "Oluşan mumu dahil et" kutusundan değiştirilir.
OLUSAN_MUM = {"dahil": True}

STABLE_VE_FIAT = {
    "USDT", "BUSD", "USDC", "FDUSD", "TUSD", "DAI", "USDP", "USDE", "USD1",
    "PYUSD", "RLUSD", "EURI", "AEUR", "SUSD", "GUSD", "LUSD", "FRAX", "UST",
    "USD", "USDS", "USDSB", "USDG", "USDD", "USDY", "USDQ", "PAX", "DAIF",
    "EUR", "TRY", "BRL", "RUB", "GBP", "AUD", "UAH", "NGN", "ZAR", "PLN",
    "RON", "ARS", "JPY", "MXN", "COP", "CZK", "IDRT", "BIDR", "VAI", "BVND",
    "BKRW", "EURC", "EURT", "EURQ", "XAUT", "PAXG", "TUSDB",
}

# İsim sezgisi: yeni çıkan stablecoin'leri de yakalar (…USD, EUR…, USD… gibi)
def stable_mi(varlik):
    if varlik in STABLE_VE_FIAT:
        return True
    return (varlik.endswith("USD") or varlik.startswith("USD")
            or varlik.endswith("EUR") or varlik.startswith("EUR"))


KALDIRACLI_SONEK = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")

SUTUNLAR = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]

_aktif_sunucu = [0]
_oturum = requests.Session()
_kilit = threading.Lock()


# =============================================================================
#  BINANCE İSTEK KATMANI
# =============================================================================

def istek(yol, parametreler=None, deneme=4):
    """Binance public GET. Hata/hız-limitinde sunucu değiştirip yeniden dener."""
    son_hata = None
    for n in range(deneme):
        with _kilit:
            sunucu = SUNUCULAR[_aktif_sunucu[0]]
        try:
            cevap = _oturum.get(f"{sunucu}{yol}", params=parametreler, timeout=20)

            if cevap.status_code in (418, 429):
                bekle = int(cevap.headers.get("Retry-After", 4)) + 2
                time.sleep(bekle)
                continue

            if cevap.status_code >= 500:
                raise requests.RequestException(f"HTTP {cevap.status_code}")

            if cevap.status_code != 200:
                raise requests.RequestException(
                    f"HTTP {cevap.status_code}: {cevap.text[:150]}")

            return cevap.json()

        except requests.RequestException as e:
            son_hata = e
            with _kilit:
                _aktif_sunucu[0] = (_aktif_sunucu[0] + 1) % len(SUNUCULAR)
            time.sleep(0.8 * (n + 1))

    raise RuntimeError(f"{deneme} denemede bağlanılamadı: {son_hata}")


def evren_getir(top_n, min_hacim_musd):
    """Taranacak sembolleri (24s hacme göre) döndürür. Stable/fiat dışlanmış."""
    bilgi = istek("/api/v3/exchangeInfo")
    uygun = set()
    for s in bilgi.get("symbols", []):
        if (s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"
                and s.get("isSpotTradingAllowed", True)
                and not stable_mi(s.get("baseAsset", ""))
                and not s.get("symbol", "").endswith(KALDIRACLI_SONEK)):
            uygun.add(s["symbol"])

    tikerlar = istek("/api/v3/ticker/24hr")
    secilenler = []
    for t in tikerlar:
        sembol = t.get("symbol")
        if sembol not in uygun:
            continue
        hacim = float(t.get("quoteVolume") or 0.0)
        if hacim < min_hacim_musd * 1_000_000:
            continue
        secilenler.append({
            "sembol": sembol,
            "coin": sembol[:-4],
            "fiyat": float(t.get("lastPrice") or 0.0),
            "degisim": float(t.get("priceChangePercent") or 0.0),
            "hacim": hacim,
        })

    secilenler.sort(key=lambda x: x["hacim"], reverse=True)
    return secilenler[:top_n]


def mum_getir(sembol, aralik, adet=320):
    """Kapanmış mumları DataFrame olarak döndürür (son yarım mum atılır)."""
    ham = istek("/api/v3/klines",
                {"symbol": sembol, "interval": aralik, "limit": adet})
    if not ham or len(ham) < 60:
        return None

    df = pd.DataFrame(ham, columns=SUTUNLAR).drop(columns=["ignore"])
    for s in ("open", "high", "low", "close", "volume", "quote_volume"):
        df[s] = pd.to_numeric(df[s], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    # Oluşan (kapanmamış) son mum: ayara göre tutulur ya da atılır
    if not OLUSAN_MUM["dahil"]:
        simdi = pd.Timestamp.now(tz="UTC")
        df = df[df["close_time"] <= simdi].reset_index(drop=True)

    return df if len(df) >= 60 else None


# =============================================================================
#  İNDİKATÖRLER  (saf pandas — harici kütüphane gerekmez)
# =============================================================================

def rsi(kapanis, periyot=14):
    fark = kapanis.diff()
    kazanc = fark.clip(lower=0.0)
    kayip = (-fark).clip(lower=0.0)
    ok = kazanc.ewm(alpha=1 / periyot, adjust=False).mean()
    ol = kayip.ewm(alpha=1 / periyot, adjust=False).mean()
    rs = ok / ol.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def macd(kapanis, hizli=12, yavas=26, sinyal=9):
    mac = kapanis.ewm(span=hizli, adjust=False).mean() - \
          kapanis.ewm(span=yavas, adjust=False).mean()
    sin = mac.ewm(span=sinyal, adjust=False).mean()
    return mac, sin, mac - sin


def stoch_rsi(kapanis, rsi_periyot=14, stoch_periyot=14, k=3, d=3):
    r = rsi(kapanis, rsi_periyot)
    en_dusuk = r.rolling(stoch_periyot).min()
    en_yuksek = r.rolling(stoch_periyot).max()
    ham = (r - en_dusuk) / (en_yuksek - en_dusuk).replace(0.0, np.nan) * 100
    kk = ham.rolling(k).mean()
    dd = kk.rolling(d).mean()
    return kk.fillna(50.0), dd.fillna(50.0)


def kdj(yuksek, dusuk, kapanis, periyot=9, k_yum=3, d_yum=3):
    llv = dusuk.rolling(periyot).min()
    hhv = yuksek.rolling(periyot).max()
    rsv = (kapanis - llv) / (hhv - llv).replace(0.0, np.nan) * 100
    rsv = rsv.fillna(50.0)
    kk = rsv.ewm(alpha=1 / k_yum, adjust=False).mean()
    dd = kk.ewm(alpha=1 / d_yum, adjust=False).mean()
    return kk, dd, 3 * kk - 2 * dd


def ema(seri, periyot):
    return seri.ewm(span=periyot, adjust=False).mean()


def obv(kapanis, hacim):
    yon = np.sign(kapanis.diff().fillna(0.0))
    return (yon * hacim).fillna(0.0).cumsum()


def williams_r(yuksek, dusuk, kapanis, periyot=14):
    hhv = yuksek.rolling(periyot).max()
    llv = dusuk.rolling(periyot).min()
    return (-100 * (hhv - kapanis) / (hhv - llv).replace(0.0, np.nan)).fillna(-50.0)


# ---------------------------------------------------------------- yardımcılar

def capraz_yukari(seri, esik, bar=3):
    """Son `bar` mum içinde seri eşiği aşağıdan yukarı kesti mi?"""
    for i in range(1, bar + 1):
        if len(seri) > i and seri.iloc[-i] > esik >= seri.iloc[-i - 1]:
            return True
    return False


def capraz_asagi(seri, esik, bar=3):
    for i in range(1, bar + 1):
        if len(seri) > i and seri.iloc[-i] < esik <= seri.iloc[-i - 1]:
            return True
    return False


def seri_capraz_yukari(a, b, bar=3):
    """a serisi b serisini aşağıdan yukarı kesti mi?"""
    for i in range(1, bar + 1):
        if len(a) > i and a.iloc[-i] > b.iloc[-i] and a.iloc[-i - 1] <= b.iloc[-i - 1]:
            return True
    return False


def dipten_donus(seri, bar=1):
    """Seri dip yapıp yukarı döndü mü? (V dönüşü)"""
    if len(seri) < 4:
        return False
    return (seri.iloc[-1] > seri.iloc[-2]) and (seri.iloc[-2] <= seri.iloc[-3])


def egim(seri, n=3):
    """Son n mumdaki yön (pozitif = yükseliyor)."""
    if len(seri) < n + 1:
        return 0.0
    return float(seri.iloc[-1] - seri.iloc[-1 - n])


def yerel_dipler(seri, pencere=3, bakilacak=90):
    """Son `bakilacak` mumdaki yerel dip indekslerini döndürür."""
    v = np.asarray(seri, dtype=float)
    n = len(v)
    if n < 2 * pencere + 5:
        return []
    basla = max(pencere, n - bakilacak)
    dipler = []
    for i in range(basla, n - pencere):
        if v[i] == np.nanmin(v[i - pencere:i + pencere + 1]):
            if dipler and i - dipler[-1] < pencere:
                if v[i] <= v[dipler[-1]]:
                    dipler[-1] = i
                continue
            dipler.append(i)
    return dipler


def yerel_tepeler(seri, pencere=3, bakilacak=90):
    """Son `bakilacak` mumdaki yerel tepe indekslerini döndürür."""
    v = np.asarray(seri, dtype=float)
    n = len(v)
    if n < 2 * pencere + 5:
        return []
    basla = max(pencere, n - bakilacak)
    tepeler = []
    for i in range(basla, n - pencere):
        if v[i] == np.nanmax(v[i - pencere:i + pencere + 1]):
            if tepeler and i - tepeler[-1] < pencere:
                if v[i] >= v[tepeler[-1]]:
                    tepeler[-1] = i
                continue
            tepeler.append(i)
    return tepeler


def pozitif_uyumsuzluk(fiyat_dusuk, gosterge, son_bar=25):
    """
    Boğa (pozitif) uyumsuzluk: fiyat daha düşük dip yaparken gösterge daha
    yüksek dip yapıyor mu?  (dönüş = düşüşten yükselişe geçiş sinyali)
    """
    dipler = yerel_dipler(fiyat_dusuk)
    if len(dipler) < 2:
        return False
    i1, i2 = dipler[-2], dipler[-1]
    if len(fiyat_dusuk) - i2 > son_bar:
        return False
    f1, f2 = float(fiyat_dusuk.iloc[i1]), float(fiyat_dusuk.iloc[i2])
    g1, g2 = float(gosterge.iloc[i1]), float(gosterge.iloc[i2])
    return (f2 < f1 * 0.999) and (g2 > g1)


def kirp(x, alt=-1.0, ust=1.0):
    return max(alt, min(ust, x))


# ---------------------------------------------------------- YÖN KAPISI
# Temel kural: bir gösterge ŞU ANDA aşağı gidiyorsa, geçmişteki kesişimi ya da
# eğimi ne olursa olsun olumlu puan ÜRETMEZ. "Düşerken sinyal" buradan engellenir.

def son_hareket(seri):
    """Son kapanmış mumdaki değişim (pozitif = yukarı döndü)."""
    if len(seri) < 2:
        return 0.0
    return float(seri.iloc[-1]) - float(seri.iloc[-2])


def yukarida_mi(seri):
    return son_hareket(seri) > 0


def ok(seri):
    return "↑" if son_hareket(seri) > 0 else ("↓" if son_hareket(seri) < 0 else "→")


def ortalama_oynaklik(seri, n=6):
    try:
        return float(seri.diff().abs().iloc[-n:].mean() or 0.0)
    except Exception:
        return 0.0


def donus_yukari(seri, guc=0.25):
    """
    Gerçek dip dönüşü: son mum yukarı, ondan önceki mum aşağıydı ve hareket
    son mumların ortalama oynaklığına göre anlamlı (mikro tik elenir).
    """
    if len(seri) < 4:
        return False
    son = son_hareket(seri)
    if son <= 0:
        return False
    onceki = float(seri.iloc[-2]) - float(seri.iloc[-3])
    if onceki > 0:
        return False                      # zaten yükseliyordu, dönüş değil
    return son >= guc * ortalama_oynaklik(seri)


def taze_capraz_yukari(seri, esik, bar=2):
    """
    Eşik yukarı kesildi + HÂLÂ eşiğin üstünde + gösterge şu anda yükseliyor.
    (Bayat kesişim ve kesip geri düşme durumları elenir.)
    """
    if float(seri.iloc[-1]) <= esik or son_hareket(seri) <= 0:
        return False
    for i in range(1, bar + 1):
        if len(seri) > i + 1 and seri.iloc[-i] > esik >= seri.iloc[-i - 1]:
            return True
    return False


def taze_seri_capraz(hizli, yavas, bar=2):
    """
    Gerçek altın kesişim: hızlı çizgi yavaşın üstünde, KENDİSİ yükseliyor ve
    makas açılıyor. Hızlı çizgi düşerken yavaş daha hızlı düştüğü için oluşan
    'sahte kesişim' bu şartlarla elenir.
    """
    if float(hizli.iloc[-1]) <= float(yavas.iloc[-1]):
        return False
    if son_hareket(hizli) <= 0:
        return False
    makas_simdi = float(hizli.iloc[-1] - yavas.iloc[-1])
    makas_once = float(hizli.iloc[-2] - yavas.iloc[-2])
    if makas_simdi <= makas_once:
        return False                      # makas daralıyor → kesişim bozuluyor
    for i in range(1, bar + 1):
        if (len(hizli) > i + 1 and hizli.iloc[-i] > yavas.iloc[-i]
                and hizli.iloc[-i - 1] <= yavas.iloc[-i - 1]):
            return True
    return False


def kesisime_yaklasiyor(hizli, yavas, bar=2):
    """
    Henüz kesmedi ama: hızlı çizgi yukarı döndü ve makas üst üste kapanıyor.
    'Düşmüş, kesişim yapmak üzere' durumu — tetik değil, hazırlık sinyali.
    """
    if float(hizli.iloc[-1]) >= float(yavas.iloc[-1]):
        return False
    if son_hareket(hizli) <= 0:
        return False
    if len(hizli) < bar + 3:
        return False
    makas = [float(yavas.iloc[-i] - hizli.iloc[-i]) for i in range(1, bar + 2)]
    return all(makas[i] < makas[i + 1] for i in range(len(makas) - 1))


def ust_uste_yukari(seri, adet=2):
    """Son `adet` mumun hepsi yukarı mı?"""
    if len(seri) < adet + 1:
        return False
    return all(float(seri.iloc[-i]) > float(seri.iloc[-i - 1])
               for i in range(1, adet + 1))


# =============================================================================
#  BAĞIMSIZ İNDİKATÖR SKORLAYICILARI
#  Her fonksiyon kendi başına -1..+1 arası "dönüş skoru" + gerekçe üretir.
# =============================================================================

def skor_rsi(df):
    r = rsi(df["close"])
    s, notlar = 0.0, []
    son = float(r.iloc[-1])
    yukari = yukarida_mi(r)

    if donus_yukari(r) and son < 55:
        s += 0.30; notlar.append("RSI dipten yukarı döndü (son mum yukarı)")
    if taze_capraz_yukari(r, 30):
        s += 0.35; notlar.append("RSI 30 üzerine çıktı ve yükseliyor")
    if taze_capraz_yukari(r, 50):
        s += 0.30; notlar.append("RSI 50 bandını yukarı kesti")
    if pozitif_uyumsuzluk(df["low"], r) and yukari:
        s += 0.35; notlar.append("RSI pozitif uyumsuzluk + yukarı dönüş")
    if ust_uste_yukari(r, 2) and son > 45:
        s += 0.15; notlar.append("RSI üst üste 2 mum yükseliyor")

    if not yukari and son < 50:
        s -= 0.35; notlar.append("RSI aşağı dönük ve 50 altında")
    if capraz_asagi(r, 50, bar=3):
        s -= 0.30; notlar.append("RSI 50 bandını aşağı kesti")
    if son > 75 and not yukari:
        s -= 0.25; notlar.append("RSI aşırı alımdan dönüyor")

    return kirp(s), notlar, f"RSI {son:.1f}{ok(r)}"


def skor_macd(df):
    mac, sin, hist = macd(df["close"])
    s, notlar = 0.0, []

    # MACD yavaş tepki verir: tetik değil, teyit göstergesi olarak puanlanır.
    if taze_seri_capraz(mac, sin):
        s += 0.45; notlar.append("MACD sinyal çizgisini yukarı kesti (makas açılıyor)")
    if donus_yukari(hist) and float(hist.iloc[-1]) < 0:
        s += 0.30; notlar.append("Histogram negatifte dip yapıp daralmaya başladı")
    if taze_capraz_yukari(hist, 0):
        s += 0.30; notlar.append("Histogram sıfırın üzerine geçti")
    if taze_capraz_yukari(mac, 0, bar=3):
        s += 0.25; notlar.append("MACD sıfır çizgisini yukarı kesti")
    if pozitif_uyumsuzluk(df["low"], hist) and yukarida_mi(hist):
        s += 0.30; notlar.append("MACD histogramında pozitif uyumsuzluk + dönüş")
    if ust_uste_yukari(hist, 2):
        s += 0.15; notlar.append("Histogram üst üste büyüyor (momentum artıyor)")

    if float(hist.iloc[-1]) < 0 and not yukarida_mi(hist):
        s -= 0.40; notlar.append("Histogram negatif ve genişliyor (satış baskısı)")
    if float(mac.iloc[-1]) < float(sin.iloc[-1]) and not yukarida_mi(mac):
        s -= 0.25; notlar.append("MACD sinyalin altında ve düşüyor")

    return kirp(s), notlar, f"hist {float(hist.iloc[-1]):+.4g}{ok(hist)}"


def skor_stoch_rsi(df):
    k, d = stoch_rsi(df["close"])
    s, notlar = 0.0, []
    sk, sd = float(k.iloc[-1]), float(d.iloc[-1])

    # StochRSI en hızlı tepki veren gösterge: TETİK. %K'nın fiilen yukarı
    # dönmüş olması şart; düşerken hiçbir olumlu puan verilmez.
    yukari = yukarida_mi(k)

    if taze_seri_capraz(k, d) and sk < 70:
        s += 0.50; notlar.append("StochRSI %K, %D'yi yukarı kesti (%K yükseliyor)")
    if taze_capraz_yukari(k, 20):
        s += 0.35; notlar.append("StochRSI aşırı satım (20) bölgesinden yukarı çıktı")
    if donus_yukari(k) and sk < 40:
        s += 0.35; notlar.append("StochRSI dipte yukarı döndü")
    if kesisime_yaklasiyor(k, d) and sk < 45:
        s += 0.25; notlar.append("StochRSI kesişime yaklaşıyor (%K döndü, makas kapanıyor)")
    if ust_uste_yukari(k, 2) and 20 <= sk <= 80:
        s += 0.15; notlar.append("StochRSI üst üste 2 mum yükseliyor")

    if not yukari and sk >= sd:
        s -= 0.30; notlar.append("%K, %D üstünde ama AŞAĞI döndü (kesişim bozuluyor)")
    if not yukari and sk < sd:
        s -= 0.35; notlar.append("StochRSI %K, %D altında ve düşüyor")
    if sk > 85 and not yukari:
        s -= 0.35; notlar.append("StochRSI tepeden dönüyor (aşırı alım)")

    return kirp(s), notlar, f"K {sk:.0f}{ok(k)}/D {sd:.0f}"


def skor_kdj(df):
    k, d, j = kdj(df["high"], df["low"], df["close"])
    s, notlar = 0.0, []
    sk, sd, sj = float(k.iloc[-1]), float(d.iloc[-1]), float(j.iloc[-1])

    if taze_seri_capraz(k, d) and sk < 65:
        s += 0.40; notlar.append("KDJ altın kesişim (%K yükselerek %D'yi kesti)")
    if donus_yukari(j) and float(j.iloc[-2]) < 25:
        s += 0.35; notlar.append("J çizgisi dipten yukarı döndü")
    if taze_capraz_yukari(j, 0):
        s += 0.30; notlar.append("J çizgisi sıfırın üzerine çıktı")
    if taze_capraz_yukari(k, 20):
        s += 0.25; notlar.append("KDJ aşırı satım bölgesinden yukarı çıktı")
    if kesisime_yaklasiyor(k, d) and sk < 45:
        s += 0.20; notlar.append("KDJ kesişime yaklaşıyor (%K döndü, henüz kesmedi)")
    if ust_uste_yukari(j, 2) and sj < 80:
        s += 0.15; notlar.append("J üst üste yükseliyor")

    if sj > 100 and not yukarida_mi(j):
        s -= 0.35; notlar.append("J tepeden dönüyor (aşırı alım)")
    if sk < sd and not yukarida_mi(k):
        s -= 0.35; notlar.append("KDJ ölüm kesişimi bölgesinde ve %K düşüyor")
    elif not yukarida_mi(j):
        s -= 0.25; notlar.append("J aşağı dönük")

    return kirp(s), notlar, f"J {sj:.0f}{ok(j)} K{sk:.0f}/D{sd:.0f}"


def skor_obv(df):
    o = obv(df["close"], df["volume"])
    o_ema = o.ewm(span=21, adjust=False).mean()
    s, notlar = 0.0, []

    # OBV birikim göstergesi: yön için son mum, güç için eğim kullanılır.
    if taze_seri_capraz(o, o_ema, bar=3):
        s += 0.40; notlar.append("OBV kendi EMA21'ini yukarı kesti (para girişi)")
    if pozitif_uyumsuzluk(df["low"], o) and egim(o, 3) > 0:
        s += 0.40; notlar.append("OBV pozitif uyumsuzluk (fiyat dip yaparken hacim birikiyor)")
    if egim(o, 5) > 0 and egim(df["close"], 5) <= 0:
        s += 0.30; notlar.append("Fiyat yatay/düşerken OBV yükseliyor (sessiz toplama)")
    if egim(o, 3) > 0 and float(o.iloc[-1]) > float(o_ema.iloc[-1]):
        s += 0.20; notlar.append("OBV EMA üzerinde ve yükseliyor")

    if egim(o, 5) < 0 and egim(df["close"], 5) >= 0:
        s -= 0.40; notlar.append("Fiyat yükselirken OBV düşüyor (dağıtım)")
    if egim(o, 3) < 0 and float(o.iloc[-1]) < float(o_ema.iloc[-1]):
        s -= 0.30; notlar.append("OBV EMA altında ve düşüyor")

    fark = (float(o.iloc[-1]) - float(o_ema.iloc[-1]))
    return kirp(s), notlar, ("OBV↑" if fark > 0 else "OBV↓")


def skor_williams(df):
    w = williams_r(df["high"], df["low"], df["close"])
    s, notlar = 0.0, []
    sw = float(w.iloc[-1])

    yukari = yukarida_mi(w)

    if taze_capraz_yukari(w, -80):
        s += 0.40; notlar.append("W%R -80 üzerine çıktı ve yükseliyor")
    if donus_yukari(w) and float(w.iloc[-2]) < -80:
        s += 0.30; notlar.append("W%R dipte yukarı döndü")
    if taze_capraz_yukari(w, -50):
        s += 0.30; notlar.append("W%R -50 orta bandını yukarı kesti")
    if pozitif_uyumsuzluk(df["low"], w) and yukari:
        s += 0.25; notlar.append("W%R pozitif uyumsuzluk + yukarı dönüş")
    if ust_uste_yukari(w, 2) and sw < -20:
        s += 0.15; notlar.append("W%R üst üste yükseliyor")

    if sw > -10 and not yukari:
        s -= 0.35; notlar.append("W%R aşırı alımdan dönüyor")
    if not yukari and sw < -50:
        s -= 0.30; notlar.append("W%R aşağı dönük, satıcı baskın")

    return kirp(s), notlar, f"W%R {sw:.0f}{ok(w)}"


def skor_ema(df):
    """
    EMA20 / EMA50 — DESTEKLEYİCİ gösterge, kesin şart değil.
      • Fiyatın EMA20'yi yukarı kırması → diğerleri destekliyorsa sağlam giriş anı
      • EMA20, EMA50 altındayken yukarı dönüp kesişime gitmesi → 2. dalga hazırlığı
    """
    kapanis = df["close"]
    e20, e50 = ema(kapanis, 20), ema(kapanis, 50)
    s, notlar = 0.0, []
    fiyat = float(kapanis.iloc[-1])
    u20, u50 = float(e20.iloc[-1]), float(e50.iloc[-1])

    # Sıralama: önce fiyat EMA20'yi keser (1. dalga / erken giriş),
    # sonra EMA20 EMA50'yi keser (2. dalga teyidi — geç ama sağlam).
    if taze_seri_capraz(kapanis, e20):
        s += 0.45
        notlar.append("Fiyat EMA20'yi yukarı kırdı"
                      + (" (EMA20 hâlâ EMA50 altında → 1. dalga girişi)"
                         if u20 < u50 else ""))
    elif fiyat > u20 and yukarida_mi(e20):
        s += 0.20; notlar.append("Fiyat EMA20 üzerinde, EMA20 yukarı dönük")

    if taze_seri_capraz(e20, e50):
        s += 0.40; notlar.append("EMA20, EMA50'yi yukarı kesti (2. dalga teyidi)")
    elif u20 < u50 and kesisime_yaklasiyor(e20, e50, bar=3):
        s += 0.30; notlar.append("EMA20, EMA50 altında ama yukarı dönüp kesişime "
                                 "yaklaşıyor (2. dalgaya hazırlık)")
    elif u20 > u50 and yukarida_mi(e20):
        s += 0.15; notlar.append("EMA20, EMA50 üzerinde ve yükseliyor")

    if fiyat < u20 and not yukarida_mi(e20):
        s -= 0.35; notlar.append("Fiyat EMA20 altında, EMA20 düşüyor")
    if u20 < u50 and not yukarida_mi(e20):
        s -= 0.25; notlar.append("EMA20, EMA50 altında ve aşağı dönük")

    konum = "fiyat>EMA20" if fiyat > u20 else "fiyat<EMA20"
    dizilim = "20>50" if u20 > u50 else "20<50"
    return kirp(s), notlar, f"{konum} {dizilim}{ok(e20)}"


def skor_yapi(df, pencere=3):
    """
    FİYAT YAPISI (LL / HL / HH / LH) — dönüşün fiyat tarafındaki kanıtı.
    Osilatörler fiyatın türevidir; hepsi birden 'döndü' derken fiyat hâlâ daha
    düşük dip yapıyor olabilir. Burada bakılan: satıcı önceki dibin altına
    indirebildi mi (LL devam) yoksa daha yüksek dip mi bıraktı (HL = dönüş).
    """
    yuksek, dusuk, kapanis = df["high"], df["low"], df["close"]
    fiyat = float(kapanis.iloc[-1])
    dipler = yerel_dipler(dusuk, pencere)
    tepeler = yerel_tepeler(yuksek, pencere)

    if len(dipler) < 2:
        return 0.0, ["yeterli yapı verisi yok"], "yapı ?"

    onceki_dip = float(dusuk.iloc[dipler[-2]])
    son_dip = float(dusuk.iloc[dipler[-1]])
    hl = son_dip > onceki_dip * 1.001          # higher low
    ll = son_dip < onceki_dip * 0.999          # lower low

    son_tepe = float(yuksek.iloc[tepeler[-1]]) if tepeler else None
    onceki_tepe = float(yuksek.iloc[tepeler[-2]]) if len(tepeler) > 1 else None
    hh = son_tepe and onceki_tepe and son_tepe > onceki_tepe * 1.001
    lh = son_tepe and onceki_tepe and son_tepe < onceki_tepe * 0.999

    s, notlar = 0.0, []

    if hl and son_tepe and fiyat > son_tepe:
        s += 0.55; notlar.append("Yapı yukarı kırıldı: HL sonrası son tepe aşıldı")
    elif hl and fiyat > son_dip:
        s += 0.35; notlar.append("Daha yüksek dip (HL) oluştu, fiyat dibin üstünde")

    if hh and hl:
        s += 0.25; notlar.append("Yükselen yapı (HH + HL)")

    if ll and fiyat <= son_dip * 1.005:
        s -= 0.45; notlar.append("Düşen dipler (LL) sürüyor, fiyat son dibin dibinde")
    elif ll and fiyat > son_dip * 1.015:
        s += 0.15; notlar.append("LL sonrası dipten tepki var ama HL teyidi yok")

    if lh and ll:
        s -= 0.25; notlar.append("Düşen tepeler (LH) + düşen dipler (LL)")
    elif lh and not hl:
        s -= 0.15; notlar.append("Son tepe bir öncekinin altında (LH)")

    yapi = "HL" if hl else ("LL" if ll else "=dip")
    tepe_yapi = "HH" if hh else ("LH" if lh else "=tepe")
    return kirp(s), notlar, f"{yapi}/{tepe_yapi} dip {son_dip:.6g}"


def atr_hesapla(df, periyot=14):
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return float(tr.rolling(periyot).mean().iloc[-1])


def cikis_plani(df, fiyat=None):
    """1 saatlik ATR'ye göre sabit stop ve hedef (bkz. STOP_ATR / HEDEF_ATR)."""
    try:
        atr = atr_hesapla(df)
        fiyat = float(fiyat or df["close"].iloc[-1])
        if not atr or not fiyat:
            return None
        return {
            "atr": atr,
            "stop": fiyat - STOP_ATR * atr,
            "hedef": fiyat + HEDEF_ATR * atr,
            "stop_yuzde": -STOP_ATR * atr / fiyat * 100,
            "hedef_yuzde": HEDEF_ATR * atr / fiyat * 100,
        }
    except Exception:
        return None


def _gunluk_geri(df, gun):
    """`gun` gün öncesine denk gelen satır indeksi (zaman damgasından)."""
    hedef = df["close_time"].iloc[-1] - pd.Timedelta(days=gun)
    uygun = df.index[df["close_time"] <= hedef]
    return int(uygun[-1]) if len(uygun) else 0


def skor_hacim(df):
    """
    HACİM PATLAMASI ve "ZATEN KAÇMIŞ MI" — 87 coin / 183 bin saatlik veri
    üzerinde yapılan ileri getiri testinin sonucu:

      • Osilatör kurulumları hacim patlaması olmadan rastgeleden KÖTÜ çalışıyor
        (hacim <2× iken +%20 olasılığı %1.2, taban %2.2)
      • Hacim ≥5× olduğunda aynı kurulum %11.2'ye çıkıyor
      • Son 7 günde %30'dan fazla yükselmiş coinde patlama olursa sıçrama sık
        ama TİPİK sonuç zarar (medyan -%1.2; %60 üstünde -%5.4) → spike & fade
      • Son 7 günde düşüşten gelen coinde patlama olursa sıçrama nadir ama
        işlemlerin %56'sı artıda kapanıyor ve risk yarı yarıya az
    """
    hac, islem, kapanis = df["quote_volume"], df["trades"], df["close"]
    if len(hac) < 60:
        return 0.0, ["yeterli veri yok"], "hacim ?"

    medyan = float(hac.iloc[-168:].median() or 0)
    patlama = float(hac.iloc[-6:].mean()) / medyan if medyan else 0.0
    islem_medyan = float(islem.iloc[-168:].median() or 0)
    islem_patlama = float(islem.iloc[-6:].mean()) / islem_medyan if islem_medyan else 0.0

    i7 = _gunluk_geri(df, 7)
    pump = (float(kapanis.iloc[-1]) / float(kapanis.iloc[i7]) - 1) * 100
    i1 = _gunluk_geri(df, 1)
    kosu = (float(kapanis.iloc[-1]) / float(kapanis.iloc[i1]) - 1) * 100

    j30 = _gunluk_geri(df, 30)
    dip = float(df["low"].iloc[j30:].min())
    tepe = float(df["high"].iloc[j30:].max())
    menzil = (float(kapanis.iloc[-1]) - dip) / (tepe - dip) * 100 if tepe > dip else 50.0

    s, notlar = 0.0, []

    # Hız kontrolü: 24 saatte %25+ koşmuşsa hacim patlaması ARTIK olumlu değil —
    # o noktada patlayan hacim birikim değil boşaltmadır (medyan -%7, kazanan %38).
    kacmis = kosu > 25

    # --- hacim patlaması
    if kacmis:
        notlar.append(f"Hacim {patlama:.1f}× ama fiyat 24 saatte %{kosu:.0f} koştu — "
                      f"bu hacim birikim değil boşaltma olabilir")
    elif patlama >= 8:
        s += 0.50; notlar.append(f"Hacim patlaması {patlama:.1f}× (normalin çok üstünde)")
    elif patlama >= 5:
        s += 0.40; notlar.append(f"Hacim patlaması {patlama:.1f}×")
    elif patlama >= 2:
        s += 0.15; notlar.append(f"Hacim normalin {patlama:.1f} katı")
    else:
        s -= 0.30; notlar.append(f"HACİMSİZ ({patlama:.1f}×) — bu durumda diğer "
                                 f"göstergelerin sinyali istatistiksel olarak değersiz")

    if islem_patlama >= 5 and patlama >= 3 and not kacmis:
        s += 0.20; notlar.append(f"İşlem sayısı da {islem_patlama:.1f}× "
                                 f"(gerçek katılım, şişirilmiş hacim değil)")

    # --- HIZ: son 24 saatte ne kadar koştu? (uzaklık değil, HIZ belirleyici)
    if kosu > 50:
        s -= 0.70; notlar.append(f"24 saatte %{kosu:.0f} koşmuş — KAÇMIŞ. "
                                 f"Bu noktada tipik sonuç -%9.4, kazanan oran %42")
    elif kosu > 25:
        s -= 0.45; notlar.append(f"24 saatte %{kosu:.0f} koşmuş — geç kalınmış, "
                                 f"tipik sonuç -%2.8, risk 3 katı")
    elif kosu > 10:
        s += 0.10; notlar.append(f"24 saatte %{kosu:.0f} — hareket başlamış ama "
                                 f"henüz aşırı değil (en verimli bölge)")

    # --- zaten kaçmış mı? (haftalık)
    if pump > 60:
        s -= 0.50; notlar.append(f"Son 7 günde %{pump:.0f} yükselmiş — aşırı pump, "
                                 f"tipik sonuç geri verme (medyan -%5.4)")
    elif pump > 30:
        s -= 0.35; notlar.append(f"Son 7 günde %{pump:.0f} yükselmiş — kaçmış olabilir, "
                                 f"sıçrasa da kalıcılığı düşük")
    elif pump < 0:
        s += 0.25; notlar.append(f"Son 7 günde %{pump:.0f} — düşüşten geliyor "
                                 f"(en tutarlı kova: %56 artıda kapanış)")

    # Menzil konumu yalnızca BİLGİ olarak taşınır, puan vermez.
    # Koşullu testte (teyitli sinyaller üzerinde) dip bölgesi tercihi zarar
    # ettirdi: menzil ALT medyan -%1.15 / kazanan %43.5, ÜST -%0.58 / %45.3.
    # Yani teyit varken "dipten al" kuralının istatistiksel dayanağı yok.

    ozet = (f"hacim {patlama:.1f}× · 24s {kosu:+.0f}% · 7g {pump:+.0f}% "
            f"· menzil %{menzil:.0f}")
    return kirp(s), notlar, ozet


SKORLAYICILAR = {
    "RSI": skor_rsi,
    "MACD": skor_macd,
    "StochRSI": skor_stoch_rsi,
    "KDJ": skor_kdj,
    "OBV": skor_obv,
    "Williams%R": skor_williams,
    "EMA20/50": skor_ema,
    "Yapı LL/HL": skor_yapi,
    "Hacim/Pump": skor_hacim,
}


# =============================================================================
#  BİRLEŞTİRME
# =============================================================================

def zaman_dilimi_analizi(df, aralik=None):
    """
    Her indikatörü BAĞIMSIZ puanlar, sonra zaman dilimine özel ağırlıklarla
    birleştirip zaman dilimi skorunu üretir.
    """
    agirliklar = IND_AGIRLIK_TF.get(aralik, IND_AGIRLIK)
    detay = {}
    toplam, agirlik_toplami = 0.0, 0.0

    for ad, fn in SKORLAYICILAR.items():
        try:
            skor, notlar, ozet = fn(df)
        except Exception as e:
            skor, notlar, ozet = 0.0, [f"hesaplanamadı: {e}"], "-"
        agirlik = agirliklar.get(ad, IND_AGIRLIK[ad])
        detay[ad] = {"skor": round(skor, 3), "notlar": notlar, "ozet": ozet}
        toplam += skor * agirlik
        agirlik_toplami += agirlik

    tf_skor = toplam / agirlik_toplami if agirlik_toplami else 0.0
    pozitif = sum(1 for d in detay.values() if d["skor"] >= 0.25)
    negatif = sum(1 for d in detay.values() if d["skor"] <= -0.25)

    i1 = _gunluk_geri(df, 1)
    kosu = (float(df["close"].iloc[-1]) / float(df["close"].iloc[i1]) - 1) * 100

    return {
        "skor": round(tf_skor, 3),
        "pozitif": pozitif,
        "negatif": negatif,
        "trend": trend_sinifi(df),
        "donus": donus_gucu(detay),
        "kosu_24s": round(kosu, 2),
        "indikatorler": detay,
    }


def trend_sinifi(df, daralma_bar=3):
    """
    Trend sınıflandırması — SADECE 1 GÜN ve 4 SAAT için kullanılır
    (1G: BTC + coin genel yön · 4S: coin fırsat değerlendirmesi).

    İki ayrı boyut:
      • Makasın İŞARETİ  (EMA20 > EMA50 mi)  → YÖN
      • Makasın EĞİMİ    (daralıyor/açılıyor) → EVRE

    Neden ayrı? 21 coin / 53 bin mumluk ileri getiri testinde:
      20>50 + açılıyor  : 4S %47.1 / 1G %52.8 yukarı  → gerçek yükseliş
      20>50 + daralıyor : 4S %47.5 / 1G %48.0 yukarı  → yükseliş içi DÜZELTME
                          (referansın altında değil — elenmemeli, alım bölgesi)
      20<50 + daralıyor : 4S %41.6 yukarı             → en zayıf durum;
                          "yükseliş" değil, olsa olsa DÖNÜŞ HAZIRLIĞI
      20<50 + açılıyor  : düşüşün kendisi
    """
    kapanis = df["close"]
    e20, e50 = ema(kapanis, 20), ema(kapanis, 50)
    fiyat = float(kapanis.iloc[-1])
    u20, u50 = float(e20.iloc[-1]), float(e50.iloc[-1])
    makas = (u20 - u50) / u50 * 100 if u50 else 0.0

    genislik = ((e20 - e50) / e50 * 100).abs()
    daraliyor = all(float(genislik.iloc[-1 - i]) < float(genislik.iloc[-2 - i])
                    for i in range(daralma_bar))
    e20_yukari = egim(e20, 3) > 0

    if makas > 0.5:                                   # EMA20 üstte → yükseliş yönü
        return "DÜZELTME" if daraliyor else "YÜKSELİŞ"

    if makas < -0.5:                                  # EMA20 altta → düşüş yönü
        if e20_yukari and fiyat > u20:
            return "DÖNÜŞ"                            # fiilen yukarı kıvrıldı
        return "DÖNÜŞ HAZIRLIĞI" if daraliyor else "DÜŞÜŞ"

    if e20_yukari and fiyat > u20:                    # makas dar
        return "DÖNÜŞ"
    return "YATAY"


# Dönüş yapısı sayılan not kalıpları (gerçekten "yukarı döndü" diyenler)
DONUS_KALIPLARI = ("yukarı kesti", "yukarı döndü", "yukarı çıktı", "yukarı kırdı",
                   "dipten", "üzerine geçti", "pozitif uyumsuzluk", "kesişime yaklaşıyor")


def donus_gucu(detay):
    """Kaç bağımsız gösterge fiilen 'dönüş' yapısı gösteriyor?"""
    sayi = 0
    for d in detay.values():
        if d["skor"] >= 0.25 and any(k in n for n in d["notlar"]
                                     for k in DONUS_KALIPLARI):
            sayi += 1
    return sayi


def giris_penceresi_acik(tf):
    """
    15 dakikalık teyit kapısı açık mı? (huninin 4. adımı)
      • StochRSI fiilen yukarı dönmüş (skor ≥ 0.25)
      • 15D genel skoru ≥ 0.15
      • en az 2 bağımsız gösterge dönüş yapısında
    Açıksa 15 dakikada alım yeri aranabilir.
    """
    on_bes = tf.get("15m", {})
    stoch = on_bes.get("indikatorler", {}).get("StochRSI", {}).get("skor", 0.0)
    return (stoch >= 0.25 and on_bes.get("skor", 0.0) >= 0.15
            and on_bes.get("donus", 0) >= 2)


def kucuk(metin):
    """Türkçe güvenli küçük harf ('İ'.lower() bozuk çıktı verir)."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def etiket(skor):
    if skor >= 0.50:
        return "GÜÇLÜ DÖNÜŞ"
    if skor >= 0.25:
        return "DÖNÜŞ BAŞLIYOR"
    if skor >= 0.05:
        return "ZAYIF TOPARLANMA"
    if skor > -0.20:
        return "NÖTR"
    if skor > -0.50:
        return "ZAYIF"
    return "DÜŞÜŞTE"


def karar_ver(tf, piyasa=None):
    """
    HUNİ — geniş zaman diliminden dar zaman dilimine sıralı eleme:

      ADIM 0  Piyasa (BTC 1G/4S) : genel hava uygun mu?
      ADIM 1  Coin 1 GÜN         : yükselişte mi ya da dönüş sonrası mı?
              → uygun değilse alt adımlara BAKILMAZ (elenir)
      ADIM 2  Coin 4 SAAT        : yükseliş mi, yatay mı, düşüş mü?
      ADIM 3  Coin 1 SAAT        : yükseliş başlangıcı (dönüş) var mı?
      ADIM 4  Coin 15 DAKİKA     : 1 saati teyit ediyor mu? → ALIM YERİ TESPİTİ

    15 dakika ölçüm değil, alım yeri çerçevesidir: yalnızca son adımda
    teyit kapısı olarak kullanılır, sıralama skoruna girmez.
    """
    def _tf(aralik):
        return tf.get(aralik, {})

    def _ind(aralik, ad):
        return _tf(aralik).get("indikatorler", {}).get(ad, {}).get("skor", 0.0)

    g, d = _tf("1d").get("skor", 0.0), _tf("4h").get("skor", 0.0)
    s, o = _tf("1h").get("skor", 0.0), _tf("15m").get("skor", 0.0)
    g_trend, d_trend = _tf("1d").get("trend", "?"), _tf("4h").get("trend", "?")
    s_donus, o_donus = _tf("1h").get("donus", 0), _tf("15m").get("donus", 0)

    def sonuc(sinif, aciklama, gecilen):
        """gecilen = huninin kaç adımı geçildi (0-4)."""
        isaret = "".join("✓" if i < gecilen else "✗" for i in range(4))
        return sinif, aciklama, isaret

    # --- ADIM 0: genel piyasa — BTC 1 GÜNLÜK trendi (elemez, kademe düşürür)
    piyasa_uyari = ""
    piyasa_kotu = False
    if piyasa:
        btc_g = piyasa.get("1d", {}).get("skor", 0.0)
        btc_trend = piyasa.get("1d", {}).get("trend", "?")
        if btc_trend in ("DÜŞÜŞ", "DÖNÜŞ HAZIRLIĞI") or btc_g < -0.15:
            piyasa_kotu = True
            piyasa_uyari = f" ⚠ BTC 1G {kucuk(btc_trend)} ({btc_g:+.2f})"

    # --- HIZ KAPISI: son 24 saatte çoktan koşmuş mu?
    # Ölçülen: uzaklık değil HIZ. EMA'dan 3+ ATR uzakta olmak, oraya yavaş
    # çıkıldıysa sorun değil (medyan +%2.5); 24 saatte %25+ koşmak ise
    # yakın da olsa kötü (medyan -%7, kazanan %38, risk 4 katı).
    kosu = tf.get("1h", {}).get("kosu_24s", 0.0)
    if kosu > 50:
        return sonuc("E — KAÇMIŞ",
                     f"Son 24 saatte %{kosu:.0f} koşmuş — tren kalkmış. Bu noktada "
                     f"girişin tipik sonucu -%9.4, kazanan oran %42, risk 5 katı. "
                     f"Soğumasını ve yeni bir dip yapısını bekle." + piyasa_uyari, 0)
    if kosu > 25:
        return sonuc("D — GEÇ KALINMIŞ",
                     f"Son 24 saatte %{kosu:.0f} koşmuş — geç kalınmış. Tipik sonuç "
                     f"-%2.8 ve risk 3 katı; geri çekilip yeniden kurulmasını bekle."
                     + piyasa_uyari, 0)

    # --- ADIM 1: 1 GÜNLÜK (coin) — genel yön uygun mu?
    # DÜZELTME = yükseliş içi geri çekilme; veri referansın altında olmadığını
    # gösterdiği için elenmez. DÖNÜŞ HAZIRLIĞI tek başına yeterli değil.
    if g_trend in ("YÜKSELİŞ", "DÖNÜŞ"):
        gun_uygun = g >= 0.0
    elif g_trend == "DÜZELTME":
        gun_uygun = g >= -0.05
    elif g_trend == "DÖNÜŞ HAZIRLIĞI":
        gun_uygun = g >= 0.25              # makas daralması tek başına yetmez
    else:                                  # DÜŞÜŞ / YATAY
        gun_uygun = g >= 0.35

    if not gun_uygun:
        return sonuc("E — 1G UYGUN DEĞİL",
                     f"1 günlük {kucuk(g_trend)} ({g:+.2f}) — huni burada kapandı, "
                     f"alt zaman dilimlerine bakmaya gerek yok." + piyasa_uyari, 0)

    # --- ADIM 2: 4 SAATLİK (coin) — alım fırsatı açısından nasıl?
    yapi_4s = _ind("4h", "Yapı LL/HL")
    if d_trend in ("YÜKSELİŞ", "DÖNÜŞ"):
        dort_uygun = d >= 0.0
    elif d_trend == "DÜZELTME":
        dort_uygun = d >= -0.05            # yükseliş içi geri çekilme = alım bölgesi
    elif d_trend in ("DÖNÜŞ HAZIRLIĞI", "YATAY"):
        # 4S'te en zayıf durum (%41.6 yukarı) → fiyat yapısından teyit şart
        dort_uygun = d >= 0.15 and yapi_4s >= 0.25
    else:                                  # DÜŞÜŞ
        dort_uygun = False

    if not dort_uygun:
        gerekce = (" — makas daralması tek başına yeterli değil, HL yapısı da yok"
                   if d_trend in ("DÖNÜŞ HAZIRLIĞI", "YATAY") else "")
        return sonuc("D — 4S UYGUN DEĞİL",
                     f"1G {kucuk(g_trend)} ✓ ama 4 saatlik {kucuk(d_trend)} "
                     f"({d:+.2f}){gerekce} — 4S'in düzelmesi gerek."
                     + piyasa_uyari, 1)

    # --- ADIM 3: 1 SAATLİK — yükseliş başlangıcı (dönüş) var mı?
    saat_donus = (s >= 0.20 and s_donus >= 2) or s >= 0.40
    if not saat_donus:
        return sonuc("C — 1S DÖNÜŞ BEKLE",
                     f"1G {kucuk(g_trend)} ✓ · 4S {kucuk(d_trend)} ✓ — sıra 1 saatlikte: "
                     f"dönüş henüz oluşmadı ({s:+.2f}, {s_donus} gösterge dönüşte)."
                     + piyasa_uyari, 2)

    # --- ADIM 4: 15 DAKİKA — 1 saati teyit ediyor mu?
    stoch_15 = _ind("15m", "StochRSI")
    teyit = giris_penceresi_acik(tf)

    # EMA ve yapı desteği (şart değil, gücü belirtir)
    olumlu_kaliplar = ("Fiyat EMA20'yi yukarı kırdı", "EMA20, EMA50'yi yukarı kesti",
                       "2. dalgaya hazırlık", "Yapı yukarı kırıldı",
                       "Daha yüksek dip (HL)", "Yükselen yapı")
    destek = []
    for aralik in ("1h", "4h", "15m"):
        for ad in ("EMA20/50", "Yapı LL/HL"):
            for n in _tf(aralik).get("indikatorler", {}).get(ad, {}).get("notlar", []):
                if any(k in n for k in olumlu_kaliplar):
                    destek.append(f"{aralik}: {n}")
    destek_yazi = (" | Destek → " + "; ".join(destek[:2])) if destek else ""

    # Hacim artık KAPI değil, BİLGİ. 500 günlük testte hacim patlaması medyan
    # sonucu iyileştirmedi, yalnızca oynaklığı artırdı (hacim ≥5×: +%20 olasılığı
    # %12.6 — tabanın 8 katı — ama 72s medyan -%1.72). Yani "piyango bileti"
    # seçici: hızlı çıkış disiplini olmadan tek başına anlamlı değil.
    hacim_skoru = _ind("1h", "Hacim/Pump")
    if hacim_skoru <= -0.20:
        hacim_notu = " | ⓘ hacim patlaması yok — hareket yavaş olabilir"
    elif hacim_skoru >= 0.40:
        hacim_notu = " | ⓘ hacim patlaması var — sert hareket ihtimali, çıkışını planla"
    else:
        hacim_notu = ""

    if teyit:
        sinif = "B — ALIM YERİ ARA (BTC zayıf)" if piyasa_kotu else "A — ALIM YERİ ARA"
        return sonuc(sinif,
                     f"1G {kucuk(g_trend)} ✓ · 4S {kucuk(d_trend)} ✓ · 1S dönüş ✓ "
                     f"({s_donus} gösterge) · 15D teyit ✓ (StochRSI {stoch_15:+.2f}) — "
                     f"15 dakikada alım yeri tespiti yap."
                     + destek_yazi + hacim_notu + piyasa_uyari, 4)

    return sonuc("B — 15D TEYİT BEKLE",
                 f"1G {kucuk(g_trend)} ✓ · 4S {kucuk(d_trend)} ✓ · 1S dönüş ✓ — "
                 f"15 dakika henüz teyit etmedi (StochRSI {stoch_15:+.2f}, "
                 f"skor {o:+.2f}). Teyit gelince alım yeri aranır."
                 + destek_yazi + hacim_notu + piyasa_uyari, 3)


def toplam_skor(tf):
    """Sıralama skoru — 15 dakika ağırlığı 0 olduğu için skora girmez."""
    toplam, agirlik = 0.0, 0.0
    for ad, w in TF_AGIRLIK.items():
        if ad in tf and w > 0:
            toplam += tf[ad]["skor"] * w
            agirlik += w
    return round(toplam / agirlik, 3) if agirlik else 0.0


# Hacim/pump ölçümü 7 ve 30 günlük geçmiş ister; dar zaman dilimlerinde
# bunun için daha çok mum gerekir.
MUM_ADEDI = {"1d": 320, "4h": 320, "1h": 400, "15m": 800}


# =============================================================================
#  ÖLÇÜLMÜŞ SİNYAL — geriye dönük testte kullanılan tanımın BİREBİR aynısı
# =============================================================================
# 78 coin / ~489 gün, 5 dakikalık çıkış simülasyonu (4/8 ATR), sonraki mumun
# açılışından giriş, %0.20 komisyon, coin başına 72 saat soğuma:
#
#   filtre yok                       : 22.5 sinyal/ay · %40.1 kazanan · +%0.56
#   TABAN + genişlik ≥2 + BTC'den zayıf:  4.4 sinyal/ay · %57.7 kazanan · +%3.20
#     %90 güven [+1.21, +5.30] · 1. yarı %57.1 / 2. yarı %58.1 kazanan
#
# Huni sınıfları (A/B/C…) ve skor BİLGİ amaçlıdır; ölçülmüş değildir.
# İşlem kararı bu tanıma dayanmalıdır.

GENISLIK_EVREN = 78       # test, hacimde ilk ~78 coinle yapıldı
GENISLIK_ESIK = 2         # aynı saatte en az 2 coinde taban şart
RS_ESIK = 0.0             # coin 24s getirisi − BTC 24s getirisi ≤ 0
SOGUMA_SAAT = 72          # aynı coine 72 saat içinde yeni sinyal yok


def _vek_donus_sayisi(df):
    """Testteki dönüş sayacı (5 bağımsız dönüş şartı)."""
    k = df["close"]
    r = rsi(k)
    kk, dd = stoch_rsi(k)
    mac, sin, hist = macd(k)
    kj, dj, _ = kdj(df["high"], df["low"], k)
    w = williams_r(df["high"], df["low"], k)
    return ((((kk > dd) & (kk.shift() <= dd.shift()) & (kk > kk.shift()) & (kk < 70)).astype(int))
            + (((r > r.shift()) & (r.shift() <= r.shift(2)) & (r < 60)).astype(int))
            + ((((hist > hist.shift()) & (hist.shift() <= hist.shift(2)) & (hist < 0))
                | ((mac > sin) & (mac.shift() <= sin.shift()))).astype(int))
            + (((kj > dj) & (kj.shift() <= dj.shift()) & (kj > kj.shift())).astype(int))
            + (((w > -80) & (w.shift() <= -80) & (w > w.shift())).astype(int)))


def _vek_trend_uygun(df):
    """Testteki 1G/4S yön kapısı."""
    k = df["close"]
    e20, e50 = ema(k, 20), ema(k, 50)
    return ((e20 - e50) / e50 * 100 > 0.5) | ((e20 > e20.shift(3)) & (k > e20))


def kapanmis(df):
    """Oluşan (kapanmamış) son mumu atar — test kapanmış mumlarla yapıldı."""
    if df is None or not len(df):
        return df
    if df["close_time"].iloc[-1] > pd.Timestamp.now(tz="UTC"):
        return df.iloc[:-1].reset_index(drop=True)
    return df


def olculmus_taban(df_1h, df_4h, df_1d):
    """Ölçülen sinyalin coine ait taban şartları (genişlik ve RS sonradan eklenir)."""
    try:
        a, b, c = kapanmis(df_1h), kapanmis(df_4h), kapanmis(df_1d)
        # Test ile aynı asgari veri: 1s'te 169 mum (7g getiri), 4s/1g'de 4 mum
        if a is None or b is None or c is None or len(a) < 169 or len(b) < 4 or len(c) < 4:
            return None
        k = a["close"]
        hac = a["quote_volume"]
        medyan = float(hac.rolling(168).median().iloc[-1])
        hacim = float(hac.rolling(6).mean().iloc[-1]) / medyan if medyan else 0.0
        pump = (float(k.iloc[-1]) / float(k.iloc[-169]) - 1) * 100
        kosu = (float(k.iloc[-1]) / float(k.iloc[-25]) - 1) * 100
        donus = int(_vek_donus_sayisi(a).iloc[-1])
        sartlar = {
            "1G yön": bool(_vek_trend_uygun(c).iloc[-1]),
            "4S yön": bool(_vek_trend_uygun(b).iloc[-1]),
            f"1S dönüş ≥2 ({donus})": donus >= 2,
            f"hacim ≥5× ({hacim:.1f}×)": hacim >= 5,
            f"7g <%30 ({pump:+.0f}%)": pump < 30,
            f"24s <%25 ({kosu:+.0f}%)": kosu < 25,
        }
        return {"taban": all(sartlar.values()), "sartlar": sartlar, "kosu": kosu,
                "mum": a["close_time"].iloc[-1].strftime(TARIH_BICIM)}
    except Exception:
        return None


SINYAL_GECMISI_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "donus_tarayici_sinyal_gecmisi.json")


def sinyal_gecmisi_oku():
    try:
        with open(SINYAL_GECMISI_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sinyal_gecmisi_yaz(gecmis):
    try:
        gecici = SINYAL_GECMISI_DOSYASI + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(gecmis, f, ensure_ascii=False, indent=1)
        os.replace(gecici, SINYAL_GECMISI_DOSYASI)
    except Exception as e:
        print(f"Sinyal geçmişi yazılamadı: {e}")


def olculmus_sinyalleri_isaretle(sonuclar, btc_kosu, gecmis=None, simdi=None):
    """
    Tarama bitince TÜM analiz edilen coinler üzerinde çalışır:
      • genişlik: hacimde ilk GENISLIK_EVREN coinde kaçında taban şart var
      • RS: coin 24s getirisi − BTC 24s getirisi
      • soğuma: aynı coine SOGUMA_SAAT içinde verilmiş sinyal varsa yeni sayılmaz
    Her sonuca r['olculmus'] = {'durum', 'sinyal', 'genislik', 'rs'} ekler.
    """
    gecmis = gecmis if gecmis is not None else {}
    simdi = simdi or time.time()
    sirali = sorted(sonuclar, key=lambda r: r.get("hacim", 0.0), reverse=True)
    for i, r in enumerate(sirali, 1):
        r["_hacim_sirasi"] = i
    genislik = sum(1 for r in sirali[:GENISLIK_EVREN]
                   if (r.get("olcum") or {}).get("taban"))

    for r in sonuclar:
        o = r.get("olcum")
        b = {"durum": "—", "sinyal": False, "genislik": genislik, "rs": None}
        if not o:
            b["durum"] = "veri yok"
        elif not o["taban"]:
            b["durum"] = "—"
        elif r["_hacim_sirasi"] > GENISLIK_EVREN:
            b["durum"] = "taban ✓ · test dışı"
        else:
            rs = (o["kosu"] - btc_kosu) if btc_kosu is not None else None
            b["rs"] = rs
            if genislik < GENISLIK_ESIK:
                b["durum"] = f"taban ✓ · genişlik {genislik}"
            elif rs is None or rs > RS_ESIK:
                b["durum"] = "taban ✓ · BTC'den güçlü"
            else:
                kayit = gecmis.get(r["sembol"])
                if kayit and kayit.get("mum") != o["mum"] and \
                        simdi - kayit.get("ts", 0) < SOGUMA_SAAT * 3600:
                    b["durum"] = f"soğumada ({(simdi - kayit['ts']) / 3600:.0f}s önce)"
                else:
                    b["durum"] = "✓ SİNYAL"
                    b["sinyal"] = True
                    if not kayit or kayit.get("mum") != o["mum"]:
                        gecmis[r["sembol"]] = {"ts": simdi, "mum": o["mum"],
                                               "fiyat": r.get("fiyat")}
        r["olculmus"] = b
    return genislik


def btc_kosu_24s():
    """BTC'nin kapanmış 1 saatlik mumlarla son 24 saatlik getirisi."""
    df = kapanmis(mum_getir("BTCUSDT", "1h", 60))
    if df is None or len(df) < 26:
        return None
    return (float(df["close"].iloc[-1]) / float(df["close"].iloc[-25]) - 1) * 100


def sembol_analiz(bilgi, mum_adedi=None, piyasa=None):
    """Tek sembol için tüm zaman dilimlerini analiz eder ve huniden geçirir."""
    tf, dfler = {}, {}
    for aralik in ZAMAN_DILIMLERI:
        df = mum_getir(bilgi["sembol"], aralik,
                       mum_adedi or MUM_ADEDI.get(aralik, 320))
        if df is None:
            continue
        tf[aralik] = zaman_dilimi_analizi(df, aralik)
        dfler[aralik] = df
    df_1h = dfler.get("1h")

    if len(tf) < len(ZAMAN_DILIMLERI):
        return None

    sinif, aciklama, huni = karar_ver(tf, piyasa)
    return {
        **bilgi,
        "tf": tf,
        "toplam": toplam_skor(tf),
        "sinif": sinif,
        "aciklama": aciklama,
        "huni": huni,
        "cikis": cikis_plani(df_1h, bilgi.get("fiyat")) if df_1h is not None else None,
        "olcum": olculmus_taban(dfler.get("1h"), dfler.get("4h"), dfler.get("1d")),
        "zaman": datetime.now().strftime(TARIH_BICIM),
    }


def btc_durumu(mum_adedi=None):
    """BTC için 1h/4h/1d piyasa durumu."""
    sonuc = {}
    for aralik in ("1d", "4h", "1h"):
        df = mum_getir("BTCUSDT", aralik, mum_adedi or MUM_ADEDI.get(aralik, 320))
        if df is not None:
            sonuc[aralik] = zaman_dilimi_analizi(df, aralik)
    return sonuc


# =============================================================================
#  HTML RAPOR
# =============================================================================

def html_rapor(sonuclar, btc, yol):
    ts = datetime.now().strftime("%d-%m-%Y %H:%M")

    def renk(s):
        if s >= 0.50: return "#0ecb81"
        if s >= 0.25: return "#7ed957"
        if s >= 0.05: return "#d3d34a"
        if s > -0.20: return "#9aa0a6"
        return "#f6465d"

    btc_html = ""
    for ad in ("1d", "4h", "1h"):
        if ad in btc:
            sk = btc[ad]["skor"]
            btc_html += (f'<span class="rozet" style="border-color:{renk(sk)};'
                         f'color:{renk(sk)}">BTC {ad}: {sk:+.2f} · {etiket(sk)}</span>')

    satirlar = []
    for i, r in enumerate(sonuclar, 1):
        hucre = "".join(
            f'<td style="color:{renk(r["tf"][a]["skor"])}">{r["tf"][a]["skor"]:+.2f}'
            f'<small> {r["tf"][a].get("trend", "")}</small></td>'
            for a in ZAMAN_DILIMLERI)

        detay = []
        for a in ZAMAN_DILIMLERI:
            ind = r["tf"][a]["indikatorler"]
            parcalar = []
            for ad in INDIKATORLER:
                d = ind[ad]
                notlar = "<br>".join("· " + html.escape(n) for n in d["notlar"]) or "—"
                parcalar.append(
                    f'<div class="ind"><b style="color:{renk(d["skor"])}">{ad} '
                    f'{d["skor"]:+.2f}</b> <i>{html.escape(d["ozet"])}</i>'
                    f'<div class="nt">{notlar}</div></div>')
            detay.append(f'<div class="tf"><h4>{a} — skor {r["tf"][a]["skor"]:+.2f} '
                         f'({etiket(r["tf"][a]["skor"])})</h4>{"".join(parcalar)}</div>')

        satirlar.append(f"""
<tr class="ana" onclick="ac({i})">
  <td>{i}</td><td><b>{html.escape(r['coin'])}</b></td>
  <td>{r['fiyat']:.8g}</td>
  <td style="color:{'#0ecb81' if r['degisim'] >= 0 else '#f6465d'}">{r['degisim']:+.2f}%</td>
  <td>{r['hacim'] / 1e6:,.1f}M</td>
  <td style="color:{renk(r['toplam'])}"><b>{r['toplam']:+.2f}</b></td>
  <td><code>{html.escape(r.get("huni", ""))}</code></td>
  {hucre}
  <td>{html.escape(r['sinif'])}</td>
  <td><small>{html.escape(r.get('zaman', ''))}</small></td>
</tr>
<tr id="d{i}" class="detay"><td colspan="13">
  <p class="ack">{html.escape(r['aciklama'])}</p>
  <div class="grid">{''.join(detay)}</div>
</td></tr>""")

    icerik = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>Dönüş Tarama Raporu — {ts}</title><style>
body{{background:#0d1117;color:#e6edf3;font:14px/1.5 "Segoe UI",system-ui,sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 4px}} .alt{{color:#8b949e;font-size:13px;margin-bottom:14px}}
.rozet{{display:inline-block;border:1px solid;border-radius:6px;padding:4px 10px;margin:0 6px 10px 0;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#161b22;color:#8b949e;text-align:left;padding:8px;position:sticky;top:0}}
td{{padding:7px 8px;border-bottom:1px solid #21262d}}
tr.ana{{cursor:pointer}} tr.ana:hover td{{background:#161b22}}
tr.detay{{display:none;background:#0b0f14}} tr.detay.acik{{display:table-row}}
.ack{{color:#8b949e;margin:6px 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;padding-bottom:10px}}
.tf{{background:#11161d;border:1px solid #21262d;border-radius:8px;padding:10px}}
.tf h4{{margin:0 0 8px;font-size:13px;color:#c9d1d9}}
.ind{{margin-bottom:8px;font-size:12px}} .nt{{color:#8b949e;margin-top:2px}}
small{{color:#6e7681}} i{{color:#8b949e;font-style:normal}}
</style></head><body>
<h1>Spot Dönüş Tarama Raporu</h1>
<div class="alt">{ts} · {len(sonuclar)} aday · Stablecoin ve fiat pariteler dışlandı ·
Her indikatör bağımsız puanlanıp birleştirildi</div>
<div>{btc_html}</div>
<table><thead><tr><th>#</th><th>Coin</th><th>Fiyat</th><th>24s</th><th>Hacim</th>
<th>SKOR</th><th>Huni</th><th>1G</th><th>4S</th><th>1S</th><th>15D</th><th>Karar</th>
<th>Sinyal zamanı</th></tr></thead>
<tbody>{''.join(satirlar)}</tbody></table>
<p class="alt">Bu rapor karar-destek amaçlıdır, yatırım tavsiyesi değildir.</p>
<script>function ac(i){{document.getElementById('d'+i).classList.toggle('acik')}}</script>
</body></html>"""

    with open(yol, "w", encoding="utf-8") as f:
        f.write(icerik)
    return yol


# =============================================================================
#  GUI
# =============================================================================

ARKA = "#0d1117"
PANEL = "#161b22"
CIZGI = "#21262d"
YAZI = "#e6edf3"
SOLUK = "#8b949e"
YESIL = "#0ecb81"
KIRMIZI = "#f6465d"
SARI = "#d3d34a"
MAVI = "#3b82f6"


def skor_rengi(s):
    if s >= 0.50: return YESIL
    if s >= 0.25: return "#7ed957"
    if s >= 0.05: return SARI
    if s > -0.20: return SOLUK
    return KIRMIZI


# ----------------------------------------------------------- ayar kalıcılığı

def ayarlari_oku():
    try:
        with open(AYAR_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def izleme_oku():
    """İzleme listesini döndürür. Dosya hiç yoksa None (göç gerekir)."""
    try:
        with open(IZLEME_DOSYASI, encoding="utf-8") as f:
            veri = json.load(f)
        return veri.get("izleme", []) if isinstance(veri, dict) else list(veri)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"İzleme listesi okunamadı: {e}")
        return []


def izleme_yaz(kayitlar, zorla=False, yedek_adet=10):
    """
    Atomik yazar ve her yazımdan önce mevcut listeyi yedekler.
    KORUMA: dolu bir listenin üzerine boş liste yazılmaz (zorla=True hariç).
    Böylece ikinci bir örnek ya da hatalı bir çalışma listeyi silemez.
    """
    mevcut = izleme_oku() or []
    if not kayitlar and mevcut and not zorla:
        return False

    try:
        if mevcut:
            os.makedirs(YEDEK_KLASORU, exist_ok=True)
            yedek = os.path.join(YEDEK_KLASORU,
                                 f"izleme_{datetime.now():%Y%m%d_%H%M%S}.json")
            with open(yedek, "w", encoding="utf-8") as f:
                json.dump({"izleme": mevcut}, f, ensure_ascii=False, indent=2)
            eskiler = sorted(os.listdir(YEDEK_KLASORU))
            for ad in eskiler[:-yedek_adet]:
                try:
                    os.remove(os.path.join(YEDEK_KLASORU, ad))
                except OSError:
                    pass

        gecici = IZLEME_DOSYASI + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({"guncelleme": datetime.now().strftime(TARIH_BICIM),
                       "izleme": kayitlar}, f, ensure_ascii=False, indent=2)
        os.replace(gecici, IZLEME_DOSYASI)      # atomik
        return True
    except Exception as e:
        print(f"İzleme listesi kaydedilemedi: {e}")
        return False


def ayarlari_yaz(ayar):
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ayarlar kaydedilemedi: {e}")


# --------------------------------------------------------- çoklu ekran desteği

def ekranlar():
    """
    Bağlı ekranların çalışma alanlarını döndürür:
        [(x, y, genislik, yukseklik), …]   — ilk sıradaki ana ekran.
    Windows dışında veya hata halinde boş liste döner.
    """
    if not sys.platform.startswith("win"):
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        bulunan = []

        def geri_cagri(tanitici, _hdc, _rect, _veri):
            bilgi = MONITORINFO()
            bilgi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(tanitici),
                                                    ctypes.byref(bilgi)):
                c = bilgi.rcWork
                bulunan.append((c.left, c.top, c.right - c.left,
                                c.bottom - c.top, bool(bilgi.dwFlags & 1)))
            return 1

        imza = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.POINTER(RECT), ctypes.c_double)
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, imza(geri_cagri), 0)

        # Ana ekran 1 numara, kalanlar soldan sağa
        bulunan.sort(key=lambda m: (not m[4], m[0]))
        return [(x, y, g, y2) for x, y, g, y2, _ in bulunan]
    except Exception:
        return []


def imlec_konumu():
    try:
        import ctypes
        from ctypes import wintypes
        nokta = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(nokta))
        return nokta.x, nokta.y
    except Exception:
        return None


def noktadaki_ekran(x, y):
    """(x, y) ekran koordinatının bulunduğu monitörün çalışma alanı."""
    for alan in ekranlar():
        ax, ay, gen, yuk = alan
        if ax <= x < ax + gen and ay <= y < ay + yuk:
            return alan
    return None


def hedef_ekran(secim):
    """Seçime göre (x, y, genislik, yukseklik) çalışma alanı döndürür."""
    liste = ekranlar()
    if not liste:
        return None

    secim = str(secim).strip().lower()
    if secim.isdigit():
        sira = max(1, int(secim)) - 1
        return liste[sira] if sira < len(liste) else liste[0]

    konum = imlec_konumu()
    if konum:
        fx, fy = konum
        for x, y, g, yk in liste:
            if x <= fx < x + g and y <= fy < y + yk:
                return (x, y, g, yk)
    return liste[0]


# Tk tablosu tek hücrede kalın font desteklemez; coin adları Unicode
# "Mathematical Sans-Serif Bold" harfleriyle kalın gösterilir.
_KALIN = {**{chr(65 + i): chr(0x1D5D4 + i) for i in range(26)},
          **{chr(97 + i): chr(0x1D5EE + i) for i in range(26)},
          **{chr(48 + i): chr(0x1D7EC + i) for i in range(10)}}


def kalin(metin):
    return "".join(_KALIN.get(h, h) for h in str(metin))


def gecen_sure(baslangic_ts):
    saniye = max(0, int(time.time() - baslangic_ts))
    gun, kalan = divmod(saniye, 86400)
    saat, kalan = divmod(kalan, 3600)
    dakika = kalan // 60
    if gun:
        return f"{gun}g {saat}s"
    if saat:
        return f"{saat}s {dakika}dk"
    return f"{dakika}dk"


# ----------------------------------------------------- sütun açıklamaları (balon)

TARAMA_ACIKLAMA = {
    "ekle": "Coini izleme listesine ekler.\n✓ işareti zaten listede olduğunu gösterir.",
    "sira": "Sıra numarası — seçili sıralamaya göre değişir.\nBaşlığa tıklayarak sıralama yapabilirsin.",
    "coin": "USDT paritesi. Stablecoin ve fiat pariteler\ntaramaya hiç alınmaz.",
    "fiyat": "Son işlem fiyatı (tarama anındaki).",
    "degisim": "Son 24 saatteki fiyat değişimi.",
    "hacim": "Son 24 saatlik işlem hacmi (milyon $).\nAyarlardaki eşiğin altındakiler taranmaz.",
    "toplam": "SIRALAMA SKORU\n1 GÜN (%30) + 4 SAAT (%35) + 1 SAAT (%35)\n\n"
              "15 dakika bu skora GİRMEZ — o bir ölçüm\nçerçevesi değil, alım yeri tespit çerçevesidir.",
    "huni": "Huninin kaç adımı geçildi:\n"
            "1️⃣ 1G yön → 2️⃣ 4S fırsat → 3️⃣ 1S dönüş → 4️⃣ 15D teyit\n\n"
            "✓✓✓✓ = dördü de tamam (alım yeri aranabilir)\n"
            "✓✓✗✗ = ilk iki adım geçti, 1 saatlik dönüş bekleniyor",
    "1d": "1. ADIM — genel yön.\nSkor ve trend: YÜKSELİŞ / DÜZELTME / DÖNÜŞ /\n"
          "DÖNÜŞ HAZIRLIĞI / YATAY / DÜŞÜŞ\n\n"
          "Uygun değilse alt zaman dilimlerine bakılmaz.",
    "4h": "2. ADIM — alım fırsatı değerlendirmesi.\n"
          "Yükseliş mi, düzeltme mi, yatay mı, düşüş mü?\n\n"
          "DÜZELTME = yükseliş içi geri çekilme (elenmez).\n"
          "DÖNÜŞ HAZIRLIĞI = makas daralıyor ama henüz\nyükseliş değil; HL yapı teyidi istenir.",
    "1h": "3. ADIM — yükseliş başlangıcı (dönüş) oluştu mu?\n"
          "Parantez içi: kaç bağımsız gösterge fiilen\n'yukarı döndü' yapısında.\n\n"
          "En az 2 gösterge gerekir.",
    "15m": "4. ADIM — 1 saati teyit ediyor mu?\n"
           "Burası ALIM YERİ TESPİT çerçevesi, ölçüm değil.\n\n"
           "StochRSI yukarı dönmeden bu adım geçilmez.",
    "sinif": "Huni kararı:\n"
             "A — alım yeri ara (4 adım tamam)\n"
             "B — 15 dakika teyidi bekleniyor\n"
             "C — 1 saatlik dönüş bekleniyor\n"
             "D — 4 saatlik uygun değil\n"
             "E — 1 günlük uygun değil (huni kapandı)",
    "tarih": "Bu satırın hesaplandığı an — yani taramanın\nbu coine geldiği zaman.",
    "olcum": ("ÖLÇÜLEN SİNYAL — geriye dönük testte kullanılan tanımın aynısı\n"
              "(kapanmış 1 saatlik mumlarla)\n\n"
              "TABAN (coine ait): 1G yön · 4S yön · 1S'te ≥2 dönüş ·\n"
              "hacim ≥5× · 7 günde <%30 · 24 saatte <%25\n"
              "+ GENİŞLİK: hacimde ilk 78 coinden ≥2'sinde aynı anda taban\n"
              "+ BTC'DEN ZAYIF: coinin 24s getirisi ≤ BTC'ninki\n"
              "+ SOĞUMA: aynı coine son 72 saatte sinyal verilmemiş\n\n"
              "Test (78 coin, ~489 gün, 5dk çıkış, 4/8 ATR, komisyon dahil):\n"
              "ayda ~4.4 sinyal · %57.7 kazanan · işlem başına +%3.20\n"
              "%90 güven [+1.21, +5.30] · iki yarıda %57.1 / %58.1 kazanan\n\n"
              "'taban ✓ · genişlik 1' = coin uygun ama piyasa geneli dönüş yok\n"
              "'taban ✓ · BTC'den güçlü' = coin zaten BTC'den fazla koşmuş\n"
              "'taban ✓ · test dışı' = hacim sırası 78'in dışında, ölçülmedi\n\n"
              "Huni ve SKOR bilgi amaçlıdır, ölçülmemiştir."),
    "cikis": ("ÇIKIŞ PLANI (1 saatlik ATR'ye göre)\n"
              f"stop girişin {STOP_ATR:g}×ATR altında · "
              f"hedef {HEDEF_ATR:g}×ATR üstünde\n\n"
              "78 coin / 500 gün / 772 gerçek sinyal, 5 DAKİKALIK mumlarla:\n"
              "%42.6 kazanan · net beklenti +%1.58 · kâr faktörü 1.45\n"
              "ortalama kazanç +%11.99 · ortalama zarar -%6.15\n\n"
              "Takip eden stop denendi ve elendi: 1 saatlik mumla iyi\n"
              "görünüyordu ama 5 dakikalıkla beklentisi yarıya düştü\n"
              "(+%1.52 → +%0.87). Kaba mum, takip stopunu tetikleyen\n"
              "mum-içi geri çekilmeleri gizliyor. Sabit hedef etkilenmiyor.\n\n"
              "ATR sabit yüzde değildir: her coin kendi oynaklığına göre\n"
              "ölçülür. Tipik coinde stop ≈ -%9.9, hedef ≈ +%19.8."),
}

IZLEME_ACIKLAMA = {
    "sil": "Coini izleme listesinden çıkarır.\nSilmeden önce otomatik yedek alınır.",
    "tarih": "Coini izleme listesine eklediğin an.",
    "huni": "ŞU ANKİ huni durumu ve sınıfı.\n5 dakikada bir (ve ↻ düğmesiyle) yenilenir.\n\n"
            "Eklediğin andaki durum değil, güncel durum.",
    "coin": "İzlenen coin.",
    "fiyat": "CANLI fiyat — 10 saniyede bir yenilenir.",
    "degisim": "Sinyal fiyatına göre değişim.\n\n"
               "▲ yeşil satır = eklediğinden beri artıda\n"
               "▼ kırmızı satır = ekside\n\n"
               "Satırın rengi bu değere göre belirlenir.",
    "giris": "Coini listeye eklediğin andaki fiyat.\nDonmuştur, değişmez — kıyas noktan.",
    "cikis": ("Eklendiği andaki ATR'ye göre hesaplanan stop ve hedef.\n"
              "Seviyeler donmuştur — sonradan kaymaz.\n\n"
              "S −x% = stop seviyesine kalan mesafe\n"
              "H +y% = hedef seviyesine kalan mesafe\n\n"
              "Fiyat seviyeye değince '✗ STOP GELDİ' veya\n"
              "'🎯 HEDEF GELDİ' yazar, Durum sütununa da yansır."),
    "en_yuksek": "Eklediğinden beri görülen EN YÜKSEK fiyatın\nsinyal fiyatına oranı.\n\n"
                 "Kaçırdığın tepeyi gösterir.",
    "en_dusuk": "Eklediğinden beri görülen EN DÜŞÜK fiyatın\nsinyal fiyatına oranı.\n\n"
                "En kötü anı (maksimum geri çekilme) gösterir.",
    "sure": "Listeye eklenmesinden bu yana geçen süre.",
    "sinyal_skor": "Coini listeye eklediğin andaki skor.\n"
                   "Donmuştur, değişmez — kıyas noktan.\n\n"
                   "1G + 4S + 1S ağırlıklı ortalaması (15dk dahil değil).",
    "anlik_skor": "Aynı skorun ŞU ANKİ değeri.\n"
                  "5 dakikada bir (ve ↻ düğmesiyle) yenilenir.\n\n"
                  "Sinyal skorundan düşükse coin zayıflıyor,\n"
                  "yüksekse güçleniyor.",
    "durum": "Sinyalin sağlığı:\n"
             "✓ korunuyor — skor eklediğin seviyede\n"
             "~ kısmen korunuyor — zayıflamış ama ayakta\n"
             "⚠ zayıflıyor — skor yarıdan fazla düştü\n"
             "✗ SİNYAL BOZULDU — skor negatife geçti",
    "pencere": "15 DAKİKALIK TEYİT KAPISI\n"
               "Açık olması için üçü birden gerekir:\n"
               "• StochRSI fiilen yukarı dönmüş\n"
               "• 15D skoru yeterli\n"
               "• en az 2 gösterge dönüş yapısında\n\n"
               "AÇIK ise 15 dakikada alım yeri aranabilir.\n"
               "Yanındaki süre kapının ne kadardır açık olduğudur.\n\n"
               "DİKKAT: Huni sütunu ✗ gösterirken kapının AÇIK\n"
               "olması tuzak işaretidir — dar çerçeve dönmüş ama\n"
               "1G/4S bozuk (düşen bıçak).",
}


class Balon:
    """Fare üzerine gelince açıklama balonu gösterir, ayrılınca kaybolur."""

    def __init__(self, tablo, aciklamalar, gecikme=420):
        self.tablo = tablo
        self.aciklamalar = aciklamalar
        self.gecikme = gecikme
        self.pencere = None
        self.zamanlayici = None
        self.son_sutun = None

        tablo.bind("<Motion>", self._hareket, add="+")
        tablo.bind("<Leave>", lambda _o: self.gizle(), add="+")
        tablo.bind("<Button-1>", lambda _o: self.gizle(), add="+")
        tablo.bind("<MouseWheel>", lambda _o: self.gizle(), add="+")

    def _hareket(self, olay):
        bolge = self.tablo.identify_region(olay.x, olay.y)
        if bolge not in ("cell", "heading"):
            self.gizle()
            return
        sutun_no = self.tablo.identify_column(olay.x)
        try:
            sutun = self.tablo["columns"][int(sutun_no.replace("#", "")) - 1]
        except (ValueError, IndexError):
            self.gizle()
            return

        if sutun == self.son_sutun and self.pencere:
            return
        self.gizle()
        self.son_sutun = sutun

        metin = self.aciklamalar.get(sutun)
        if not metin:
            return
        baslik = self.tablo.heading(sutun, "text").strip()
        self.zamanlayici = self.tablo.after(
            self.gecikme, lambda: self.goster(baslik, metin, olay.x_root, olay.y_root))

    def goster(self, baslik, metin, x, y):
        self.gizle()
        self.pencere = tk.Toplevel(self.tablo)
        self.pencere.wm_overrideredirect(True)
        self.pencere.attributes("-topmost", True)

        cerceve = tk.Frame(self.pencere, bg=CIZGI, padx=1, pady=1)
        cerceve.pack()
        ic = tk.Frame(cerceve, bg=PANEL, padx=10, pady=8)
        ic.pack()
        if baslik:
            tk.Label(ic, text=baslik, bg=PANEL, fg=YAZI, justify="left",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(ic, text=metin, bg=PANEL, fg=SOLUK, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w")

        self.pencere.update_idletasks()
        gen, yuk = self.pencere.winfo_width(), self.pencere.winfo_height()
        sol, ust = x + 16, y + 20

        # Balon, farenin BULUNDUĞU ekranın içinde kalmalı.
        # (winfo_screenwidth() Windows'ta sadece birincil ekranı bildirir;
        #  çoklu ekranda balonu yanlış monitöre atar.)
        alan = noktadaki_ekran(x, y)
        if alan:
            ax, ay, ekran_gen, ekran_yuk = alan
            if sol + gen > ax + ekran_gen - 8:
                sol = max(ax + 8, x - gen - 16)        # imlecin soluna al
            if ust + yuk > ay + ekran_yuk - 8:
                ust = max(ay + 8, y - yuk - 12)        # imlecin üstüne al
            sol = min(max(sol, ax + 8), ax + ekran_gen - gen - 8)
            ust = min(max(ust, ay + 8), ay + ekran_yuk - yuk - 8)

        self.pencere.wm_geometry(f"+{int(sol)}+{int(ust)}")

    def gizle(self):
        if self.zamanlayici:
            try:
                self.tablo.after_cancel(self.zamanlayici)
            except Exception:
                pass
            self.zamanlayici = None
        if self.pencere:
            self.pencere.destroy()
            self.pencere = None
        self.son_sutun = None


class Uygulama(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Spot Dönüş Tarayıcı — RSI · MACD · StochRSI · KDJ · OBV · W%R")
        self.geometry("1480x860")
        self.minsize(900, 560)
        self.configure(bg=ARKA)

        # Ana yerleşim: üst panel ve durum çubuğu sabit, orta bölüm esner
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.ayar = ayarlari_oku()

        self.kuyruk = queue.Queue()
        self.sonuclar = []
        self.btc = {}
        self.piyasa = None            # karar huninin 0. adımı (BTC)
        self.izleme = []              # izleme listesi kayıtları
        self.calisiyor = False
        self.durdur = threading.Event()
        self._kapaniyor = threading.Event()

        self.sirala_sutun = self.ayar.get("sirala_sutun", "toplam")
        self.sirala_ters = self.ayar.get("sirala_ters", True)
        self.izleme_sirala_sutun = self.ayar.get("izleme_sirala_sutun", "tarih")
        self.izleme_sirala_ters = self.ayar.get("izleme_sirala_ters", True)
        self._gosterilen = []
        self._izleme_gosterilen = []

        self._stil()
        self._ust_panel()
        self._sekmeler()
        self._detay()
        self._durum()

        self._izlemeyi_yukle()
        self._pencereyi_geri_yukle()
        self._ayrac_zamanlayici = self.after(250, self._ayraci_geri_yukle)

        self.protocol("WM_DELETE_WINDOW", self.kapat)
        self._zamanlayici = self.after(120, self._kuyruk_isle)

        threading.Thread(target=self._canli_dongu, daemon=True).start()
        threading.Thread(target=self._skor_dongusu, daemon=True).start()

    # ------------------------------------------------------------------ stil
    def _stil(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Treeview",
                     background=PANEL, fieldbackground=PANEL, foreground=YAZI,
                     rowheight=26, borderwidth=0, font=("Segoe UI", 10))
        st.configure("Treeview.Heading",
                     background=CIZGI, foreground=SOLUK, relief="flat",
                     font=("Segoe UI", 9, "bold"))
        st.map("Treeview.Heading", background=[("active", "#2d333b")])
        st.map("Treeview", background=[("selected", "#1f6feb")],
               foreground=[("selected", "white")])
        st.configure("TProgressbar", background=MAVI, troughcolor=CIZGI,
                     borderwidth=0, thickness=6)

        # Kaydırma çubukları da koyu tema ile uyumlu olsun
        st.configure("TScrollbar", background=CIZGI, troughcolor=ARKA,
                     bordercolor=ARKA, arrowcolor=SOLUK, relief="flat",
                     borderwidth=0)
        st.map("TScrollbar", background=[("active", "#2d333b")])

        # Açılış ekranı seçim kutusu
        st.configure("Ekran.TCombobox", fieldbackground=ARKA, background=CIZGI,
                     foreground=YAZI, arrowcolor=SOLUK, bordercolor=CIZGI,
                     lightcolor=CIZGI, darkcolor=CIZGI, borderwidth=0)
        st.map("Ekran.TCombobox",
               fieldbackground=[("readonly", ARKA)],
               foreground=[("readonly", YAZI)],
               selectbackground=[("readonly", ARKA)],
               selectforeground=[("readonly", YAZI)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", YAZI)
        self.option_add("*TCombobox*Listbox.selectBackground", MAVI)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _etiket(self, ana, metin, **kw):
        kw.setdefault("bg", ana["bg"])
        kw.setdefault("fg", SOLUK)
        kw.setdefault("font", ("Segoe UI", 9))
        return tk.Label(ana, text=metin, **kw)

    # ------------------------------------------------------------- üst panel
    def _ust_panel(self):
        """
        İki şeritli, dar pencerede de bozulmayan üst panel:
          1. şerit → başlık + işlem düğmeleri (her zaman görünür, solda)
          2. şerit → ayar alanları (dar pencerede alt satıra sarar)
        """
        ust = tk.Frame(self, bg=PANEL, padx=14, pady=8)
        ust.grid(row=0, column=0, sticky="ew")

        serit1 = self.serit1 = tk.Frame(ust, bg=PANEL)
        serit1.pack(fill="x")

        tk.Label(serit1, text="SPOT DÖNÜŞ TARAYICI", bg=PANEL, fg=YAZI,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 20))

        self.btn_tara = tk.Button(serit1, text="▶  TARAMAYI BAŞLAT",
                                  command=self.tara, bg=MAVI, fg="white",
                                  activebackground="#2563eb", activeforeground="white",
                                  relief="flat", font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=6, cursor="hand2")
        self.btn_tara.pack(side="left", padx=4)

        self.btn_dur = tk.Button(serit1, text="■ Durdur", command=self.iptal,
                                 bg=CIZGI, fg=SOLUK, activebackground="#2d333b",
                                 relief="flat", font=("Segoe UI", 9),
                                 padx=12, pady=6, state="disabled", cursor="hand2")
        self.btn_dur.pack(side="left", padx=4)

        self.btn_html = tk.Button(serit1, text="HTML rapor", command=self.html_kaydet,
                                  bg=CIZGI, fg=YAZI, activebackground="#2d333b",
                                  relief="flat", font=("Segoe UI", 9),
                                  padx=12, pady=6, cursor="hand2")
        self.btn_html.pack(side="left", padx=4)

        self.btn_csv = tk.Button(serit1, text="CSV", command=self.csv_kaydet,
                                 bg=CIZGI, fg=YAZI, activebackground="#2d333b",
                                 relief="flat", font=("Segoe UI", 9),
                                 padx=12, pady=6, cursor="hand2")
        self.btn_csv.pack(side="left", padx=4)

        # --- 2. şerit: ayarlar (dar pencerede kendiliğinden alt satıra sarar)
        self.serit2 = tk.Frame(ust, bg=PANEL)
        self.serit2.pack(fill="x", pady=(8, 0))
        self._saran_ogeler = []          # (widget, genislik) — sarma hesabı için

        def alan(baslik, varsayilan, genislik=7):
            cerceve = tk.Frame(self.serit2, bg=PANEL)
            self._etiket(cerceve, baslik).pack(anchor="w")
            deg = tk.StringVar(value=str(varsayilan))
            tk.Entry(cerceve, textvariable=deg, width=genislik, bg=ARKA, fg=YAZI,
                     insertbackground=YAZI, relief="flat",
                     highlightthickness=1, highlightbackground=CIZGI,
                     highlightcolor=MAVI, font=("Segoe UI", 10)).pack(anchor="w")
            self._saran_ogeler.append(cerceve)
            return deg

        self.v_top = alan("Coin sayısı (hacimde ilk N)", 250, 9)
        self.v_hacim = alan("Min 24s hacim (milyon $)", 5, 9)
        self.v_esik = alan("Min toplam skor", 0.10, 9)
        self.v_isci = alan("Eşzamanlı istek", 6, 9)

        onaylar = tk.Frame(self.serit2, bg=PANEL)
        self._saran_ogeler.append(onaylar)

        self.v_sadece = tk.BooleanVar(value=True)
        tk.Checkbutton(onaylar, text="Sadece huni A/B/C (ölçülen tabanlılar her zaman gösterilir)",
                       variable=self.v_sadece, bg=PANEL, fg=SOLUK,
                       selectcolor=ARKA, activebackground=PANEL,
                       activeforeground=YAZI, font=("Segoe UI", 9),
                       highlightthickness=0, bd=0).pack(anchor="w")

        self.v_olusan = tk.BooleanVar(value=OLUSAN_MUM["dahil"])
        tk.Checkbutton(onaylar, text="Oluşan mumu dahil et (grafikle aynı)",
                       variable=self.v_olusan, command=self._olusan_degisti,
                       bg=PANEL, fg=SOLUK, selectcolor=ARKA,
                       activebackground=PANEL, activeforeground=YAZI,
                       font=("Segoe UI", 9), highlightthickness=0,
                       bd=0).pack(anchor="w")

        self.v_btc = tk.BooleanVar(value=True)
        tk.Checkbutton(onaylar, text="BTC piyasa durumunu da kontrol et",
                       variable=self.v_btc, bg=PANEL, fg=SOLUK,
                       selectcolor=ARKA, activebackground=PANEL,
                       activeforeground=YAZI, font=("Segoe UI", 9),
                       highlightthickness=0, bd=0).pack(anchor="w")

        # Açılış ekranı seçimi (çoklu monitör) — 1. şeritte, CSV düğmesinin sağında
        ekran_cer = tk.Frame(self.serit1, bg=PANEL)
        ekran_cer.pack(side="left", padx=(22, 0))
        self._etiket(ekran_cer, "Açılış ekranı").pack(anchor="w")

        self._ekran_secenek = {"İmleçteki ekran": "mouse", "Son konum": "kayitli"}
        for no in range(1, max(2, len(ekranlar())) + 1):
            self._ekran_secenek[f"{no}. ekran"] = str(no)

        self.v_ekran = tk.StringVar()
        kutu = ttk.Combobox(ekran_cer, textvariable=self.v_ekran, width=14,
                            state="readonly", style="Ekran.TCombobox",
                            values=list(self._ekran_secenek))
        kutu.pack(anchor="w")

        simdiki = str(self.ayar.get("acilis_ekrani", ACILIS_EKRANI))
        self.v_ekran.set(next((ad for ad, d in self._ekran_secenek.items()
                               if d == simdiki), "İmleçteki ekran"))
        kutu.bind("<<ComboboxSelected>>", self._ekran_secildi)

        # Önceki oturumun girdilerini geri yükle
        kayitli = self.ayar.get("girdiler", {})
        for anahtar, degisken in (("top", self.v_top), ("hacim", self.v_hacim),
                                  ("esik", self.v_esik), ("isci", self.v_isci)):
            if anahtar in kayitli:
                degisken.set(str(kayitli[anahtar]))
        self.v_sadece.set(bool(kayitli.get("sadece", True)))
        self.v_btc.set(bool(kayitli.get("btc", True)))
        self.v_olusan.set(bool(kayitli.get("olusan", True)))
        self._olusan_degisti()

        self._son_serit_genislik = 0
        self.serit2.bind("<Configure>", self._serit_yerlestir)
        self._serit_yerlestir()

    def _olusan_degisti(self):
        """Oluşan mum ayarı — bir sonraki taramadan itibaren geçerli."""
        OLUSAN_MUM["dahil"] = bool(self.v_olusan.get())
        if hasattr(self, "durum_yazi"):
            self.durum_yazi.configure(
                text="Oluşan mum dahil — grafikte gördüğünle aynı (değerler mum "
                     "kapanana kadar değişir)." if OLUSAN_MUM["dahil"] else
                     "Sadece kapanmış mumlar — 1G'de 24 saate kadar geriden gelir.")

    def _serit_yerlestir(self, _olay=None):
        """Ayar alanlarını pencere genişliğine göre satırlara böler (sarma)."""
        genislik = self.serit2.winfo_width()
        if genislik <= 1:
            genislik = self.winfo_width() - 28
        if abs(genislik - self._son_serit_genislik) < 8:
            return
        self._son_serit_genislik = genislik

        satir = sutun = 0
        kullanilan = 0
        for oge in self._saran_ogeler:
            gerekli = oge.winfo_reqwidth() + 20
            if sutun and kullanilan + gerekli > genislik:
                satir += 1
                sutun = 0
                kullanilan = 0
            oge.grid(row=satir, column=sutun, padx=(0, 20), pady=(0, 6), sticky="w")
            kullanilan += gerekli
            sutun += 1

    # -------------------------------------------------------------- sekmeler
    def _sekmeler(self):
        st = ttk.Style(self)
        st.configure("TNotebook", background=ARKA, borderwidth=0)
        st.configure("TNotebook.Tab", background=PANEL, foreground=SOLUK,
                     padding=(18, 8), font=("Segoe UI", 10, "bold"), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", ARKA)],
               foreground=[("selected", YAZI)])

        st.configure("Ayrac.TPanedwindow", background=ARKA)
        st.configure("Sashy.TPanedwindow", background=CIZGI)

        # Tablo ile detay paneli arasında sürüklenebilir ayraç
        self.bolme = ttk.PanedWindow(self, orient="vertical",
                                     style="Ayrac.TPanedwindow")
        self.bolme.grid(row=1, column=0, sticky="nsew", padx=14, pady=(8, 0))

        self.ust_bolum = tk.Frame(self.bolme, bg=ARKA)
        self.bolme.add(self.ust_bolum, weight=3)

        self.sekmeler = ttk.Notebook(self.ust_bolum)
        self.sekmeler.pack(fill="both", expand=True)

        self.sekme_tarama = tk.Frame(self.sekmeler, bg=ARKA)
        self.sekme_izleme = tk.Frame(self.sekmeler, bg=ARKA)
        self.sekmeler.add(self.sekme_tarama, text="  TARAMA  ")
        self.sekmeler.add(self.sekme_izleme, text="  İZLEME LİSTESİ (0)  ")

        self._tarama_sekmesi()
        self._izleme_sekmesi()
        self.sekmeler.bind("<<NotebookTabChanged>>", self._sekme_degisti)

    def _sekme_degisti(self, _olay=None):
        """İzleme sekmesine bakınca uyarı işareti (🔔) temizlenir."""
        if getattr(self, "_uyari_bekliyor", False) and \
                self.sekmeler.select() == str(self.sekme_izleme):
            self._uyari_bekliyor = False
            self._izleme_doldur()

    def _tablo_kur(self, ana, sutunlar, basliklar, sirala_fn, kayit_adi):
        """Ortak tablo kurucu — sütun genişlikleri ayar dosyasından geri yüklenir."""
        cerceve = tk.Frame(ana, bg=ARKA)
        cerceve.pack(fill="both", expand=True)

        tablo = ttk.Treeview(cerceve, columns=sutunlar, show="headings", height=13)
        kayitli = self.ayar.get("sutunlar", {}).get(kayit_adi, {})

        for s in sutunlar:
            baslik, gen, hiza = basliklar[s]
            tablo.heading(s, text=baslik, anchor=hiza,
                          command=lambda c=s: sirala_fn(c))
            tablo.column(s, width=int(kayitli.get(s, gen)), anchor=hiza,
                         minwidth=36, stretch=False)

        kaydir = ttk.Scrollbar(cerceve, orient="vertical", command=tablo.yview)
        yatay = ttk.Scrollbar(cerceve, orient="horizontal", command=tablo.xview)
        tablo.configure(yscrollcommand=kaydir.set, xscrollcommand=yatay.set)

        tablo.grid(row=0, column=0, sticky="nsew")
        kaydir.grid(row=0, column=1, sticky="ns")
        yatay.grid(row=1, column=0, sticky="ew")
        cerceve.rowconfigure(0, weight=1)
        cerceve.columnconfigure(0, weight=1)

        for ad, renk in (("a", YESIL), ("b", "#7ed957"), ("c", SARI),
                         ("d", SOLUK), ("e", KIRMIZI),
                         ("artı", YESIL), ("eksi", KIRMIZI), ("notr", YAZI)):
            tablo.tag_configure(ad, foreground=renk)
        tablo.tag_configure("olcum_sinyal", foreground="#ffffff", background="#0f3d2a")

        return tablo

    # ----------------------------------------------------------- tarama sekmesi
    def _tarama_sekmesi(self):
        self.btc_yazi = tk.Label(self.sekme_tarama,
                                 text="BTC piyasa durumu — tarama sonrası dolacak",
                                 bg=ARKA, fg=SOLUK, font=("Segoe UI", 10),
                                 anchor="w")
        self.btc_yazi.pack(fill="x", pady=(8, 6))

        sutunlar = ("ekle", "sira", "coin", "olcum", "fiyat", "degisim", "hacim",
                    "toplam", "huni", "1d", "4h", "1h", "15m", "cikis",
                    "sinif", "tarih")
        basliklar = {
            "ekle": ("＋", 52, "center"), "sira": ("#", 40, "center"),
            "coin": ("Coin", 105, "w"),
            "olcum": ("Ölçülen sinyal", 170, "w"), "fiyat": ("Fiyat", 95, "e"),
            "degisim": ("24s %", 72, "e"), "hacim": ("Hacim", 88, "e"),
            "toplam": ("SKOR", 72, "center"), "huni": ("Huni", 62, "center"),
            "1d": ("1 GÜN (trend)", 150, "center"),
            "4h": ("4 SAAT (trend)", 150, "center"),
            "1h": ("1 SAAT", 96, "center"), "15m": ("15 DAK ⟶ alım", 96, "center"),
            "cikis": ("Stop / Hedef", 130, "center"),
            "sinif": ("Karar", 215, "w"),
            "tarih": ("Sinyal zamanı", 120, "center"),
        }

        self.tablo = self._tablo_kur(self.sekme_tarama, sutunlar, basliklar,
                                     self.sirala, "tarama")
        self.tablo.bind("<<TreeviewSelect>>", self.secim_degisti)
        self.tablo.bind("<Button-1>", self._tarama_tikla, add="+")
        self.tablo.bind("<Double-1>", self._izlemeye_ekle_secili)
        Balon(self.tablo, TARAMA_ACIKLAMA)

    # ---------------------------------------------------------- izleme sekmesi
    def _izleme_sekmesi(self):
        arac = tk.Frame(self.sekme_izleme, bg=ARKA)
        arac.pack(fill="x", pady=(8, 6))

        self.izleme_bilgi = tk.Label(
            arac, text="Liste boş — tarama sekmesinde bir satırın solundaki ＋ "
                       "düğmesine tıklayarak coin ekleyin.",
            bg=ARKA, fg=SOLUK, font=("Segoe UI", 10), anchor="w")
        self.izleme_bilgi.pack(side="left")

        def dugme(metin, komut, renk=CIZGI, yazi=YAZI):
            return tk.Button(arac, text=metin, command=komut, bg=renk, fg=yazi,
                             activebackground="#2d333b", relief="flat",
                             font=("Segoe UI", 9), padx=12, pady=5, cursor="hand2")

        self.v_uyari = tk.BooleanVar(value=True)
        tk.Checkbutton(arac, text="🔔 A sinyalinde uyar", variable=self.v_uyari,
                       bg=ARKA, fg=SOLUK, selectcolor=PANEL, activebackground=ARKA,
                       activeforeground=YAZI, font=("Segoe UI", 9),
                       highlightthickness=0, bd=0).pack(side="right", padx=(4, 12))

        dugme("Listeyi temizle", self.izlemeyi_temizle).pack(side="right", padx=4)
        dugme("Seçiliyi çıkar", self.izlemeden_cikar).pack(side="right", padx=4)
        dugme("↻ Skorları yenile", self.skorlari_yenile,
              renk=MAVI, yazi="white").pack(side="right", padx=4)

        sutunlar = ("sil", "tarih", "huni", "coin", "fiyat", "degisim", "sinyal_skor",
                    "anlik_skor", "giris", "cikis", "en_yuksek", "en_dusuk", "sure",
                    "durum", "pencere")
        basliklar = {
            "sil": ("✕", 40, "center"), "tarih": ("Eklenme", 122, "center"),
            "huni": ("Huni", 88, "center"), "coin": ("Coin", 100, "w"),
            "fiyat": ("Anlık fiyat", 100, "e"), "degisim": ("Değişim", 88, "e"),
            "giris": ("Sinyal fiyatı", 100, "e"),
            "cikis": ("Stop / Hedef", 155, "center"),
            "en_yuksek": ("En yüksek", 82, "e"), "en_dusuk": ("En düşük", 82, "e"),
            "sure": ("Süre", 70, "center"),
            "sinyal_skor": ("Sinyal skoru", 92, "center"),
            "anlik_skor": ("Şimdiki skor", 96, "center"),
            "durum": ("Durum", 190, "w"),
            "pencere": ("Giriş", 130, "center"),
        }

        self.izleme_tablo = self._tablo_kur(self.sekme_izleme, sutunlar, basliklar,
                                            self.izleme_sirala, "izleme")
        self.izleme_tablo.bind("<<TreeviewSelect>>", self.izleme_secim_degisti)
        self.izleme_tablo.bind("<Button-1>", self._izleme_tikla, add="+")
        Balon(self.izleme_tablo, IZLEME_ACIKLAMA)

    # ---------------------------------------------------------------- detay
    def _detay(self):
        alt = tk.Frame(self.bolme, bg=ARKA, pady=6)
        self.bolme.add(alt, weight=1)

        tk.Label(alt, text="SEÇİLİ COİN — İNDİKATÖR KIRILIMI (her indikatör bağımsız puanlanır)",
                 bg=ARKA, fg=SOLUK, font=("Segoe UI", 9, "bold")).pack(anchor="w")

        kutu = tk.Frame(alt, bg=PANEL)
        kutu.pack(fill="both", expand=True, pady=(4, 0))

        self.detay = tk.Text(kutu, height=8, bg=PANEL, fg=YAZI, relief="flat",
                             wrap="word", font=("Consolas", 10), padx=10, pady=8,
                             insertbackground=YAZI)
        kaydir = ttk.Scrollbar(kutu, orient="vertical", command=self.detay.yview)
        self.detay.configure(yscrollcommand=kaydir.set, state="disabled")
        self.detay.pack(side="left", fill="both", expand=True)
        kaydir.pack(side="right", fill="y")

        for ad, renk in (("yesil", YESIL), ("kirmizi", KIRMIZI), ("sari", SARI),
                         ("soluk", SOLUK), ("beyaz", YAZI)):
            self.detay.tag_configure(ad, foreground=renk)
        self.detay.tag_configure("baslik", foreground=YAZI,
                                 font=("Consolas", 11, "bold"))
        self.detay.tag_configure("tf", foreground=MAVI,
                                 font=("Consolas", 10, "bold"))

    # ---------------------------------------------------------------- durum
    def _durum(self):
        cerceve = tk.Frame(self, bg=PANEL, padx=14, pady=6)
        cerceve.grid(row=2, column=0, sticky="ew")
        self.ilerleme = ttk.Progressbar(cerceve, mode="determinate", maximum=100)
        self.ilerleme.pack(fill="x")
        self.durum_yazi = tk.Label(cerceve, text="Hazır.", bg=PANEL, fg=SOLUK,
                                   font=("Segoe UI", 9), anchor="w")
        self.durum_yazi.pack(fill="x", pady=(4, 0))

    # =========================================================== tarama akışı
    def tara(self):
        if self.calisiyor:
            return
        try:
            top_n = max(5, int(float(self.v_top.get())))
            min_hacim = max(0.0, float(self.v_hacim.get()))
            esik = float(self.v_esik.get())
            isci = max(1, min(12, int(float(self.v_isci.get()))))
        except ValueError:
            messagebox.showerror("Ayar hatası", "Sayısal alanları kontrol edin.")
            return

        self.calisiyor = True
        self.durdur.clear()
        self.sonuclar = []
        self.tablo.delete(*self.tablo.get_children())
        self.btn_tara.configure(state="disabled", bg=CIZGI)
        self.btn_dur.configure(state="normal", fg=YAZI)
        self.ilerleme["value"] = 0

        threading.Thread(target=self._tarama_isi,
                         args=(top_n, min_hacim, esik, isci),
                         daemon=True).start()

    def iptal(self):
        self.durdur.set()
        self.durum_yazi.configure(text="Durduruluyor… açık istekler tamamlanıyor.")

    def _tarama_isi(self, top_n, min_hacim, esik, isci):
        try:
            self.kuyruk.put(("durum", "Sembol evreni alınıyor…"))
            evren = evren_getir(top_n, min_hacim)
            if not evren:
                self.kuyruk.put(("bitti", "Filtrelere uyan sembol bulunamadı."))
                return

            # ADIM 0: genel piyasa. Açıksa karara da girer (BTC zayıfsa kademe düşer).
            self.piyasa = None
            if self.v_btc.get():
                self.kuyruk.put(("durum", "Genel piyasa (BTC) kontrol ediliyor…"))
                try:
                    self.piyasa = btc_durumu()
                    self.kuyruk.put(("btc", self.piyasa))
                except Exception as e:
                    self.kuyruk.put(("durum", f"BTC durumu alınamadı: {e}"))

            toplam = len(evren)
            self.kuyruk.put(("durum", f"{toplam} coin, 4 zaman dilimi taranıyor…"))
            bitti = 0
            hepsi = []            # genişlik hesabı için gösterilmeyenler dahil TÜMÜ

            with ThreadPoolExecutor(max_workers=isci) as havuz:
                isler = {havuz.submit(self._guvenli_analiz, b): b for b in evren}
                for is_ in as_completed(isler):
                    if self.durdur.is_set():
                        break
                    sonuc = is_.result()
                    bitti += 1
                    bilgi = isler[is_]
                    self.kuyruk.put(("ilerleme", (bitti, toplam, bilgi["coin"])))
                    if not sonuc:
                        continue
                    hepsi.append(sonuc)
                    # Ölçülen tabanı olan coin, skor/huni filtresine takılmadan gösterilir
                    taban = (sonuc.get("olcum") or {}).get("taban")
                    if not taban:
                        if sonuc["toplam"] < esik:
                            continue
                        if self.v_sadece.get() and sonuc["sinif"][0] not in "ABC":
                            continue
                    self.kuyruk.put(("sonuc", sonuc))

            # Ölçülen sinyal: genişlik + BTC'ye göreli güç + soğuma (tümü üzerinde)
            if hepsi and not self.durdur.is_set():
                self.kuyruk.put(("durum", "Ölçülen sinyal hesaplanıyor (genişlik, RS, soğuma)…"))
                try:
                    btc_k = btc_kosu_24s()
                    gecmis = sinyal_gecmisi_oku()
                    genislik = olculmus_sinyalleri_isaretle(hepsi, btc_k, gecmis)
                    sinyal_gecmisi_yaz(gecmis)
                    yeni = sum(1 for r in hepsi if r["olculmus"]["sinyal"])
                    self.kuyruk.put(("olcum", {"genislik": genislik, "sinyal": yeni,
                                               "btc_kosu": btc_k}))
                except Exception as e:
                    self.kuyruk.put(("durum", f"Ölçülen sinyal hesaplanamadı: {e}"))

            self.kuyruk.put(("bitti", None))

        except Exception as e:
            self.kuyruk.put(("bitti", f"HATA: {type(e).__name__}: {e}"))

    def _guvenli_analiz(self, bilgi):
        if self.durdur.is_set():
            return None
        try:
            return sembol_analiz(bilgi, piyasa=getattr(self, "piyasa", None))
        except Exception:
            return None

    # ------------------------------------------------------------- kuyruk
    def _kuyruk_isle(self):
        yenile = False
        try:
            while True:
                tur, veri = self.kuyruk.get_nowait()

                if tur == "durum":
                    self.durum_yazi.configure(text=veri)

                elif tur == "ilerleme":
                    bitti, toplam, coin = veri
                    self.ilerleme["value"] = bitti / toplam * 100
                    self.durum_yazi.configure(
                        text=f"{bitti}/{toplam} tarandı  ·  son: {coin}  ·  "
                             f"{len(self.sonuclar)} aday bulundu")

                elif tur == "btc":
                    self.btc = veri
                    self._btc_yaz()

                elif tur == "sonuc":
                    if not self.sonuclar:
                        self.son_olcum = None
                    self.sonuclar.append(veri)
                    yenile = True

                elif tur == "canli":
                    for k in self.izleme:
                        fiyat = veri.get(k["sembol"])
                        if fiyat:
                            k["fiyat"] = fiyat
                            k["en_yuksek"] = max(k["en_yuksek"], fiyat)
                            k["en_dusuk"] = min(k["en_dusuk"], fiyat)
                    self._izleme_doldur()

                elif tur == "izleme_skor":
                    sembol, sonuc = veri
                    for k in self.izleme:
                        if k["sembol"] == sembol:
                            self._izleme_guncelle(k, sonuc)
                    self._izleme_doldur()

                elif tur == "olcum":
                    self.son_olcum = veri
                    yenile = True

                elif tur == "bitti":
                    self.calisiyor = False
                    self.btn_tara.configure(state="normal", bg=MAVI)
                    self.btn_dur.configure(state="disabled", fg=SOLUK)
                    self.ilerleme["value"] = 100
                    o = getattr(self, "son_olcum", None)
                    olcum_yazi = ""
                    if o:
                        btc = (f"BTC 24s {o['btc_kosu']:+.1f}%"
                               if o.get("btc_kosu") is not None else "BTC ?")
                        olcum_yazi = (f"  ·  ÖLÇÜLEN SİNYAL: {o['sinyal']}  "
                                      f"(genişlik {o['genislik']}/{GENISLIK_EVREN}, "
                                      f"eşik ≥{GENISLIK_ESIK} · {btc})")
                    mesaj = veri or (f"Tarama bitti — {len(self.sonuclar)} satır"
                                     f"{olcum_yazi}")
                    self.durum_yazi.configure(text=mesaj)
                    yenile = True

        except queue.Empty:
            pass

        if yenile:
            self._tabloyu_doldur()

        if not self._kapaniyor.is_set():
            self._zamanlayici = self.after(120, self._kuyruk_isle)

    def _btc_yaz(self):
        parcalar = []
        for ad in ("1d", "4h", "1h"):
            if ad in self.btc:
                sk = self.btc[ad]["skor"]
                parcalar.append(f"{ad}: {sk:+.2f} ({etiket(sk)}, "
                                f"{self.btc[ad]['pozitif']}/{len(INDIKATORLER)} indikatör olumlu)")
        if not parcalar:
            return
        ortalama = np.mean([self.btc[a]["skor"] for a in self.btc])
        self.btc_yazi.configure(
            text="BTC PİYASA DURUMU   |   " + "   ·   ".join(parcalar),
            fg=skor_rengi(ortalama))

    # ------------------------------------------------------------- tablo
    def sirala(self, sutun):
        if self.sirala_sutun == sutun:
            self.sirala_ters = not self.sirala_ters
        else:
            self.sirala_sutun, self.sirala_ters = sutun, True
        self._tabloyu_doldur()

    def _anahtar(self, r):
        s = self.sirala_sutun
        if s in ZAMAN_DILIMLERI:
            return r["tf"][s]["skor"]
        if s in ("toplam", "fiyat", "degisim", "hacim"):
            return r[s]
        if s == "coin":
            return r["coin"]
        if s == "sinif":
            return r["sinif"]
        if s == "tarih":
            return r.get("zaman", "")
        if s == "huni":
            return r.get("huni", "").count("✓")
        if s == "olcum":
            b = r.get("olculmus") or {}
            taban = (r.get("olcum") or {}).get("taban", False)
            return (b.get("sinyal", False), taban, r["toplam"])
        return r["toplam"]

    def _tabloyu_doldur(self):
        secili = self.tablo.selection()
        self.tablo.delete(*self.tablo.get_children())
        try:
            sirali = sorted(self.sonuclar, key=self._anahtar, reverse=self.sirala_ters)
        except TypeError:
            sirali = self.sonuclar
        self._gosterilen = sirali

        izlenen = {i["sembol"] for i in self.izleme}
        for i, r in enumerate(sirali, 1):
            olculmus = r.get("olculmus") or {}
            if olculmus.get("sinyal"):
                etiketler = ("olcum_sinyal",)
            else:
                etiketler = (r["sinif"][0].lower(),)
            olcum_yazi = olculmus.get("durum") or (
                "taban ✓ · hesaplanıyor…" if (r.get("olcum") or {}).get("taban") else "—")
            self.tablo.insert("", "end", iid=str(i - 1), tags=etiketler, values=(
                "✓" if r["sembol"] in izlenen else "＋",
                i, kalin(r["coin"]), olcum_yazi,
                f"{r['fiyat']:.8g}", f"{r['degisim']:+.2f}",
                f"{r['hacim'] / 1e6:,.1f}M", f"{r['toplam']:+.2f}",
                r.get("huni", ""),
                f"{r['tf']['1d']['skor']:+.2f} {r['tf']['1d'].get('trend', '')}",
                f"{r['tf']['4h']['skor']:+.2f} {r['tf']['4h'].get('trend', '')}",
                f"{r['tf']['1h']['skor']:+.2f} ({r['tf']['1h'].get('donus', 0)} dönüş)",
                f"{r['tf']['15m']['skor']:+.2f} ({r['tf']['15m'].get('donus', 0)} dönüş)",
                (f"{r['cikis']['stop_yuzde']:+.1f}% / {r['cikis']['hedef_yuzde']:+.1f}%"
                 if r.get("cikis") else "—"),
                r["sinif"], r.get("zaman", ""),
            ))

        if secili and secili[0] in self.tablo.get_children():
            self.tablo.selection_set(secili[0])

    # ====================================================== izleme listesi
    def _tarama_tikla(self, olay):
        """Tablonun en solundaki ＋ sütununa tıklandıysa coini izlemeye alır."""
        if self.tablo.identify_region(olay.x, olay.y) != "cell":
            return
        if self.tablo.identify_column(olay.x) != "#1":
            return
        satir = self.tablo.identify_row(olay.y)
        if not satir:
            return
        try:
            self.izlemeye_ekle(self._gosterilen[int(satir)])
        except (ValueError, IndexError):
            pass
        return "break"

    def _izlemeye_ekle_secili(self, _olay=None):
        secim = self.tablo.selection()
        if secim:
            try:
                self.izlemeye_ekle(self._gosterilen[int(secim[0])])
            except (ValueError, IndexError):
                pass

    def izlemeye_ekle(self, r):
        if any(i["sembol"] == r["sembol"] for i in self.izleme):
            self.durum_yazi.configure(text=f"{r['coin']} zaten izleme listesinde.")
            self.sekmeler.select(self.sekme_izleme)
            return

        simdi = time.time()
        self.izleme.append({
            "sembol": r["sembol"],
            "coin": r["coin"],
            "eklenme_ts": simdi,
            "eklenme": datetime.now().strftime(TARIH_BICIM),
            "giris_fiyat": r["fiyat"],
            "fiyat": r["fiyat"],
            "en_yuksek": r["fiyat"],
            "en_dusuk": r["fiyat"],
            "sinyal_skor": r["toplam"],
            "sinyal_sinif": r["sinif"],
            "sinyal_tf": {a: r["tf"][a]["skor"] for a in ZAMAN_DILIMLERI},
            "cikis": r.get("cikis"),        # eklendiği andaki stop/hedef — donuk
            "sinyal_detay": r,
            "anlik": None,
            "anlik_zaman": "",
        })
        self.durum_yazi.configure(
            text=f"{r['coin']} izleme listesine eklendi — "
                 f"sinyal fiyatı {r['fiyat']:.8g}, canlı takip başladı.")
        self._izleme_doldur()
        self._tabloyu_doldur()
        self._izlemeyi_kaydet()

    def _izleme_tikla(self, olay):
        if self.izleme_tablo.identify_region(olay.x, olay.y) != "cell":
            return
        if self.izleme_tablo.identify_column(olay.x) != "#1":
            return
        satir = self.izleme_tablo.identify_row(olay.y)
        if not satir:
            return
        try:
            kayit = self._izleme_gosterilen[int(satir)]
        except (ValueError, IndexError):
            return
        self.izleme = [i for i in self.izleme if i["sembol"] != kayit["sembol"]]
        self.durum_yazi.configure(text=f"{kayit['coin']} izlemeden çıkarıldı.")
        self._izleme_doldur()
        self._tabloyu_doldur()
        self._izlemeyi_kaydet()
        return "break"

    def izlemeden_cikar(self):
        secim = self.izleme_tablo.selection()
        if not secim:
            return
        cikanlar = set()
        for s in secim:
            try:
                cikanlar.add(self._izleme_gosterilen[int(s)]["sembol"])
            except (ValueError, IndexError):
                pass
        self.izleme = [i for i in self.izleme if i["sembol"] not in cikanlar]
        self._izleme_doldur()
        self._tabloyu_doldur()
        self._izlemeyi_kaydet()

    def izlemeyi_temizle(self):
        if not self.izleme:
            return
        if not messagebox.askyesno(
                "İzleme listesi",
                f"Listedeki {len(self.izleme)} coin silinsin mi?\n\n"
                f"(Silmeden önce otomatik yedek alınır: "
                f"{os.path.basename(YEDEK_KLASORU)} klasörü)"):
            return
        self.izleme = []
        self._izleme_temizlendi = True        # korumayı bilerek aş
        self._izleme_doldur()
        self._tabloyu_doldur()
        self._izlemeyi_kaydet()
        self._izleme_temizlendi = False

    def izleme_sirala(self, sutun):
        if self.izleme_sirala_sutun == sutun:
            self.izleme_sirala_ters = not self.izleme_sirala_ters
        else:
            self.izleme_sirala_sutun, self.izleme_sirala_ters = sutun, True
        self._izleme_doldur()

    def _izleme_anahtar(self, k):
        s = self.izleme_sirala_sutun
        degisim = self._degisim(k)
        return {
            "tarih": k["eklenme_ts"], "sure": -k["eklenme_ts"],
            "coin": k["coin"], "giris": k["giris_fiyat"], "fiyat": k["fiyat"],
            "degisim": degisim,
            "en_yuksek": self._yuzde(k, k["en_yuksek"]),
            "en_dusuk": self._yuzde(k, k["en_dusuk"]),
            "sinyal_skor": k["sinyal_skor"],
            "anlik_skor": k["anlik"]["toplam"] if k["anlik"] else -9,
            "huni": ((k["anlik"]["huni"].count("✓"), -ord(k["anlik"]["sinif"][0]))
                     if k["anlik"] else (-1, 0)),
            "pencere": (k.get("pencere_acik", False), -(k.get("pencere_ts") or 0)),
            "durum": self._izleme_durum(k)[0],
        }.get(s, k["eklenme_ts"])

    @staticmethod
    def _yuzde(k, fiyat):
        giris = k["giris_fiyat"] or 0.0
        return (fiyat - giris) / giris * 100 if giris else 0.0

    def _degisim(self, k):
        return self._yuzde(k, k["fiyat"])

    def _izleme_durum(self, k):
        """
        Sinyal sonrası durumu: skor korunuyor mu, bozuldu mu?
        Satır rengi fiyat değişimini gösterdiği için durum, metnin başındaki
        işaretle okunur: ✓ korunuyor · ~ kısmen · ⚠ zayıflıyor · ✗ bozuldu
        """
        c = k.get("cikis")
        if c and "hedef" in c:
            if k["fiyat"] <= c["stop"]:
                return "✗ STOP — planlanan çıkış", "eksi"
            if k["fiyat"] >= c["hedef"]:
                return "🎯 HEDEF — kâr al", "artı"
        if not k["anlik"]:
            return "· skor bekleniyor…", "notr"
        yeni = k["anlik"]["toplam"]
        eski = k["sinyal_skor"]
        sinif = k["anlik"]["sinif"]
        if yeni < -0.05:
            return f"✗ SİNYAL BOZULDU ({sinif[0]})", "eksi"
        if yeni >= max(0.25, eski * 0.8):
            return f"✓ sinyal korunuyor ({sinif[0]})", "artı"
        if yeni < eski * 0.5:
            return f"⚠ zayıflıyor ({sinif[0]})", "eksi"
        return f"~ kısmen korunuyor ({sinif[0]})", "notr"

    def _cikis_metni(self, k):
        """Stop ve hedefe kalan mesafe."""
        c = k.get("cikis")
        if not c or "hedef" not in c:
            return "—"
        fiyat = k["fiyat"]
        if fiyat <= c["stop"]:
            return "✗ STOP GELDİ"
        if fiyat >= c["hedef"]:
            return "🎯 HEDEF GELDİ"
        return (f"S −{(fiyat / c['stop'] - 1) * 100:.1f}% · "
                f"H +{(c['hedef'] / fiyat - 1) * 100:.1f}%")

    def _pencere_metni(self, k):
        """15dk teyit kapısının durumu ve ne kadardır açık olduğu."""
        if not k.get("anlik"):
            return "…"
        if not k.get("pencere_acik"):
            return "kapalı"
        basla = k.get("pencere_ts")
        return f"AÇIK · {gecen_sure(basla)}" if basla else "AÇIK"

    def _izleme_guncelle(self, k, sonuc):
        """Yeni analiz geldiğinde pencere durumunu ve A geçişini işaretler."""
        onceki_sinif = (k.get("anlik") or {}).get("sinif", "")
        k["anlik"] = sonuc
        k["anlik_zaman"] = sonuc["zaman"]

        acik = giris_penceresi_acik(sonuc["tf"])
        if acik and not k.get("pencere_acik"):
            k["pencere_ts"] = time.time()          # kapı yeni açıldı
        if not acik:
            k["pencere_ts"] = None
        k["pencere_acik"] = acik

        # A sınıfına YENİ geçtiyse uyar
        if sonuc["sinif"].startswith("A") and not onceki_sinif.startswith("A"):
            self._a_uyarisi(k, sonuc)

    def _a_uyarisi(self, k, sonuc):
        """A sinyali: ses + görev çubuğunda yanıp sönme + durum çubuğu."""
        mesaj = (f"🔔 {k['coin']} → {sonuc['sinif']}  ·  "
                 f"fiyat {k['fiyat']:.8g}  ·  {datetime.now():%H:%M}  —  "
                 f"15 dakikada alım yeri aranabilir.")
        self.durum_yazi.configure(text=mesaj, fg=YESIL)
        self._uyari_bekliyor = True            # sekmedeki 🔔 işareti
        self._izleme_doldur()

        if not self.v_uyari.get():
            return
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            try:
                self.bell()
            except Exception:
                pass
        try:                                        # görev çubuğunda yanıp sön
            import ctypes
            from ctypes import wintypes

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND),
                            ("dwFlags", wintypes.DWORD), ("uCount", wintypes.UINT),
                            ("dwTimeout", wintypes.DWORD)]

            bilgi = FLASHWINFO()
            bilgi.cbSize = ctypes.sizeof(FLASHWINFO)
            bilgi.hwnd = int(self.wm_frame(), 16)
            bilgi.dwFlags = 0x00000003 | 0x0000000C   # FLASHW_ALL | TIMERNOFG
            bilgi.uCount = 6
            bilgi.dwTimeout = 0
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(bilgi))
        except Exception:
            pass

    def _izleme_doldur(self):
        secili = self.izleme_tablo.selection()
        self.izleme_tablo.delete(*self.izleme_tablo.get_children())
        try:
            sirali = sorted(self.izleme, key=self._izleme_anahtar,
                            reverse=self.izleme_sirala_ters)
        except TypeError:
            sirali = list(self.izleme)
        self._izleme_gosterilen = sirali

        for i, k in enumerate(sirali):
            degisim = self._degisim(k)
            durum, _ = self._izleme_durum(k)
            anlik = k["anlik"]

            # Satır rengi = sinyal anından bu yana fiyat değişimi (yeşil / kırmızı)
            if degisim > 0.05:
                renk_etiket = "artı"
            elif degisim < -0.05:
                renk_etiket = "eksi"
            else:
                renk_etiket = "notr"
            yon = "▲" if degisim > 0.05 else ("▼" if degisim < -0.05 else "•")

            huni = f"{anlik['huni']} {anlik['sinif'][0]}" if anlik else "…"
            anlik_skor = f"{anlik['toplam']:+.2f}" if anlik else "…"
            pencere = self._pencere_metni(k)

            self.izleme_tablo.insert("", "end", iid=str(i), tags=(renk_etiket,), values=(
                "✕", k["eklenme"], huni, kalin(k["coin"]),
                f"{k['fiyat']:.8g}", f"{yon} {degisim:+.2f}%",
                f"{k['sinyal_skor']:+.2f}", anlik_skor,
                f"{k['giris_fiyat']:.8g}", self._cikis_metni(k),
                f"{self._yuzde(k, k['en_yuksek']):+.2f}%",
                f"{self._yuzde(k, k['en_dusuk']):+.2f}%",
                gecen_sure(k["eklenme_ts"]),
                durum, pencere,
            ))

        if secili and secili[0] in self.izleme_tablo.get_children():
            self.izleme_tablo.selection_set(secili[0])

        zil = "🔔 " if getattr(self, "_uyari_bekliyor", False) else ""
        self.sekmeler.tab(self.sekme_izleme,
                          text=f"  {zil}İZLEME LİSTESİ ({len(self.izleme)})  ")
        if self.izleme:
            kazanan = sum(1 for k in self.izleme if self._degisim(k) > 0)
            self.izleme_bilgi.configure(
                text=f"{len(self.izleme)} coin izleniyor  ·  {kazanan} artıda  ·  "
                     f"fiyatlar {CANLI_ARALIK} sn, skorlar {SKOR_ARALIK // 60} dk "
                     f"aralıkla yenileniyor")
        else:
            self.izleme_bilgi.configure(
                text="Liste boş — tarama sekmesinde bir satırın solundaki ＋ "
                     "düğmesine tıklayarak coin ekleyin.")

    # ------------------------------------------------------- canlı yenileme
    def _canli_dongu(self):
        while not self._kapaniyor.is_set():
            try:
                semboller = [k["sembol"] for k in list(self.izleme)]
                if semboller:
                    veri = istek("/api/v3/ticker/price", {
                        "symbols": json.dumps(semboller, separators=(",", ":"))})
                    self.kuyruk.put(("canli", {d["symbol"]: float(d["price"])
                                               for d in veri}))
            except Exception:
                pass
            self._kapaniyor.wait(CANLI_ARALIK)

    def _skor_dongusu(self):
        while not self._kapaniyor.is_set():
            self._kapaniyor.wait(SKOR_ARALIK)
            if self._kapaniyor.is_set():
                break
            self._izleme_skorlarini_hesapla()

    def skorlari_yenile(self):
        if not self.izleme:
            return
        self.durum_yazi.configure(text="İzleme listesi skorları yenileniyor…")
        threading.Thread(target=self._izleme_skorlarini_hesapla, daemon=True).start()

    def _izleme_skorlarini_hesapla(self):
        for k in list(self.izleme):
            if self._kapaniyor.is_set():
                return
            try:
                sonuc = sembol_analiz({"sembol": k["sembol"], "coin": k["coin"],
                                       "fiyat": k["fiyat"], "degisim": 0.0,
                                       "hacim": 0.0}, piyasa=self.piyasa)
                if sonuc:
                    self.kuyruk.put(("izleme_skor", (k["sembol"], sonuc)))
            except Exception:
                pass

    # ------------------------------------------------------------ kalıcılık
    def _izlemeyi_kaydet(self):
        """İzleme listesi kendi dosyasına, atomik ve yedekli yazılır."""
        kayitlar = [{
            anahtar: k[anahtar] for anahtar in
            ("sembol", "coin", "eklenme_ts", "eklenme", "giris_fiyat", "fiyat",
             "en_yuksek", "en_dusuk", "sinyal_skor", "sinyal_sinif", "sinyal_tf",
             "cikis")
        } for k in self.izleme]

        yazildi = izleme_yaz(kayitlar, zorla=getattr(self, "_izleme_temizlendi", False))
        if not yazildi:
            print("İzleme listesi korundu: boş liste, dolu kaydın üzerine yazılmadı.")

        self.ayar.pop("izleme", None)     # artık ayrı dosyada tutuluyor
        ayarlari_yaz(self.ayar)

    def _izlemeyi_yukle(self):
        kayitlar = izleme_oku()
        if kayitlar is None:              # dosya yok → eski ayar dosyasından göç
            kayitlar = self.ayar.get("izleme", [])
            if kayitlar:
                izleme_yaz(kayitlar, zorla=True)

        for k in kayitlar:
            try:
                k.setdefault("anlik", None)
                k.setdefault("anlik_zaman", "")
                k.setdefault("sinyal_detay", None)
                k.setdefault("cikis", None)
                self.izleme.append(k)
            except Exception:
                pass
        self._izleme_doldur()
        if self.izleme:
            threading.Thread(target=self._izleme_skorlarini_hesapla,
                             daemon=True).start()

    def _pencereyi_geri_yukle(self):
        """
        Boyut önceki oturumdan gelir; konum ACILIS_EKRANI ayarına göre seçilen
        ekranın ortasına taşınır ("kayitli" seçilirse eski konum korunur).
        """
        olcu = self.ayar.get("pencere") or ""
        genislik, yukseklik = 1480, 860
        try:
            boyut = olcu.split("+")[0]
            genislik, yukseklik = (int(p) for p in boyut.split("x"))
        except Exception:
            pass

        secim = self.ayar.get("acilis_ekrani", ACILIS_EKRANI)
        alan = None if str(secim).lower() == "kayitli" else hedef_ekran(secim)

        if alan:
            x, y, ekran_g, ekran_y = alan
            # Pencere hedef ekrana sığmıyorsa küçült
            genislik = max(self.minsize()[0], min(genislik, ekran_g - 40))
            yukseklik = max(self.minsize()[1], min(yukseklik, ekran_y - 40))
            sol = x + (ekran_g - genislik) // 2
            ust = y + (ekran_y - yukseklik) // 2
            self.geometry(f"{genislik}x{yukseklik}+{sol}+{ust}")
        elif olcu:
            try:
                self.geometry(olcu)
            except Exception:
                pass

        if self.ayar.get("tam_ekran"):
            try:
                self.state("zoomed")
            except Exception:
                pass

    def _ekran_secildi(self, _olay=None):
        """Seçim değişince pencereyi hemen o ekranın ortasına taşır."""
        self.ayar["acilis_ekrani"] = self._ekran_secenek.get(self.v_ekran.get(),
                                                             ACILIS_EKRANI)
        if self.ayar["acilis_ekrani"] == "kayitli":
            self.durum_yazi.configure(
                text="Uygulama bundan sonra en son kapatıldığı konumda açılacak.")
            return
        if self.state() == "zoomed":
            self.state("normal")
        self.ayar["pencere"] = self.geometry()
        self._pencereyi_geri_yukle()
        self.durum_yazi.configure(
            text=f"Açılış ekranı: {self.v_ekran.get()} — pencere ortalandı.")

    def _ayraci_geri_yukle(self):
        """Detay panelinin yüksekliğini geri yükler ve pencereye göre sınırlar."""
        self._detay_yukseklik = int(self.ayar.get("detay_yuksekligi", 200))
        self._ayraci_uygula()
        self.bolme.bind("<Configure>", lambda _o: self._ayraci_uygula())
        self.bolme.bind("<ButtonRelease-1>", self._ayrac_surukdendi)

    def _ayraci_uygula(self):
        """Detay paneli asla tabloyu ezmesin: en çok pencerenin %45'i kadar."""
        toplam = self.bolme.winfo_height()
        if toplam < 140:
            return
        detay = min(self._detay_yukseklik, max(90, int(toplam * 0.45)))
        konum = max(110, toplam - detay)
        try:
            if abs(self.bolme.sashpos(0) - konum) > 2:
                self.bolme.sashpos(0, konum)
        except Exception:
            pass

    def _ayrac_surukdendi(self, _olay=None):
        """Kullanıcı ayracı sürükleyince yeni detay yüksekliğini hatırla."""
        try:
            self._detay_yukseklik = max(60, self.bolme.winfo_height()
                                        - self.bolme.sashpos(0))
        except Exception:
            pass

    def _sutunlari_kaydet(self):
        self.ayar["sutunlar"] = {
            "tarama": {s: self.tablo.column(s, "width")
                       for s in self.tablo["columns"]},
            "izleme": {s: self.izleme_tablo.column(s, "width")
                       for s in self.izleme_tablo["columns"]},
        }

    def kapat(self):
        self._kapaniyor.set()
        self.durdur.set()
        for zamanlayici in ("_zamanlayici", "_ayrac_zamanlayici"):
            try:
                self.after_cancel(getattr(self, zamanlayici))
            except Exception:
                pass
        try:
            self._sutunlari_kaydet()
            self.ayar["tam_ekran"] = (self.state() == "zoomed")
            if not self.ayar["tam_ekran"]:
                self.ayar["pencere"] = self.geometry()
            self._ayrac_surukdendi()
            self.ayar["detay_yuksekligi"] = getattr(self, "_detay_yukseklik", 200)
            self.ayar["acilis_ekrani"] = self._ekran_secenek.get(
                self.v_ekran.get(), ACILIS_EKRANI)
            self.ayar["sirala_sutun"] = self.sirala_sutun
            self.ayar["sirala_ters"] = self.sirala_ters
            self.ayar["izleme_sirala_sutun"] = self.izleme_sirala_sutun
            self.ayar["izleme_sirala_ters"] = self.izleme_sirala_ters
            self.ayar["girdiler"] = {
                "top": self.v_top.get(), "hacim": self.v_hacim.get(),
                "esik": self.v_esik.get(), "isci": self.v_isci.get(),
                "sadece": self.v_sadece.get(), "btc": self.v_btc.get(),
                "olusan": self.v_olusan.get(),
            }
            self._izlemeyi_kaydet()   # ayarları da diske yazar
        except Exception as e:
            print(f"Kapanışta ayar kaydı: {e}")
        self.destroy()

    # ------------------------------------------------------------- detay
    def secim_degisti(self, _olay=None):
        secim = self.tablo.selection()
        if not secim or not self._gosterilen:
            return
        try:
            r = self._gosterilen[int(secim[0])]
        except (ValueError, IndexError):
            return
        self._detay_yaz(r)

    def izleme_secim_degisti(self, _olay=None):
        secim = self.izleme_tablo.selection()
        if not secim or not self._izleme_gosterilen:
            return
        try:
            k = self._izleme_gosterilen[int(secim[0])]
        except (ValueError, IndexError):
            return

        r = k["anlik"] or k.get("sinyal_detay")
        ustbilgi = (
            f"İZLEMEDE  ·  eklenme {k['eklenme']}  ·  {gecen_sure(k['eklenme_ts'])} geçti\n"
            f"Sinyal fiyatı {k['giris_fiyat']:.8g}  →  anlık {k['fiyat']:.8g}  "
            f"({self._degisim(k):+.2f}%)   "
            f"en yüksek {self._yuzde(k, k['en_yuksek']):+.2f}%  ·  "
            f"en düşük {self._yuzde(k, k['en_dusuk']):+.2f}%\n"
            f"Sinyal anı skoru {k['sinyal_skor']:+.2f} ({k['sinyal_sinif']})  →  "
            + (f"anlık skor {k['anlik']['toplam']:+.2f} ({k['anlik']['sinif']}), "
               f"güncelleme {k['anlik_zaman']}\n"
               if k["anlik"] else "anlık skor henüz hesaplanmadı\n"))

        if r:
            self._detay_yaz(r, ustbilgi)
        else:
            self.detay.configure(state="normal")
            self.detay.delete("1.0", "end")
            self.detay.insert("end", f"{k['coin']}  ({k['sembol']})\n", "baslik")
            self.detay.insert("end", ustbilgi, "soluk")
            self.detay.configure(state="disabled")

    def _detay_yaz(self, r, ustbilgi=None):
        self.detay.configure(state="normal")
        self.detay.delete("1.0", "end")

        self.detay.insert("end", f"{r['coin']}  ({r['sembol']})   ", "baslik")
        self.detay.insert("end", f"fiyat {r['fiyat']:.8g}  ·  24s {r['degisim']:+.2f}%"
                                 f"  ·  hacim {r['hacim'] / 1e6:,.1f}M$  ·  "
                                 f"sinyal {r.get('zaman', '')}\n", "soluk")
        if ustbilgi:
            self.detay.insert("end", ustbilgi, "beyaz")
        self.detay.insert("end", f"SKOR {r['toplam']:+.2f} (1G+4S+1S)   →   {r['sinif']}\n",
                          "yesil" if r["toplam"] >= 0.25 else "sari")
        self.detay.insert("end", f"{r['aciklama']}\n", "soluk")

        # Huni: hangi adım geçildi, nerede kapandı?
        huni = r.get("huni", "")
        adimlar = ("1G yükseliş/dönüş mü?", "4S fırsat var mı?",
                   "1S dönüş başladı mı?", "15D teyit etti mi?")
        self.detay.insert("end", "HUNİ  ", "baslik")
        for i, ad in enumerate(adimlar):
            gecti = i < len(huni) and huni[i] == "✓"
            self.detay.insert("end", f"{'✓' if gecti else '✗'} {ad}   ",
                              "yesil" if gecti else "kirmizi")
        self.detay.insert("end", "\n", "soluk")

        o = r.get("olcum")
        if o:
            b = r.get("olculmus") or {}
            self.detay.insert("end", "ÖLÇÜLEN SİNYAL  ", "baslik")
            self.detay.insert("end", f"{b.get('durum', 'hesaplanmadı')}\n",
                              "yesil" if b.get("sinyal") else "sari")
            self.detay.insert("end", "   taban: ", "soluk")
            for ad, ok in o["sartlar"].items():
                self.detay.insert("end", f"{'✓' if ok else '✗'} {ad}   ",
                                  "yesil" if ok else "kirmizi")
            self.detay.insert("end", f"(mum {o['mum']})\n", "soluk")
            if b:
                gen_ok = b["genislik"] >= GENISLIK_ESIK
                self.detay.insert("end", "   piyasa: ", "soluk")
                self.detay.insert("end",
                                  f"{'✓' if gen_ok else '✗'} genişlik {b['genislik']}"
                                  f"/{GENISLIK_EVREN} (≥{GENISLIK_ESIK})   ",
                                  "yesil" if gen_ok else "kirmizi")
                if b.get("rs") is not None:
                    rs_ok = b["rs"] <= RS_ESIK
                    self.detay.insert("end",
                                      f"{'✓' if rs_ok else '✗'} BTC'ye göre 24s "
                                      f"{b['rs']:+.1f} puan (≤{RS_ESIK:g})\n",
                                      "yesil" if rs_ok else "kirmizi")
                else:
                    self.detay.insert("end", "\n", "soluk")

        c = r.get("cikis")
        if c and "hedef" in c:
            self.detay.insert("end", "ÇIKIŞ PLANI  ", "baslik")
            self.detay.insert("end",
                              f"stop {c['stop']:.8g} ({c['stop_yuzde']:+.1f}%)", "kirmizi")
            self.detay.insert("end", "   ·   ", "soluk")
            self.detay.insert("end",
                              f"hedef {c['hedef']:.8g} ({c['hedef_yuzde']:+.1f}%)", "yesil")
            self.detay.insert("end",
                              f"   ·   saatlik ATR {c['atr']:.6g} · plan "
                              f"{STOP_ATR:g}/{HEDEF_ATR:g} ATR\n", "soluk")
        self.detay.insert("end", "\n", "soluk")

        for aralik in ZAMAN_DILIMLERI:
            t = r["tf"][aralik]
            rol = {"1d": "1. ADIM — genel yön",
                   "4h": "2. ADIM — fırsat değerlendirme",
                   "1h": "3. ADIM — dönüş (yükseliş başlangıcı)",
                   "15m": "4. ADIM — teyit + ALIM YERİ TESPİTİ"}[aralik]
            self.detay.insert("end",
                              f"── {aralik}  [{rol}]   skor {t['skor']:+.2f} "
                              f"({etiket(t['skor'])})  ·  trend {t.get('trend', '?')}"
                              f"  ·  {t.get('donus', 0)} gösterge dönüşte"
                              f"  ·  olumlu {t['pozitif']}/{len(INDIKATORLER)}, "
                              f"olumsuz {t['negatif']}/{len(INDIKATORLER)}\n", "tf")

            for ad in INDIKATORLER:
                d = t["indikatorler"][ad]
                renk = "yesil" if d["skor"] >= 0.25 else (
                    "kirmizi" if d["skor"] <= -0.25 else "soluk")
                self.detay.insert("end", f"   {ad:<11} {d['skor']:+.2f}  ", renk)
                self.detay.insert("end", f"{d['ozet']}\n", "soluk")
                for n in d["notlar"]:
                    self.detay.insert("end", f"        · {n}\n", "soluk")
            self.detay.insert("end", "\n")

        self.detay.configure(state="disabled")

    # ------------------------------------------------------------- kaydetme
    def html_kaydet(self):
        if not self.sonuclar:
            messagebox.showinfo("Rapor", "Önce tarama yapın.")
            return
        varsayilan = f"donus_rapor_{datetime.now():%Y%m%d_%H%M%S}.html"
        yol = filedialog.asksaveasfilename(
            defaultextension=".html", initialfile=varsayilan,
            filetypes=[("HTML", "*.html")])
        if not yol:
            return
        sirali = sorted(self.sonuclar, key=lambda r: r["toplam"], reverse=True)
        html_rapor(sirali, self.btc, yol)
        self.durum_yazi.configure(text=f"Rapor kaydedildi: {yol}")
        if messagebox.askyesno("Rapor hazır", "Raporu tarayıcıda açayım mı?"):
            webbrowser.open("file:///" + yol.replace("\\", "/"))

    def csv_kaydet(self):
        if not self.sonuclar:
            messagebox.showinfo("CSV", "Önce tarama yapın.")
            return
        varsayilan = f"donus_tarama_{datetime.now():%Y%m%d_%H%M%S}.csv"
        yol = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=varsayilan,
            filetypes=[("CSV", "*.csv")])
        if not yol:
            return

        sirali = sorted(self.sonuclar, key=lambda r: r["toplam"], reverse=True)
        basliklar = ["coin", "sembol", "sinyal_zamani", "fiyat", "degisim_24s",
                     "hacim_usd", "toplam_skor", "karar"]
        for a in ZAMAN_DILIMLERI:
            basliklar.append(f"{a}_skor")
            basliklar += [f"{a}_{ind}" for ind in INDIKATORLER]

        with open(yol, "w", newline="", encoding="utf-8-sig") as f:
            yazici = csv.writer(f, delimiter=";")
            yazici.writerow(basliklar)
            for r in sirali:
                satir = [r["coin"], r["sembol"], r.get("zaman", ""), r["fiyat"],
                         round(r["degisim"], 2), int(r["hacim"]), r["toplam"],
                         r["sinif"]]
                for a in ZAMAN_DILIMLERI:
                    satir.append(r["tf"][a]["skor"])
                    satir += [r["tf"][a]["indikatorler"][ind]["skor"]
                              for ind in INDIKATORLER]
                yazici.writerow(satir)

        self.durum_yazi.configure(text=f"CSV kaydedildi: {yol}")


if __name__ == "__main__":
    Uygulama().mainloop()
