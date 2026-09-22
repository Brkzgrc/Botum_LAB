# -*- coding: utf-8 -*-
"""
UYGULAMA 2 — ROL DAGILIMI (Role-Based) Scanner  v2
===================================================
Sinyal mantigi degismedi:
    4H  -> MACD (Trend Filtresi) + RSI (Momentum Onayi)        [2 puan]
    1H  -> Williams%R (Orta Vadeli Donus) + MACD (Yapi Uyumu)  [2 puan]
    15m -> KDJ (Giris Tetikleyicisi) + StochRSI (Hassas Filtre)[2 puan]
    Toplam 6/6.

v2'de duzeltilenler (sinyal mantigi haric):
    * KRITIK: 15m StochRSI hesabi 'rsi' kolonuna ihtiyac duyuyordu ama
      calc_rsi() hic cagrilmiyordu -> her coin KeyError ile hata veriyor,
      tarama hep "0 sinyal" donduruyordu. calc_rsi() artik cagriliyor.
    * Tek paylasilan ccxt nesnesi -> enableRateLimit gercekten calisiyor
    * Tum Tkinter erisimleri ana thread'e tasindi (root.after)
    * Hatalar artik sessizce yutulmuyor, loga yaziliyor
    * Wilder (RMA) tabanli standart RSI
    * Yetersiz veri / NaN kontrolu
    * Kaldiracli token filtresi duzeltildi (JUP gibi coinler artik elenmiyor)
    * Guncel stablecoin/fiat listesi
    * Portfoy dosyasi script klasorune sabitlendi
    * Kapanmis mum secenegi (repaint onleme)
    * Hacim on filtresi -> daha az istek, daha az ban riski
    * Progress bar, siralanabilir kolonlar, detay penceresi, renkli log
      (log paneli tablonun USTUNDE)
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
PORTFOLIO_FILE = os.path.join(APP_DIR, "portfolio_role_based.json")

MAX_SCORE = 6
OHLCV_LIMIT = 200
MIN_BARS = 120

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

ROW_FULL   = '#123d2b'
ROW_STRONG = '#16304a'
ROW_MED    = '#26263a'


# ============================================================
# YARDIMCILAR
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
        ex = cls.get()
        with cls.net_lock:
            return ex.fetch_tickers()

    @classmethod
    def ohlcv(cls, symbol, timeframe, limit=OHLCV_LIMIT):
        ex = cls.get()
        with cls.net_lock:
            return ex.fetch_ohlcv(symbol, timeframe, limit=limit)


# ============================================================
# GOSTERGE MOTORU — ROL DAGILIMI
# ============================================================
class IndicatorEngine:
    """Her TF'de sadece o TF'ye atanmis gostergeleri hesaplar."""

    @staticmethod
    def fetch(symbol, timeframe, limit=OHLCV_LIMIT):
        ohlcv = Exchange.ohlcv(symbol, timeframe, limit=limit)
        return pd.DataFrame(
            ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    @staticmethod
    def _rma(series, period):
        return series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    @classmethod
    def calc_macd(cls, df):
        close = df['close']
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        return df

    @classmethod
    def calc_rsi(cls, df):
        close = df['close']
        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        avg_gain = cls._rma(gain, 14)
        avg_loss = cls._rma(loss, 14)
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = rsi.where(avg_loss != 0, 100.0)
        rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
        df['rsi'] = rsi
        return df

    @staticmethod
    def calc_stochrsi(df):
        # NOT: bu fonksiyon df['rsi'] kolonunu okur -> calc_rsi() ONCE cagrilmali.
        # v1'deki hata tam olarak buydu: 15m analizinde calc_rsi() hic cagrilmiyordu.
        min_rsi = df['rsi'].rolling(window=14).min()
        max_rsi = df['rsi'].rolling(window=14).max()
        rng = max_rsi - min_rsi
        stochrsi = ((df['rsi'] - min_rsi) / rng).where(rng != 0, 0.5)
        df['stochrsi_k'] = stochrsi.rolling(window=3).mean()
        df['stochrsi_d'] = df['stochrsi_k'].rolling(window=3).mean()
        return df

    @staticmethod
    def calc_kdj(df):
        close, high, low = df['close'], df['high'], df['low']
        ll = low.rolling(window=9).min()
        hh = high.rolling(window=9).max()
        rng = hh - ll
        rsv = (((close - ll) / rng) * 100).where(rng != 0, 50.0)
        df['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
        return df

    @staticmethod
    def calc_williams(df):
        close, high, low = df['close'], df['high'], df['low']
        hh = high.rolling(window=14).max()
        ll = low.rolling(window=14).min()
        rng = hh - ll
        df['williams_r'] = (((hh - close) / rng) * -100).where(rng != 0, -50.0)
        return df

    @classmethod
    def _last_row(cls, df, closed_only):
        idx = -2 if (closed_only and len(df) >= 2) else -1
        return df.iloc[idx]

    # ===== 4H: TREND + MOMENTUM =====
    @classmethod
    def analyze_4h(cls, symbol, closed_only=True):
        try:
            df = cls.fetch(symbol, '4h')
        except Exception as e:
            return {'error': f"{type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = cls.calc_macd(df)
        df = cls.calc_rsi(df)
        last = cls._last_row(df, closed_only)
        if any(pd.isna(last[c]) for c in ('macd', 'macd_signal', 'rsi')):
            return {'error': 'gosterge degeri NaN'}

        macd_ok = bool((last['macd'] > last['macd_signal']) and (last['macd'] > 0))
        rsi_ok = bool(last['rsi'] > 50)

        return {
            'score': sum([macd_ok, rsi_ok]),
            'role': 'Trend Filtresi + Momentum Onayi',
            'items': [
                ('MACD (trend)', macd_ok, f"{last['macd']:.6f} / sig {last['macd_signal']:.6f}"),
                ('RSI (momentum)', rsi_ok, f"{last['rsi']:.1f}"),
            ],
        }

    # ===== 1H: DONUS + YAPI =====
    @classmethod
    def analyze_1h(cls, symbol, closed_only=True):
        try:
            df = cls.fetch(symbol, '1h')
        except Exception as e:
            return {'error': f"{type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = cls.calc_williams(df)
        df = cls.calc_macd(df)
        last = cls._last_row(df, closed_only)
        if any(pd.isna(last[c]) for c in ('williams_r', 'macd', 'macd_signal')):
            return {'error': 'gosterge degeri NaN'}

        will_ok = bool(last['williams_r'] > -50)
        macd_ok = bool(last['macd'] > last['macd_signal'])

        return {
            'score': sum([will_ok, macd_ok]),
            'role': 'Orta Vadeli Donus + Yapi Uyumu',
            'items': [
                ('Williams%R (donus)', will_ok, f"{last['williams_r']:.1f}"),
                ('MACD (yapi)', macd_ok, f"{last['macd']:.6f} / sig {last['macd_signal']:.6f}"),
            ],
        }

    # ===== 15m: TETIKLEYICI + FILTRE =====
    @classmethod
    def analyze_15m(cls, symbol, closed_only=True):
        try:
            df = cls.fetch(symbol, '15m')
        except Exception as e:
            return {'error': f"{type(e).__name__}: {e}"}
        if df is None or len(df) < MIN_BARS:
            return {'error': f"yetersiz veri ({0 if df is None else len(df)} mum)"}

        df = cls.calc_kdj(df)
        df = cls.calc_rsi(df)          # <-- v1'de eksikti, StochRSI buna bagimli
        df = cls.calc_stochrsi(df)
        last = cls._last_row(df, closed_only)
        needed = ('kdj_k', 'kdj_d', 'kdj_j', 'stochrsi_k', 'stochrsi_d')
        if any(pd.isna(last[c]) for c in needed):
            return {'error': 'gosterge degeri NaN'}

        kdj_ok = bool((last['kdj_k'] > last['kdj_d']) and (last['kdj_j'] > 20))
        stoch_ok = bool((last['stochrsi_k'] > last['stochrsi_d']) and (last['stochrsi_k'] > 0.20))

        return {
            'score': sum([kdj_ok, stoch_ok]),
            'role': 'Giris Tetikleyicisi + Hassas Filtre',
            'items': [
                ('KDJ (tetik)', kdj_ok,
                 f"K {last['kdj_k']:.1f} / D {last['kdj_d']:.1f} / J {last['kdj_j']:.1f}"),
                ('StochRSI (filtre)', stoch_ok,
                 f"K {last['stochrsi_k']:.3f} / D {last['stochrsi_d']:.3f}"),
            ],
        }


# ============================================================
# UYGULAMA
# ============================================================
class AppRoleBased:

    def __init__(self, root):
        self.root = root
        self.root.title("UYGULAMA 2 — Rol Dagilimi Scanner  |  4H Trend · 1H Donus · 15m Tetik")
        self.root.geometry("1320x880")
        self.root.configure(bg=C_BG)

        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._closing = False

        self.last_results = {}
        self.ticker_map = {}
        self.portfolio = self.load_portfolio()

        self._build_settings_vars()
        self._build_style()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------------------------------------------------------
    def _build_settings_vars(self):
        self.var_interval = tk.StringVar(value='10')
        self.var_threshold = tk.StringVar(value='5')
        self.var_minvol = tk.StringVar(value='5')
        self.var_topn = tk.StringVar(value='0')
        self.var_closed = tk.BooleanVar(value=True)

        self.cfg = {}
        for var in (self.var_interval, self.var_threshold,
                    self.var_minvol, self.var_topn, self.var_closed):
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

        self.cfg = {
            'interval': as_int(self.var_interval, 10, 1, 1440),
            'threshold': as_int(self.var_threshold, 5, 1, MAX_SCORE),
            'minvol': as_int(self.var_minvol, 5, 0, 100000),
            'topn': as_int(self.var_topn, 0, 0, 5000),
            'closed': bool(self.var_closed.get()),
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

        st.configure('Treeview',
                     background='#14141f', fieldbackground='#14141f',
                     foreground=C_TEXT, rowheight=26, borderwidth=0,
                     font=('Segoe UI', 10))
        st.configure('Treeview.Heading',
                     background='#22223a', foreground='#a9b8cc',
                     font=('Segoe UI', 9, 'bold'), relief='flat', padding=6)
        st.map('Treeview.Heading', background=[('active', '#2e2e4d')])
        st.map('Treeview',
               background=[('selected', '#2d6cdf')],
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

    # --------------------------------------------------------
    # SEKME 1 — TARAMA
    # --------------------------------------------------------
    def _build_scan_tab(self):
        self.tab_scan.rowconfigure(2, weight=1)
        self.tab_scan.columnconfigure(0, weight=1)

        # ---- kontrol paneli
        ctrl = tk.Frame(self.tab_scan, bg=C_PANEL)
        ctrl.grid(row=0, column=0, sticky='ew', pady=(0, 8))

        inner = tk.Frame(ctrl, bg=C_PANEL)
        inner.pack(fill='x', padx=14, pady=10)

        def field(col, label, var, width=6, hint=''):
            box = tk.Frame(inner, bg=C_PANEL)
            box.grid(row=0, column=col, padx=(0, 18), sticky='w')
            self._label(box, label, bold=True).pack(anchor='w')
            e = ttk.Entry(box, textvariable=var, width=width, style='Dark.TEntry',
                          font=('Segoe UI', 10))
            e.pack(anchor='w', pady=(2, 0))
            if hint:
                self._label(box, hint, fg='#5f6b7a', size=8).pack(anchor='w')
            return e

        field(0, "Tarama araligi", self.var_interval, 6, "dakika")
        field(1, f"Min skor (1-{MAX_SCORE})", self.var_threshold, 5, f"/ {MAX_SCORE}")
        field(2, "Min 24s hacim", self.var_minvol, 7, "milyon USDT")
        field(3, "Ilk N coin", self.var_topn, 6, "0 = sinirsiz")

        opt = tk.Frame(inner, bg=C_PANEL)
        opt.grid(row=0, column=4, padx=(0, 20), sticky='w')
        self._label(opt, "Secenek", bold=True).pack(anchor='w')
        ttk.Checkbutton(opt, text="Sadece kapanmis mum", variable=self.var_closed,
                        style='Dark.TCheckbutton').pack(anchor='w', pady=(4, 0))

        btns = tk.Frame(inner, bg=C_PANEL)
        btns.grid(row=0, column=5, sticky='w')
        self._label(btns, " ", bold=True).pack(anchor='w')
        row = tk.Frame(btns, bg=C_PANEL)
        row.pack()
        self.btn_start = self._button(row, "BASLAT", C_ACCENT, self.start_scan, 11)
        self.btn_start.pack(side='left', padx=(0, 6))
        self.btn_stop = self._button(row, "DURDUR", C_DANGER, self.stop_scan, 11)
        self.btn_stop.pack(side='left')
        self.btn_stop.config(state='disabled')

        add = tk.Frame(inner, bg=C_PANEL)
        add.grid(row=0, column=6, sticky='e', padx=(20, 0))
        self._label(add, " ", bold=True).pack(anchor='e')
        self.btn_add = self._button(add, "PORTFOYE EKLE", C_INFO, self.add_to_portfolio, 16)
        self.btn_add.pack(anchor='e')

        status = tk.Frame(inner, bg=C_PANEL)
        status.grid(row=0, column=7, sticky='e', padx=(20, 0))
        inner.columnconfigure(7, weight=1)
        self._label(status, " ", bold=True).pack(anchor='e')
        self.lbl_status = tk.Label(status, text="● Bekliyor", bg=C_PANEL, fg=C_MUTED,
                                   font=('Segoe UI', 10, 'bold'))
        self.lbl_status.pack(anchor='e')

        # ---- ilerleme
        prog = tk.Frame(self.tab_scan, bg=C_BG)
        prog.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        prog.columnconfigure(0, weight=1)

        self.var_progress = tk.DoubleVar(value=0.0)
        self.pbar = ttk.Progressbar(prog, variable=self.var_progress, maximum=100.0,
                                    style='Dark.Horizontal.TProgressbar')
        self.pbar.grid(row=0, column=0, sticky='ew', padx=(0, 12))
        self.lbl_progress = tk.Label(prog, text="0 / 0   ·   kalan --:--   ·   0 sinyal",
                                     bg=C_BG, fg=C_MUTED, font=('Consolas', 9))
        self.lbl_progress.grid(row=0, column=1, sticky='e')

        # ---- log + tablo: dikeyde surukleyerek yeniden boyutlandirilabilir,
        #      log basligindaki dugmeyle acilir/kapanir (PanedWindow, sabit olcu yok)
        self.paned = tk.PanedWindow(self.tab_scan, orient='vertical', bg=C_BG,
                                    sashwidth=6, sashrelief='flat', bd=0,
                                    sashpad=1, opaqueresize=True)
        self.paned.grid(row=2, column=0, sticky='nsew')

        # -- log paneli
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

        self.txt_log.tag_configure('info', foreground=C_MUTED)
        self.txt_log.tag_configure('ok', foreground=C_ACCENT)
        self.txt_log.tag_configure('sig', foreground='#7bed9f')
        self.txt_log.tag_configure('warn', foreground=C_WARN)
        self.txt_log.tag_configure('err', foreground=C_DANGER)
        self.txt_log.config(state='disabled')

        self.paned.add(self.logf, minsize=40, height=170, stretch='never')

        # -- tablo paneli
        self.scan_table_wrap = tk.Frame(self.paned, bg=C_BG)
        wrap = self.scan_table_wrap
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        cols = ('coin', 'price', 'vol', 's4h', 's1h', 's15m', 'total', 'signal')
        heads = {
            'coin': ('Coin', 130), 'price': ('Fiyat', 110), 'vol': ('24s Hacim', 100),
            's4h': ('4H', 80), 's1h': ('1H', 80), 's15m': ('15m', 80),
            'total': ('Toplam', 90), 'signal': ('Sinyal', 120),
        }
        self.tree_scan = ttk.Treeview(wrap, columns=cols, show='headings', selectmode='extended')
        for c in cols:
            text, w = heads[c]
            self.tree_scan.heading(c, text=text,
                                   command=lambda cc=c: self._sort_tree(self.tree_scan, cc, False))
            self.tree_scan.column(c, width=w, anchor='center',
                                  stretch=(c in ('coin', 'signal')))
        self.tree_scan.grid(row=0, column=0, sticky='nsew')

        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.tree_scan.yview)
        self.tree_scan.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky='ns')

        self.tree_scan.tag_configure('full', background=ROW_FULL)
        self.tree_scan.tag_configure('strong', background=ROW_STRONG)
        self.tree_scan.tag_configure('medium', background=ROW_MED)
        self.tree_scan.bind('<Double-1>', self.show_detail)

        self.paned.add(wrap, minsize=150, stretch='always')

        self._log_visible = True

    def toggle_log(self):
        """Log panelini acar/kapatir; tablo bosalan alani kaplar."""
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
    # SEKME 2 — PORTFOY
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

        cols = ('coin', 'date', 'total', 'entry', 'now', 'pnl', 'note')
        heads = {
            'coin': ('Coin', 120), 'date': ('Eklenme', 140), 'total': ('Skor', 80),
            'entry': ('Giris Fiyati', 120), 'now': ('Guncel', 120),
            'pnl': ('Degisim', 100), 'note': ('Not', 420),
        }
        self.tree_portfolio = ttk.Treeview(wrap, columns=cols, show='headings')
        for c in cols:
            text, w = heads[c]
            self.tree_portfolio.heading(
                c, text=text,
                command=lambda cc=c: self._sort_tree(self.tree_portfolio, cc, False))
            self.tree_portfolio.column(c, width=w, stretch=(c == 'note'),
                                       anchor='w' if c == 'note' else 'center')
        self.tree_portfolio.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.tree_portfolio.yview)
        self.tree_portfolio.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky='ns')

        self.tree_portfolio.tag_configure('up', foreground='#7bed9f')
        self.tree_portfolio.tag_configure('down', foreground='#ff7675')
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
    # THREAD -> UI KOPRUSU
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

    def set_progress(self, done, total, signals, eta=None):
        def apply():
            pct = (done / total * 100.0) if total else 0.0
            self.var_progress.set(pct)
            self.lbl_progress.config(
                text=f"{done} / {total}   ·   kalan {fmt_eta(eta)}   ·   {signals} sinyal")
        self._ui(apply)

    # --------------------------------------------------------
    # TARAMA KONTROLU
    # --------------------------------------------------------
    def start_scan(self):
        if self.running:
            return
        if self.thread is not None and self.thread.is_alive():
            messagebox.showinfo("Bekleyin",
                                "Onceki tarama hala kapaniyor. Birkac saniye sonra tekrar deneyin.")
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
    # SEMBOL LISTESI
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
            tickers = Exchange.tickers()
            self.ticker_map = tickers
        except Exception as e:
            self.log(f"Hacim verisi alinamadi, filtre atlaniyor: {type(e).__name__}: {e}", 'warn')
            return sorted(candidates)

        min_vol = cfg['minvol'] * 1_000_000
        scored = []
        for sym in candidates:
            t = tickers.get(sym) or {}
            qv = t.get('quoteVolume') or 0
            if qv >= min_vol:
                scored.append((qv, sym))
        scored.sort(reverse=True)

        if cfg['topn'] > 0:
            scored = scored[:cfg['topn']]
        return [s for _, s in scored]

    # --------------------------------------------------------
    # TARAMA DONGUSU
    # --------------------------------------------------------
    def _scan_loop(self):
        while self.running:
            cfg = dict(self.cfg)

            self.log("Tarama basliyor...", 'ok')
            self.set_progress(0, 0, 0)
            symbols = self.get_symbols(cfg)
            total = len(symbols)

            if total == 0:
                self.log("Tarancak coin bulunamadi (hacim filtresi cok yuksek olabilir).", 'warn')
            else:
                self.log(f"{total} coin taranacak  ·  min hacim {cfg['minvol']}M$  ·  "
                         f"mum: {'kapanmis' if cfg['closed'] else 'canli'}", 'info')

            self._ui(lambda: self.tree_scan.delete(*self.tree_scan.get_children()))
            self.last_results.clear()

            signal_count = 0
            err_count = 0
            err_samples = []
            t0 = time.time()

            for idx, symbol in enumerate(symbols, start=1):
                if not self.running:
                    self.log("Tarama yarida kesildi.", 'warn')
                    break

                res4h = IndicatorEngine.analyze_4h(symbol, closed_only=cfg['closed'])
                res1h = IndicatorEngine.analyze_1h(symbol, closed_only=cfg['closed'])
                res15m = IndicatorEngine.analyze_15m(symbol, closed_only=cfg['closed'])

                elapsed = time.time() - t0
                eta = (elapsed / idx) * (total - idx) if idx else None
                self.set_progress(idx, total, signal_count, eta)

                errs = [(tf, r['error']) for tf, r in
                        (('4h', res4h), ('1h', res1h), ('15m', res15m)) if 'error' in r]
                if errs:
                    err_count += 1
                    if len(err_samples) < 5:
                        tf, msg = errs[0]
                        err_samples.append(f"{symbol} -> {tf}: {msg}")
                    continue

                scores = {'4h': res4h['score'], '1h': res1h['score'], '15m': res15m['score']}
                total_score = scores['4h'] + scores['1h'] + scores['15m']
                self.last_results[symbol] = {
                    'scores': scores, 'total': total_score,
                    'detail': {'4h': res4h, '1h': res1h, '15m': res15m},
                }

                if total_score >= cfg['threshold']:
                    signal_count += 1
                    if total_score == MAX_SCORE:
                        tag, txt = 'full', "TAM UYUM"
                    elif total_score >= MAX_SCORE - 1:
                        tag, txt = 'strong', "GUCLU"
                    else:
                        tag, txt = 'medium', "IZLE"

                    t = self.ticker_map.get(symbol) or {}
                    row = (symbol, fmt_price(t.get('last')), fmt_vol(t.get('quoteVolume')),
                           f"{scores['4h']}/2", f"{scores['1h']}/2", f"{scores['15m']}/2",
                           f"{total_score}/{MAX_SCORE}", txt)
                    self._ui(self._insert_scan_row, row, tag)
                    self.log(f"SINYAL  {symbol}  ·  {total_score}/{MAX_SCORE}  ({txt})", 'sig')

            if self.running:
                took = int(time.time() - t0)
                self.log(f"Tarama tamamlandi  ·  {signal_count} sinyal  ·  "
                         f"{err_count} coin atlandi  ·  {fmt_eta(took)} surdu", 'ok')
                for s in err_samples:
                    self.log(f"  atlandi: {s}", 'err')
                if err_count and err_count == len(symbols):
                    self.log("TUM coinler hata verdi — internet/borsa erisimini kontrol edin.", 'err')
                self.set_status(
                    f"{datetime.now().strftime('%H:%M:%S')} · {signal_count} sinyal", C_ACCENT)
                self.set_progress(len(symbols), len(symbols), signal_count, 0)

                wait = cfg['interval'] * 60
                self.log(f"Sonraki tarama {cfg['interval']} dakika sonra.", 'info')
                self._stop_event.wait(wait)

        self._ui(lambda: (self.btn_start.config(state='normal'),
                          self.btn_stop.config(state='disabled')))

    def _insert_scan_row(self, values, tag):
        self.tree_scan.insert('', 'end', values=values, tags=(tag,))

    # --------------------------------------------------------
    # DETAY PENCERESI
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
        win.title(f"{symbol} — gosterge detayi")
        win.configure(bg=C_BG)
        win.geometry("520x420")
        win.transient(self.root)

        tk.Label(win, text=symbol, bg=C_BG, fg=C_ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=18, pady=(14, 2))
        tk.Label(win, text=f"Toplam skor: {data['total']}/{MAX_SCORE}",
                 bg=C_BG, fg=C_TEXT, font=('Segoe UI', 10)).pack(anchor='w', padx=18)

        box = tk.Text(win, bg='#0c0c14', fg=C_TEXT, font=('Consolas', 10),
                      relief='flat', padx=12, pady=10, wrap='none')
        box.pack(fill='both', expand=True, padx=14, pady=12)
        box.tag_configure('h', foreground=C_INFO)
        box.tag_configure('role', foreground=C_MUTED)
        box.tag_configure('ok', foreground='#7bed9f')
        box.tag_configure('no', foreground='#ff7675')

        for tf in ('4h', '1h', '15m'):
            res = data['detail'].get(tf)
            if not res:
                continue
            box.insert(tk.END, f"\n{tf.upper():>4}  ({res['score']}/2)\n", 'h')
            box.insert(tk.END, f"   rol: {res['role']}\n", 'role')
            for name, ok, val in res['items']:
                box.insert(tk.END, f"   {'+' if ok else '-'}  {name:<20} {val}\n",
                           'ok' if ok else 'no')
        box.config(state='disabled')

        self._button(win, "KAPAT", C_PANEL2, win.destroy, 10).pack(pady=(0, 14))

    # --------------------------------------------------------
    @staticmethod
    def _sort_tree(tree, col, reverse):
        def key(value):
            s = str(value).replace('%', '').replace(',', '').strip()
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
        tree.heading(col, command=lambda: AppRoleBased._sort_tree(tree, col, not reverse))

    # --------------------------------------------------------
    # PORTFOY
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
        for item in self.portfolio:
            coin = item.get('coin', '')
            entry = item.get('entry_price')
            t = self.ticker_map.get(coin) or {}
            now = t.get('last')

            pnl_txt, tag = '-', ''
            if entry and now:
                try:
                    pct = (float(now) - float(entry)) / float(entry) * 100.0
                    pnl_txt = f"{pct:+.2f}%"
                    tag = 'up' if pct >= 0 else 'down'
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

            self.tree_portfolio.insert('', 'end', tags=(tag,) if tag else (), values=(
                coin, item.get('date', ''), f"{item.get('score', 0)}/{MAX_SCORE}",
                fmt_price(entry), fmt_price(now), pnl_txt, item.get('note', '')))

        self.lbl_pf_info.config(text=f"{len(self.portfolio)} kayit")

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
            values = self.tree_scan.item(item_id, 'values')
            coin = values[0]
            try:
                total = int(str(values[6]).split('/')[0])
            except (ValueError, IndexError):
                total = 0
            if any(p.get('coin') == coin for p in self.portfolio):
                self.log(f"{coin} zaten portfoyde.", 'warn')
                continue

            t = self.ticker_map.get(coin) or {}
            self.portfolio.append({
                'coin': coin,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'score': total,
                'entry_price': t.get('last'),
                'note': '',
            })
            added += 1
            self.log(f"{coin} portfoye eklendi  ·  {total}/{MAX_SCORE}", 'ok')

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
        self.log(f"{len(coins)} kayit portfoyden silindi.", 'warn')

    def _on_pf_select(self, _event=None):
        sel = self.tree_portfolio.selection()
        if not sel:
            return
        values = self.tree_portfolio.item(sel[0], 'values')
        self.entry_note.delete(0, tk.END)
        self.entry_note.insert(0, values[6])

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
        app = AppRoleBased(root)
        root.mainloop()
    except Exception as exc:
        try:
            err = tk.Tk()
            err.withdraw()
            messagebox.showerror("Baslatma hatasi",
                                 f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
