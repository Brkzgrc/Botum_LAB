# -*- coding: utf-8 -*-
"""
TARAYICI 2 — PULLBACK / GERI CEKILME
=============================================================================
Tasarim ilkeleri momentum tarayicisiyla ayni (4H sert kapi, kenar tetikleme,
ortogonal girdiler, gecersizlik seviyesi) — FARK GIRIS FELSEFESINDE:

  Momentum tarayicisi uc zaman diliminin HIZALI oldugu ani arar.
  Bu dosya ise MTF UYUMSUZLUGUNU arar:

        4H  trend yukari          (izin — sert kapi, ayni)
        1H  geri cekilmis         (setup — aranan sey uyumsuzluk)
        15m donuyor               (tetik — taze KDJ kesisimi)

  Neden: uc TF maksimum hizalandigi an, hareketin en uzadigi andir. Yukselis
  trendi icindeki geri cekilme, ayni izinle daha iyi bir giris noktasi verir.
  Iki TF'nin ayri ayri icermedigi, yalnizca ILISKILERINDE var olan bilgi budur.

Puanlama: kapi gectikten SONRA  1H geri cekilme (2) + 15m donus (2) = 4 puan.
Kardes dosya: crypto_scanner_momentum.pyw
"""

import json
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

import ccxt
import pandas as pd

# ============================================================
# SABITLER
# ============================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(APP_DIR, "portfolio_pullback.json")

STRATEGY_NAME = "PULLBACK / GERI CEKILME"
MAX_SCORE = 4
OHLCV_LIMIT = 200
MIN_BARS = 120

RS_LOOKBACK = 42
RVOL_BARS = 3
RVOL_BASE = 20
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0
COOLDOWN_MIN = 120

# --- pullback parametreleri
PB_LOOKBACK = 12          # 1h bar — son 12 saatte geri cekilme oldu mu
PB_DEPTH = -70.0          # Williams%R bu seviyenin altina indiyse "geri cekilme"
CROSS_WITHIN = 3          # 15m — kesisim son N bar icinde olmali (taze)
CROSS_OVERSOLD = 35.0     # kesisim oncesi K bu seviyenin altindaydi mi (dipten donus)
EMA_TREND = 50            # 1h yapisal destek

EXCLUDED_BASES = {
    'USDT', 'USDC', 'FDUSD', 'TUSD', 'DAI', 'USDP', 'PYUSD', 'USDE', 'USD1',
    'RLUSD', 'EURI', 'AEUR', 'USTC', 'BUSD', 'PAX',
    'EUR', 'GBP', 'TRY', 'BRL', 'AUD', 'CAD', 'CHF', 'JPY', 'RUB', 'UAH',
    'PLN', 'ZAR', 'SEK', 'NOK', 'DKK', 'HUF', 'CZK', 'RON', 'MXN', 'ARS',
    'COP', 'PEN', 'CLP', 'VND', 'THB', 'IDR', 'PHP', 'MYR', 'SGD', 'HKD',
    'KRW', 'CNY', 'NGN', 'GHS', 'KES', 'XAF', 'XOF', 'BIDR', 'IDRT',
    'BKRW', 'BVND',
}

C_BG      = '#0f0f1a'
C_PANEL   = '#171726'
C_PANEL2  = '#1f1f33'
C_LINE    = '#2c2c44'
C_TEXT    = '#e6ebf0'
C_MUTED   = '#8b98a9'
C_ACCENT  = '#00b894'
C_DANGER  = '#e05252'
C_INFO    = '#4a9eff'
C_WARN    = '#f0b429'

ROW_NEW   = '#123d2b'
ROW_CONT  = '#1c1c2c'
ROW_FIRST = '#16304a'


# ============================================================
# BICIMLEME
# ============================================================
def fmt_price(p):
    if p is None:
        return '-'
    try:
        p = float(p)
    except (TypeError, ValueError):
        return '-'
    if p >= 100:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:.4f}"
    if p >= 0.01:
        return f"{p:.6f}"
    return f"{p:.8f}"


def fmt_vol(v):
    if not v:
        return '-'
    try:
        v = float(v)
    except (TypeError, ValueError):
        return '-'
    if v >= 1e9:
        return f"{v / 1e9:.2f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def fmt_eta(seconds):
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ============================================================
# BORSA — TEK PAYLASILAN NESNE
# ============================================================
class Exchange:
    _ex = None
    _init_lock = threading.Lock()
    net_lock = threading.Lock()
    _markets = None
    _markets_ts = 0.0
    MARKETS_TTL = 3600

    @classmethod
    def get(cls):
        with cls._init_lock:
            if cls._ex is None:
                cls._ex = ccxt.binance({
                    'enableRateLimit': True,
                    'timeout': 20000,
                    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True},
                })
            return cls._ex

    @classmethod
    def markets(cls):
        ex = cls.get()
        now = time.time()
        if cls._markets is None or (now - cls._markets_ts) > cls.MARKETS_TTL:
            with cls.net_lock:
                cls._markets = ex.load_markets()
            cls._markets_ts = now
        return cls._markets

    @classmethod
    def tickers(cls):
        with cls.net_lock:
            return cls.get().fetch_tickers()

    @classmethod
    def ohlcv(cls, symbol, timeframe, limit=OHLCV_LIMIT):
        with cls.net_lock:
            return cls.get().fetch_ohlcv(symbol, timeframe, limit=limit)


def fetch_df(symbol, timeframe, limit=OHLCV_LIMIT):
    rows = Exchange.ohlcv(symbol, timeframe, limit=limit)
    return pd.DataFrame(
        rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


# ============================================================
# GOSTERGE CEKIRDEGI
# ============================================================
def rma(series, n):
    return series.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def add_macd(df):
    c = df['close']
    df['macd'] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    return df


def add_rsi(df, n=14):
    d = df['close'].diff()
    gain, loss = d.clip(lower=0.0), (-d).clip(lower=0.0)
    ag, al = rma(gain, n), rma(loss, n)
    r = 100.0 - (100.0 / (1.0 + ag / al))
    r = r.where(al != 0, 100.0)
    r = r.where(~((ag == 0) & (al == 0)), 50.0)
    df['rsi'] = r
    return df


def add_kdj(df, n=9):
    ll = df['low'].rolling(n).min()
    hh = df['high'].rolling(n).max()
    rng = hh - ll
    rsv = (((df['close'] - ll) / rng) * 100).where(rng != 0, 50.0)
    df['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    return df


def add_williams(df, n=14):
    hh = df['high'].rolling(n).max()
    ll = df['low'].rolling(n).min()
    rng = hh - ll
    df['williams_r'] = (((hh - df['close']) / rng) * -100).where(rng != 0, -50.0)
    return df


def add_atr(df, n=ATR_PERIOD):
    prev = df['close'].shift()
    tr = pd.concat([df['high'] - df['low'],
                    (df['high'] - prev).abs(),
                    (df['low'] - prev).abs()], axis=1).max(axis=1)
    df['atr'] = rma(tr, n)
    return df


def add_ema(df, span, name):
    df[name] = df['close'].ewm(span=span, adjust=False).mean()
    return df


def rvol_at(df, pos, bars=RVOL_BARS, base=RVOL_BASE):
    v = df['volume']
    end = len(v) + pos + 1
    if end - bars - base < 0:
        return None
    recent = float(v.iloc[end - bars:end].sum())
    ref = float(v.iloc[end - bars - base:end - bars].mean()) * bars
    if ref <= 0:
        return None
    return recent / ref


def rs_vs_btc(df, btc_map, pos, n=RS_LOOKBACK):
    end = len(df) + pos
    if end - n < 0:
        return None
    try:
        ts_now = int(df['timestamp'].iloc[end])
        ts_then = int(df['timestamp'].iloc[end - n])
        c_now = float(df['close'].iloc[end])
        c_then = float(df['close'].iloc[end - n])
    except (ValueError, TypeError, IndexError):
        return None
    b_now, b_then = btc_map.get(ts_now), btc_map.get(ts_then)
    if not b_now or not b_then or c_then <= 0 or b_then <= 0:
        return None
    return ((c_now / c_then) - (b_now / b_then)) * 100.0


def fresh_cross_up(df, pos, within=CROSS_WITHIN, oversold=CROSS_OVERSOLD):
    """15m KDJ'de son `within` bar icinde asiri satimdan yukari kesisim var mi?

    Momentum tarayicisindaki "K > D" seviye kontrolunden farkli: burada
    kesisim ANI aranir, cunku pullback stratejisinde donus taze olmalidir.
    """
    k, d = df['kdj_k'], df['kdj_d']
    end = len(df) + pos
    if end < within + 8:
        return False, "yetersiz bar"
    if pd.isna(k.iloc[end]) or pd.isna(d.iloc[end]):
        return False, "NaN"
    if not (k.iloc[end] > d.iloc[end]):
        return False, "K henuz D'nin altinda"
    for j in range(end - within + 1, end + 1):
        if j - 1 < 0:
            continue
        if k.iloc[j - 1] <= d.iloc[j - 1] and k.iloc[j] > d.iloc[j]:
            lo = float(k.iloc[max(0, j - 6):j + 1].min())
            ago = end - j
            if lo < oversold:
                return True, f"{ago} bar once kesisti, K dibi {lo:.1f}"
            return False, f"kesisim var ama K dibi {lo:.1f} (>= {oversold:.0f})"
    return False, f"son {within} barda taze kesisim yok"


# ============================================================
# STRATEJI — PULLBACK
# ============================================================
class Strategy:
    """4H sert kapi -> 1H geri cekilme (2 puan) -> 15m donus tetigi (2 puan)."""

    NAME = STRATEGY_NAME

    @staticmethod
    def _pos(df, closed_only):
        return -2 if (closed_only and len(df) >= 2) else -1

    # ---------- 1. asama: 4H SERT KAPI (momentum dosyasiyla ayni) ----------
    @classmethod
    def gate_4h(cls, symbol, cfg, btc_map):
        try:
            df = fetch_df(symbol, '4h')
        except Exception as e:
            return {'error': f"4h {type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"4h yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = add_macd(df)
        df = add_rsi(df)
        df = add_atr(df)
        pos = cls._pos(df, cfg['closed'])
        last = df.iloc[pos]
        if any(pd.isna(last[c]) for c in ('macd', 'macd_signal', 'rsi', 'atr')):
            return {'error': '4h gosterge NaN'}

        macd_ok = bool(last['macd'] > last['macd_signal'] and last['macd'] > 0)
        rsi_ok = bool(last['rsi'] > 50)

        close = float(last['close'])
        atr = float(last['atr'])
        return {
            'passed': macd_ok and rsi_ok,
            'close': close,
            'atr': atr,
            'atr_pct': (atr / close * 100.0) if close else None,
            'rs': rs_vs_btc(df, btc_map, pos),
            'stop': close - ATR_STOP_MULT * atr,
            'items': [
                ('MACD(4h) trend', macd_ok,
                 f"{last['macd']:.6f} / sig {last['macd_signal']:.6f}"),
                ('RSI(4h) > 50', rsi_ok, f"{last['rsi']:.1f}"),
            ],
        }

    # ---------- 2. asama: 1H GERI CEKILME ----------
    @classmethod
    def setup_1h(cls, symbol, cfg):
        try:
            df = fetch_df(symbol, '1h')
        except Exception as e:
            return {'error': f"1h {type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"1h yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = add_williams(df)
        df = add_ema(df, EMA_TREND, 'ema_trend')
        pos = cls._pos(df, cfg['closed'])
        last = df.iloc[pos]
        if any(pd.isna(last[c]) for c in ('williams_r', 'ema_trend')):
            return {'error': '1h gosterge NaN'}

        end = len(df) + pos
        window = df['williams_r'].iloc[max(0, end - PB_LOOKBACK + 1):end + 1]
        dip = float(window.min()) if len(window) else 0.0

        # 1) gercekten geri cekildi mi?
        dip_ok = bool(dip < PB_DEPTH)
        # 2) ama yapi bozulmadi mi? (geri cekilme != trend kirilmasi)
        hold_ok = bool(float(last['close']) > float(last['ema_trend']))

        return {
            'score': int(dip_ok) + int(hold_ok),
            'items': [
                (f"Geri cekilme (W%R < {PB_DEPTH:.0f})", dip_ok,
                 f"son {PB_LOOKBACK} barda dip {dip:.1f}  ·  su an {last['williams_r']:.1f}"),
                (f"EMA{EMA_TREND} uzerinde", hold_ok,
                 f"{fmt_price(last['close'])} vs {fmt_price(last['ema_trend'])}"),
            ],
        }

    # ---------- 3. asama: 15m DONUS TETIGI ----------
    @classmethod
    def trigger_15m(cls, symbol, cfg):
        try:
            df = fetch_df(symbol, '15m')
        except Exception as e:
            return {'error': f"15m {type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"15m yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = add_kdj(df)
        pos = cls._pos(df, cfg['closed'])
        if pd.isna(df['kdj_k'].iloc[pos]):
            return {'error': '15m gosterge NaN'}

        cross_ok, cross_info = fresh_cross_up(df, pos)
        rvol = rvol_at(df, pos)
        rvol_ok = bool(rvol is not None and rvol >= cfg['minrvol'])

        return {
            'score': int(cross_ok) + int(rvol_ok),
            'rvol': rvol,
            'items': [
                ("KDJ(15m) taze donus", cross_ok, cross_info),
                (f"RVOL(15m) >= {cfg['minrvol']:.1f}", rvol_ok,
                 "hesaplanamadi" if rvol is None else f"{rvol:.2f}x"),
            ],
        }


# ============================================================
# UYGULAMA
# ============================================================
class ScannerApp:

    def __init__(self, root):
        self.root = root
        self.root.title(f"TARAYICI — {STRATEGY_NAME}  |  4H kapi · 1H geri cekilme · 15m donus")
        self.root.geometry("1420x900")
        self.root.configure(bg=C_BG)

        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._closing = False

        self.last_results = {}
        self.ticker_map = {}
        self.prev_pass = {}
        self.last_new_ts = {}
        self._first_cycle = True

        self.portfolio = self.load_portfolio()

        self._build_settings_vars()
        self._build_style()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------------------------------------------------------
    def _build_settings_vars(self):
        self.var_interval = tk.StringVar(value='10')
        self.var_threshold = tk.StringVar(value=str(MAX_SCORE))
        self.var_minvol = tk.StringVar(value='5')
        self.var_topn = tk.StringVar(value='0')
        self.var_minrvol = tk.StringVar(value='1.2')
        self.var_minrs = tk.StringVar(value='0')
        self.var_atrmin = tk.StringVar(value='1.0')
        self.var_atrmax = tk.StringVar(value='25')
        self.var_closed = tk.BooleanVar(value=True)
        self.var_only_new = tk.BooleanVar(value=False)

        self.cfg = {}
        for var in (self.var_interval, self.var_threshold, self.var_minvol,
                    self.var_topn, self.var_minrvol, self.var_minrs,
                    self.var_atrmin, self.var_atrmax,
                    self.var_closed, self.var_only_new):
            var.trace_add('write', lambda *_: self._sync_cfg())
        self._sync_cfg()

    def _sync_cfg(self):
        def as_int(var, default, lo=None, hi=None):
            try:
                v = int(str(var.get()).strip())
            except (ValueError, TypeError):
                return default
            if lo is not None and v < lo:
                return lo
            if hi is not None and v > hi:
                return hi
            return v

        def as_float(var, default, lo=None, hi=None):
            try:
                v = float(str(var.get()).strip().replace(',', '.'))
            except (ValueError, TypeError):
                return default
            if lo is not None and v < lo:
                return lo
            if hi is not None and v > hi:
                return hi
            return v

        self.cfg = {
            'interval': as_int(self.var_interval, 10, 1, 1440),
            'threshold': as_int(self.var_threshold, MAX_SCORE, 0, MAX_SCORE),
            'minvol': as_int(self.var_minvol, 5, 0, 100000),
            'topn': as_int(self.var_topn, 0, 0, 5000),
            'minrvol': as_float(self.var_minrvol, 1.2, 0.0, 100.0),
            'minrs': as_float(self.var_minrs, 0.0, -1000.0, 1000.0),
            'atrmin': as_float(self.var_atrmin, 1.0, 0.0, 1000.0),
            'atrmax': as_float(self.var_atrmax, 25.0, 0.0, 1000.0),
            'closed': bool(self.var_closed.get()),
            'only_new': bool(self.var_only_new.get()),
        }

    # --------------------------------------------------------
    def _build_style(self):
        st = ttk.Style()
        st.theme_use('clam')

        st.configure('TNotebook', background=C_BG, borderwidth=0, tabmargins=[4, 6, 4, 0])
        st.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'),
                     padding=[20, 8], borderwidth=0)
        st.map('TNotebook.Tab',
               background=[('selected', C_PANEL), ('!selected', '#13131f')],
               foreground=[('selected', C_ACCENT), ('!selected', C_MUTED)])

        st.configure('Treeview', background='#14141f', fieldbackground='#14141f',
                     foreground=C_TEXT, rowheight=26, borderwidth=0,
                     font=('Segoe UI', 10))
        st.configure('Treeview.Heading', background='#22223a', foreground='#a9b8cc',
                     font=('Segoe UI', 9, 'bold'), relief='flat', padding=6)
        st.map('Treeview.Heading', background=[('active', '#2e2e4d')])
        st.map('Treeview', background=[('selected', '#2d6cdf')],
               foreground=[('selected', 'white')])

        st.configure('Dark.TEntry', fieldbackground=C_PANEL2, foreground=C_TEXT,
                     bordercolor=C_LINE, lightcolor=C_LINE, darkcolor=C_LINE, padding=4)
        st.configure('Dark.TCheckbutton', background=C_PANEL, foreground=C_TEXT,
                     font=('Segoe UI', 9))
        st.map('Dark.TCheckbutton', background=[('active', C_PANEL)],
               foreground=[('active', C_TEXT)])
        st.configure('Dark.Horizontal.TProgressbar', troughcolor=C_PANEL2,
                     background=C_ACCENT, bordercolor=C_PANEL2,
                     lightcolor=C_ACCENT, darkcolor=C_ACCENT)
        st.configure('Vertical.TScrollbar', background=C_PANEL2, troughcolor=C_BG,
                     bordercolor=C_BG, arrowcolor=C_MUTED)

    @staticmethod
    def _button(parent, text, color, command, width=13):
        return tk.Button(parent, text=text, command=command, width=width,
                         bg=color, fg='white', activebackground=color,
                         activeforeground='white', disabledforeground='#6d7b8d',
                         font=('Segoe UI', 9, 'bold'), relief='flat', bd=0,
                         cursor='hand2', padx=6, pady=5)

    @staticmethod
    def _label(parent, text, fg=C_MUTED, bg=C_PANEL, size=9, bold=False):
        return tk.Label(parent, text=text, bg=bg, fg=fg,
                        font=('Segoe UI', size, 'bold' if bold else 'normal'))

    # --------------------------------------------------------
    def _build_layout(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(10, 12))

        self.tab_scan = tk.Frame(self.notebook, bg=C_BG)
        self.notebook.add(self.tab_scan, text="  TARAMA  ")
        self._build_scan_tab()

        self.tab_portfolio = tk.Frame(self.notebook, bg=C_BG)
        self.notebook.add(self.tab_portfolio, text="  PORTFOY  ")
        self._build_portfolio_tab()

    def _build_scan_tab(self):
        self.tab_scan.rowconfigure(2, weight=1)
        self.tab_scan.columnconfigure(0, weight=1)

        ctrl = tk.Frame(self.tab_scan, bg=C_PANEL)
        ctrl.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        inner = tk.Frame(ctrl, bg=C_PANEL)
        inner.pack(fill='x', padx=14, pady=10)

        def field(col, label, var, width, hint=''):
            box = tk.Frame(inner, bg=C_PANEL)
            box.grid(row=0, column=col, padx=(0, 14), sticky='w')
            self._label(box, label, bold=True).pack(anchor='w')
            ttk.Entry(box, textvariable=var, width=width, style='Dark.TEntry',
                      font=('Segoe UI', 10)).pack(anchor='w', pady=(2, 0))
            if hint:
                self._label(box, hint, fg='#5f6b7a', size=8).pack(anchor='w')

        field(0, "Aralik", self.var_interval, 5, "dakika")
        field(1, "Min skor", self.var_threshold, 4, f"/ {MAX_SCORE}")
        field(2, "Min hacim", self.var_minvol, 6, "milyon $")
        field(3, "Ilk N", self.var_topn, 5, "0 = hepsi")
        field(4, "Min RVOL", self.var_minrvol, 5, "kat")
        field(5, "Min RS", self.var_minrs, 5, "% (BTC)")
        field(6, "ATR% alt", self.var_atrmin, 5, "filtre")
        field(7, "ATR% ust", self.var_atrmax, 5, "filtre")

        status = tk.Frame(inner, bg=C_PANEL)
        status.grid(row=0, column=8, sticky='e', padx=(18, 0))
        inner.columnconfigure(8, weight=1)
        self._label(status, " ", bold=True).pack(anchor='e')
        self.lbl_status = tk.Label(status, text="● Bekliyor", bg=C_PANEL, fg=C_MUTED,
                                   font=('Segoe UI', 10, 'bold'))
        self.lbl_status.pack(anchor='e')

        opts = tk.Frame(inner, bg=C_PANEL)
        opts.grid(row=1, column=0, columnspan=6, sticky='w', pady=(10, 0))
        ttk.Checkbutton(opts, text="Sadece kapanmis mum", variable=self.var_closed,
                        style='Dark.TCheckbutton').pack(side='left', padx=(0, 18))
        ttk.Checkbutton(opts, text="Sadece YENI sinyaller", variable=self.var_only_new,
                        style='Dark.TCheckbutton').pack(side='left')

        actions = tk.Frame(inner, bg=C_PANEL)
        actions.grid(row=1, column=6, columnspan=3, sticky='e', pady=(10, 0))
        self.btn_start = self._button(actions, "BASLAT", C_ACCENT, self.start_scan, 11)
        self.btn_start.pack(side='left', padx=(0, 6))
        self.btn_stop = self._button(actions, "DURDUR", C_DANGER, self.stop_scan, 11)
        self.btn_stop.pack(side='left', padx=(0, 14))
        self.btn_stop.config(state='disabled')
        self.btn_add = self._button(actions, "PORTFOYE EKLE", C_INFO,
                                    self.add_to_portfolio, 16)
        self.btn_add.pack(side='left')

        prog = tk.Frame(self.tab_scan, bg=C_BG)
        prog.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        prog.columnconfigure(0, weight=1)
        self.var_progress = tk.DoubleVar(value=0.0)
        ttk.Progressbar(prog, variable=self.var_progress, maximum=100.0,
                        style='Dark.Horizontal.TProgressbar'
                        ).grid(row=0, column=0, sticky='ew', padx=(0, 12))
        self.lbl_progress = tk.Label(
            prog, text="0 / 0   ·   kalan --:--   ·   kapi 0   ·   0 sinyal",
            bg=C_BG, fg=C_MUTED, font=('Consolas', 9))
        self.lbl_progress.grid(row=0, column=1, sticky='e')

        self.paned = tk.PanedWindow(self.tab_scan, orient='vertical', bg=C_BG,
                                    sashwidth=6, sashrelief='flat', bd=0,
                                    sashpad=1, opaqueresize=True)
        self.paned.grid(row=2, column=0, sticky='nsew')

        self.logf = tk.Frame(self.paned, bg=C_PANEL)
        log_head = tk.Frame(self.logf, bg=C_PANEL)
        log_head.pack(fill='x')
        tk.Label(log_head, text="  ANLIK LOG", bg=C_PANEL, fg=C_WARN,
                 font=('Segoe UI', 9, 'bold')).pack(side='left', pady=(6, 2))
        self.btn_log_toggle = tk.Button(
            log_head, text="▾ Gizle", bg=C_PANEL, fg=C_MUTED,
            activebackground=C_PANEL, activeforeground=C_TEXT,
            relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 8, 'bold'),
            command=self.toggle_log)
        self.btn_log_toggle.pack(side='right', padx=8)

        log_holder = tk.Frame(self.logf, bg=C_PANEL)
        log_holder.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.txt_log = tk.Text(log_holder, bg='#0c0c14', fg=C_TEXT,
                               font=('Consolas', 9), wrap='word', relief='flat',
                               padx=8, pady=6, insertbackground=C_TEXT)
        self.txt_log.pack(side='left', fill='both', expand=True)
        logsb = ttk.Scrollbar(log_holder, orient='vertical', command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=logsb.set)
        logsb.pack(side='right', fill='y')
        for tag, col in (('info', C_MUTED), ('ok', C_ACCENT), ('sig', '#7bed9f'),
                         ('warn', C_WARN), ('err', C_DANGER)):
            self.txt_log.tag_configure(tag, foreground=col)
        self.txt_log.config(state='disabled')
        self.paned.add(self.logf, minsize=40, height=170, stretch='never')

        self.scan_table_wrap = tk.Frame(self.paned, bg=C_BG)
        wrap = self.scan_table_wrap
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        cols = ('coin', 'price', 'vol', 'score', 'rs', 'rvol', 'atrp', 'stop', 'state')
        heads = {
            'coin': ('Coin', 130), 'price': ('Fiyat', 105), 'vol': ('24s Hacim', 95),
            'score': ('Skor', 70), 'rs': ('RS (BTC)', 95), 'rvol': ('RVOL', 80),
            'atrp': ('ATR%', 75), 'stop': ('Stop (2×ATR)', 115), 'state': ('Durum', 110),
        }
        self.tree_scan = ttk.Treeview(wrap, columns=cols, show='headings',
                                      selectmode='extended')
        for c in cols:
            text, w = heads[c]
            self.tree_scan.heading(
                c, text=text, command=lambda cc=c: self._sort_tree(self.tree_scan, cc, True))
            self.tree_scan.column(c, width=w, anchor='center',
                                  stretch=(c in ('coin', 'state')))
        self.tree_scan.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.tree_scan.yview)
        self.tree_scan.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky='ns')

        self.tree_scan.tag_configure('new', background=ROW_NEW)
        self.tree_scan.tag_configure('cont', background=ROW_CONT)
        self.tree_scan.tag_configure('first', background=ROW_FIRST)
        self.tree_scan.bind('<Double-1>', self.show_detail)

        self.paned.add(wrap, minsize=150, stretch='always')
        self._log_visible = True

    def toggle_log(self):
        if self._log_visible:
            self.paned.forget(self.logf)
            self.btn_log_toggle.config(text="▸ Goster")
            self._log_visible = False
        else:
            self.paned.add(self.logf, before=self.scan_table_wrap,
                           minsize=40, height=170, stretch='never')
            self.btn_log_toggle.config(text="▾ Gizle")
            self._log_visible = True

    # --------------------------------------------------------
    def _build_portfolio_tab(self):
        self.tab_portfolio.rowconfigure(1, weight=1)
        self.tab_portfolio.columnconfigure(0, weight=1)

        bar = tk.Frame(self.tab_portfolio, bg=C_PANEL)
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        inner = tk.Frame(bar, bg=C_PANEL)
        inner.pack(fill='x', padx=14, pady=10)
        tk.Label(inner, text="Kayitli Sinyaller", bg=C_PANEL, fg=C_TEXT,
                 font=('Segoe UI', 11, 'bold')).pack(side='left', padx=(0, 20))
        self._button(inner, "FIYATLARI GUNCELLE", C_INFO,
                     self.refresh_prices, 20).pack(side='left', padx=4)
        self._button(inner, "SIL", C_DANGER, self.delete_portfolio, 9).pack(side='left', padx=4)
        self.lbl_pf_info = tk.Label(inner, text="", bg=C_PANEL, fg=C_MUTED,
                                    font=('Segoe UI', 9))
        self.lbl_pf_info.pack(side='right')

        wrap = tk.Frame(self.tab_portfolio, bg=C_BG)
        wrap.grid(row=1, column=0, sticky='nsew')
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        cols = ('coin', 'date', 'score', 'entry', 'stop', 'now', 'pnl', 'state', 'note')
        heads = {
            'coin': ('Coin', 115), 'date': ('Eklenme', 130), 'score': ('Skor', 65),
            'entry': ('Giris', 105), 'stop': ('Stop', 105), 'now': ('Guncel', 105),
            'pnl': ('Degisim', 90), 'state': ('Durum', 110), 'note': ('Not', 340),
        }
        self.tree_portfolio = ttk.Treeview(wrap, columns=cols, show='headings')
        for c in cols:
            text, w = heads[c]
            self.tree_portfolio.heading(
                c, text=text,
                command=lambda cc=c: self._sort_tree(self.tree_portfolio, cc, True))
            self.tree_portfolio.column(c, width=w, stretch=(c == 'note'),
                                       anchor='w' if c == 'note' else 'center')
        self.tree_portfolio.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.tree_portfolio.yview)
        self.tree_portfolio.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky='ns')

        self.tree_portfolio.tag_configure('up', foreground='#7bed9f')
        self.tree_portfolio.tag_configure('down', foreground='#ff7675')
        self.tree_portfolio.tag_configure('stopped', background='#3d1a1a',
                                          foreground='#ff9f9f')
        self.tree_portfolio.bind('<<TreeviewSelect>>', self._on_pf_select)

        note = tk.Frame(self.tab_portfolio, bg=C_PANEL)
        note.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        ni = tk.Frame(note, bg=C_PANEL)
        ni.pack(fill='x', padx=14, pady=10)
        tk.Label(ni, text="Not:", bg=C_PANEL, fg=C_TEXT,
                 font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 8))
        self.entry_note = ttk.Entry(ni, style='Dark.TEntry', font=('Segoe UI', 10))
        self.entry_note.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self._button(ni, "NOTU KAYDET", C_ACCENT, self.update_note, 14).pack(side='left')

        self.refresh_portfolio()

    # --------------------------------------------------------
    def _ui(self, fn, *args, **kwargs):
        if self._closing:
            return
        try:
            self.root.after(0, lambda: fn(*args, **kwargs))
        except (RuntimeError, tk.TclError):
            pass

    def log(self, message, level='info'):
        self._ui(self._log_ui, message, level)

    def _log_ui(self, message, level):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, f"[{ts}]  {message}\n", level)
        total = int(self.txt_log.index('end-1c').split('.')[0])
        if total > 400:
            self.txt_log.delete('1.0', f"{total - 300}.0")
        self.txt_log.config(state='disabled')
        self.txt_log.see(tk.END)

    def set_status(self, text, color=C_MUTED):
        self._ui(lambda: self.lbl_status.config(text=f"● {text}", fg=color))

    def set_progress(self, done, total, gate, signals, eta=None):
        def apply():
            self.var_progress.set((done / total * 100.0) if total else 0.0)
            self.lbl_progress.config(
                text=f"{done} / {total}   ·   kalan {fmt_eta(eta)}   ·   "
                     f"kapi {gate}   ·   {signals} sinyal")
        self._ui(apply)

    # --------------------------------------------------------
    def start_scan(self):
        if self.running:
            return
        if self.thread is not None and self.thread.is_alive():
            messagebox.showinfo("Bekleyin", "Onceki tarama hala kapaniyor.")
            return
        self.running = True
        self._stop_event.clear()
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.set_status("Taraniyor", C_ACCENT)
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()

    def stop_scan(self):
        if not self.running:
            return
        self.running = False
        self._stop_event.set()
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.set_status("Durduruldu", C_DANGER)
        self.log("Tarama durduruldu.", 'warn')

    def on_close(self):
        self._closing = True
        self.running = False
        self._stop_event.set()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # --------------------------------------------------------
    def get_symbols(self, cfg):
        try:
            markets = Exchange.markets()
        except Exception as e:
            self.log(f"Market listesi alinamadi: {type(e).__name__}: {e}", 'err')
            return []

        spot_bases = {m.get('base') for m in markets.values() if m.get('spot')}

        def is_leveraged(base):
            for suf in ('UP', 'DOWN', 'BULL', 'BEAR'):
                if base.endswith(suf) and len(base) > len(suf) and base[:-len(suf)] in spot_bases:
                    return True
            return False

        candidates = []
        for sym, m in markets.items():
            if not (m.get('spot') and m.get('active')):
                continue
            if m.get('quote') != 'USDT':
                continue
            base = m.get('base') or ''
            if not base or base in EXCLUDED_BASES or is_leveraged(base):
                continue
            candidates.append(sym)

        try:
            self.ticker_map = Exchange.tickers()
        except Exception as e:
            self.log(f"Hacim verisi alinamadi, filtre atlaniyor: {type(e).__name__}: {e}", 'warn')
            return sorted(candidates)

        min_vol = cfg['minvol'] * 1_000_000
        scored = []
        for sym in candidates:
            qv = (self.ticker_map.get(sym) or {}).get('quoteVolume') or 0
            if qv >= min_vol:
                scored.append((qv, sym))
        scored.sort(reverse=True)
        if cfg['topn'] > 0:
            scored = scored[:cfg['topn']]
        return [s for _, s in scored]

    def _btc_reference(self):
        try:
            btc = fetch_df('BTC/USDT', '4h')
            return {int(t): float(c) for t, c in zip(btc['timestamp'], btc['close'])}
        except Exception as e:
            self.log(f"BTC referansi alinamadi, RS hesaplanmayacak: "
                     f"{type(e).__name__}: {e}", 'warn')
            return {}

    # --------------------------------------------------------
    def _scan_loop(self):
        while self.running:
            cfg = dict(self.cfg)
            self.log(f"Tarama basliyor  ·  strateji: {STRATEGY_NAME}", 'ok')
            self.set_progress(0, 0, 0, 0)

            btc_map = self._btc_reference()
            symbols = self.get_symbols(cfg)
            total = len(symbols)

            if total == 0:
                self.log("Taranacak coin bulunamadi (hacim filtresi cok yuksek olabilir).", 'warn')
            else:
                self.log(f"{total} coin  ·  min hacim {cfg['minvol']}M$  ·  "
                         f"esik {cfg['threshold']}/{MAX_SCORE}  ·  "
                         f"mum: {'kapanmis' if cfg['closed'] else 'canli'}", 'info')

            self._ui(lambda: self.tree_scan.delete(*self.tree_scan.get_children()))
            self.last_results.clear()

            gate_pass = 0
            signal_count = 0
            new_count = 0
            err_count = 0
            err_samples = []
            t0 = time.time()
            seen = set()

            for idx, symbol in enumerate(symbols, start=1):
                if not self.running:
                    self.log("Tarama yarida kesildi.", 'warn')
                    break

                seen.add(symbol)
                row = self._evaluate(symbol, cfg, btc_map)

                elapsed = time.time() - t0
                eta = (elapsed / idx) * (total - idx) if idx else None
                self.set_progress(idx, total, gate_pass, signal_count, eta)

                if row is None:
                    continue
                if 'error' in row:
                    err_count += 1
                    if len(err_samples) < 5:
                        err_samples.append(f"{symbol} -> {row['error']}")
                    self.prev_pass[symbol] = False
                    continue

                if row['gate']:
                    gate_pass += 1

                passed = row['passed']
                was = self.prev_pass.get(symbol, False)
                self.prev_pass[symbol] = passed
                if not passed:
                    continue

                signal_count += 1

                now = time.time()
                if self._first_cycle:
                    state, tag = "ILK TARAMA", 'first'
                elif not was:
                    last = self.last_new_ts.get(symbol, 0)
                    if now - last < COOLDOWN_MIN * 60:
                        state, tag = "devam", 'cont'
                    else:
                        state, tag = "YENI", 'new'
                        self.last_new_ts[symbol] = now
                        new_count += 1
                else:
                    state, tag = "devam", 'cont'

                if cfg['only_new'] and tag != 'new':
                    continue

                row['state'] = state
                self.last_results[symbol] = row
                self._ui(self._insert_row, symbol, row, tag)

                if tag == 'new':
                    self.log(f"YENI SINYAL  {symbol}  ·  {row['score']}/{MAX_SCORE}  ·  "
                             f"RS {row['rs']:+.1f}%  ·  RVOL {row['rvol']:.2f}x", 'sig')

            if self.running:
                took = int(time.time() - t0)
                for sym in list(self.prev_pass):
                    if sym not in seen:
                        self.prev_pass.pop(sym, None)

                saved = max(0, (len(seen) - gate_pass)) * 2
                self.log(f"Tamamlandi  ·  4H kapi gecen: {gate_pass}/{len(seen)}  ·  "
                         f"{signal_count} sinyal ({new_count} yeni)  ·  "
                         f"{err_count} hata  ·  {fmt_eta(took)}", 'ok')
                self.log(f"Sert kapi sayesinde ~{saved} istek yapilmadi.", 'info')
                for s in err_samples:
                    self.log(f"  atlandi: {s}", 'err')
                if self._first_cycle:
                    self.log("Ilk tur referans alindi; bundan sonra sadece YENI "
                             "gecisler sinyal sayilacak.", 'warn')
                self._first_cycle = False

                self.set_status(f"{datetime.now().strftime('%H:%M:%S')} · "
                                f"{signal_count} sinyal ({new_count} yeni)", C_ACCENT)
                self.set_progress(len(seen), len(seen), gate_pass, signal_count, 0)
                self._ui(lambda: self._sort_tree(self.tree_scan, 'rs', True))

                self.log(f"Sonraki tarama {cfg['interval']} dakika sonra.", 'info')
                self._stop_event.wait(cfg['interval'] * 60)

        self._ui(lambda: (self.btn_start.config(state='normal'),
                          self.btn_stop.config(state='disabled')))

    # --------------------------------------------------------
    def _evaluate(self, symbol, cfg, btc_map):
        g = Strategy.gate_4h(symbol, cfg, btc_map)
        if 'error' in g:
            return g
        if not g['passed']:
            return None

        atr_pct = g['atr_pct']
        if atr_pct is None or not (cfg['atrmin'] <= atr_pct <= cfg['atrmax']):
            return {'gate': True, 'passed': False}
        rs = g['rs']
        if rs is None or rs < cfg['minrs']:
            return {'gate': True, 'passed': False}

        s = Strategy.setup_1h(symbol, cfg)
        if 'error' in s:
            return s
        t = Strategy.trigger_15m(symbol, cfg)
        if 'error' in t:
            return t

        score = s['score'] + t['score']
        tk_ = self.ticker_map.get(symbol) or {}
        return {
            'gate': True,
            'passed': score >= cfg['threshold'],
            'score': score,
            'rs': rs,
            'rvol': t['rvol'] if t['rvol'] is not None else 0.0,
            'atr_pct': atr_pct,
            'stop': g['stop'],
            'close': g['close'],
            'price': tk_.get('last') or g['close'],
            'vol24': tk_.get('quoteVolume'),
            'detail': {'4h': g, '1h': s, '15m': t},
        }

    def _insert_row(self, symbol, row, tag):
        self.tree_scan.insert('', 'end', tags=(tag,), values=(
            symbol,
            fmt_price(row['price']),
            fmt_vol(row['vol24']),
            f"{row['score']}/{MAX_SCORE}",
            f"{row['rs']:+.1f}%",
            f"{row['rvol']:.2f}x",
            f"{row['atr_pct']:.1f}",
            fmt_price(row['stop']),
            row['state'],
        ))

    # --------------------------------------------------------
    def show_detail(self, _event=None):
        sel = self.tree_scan.selection()
        if not sel:
            return
        symbol = self.tree_scan.item(sel[0], 'values')[0]
        data = self.last_results.get(symbol)
        if not data:
            return

        win = tk.Toplevel(self.root)
        win.title(f"{symbol} — {STRATEGY_NAME}")
        win.configure(bg=C_BG)
        win.geometry("620x520")
        win.transient(self.root)

        tk.Label(win, text=symbol, bg=C_BG, fg=C_ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=18, pady=(14, 2))
        tk.Label(win, text=f"Skor {data['score']}/{MAX_SCORE}   ·   "
                           f"RS {data['rs']:+.1f}%   ·   RVOL {data['rvol']:.2f}x   ·   "
                           f"ATR% {data['atr_pct']:.1f}",
                 bg=C_BG, fg=C_TEXT, font=('Segoe UI', 10)).pack(anchor='w', padx=18)

        box = tk.Text(win, bg='#0c0c14', fg=C_TEXT, font=('Consolas', 10),
                      relief='flat', padx=12, pady=10, wrap='none')
        box.pack(fill='both', expand=True, padx=14, pady=12)
        box.tag_configure('h', foreground=C_INFO)
        box.tag_configure('gate', foreground=C_WARN)
        box.tag_configure('ok', foreground='#7bed9f')
        box.tag_configure('no', foreground='#ff7675')

        g = data['detail']['4h']
        box.insert(tk.END, "\n 4H — SERT KAPI (gecilmesi zorunlu)\n", 'gate')
        for name, ok, val in g['items']:
            box.insert(tk.END, f"   {'+' if ok else '-'}  {name:<26} {val}\n",
                       'ok' if ok else 'no')

        for tf, title in (('1h', '1H — GERI CEKILME YAPISI (2 puan)'),
                          ('15m', '15m — DONUS TETIGI (2 puan)')):
            r = data['detail'][tf]
            box.insert(tk.END, f"\n {title}   ({r['score']}/2)\n", 'h')
            for name, ok, val in r['items']:
                box.insert(tk.END, f"   {'+' if ok else '-'}  {name:<26} {val}\n",
                           'ok' if ok else 'no')

        box.insert(tk.END, "\n RISK\n", 'h')
        box.insert(tk.END, f"   4H kapanis      {fmt_price(data['close'])}\n")
        box.insert(tk.END, f"   Stop (2xATR)    {fmt_price(data['stop'])}\n")
        box.insert(tk.END, f"   Mesafe          {data['atr_pct'] * ATR_STOP_MULT:.1f}%\n")
        box.config(state='disabled')

        self._button(win, "KAPAT", C_PANEL2, win.destroy, 10).pack(pady=(0, 14))

    # --------------------------------------------------------
    @staticmethod
    def _sort_tree(tree, col, reverse):
        def key(value):
            s = str(value).replace('%', '').replace(',', '').replace('×', '')
            s = s.replace('x', '').replace('+', '').strip()
            if '/' in s:
                s = s.split('/')[0]
            mult = 1.0
            if s.endswith('B'):
                s, mult = s[:-1], 1e9
            elif s.endswith('M'):
                s, mult = s[:-1], 1e6
            elif s.endswith('K'):
                s, mult = s[:-1], 1e3
            try:
                return (0, float(s) * mult, '')
            except ValueError:
                return (1, 0.0, str(value).lower())

        rows = [(tree.set(k, col), k) for k in tree.get_children('')]
        rows.sort(key=lambda r: key(r[0]), reverse=reverse)
        for i, (_, k) in enumerate(rows):
            tree.move(k, '', i)
        tree.heading(col, command=lambda: ScannerApp._sort_tree(tree, col, not reverse))

    # --------------------------------------------------------
    def load_portfolio(self):
        if not os.path.exists(PORTFOLIO_FILE):
            return []
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def save_portfolio(self):
        try:
            with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.portfolio, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Kayit hatasi", f"Portfoy yazilamadi:\n{e}")

    def refresh_portfolio(self):
        self.tree_portfolio.delete(*self.tree_portfolio.get_children())
        stopped = 0
        for item in self.portfolio:
            coin = item.get('coin', '')
            entry = item.get('entry_price')
            stop = item.get('stop')
            now = (self.ticker_map.get(coin) or {}).get('last')

            pnl_txt, state, tag = '-', '-', ''
            if entry and now:
                try:
                    pct = (float(now) - float(entry)) / float(entry) * 100.0
                    pnl_txt = f"{pct:+.2f}%"
                    tag = 'up' if pct >= 0 else 'down'
                    state = "acik"
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
            if stop and now:
                try:
                    if float(now) <= float(stop):
                        state, tag = "STOP KIRILDI", 'stopped'
                        stopped += 1
                except (TypeError, ValueError):
                    pass

            self.tree_portfolio.insert('', 'end', tags=(tag,) if tag else (), values=(
                coin, item.get('date', ''), f"{item.get('score', 0)}/{MAX_SCORE}",
                fmt_price(entry), fmt_price(stop), fmt_price(now),
                pnl_txt, state, item.get('note', '')))

        info = f"{len(self.portfolio)} kayit"
        if stopped:
            info += f"   ·   {stopped} stop kirildi"
        self.lbl_pf_info.config(text=info)

    def refresh_prices(self):
        def work():
            try:
                self.ticker_map = Exchange.tickers()
                self._ui(self.refresh_portfolio)
                self.log("Portfoy fiyatlari guncellendi.", 'ok')
            except Exception as e:
                self.log(f"Fiyat guncellenemedi: {type(e).__name__}: {e}", 'err')
        threading.Thread(target=work, daemon=True).start()

    def add_to_portfolio(self):
        sel = self.tree_scan.selection()
        if not sel:
            messagebox.showwarning("Uyari", "Tarama listesinden en az bir coin secin.")
            return
        added = 0
        for item_id in sel:
            coin = self.tree_scan.item(item_id, 'values')[0]
            data = self.last_results.get(coin)
            if not data:
                continue
            if any(p.get('coin') == coin for p in self.portfolio):
                self.log(f"{coin} zaten portfoyde.", 'warn')
                continue
            self.portfolio.append({
                'coin': coin,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'score': data['score'],
                'entry_price': data['price'],
                'stop': data['stop'],
                'rs': round(data['rs'], 2),
                'rvol': round(data['rvol'], 2),
                'atr_pct': round(data['atr_pct'], 2),
                'strategy': STRATEGY_NAME,
                'note': '',
            })
            added += 1
            self.log(f"{coin} portfoye eklendi  ·  stop {fmt_price(data['stop'])}", 'ok')
        if added:
            self.save_portfolio()
            self.refresh_portfolio()
            self.notebook.select(self.tab_portfolio)

    def delete_portfolio(self):
        sel = self.tree_portfolio.selection()
        if not sel:
            messagebox.showwarning("Uyari", "Silmek icin bir kayit secin.")
            return
        coins = {self.tree_portfolio.item(i, 'values')[0] for i in sel}
        if not messagebox.askyesno("Onay", f"{len(coins)} kayit silinsin mi?"):
            return
        self.portfolio = [p for p in self.portfolio if p.get('coin') not in coins]
        self.save_portfolio()
        self.refresh_portfolio()
        self.log(f"{len(coins)} kayit silindi.", 'warn')

    def _on_pf_select(self, _event=None):
        sel = self.tree_portfolio.selection()
        if not sel:
            return
        self.entry_note.delete(0, tk.END)
        self.entry_note.insert(0, self.tree_portfolio.item(sel[0], 'values')[8])

    def update_note(self):
        sel = self.tree_portfolio.selection()
        if not sel:
            messagebox.showwarning("Uyari", "Not icin bir kayit secin.")
            return
        coin = self.tree_portfolio.item(sel[0], 'values')[0]
        note = self.entry_note.get().strip()
        for p in self.portfolio:
            if p.get('coin') == coin:
                p['note'] = note
                break
        self.save_portfolio()
        self.refresh_portfolio()
        self.log(f"{coin} notu guncellendi.", 'info')


# ============================================================
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ScannerApp(root)
        root.mainloop()
    except Exception as exc:
        try:
            err = tk.Tk()
            err.withdraw()
            messagebox.showerror("Baslatma hatasi", f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
