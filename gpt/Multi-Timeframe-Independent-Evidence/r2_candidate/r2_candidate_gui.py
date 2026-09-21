from __future__ import annotations

"""Desktop GUI for the frozen r2 Binance Spot signal scanner.

The signal, indicator, universe, cooldown and Binance candle logic lives in
``r2_candidate_scanner.py``.  This module only orchestrates those public
functions in background threads and presents their results.
"""

import csv
import json
import queue
import sys
import tempfile
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import r2_candidate_scanner as scanner


APP_TITLE = "Frozen r2 Crypto Scanner"
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "gui_data"
TRACK_FILE = DATA_DIR / "tracked_signals.json"

COLORS = {
    "bg": "#0b1120",
    "panel": "#111827",
    "panel_2": "#172033",
    "border": "#273449",
    "text": "#e5edf8",
    "muted": "#8ea0b8",
    "accent": "#38bdf8",
    "accent_dark": "#075985",
    "green": "#34d399",
    "red": "#fb7185",
    "amber": "#fbbf24",
    "selection": "#1d4ed8",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def fmt_price(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    if abs(number) >= 1:
        return f"{number:,.6f}".rstrip("0").rstrip(".")
    return f"{number:.10f}".rstrip("0").rstrip(".")


def fmt_num(value: Any, digits: int = 2, suffix: str = "") -> str:
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def fmt_duration(start_iso: str) -> str:
    try:
        elapsed = datetime.now(timezone.utc) - parse_time(start_iso)
    except (TypeError, ValueError):
        return "—"
    total_minutes = max(0, int(elapsed.total_seconds() // 60))
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}g {hours}s"
    if hours:
        return f"{hours}s {minutes}dk"
    return f"{minutes}dk"


class TrackingStore:
    """Small persistent JSON store; signal keys are symbol + decision time."""

    def __init__(self, path: Path = TRACK_FILE):
        self.path = Path(path)
        self.records: dict[str, dict[str, Any]] = {}
        self.load()

    @staticmethod
    def key(symbol: str, signal_time: str) -> str:
        return f"{str(symbol).upper()}|{signal_time}"

    def load(self) -> None:
        self.records = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("tracking JSON root must be a list")
            for item in raw:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol", "")).upper()
                signal_time = str(item.get("signal_time", ""))
                if symbol and signal_time:
                    self.records[self.key(symbol, signal_time)] = item
        except Exception:
            broken = self.path.with_name(self.path.stem + "_broken.json")
            try:
                self.path.replace(broken)
            except OSError:
                pass
            self.records = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = list(self.records.values())
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self.path)

    def add_signal(self, signal: dict[str, Any]) -> bool:
        symbol = str(signal["symbol"]).upper()
        signal_time = str(signal["decision_time_utc"])
        key = self.key(symbol, signal_time)
        if key in self.records:
            return False
        signal_price = float(signal["last_closed_15m_price"])
        self.records[key] = {
            "symbol": symbol,
            "signal_time": signal_time,
            "signal_price": signal_price,
            "added_time": utc_now_iso(),
            "current_price": signal_price,
            "high_price": signal_price,
            "low_price": signal_price,
            "change_pct": 0.0,
            "max_up_pct": 0.0,
            "max_down_pct": 0.0,
            "status": "Takipte",
        }
        self.save()
        return True

    def apply_prices(self, prices: dict[str, float]) -> int:
        updated = 0
        for rec in self.records.values():
            symbol = str(rec["symbol"])
            if symbol not in prices:
                continue
            price = float(prices[symbol])
            signal_price = float(rec["signal_price"])
            high_price = max(float(rec.get("high_price", signal_price)), price)
            low_price = min(float(rec.get("low_price", signal_price)), price)
            change_pct = (price / signal_price - 1.0) * 100.0
            max_up_pct = (high_price / signal_price - 1.0) * 100.0
            max_down_pct = (low_price / signal_price - 1.0) * 100.0
            rec.update({
                "current_price": price,
                "high_price": high_price,
                "low_price": low_price,
                "change_pct": change_pct,
                "max_up_pct": max_up_pct,
                "max_down_pct": max_down_pct,
                "last_update": utc_now_iso(),
                "status": "Pozitif" if change_pct > 0 else "Negatif" if change_pct < 0 else "Nötr",
            })
            updated += 1
        if updated:
            self.save()
        return updated

    def remove(self, keys: list[str]) -> None:
        for key in keys:
            self.records.pop(key, None)
        self.save()

    def clear(self) -> None:
        self.records.clear()
        self.save()


class R2ScannerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1480x900")
        self.root.minsize(1120, 720)
        self.root.configure(bg=COLORS["bg"])

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.store = TrackingStore()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.stop_event = threading.Event()
        self.scan_thread: threading.Thread | None = None
        self.price_thread: threading.Thread | None = None
        self.signal_by_iid: dict[str, dict[str, Any]] = {}
        self._closing = False

        self.status_var = tk.StringVar(value="Hazır")
        self.scan_count_var = tk.StringVar(value="0")
        self.signal_count_var = tk.StringVar(value="0")
        self.error_count_var = tk.StringVar(value="0")
        self.total_count_var = tk.StringVar(value="0")
        self.progress_var = tk.DoubleVar(value=0)
        self.workers_var = tk.IntVar(value=scanner.DEFAULT_WORKERS)
        self.track_status_var = tk.StringVar(value="Takip listesi hazır")

        self._configure_style()
        self._build_header()
        self._build_tabs()
        self._refresh_tracking_table()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_events)
        self.root.after(60_000, self._refresh_tracking_durations)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Panel2.TFrame", background=COLORS["panel_2"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
        style.configure("StatTitle.TLabel", background=COLORS["panel_2"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("StatValue.TLabel", background=COLORS["panel_2"], foreground=COLORS["text"], font=("Segoe UI", 15, "bold"))
        style.configure("Status.TLabel", background=COLORS["accent_dark"], foreground="#e0f2fe", padding=(12, 6), font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["panel"], foreground=COLORS["muted"], padding=(18, 10), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", COLORS["panel_2"])], foreground=[("selected", COLORS["accent"])])
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=30, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=COLORS["panel_2"], foreground=COLORS["text"], relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", COLORS["selection"])], foreground=[("selected", "#ffffff")])
        style.configure("Accent.TButton", background=COLORS["accent_dark"], foreground="#ffffff", padding=(14, 9), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#0369a1"), ("disabled", COLORS["border"])])
        style.configure("Danger.TButton", background="#881337", foreground="#ffffff", padding=(14, 9), font=("Segoe UI", 10, "bold"))
        style.map("Danger.TButton", background=[("active", "#be123c"), ("disabled", COLORS["border"])])
        style.configure("Secondary.TButton", background=COLORS["panel_2"], foreground=COLORS["text"], padding=(12, 8), font=("Segoe UI", 9, "bold"))
        style.map("Secondary.TButton", background=[("active", COLORS["border"])])
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["panel_2"], background=COLORS["accent"], bordercolor=COLORS["panel_2"])
        style.configure("TSpinbox", fieldbackground=COLORS["panel_2"], foreground=COLORS["text"], arrowcolor=COLORS["accent"])

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 12))
        header.pack(fill="x")
        left = ttk.Frame(header, style="App.TFrame")
        left.pack(side="left")
        ttk.Label(left, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text=f"{scanner.CANDIDATE_VERSION} · Binance Spot/USDT · Yalnız sinyal ve takip",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="right", padx=(12, 0))

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.scan_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=2)
        self.track_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=2)
        self.notebook.add(self.scan_tab, text="  SİNYAL TARAYICI  ")
        self.notebook.add(self.track_tab, text="  TAKİP SİSTEMİ  ")
        self._build_scanner_tab()
        self._build_tracking_tab()

    def _build_scanner_tab(self) -> None:
        controls = ttk.Frame(self.scan_tab, style="Panel.TFrame", padding=16)
        controls.pack(fill="x", pady=(10, 10))

        button_box = ttk.Frame(controls, style="Panel.TFrame")
        button_box.pack(side="left", fill="y")
        self.start_button = ttk.Button(button_box, text="Taramayı Başlat", style="Accent.TButton", command=self.start_scan)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(button_box, text="Durdur", style="Danger.TButton", command=self.stop_scan, state="disabled")
        self.stop_button.pack(side="left")

        worker_box = ttk.Frame(controls, style="Panel.TFrame")
        worker_box.pack(side="left", padx=24)
        ttk.Label(worker_box, text="Workers", style="PanelTitle.TLabel").pack(anchor="w")
        self.workers_spin = ttk.Spinbox(worker_box, from_=1, to=32, width=6, textvariable=self.workers_var)
        self.workers_spin.pack(anchor="w", pady=(4, 0))

        stats = ttk.Frame(controls, style="Panel.TFrame")
        stats.pack(side="right")
        self._stat_card(stats, "Taranan", self.scan_count_var).pack(side="left", padx=5)
        self._stat_card(stats, "Toplam Coin", self.total_count_var).pack(side="left", padx=5)
        self._stat_card(stats, "Sinyal", self.signal_count_var).pack(side="left", padx=5)
        self._stat_card(stats, "Hata", self.error_count_var).pack(side="left", padx=5)

        progress_frame = ttk.Frame(self.scan_tab, style="Panel.TFrame", padding=(16, 10))
        progress_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(progress_frame, text="Tarama İlerlemesi", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 7))
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")

        signal_panel = ttk.Frame(self.scan_tab, style="Panel.TFrame", padding=14)
        signal_panel.pack(fill="both", expand=True, pady=(0, 10))
        signal_header = ttk.Frame(signal_panel, style="Panel.TFrame")
        signal_header.pack(fill="x", pady=(0, 10))
        ttk.Label(signal_header, text="Bulunan Sinyaller", style="PanelTitle.TLabel").pack(side="left")
        ttk.Button(signal_header, text="Takibe Al", style="Accent.TButton", command=self.follow_selected_signal).pack(side="right", padx=(8, 0))
        ttk.Button(signal_header, text="Detay", style="Secondary.TButton", command=self.show_signal_detail).pack(side="right")

        signal_table_frame = ttk.Frame(signal_panel, style="Panel.TFrame")
        signal_table_frame.pack(fill="both", expand=True)
        signal_columns = (
            "symbol", "signal_time", "price", "entry_time", "lead_gap", "m15_motion",
            "h4_motion", "btc_tsi", "btc_bb", "coin_bb", "dd48",
        )
        self.signal_tree = ttk.Treeview(signal_table_frame, columns=signal_columns, show="headings", height=9)
        signal_specs = {
            "symbol": ("Coin", 105), "signal_time": ("Sinyal Zamanı (UTC)", 190),
            "price": ("Sinyal Fiyatı", 115), "entry_time": ("En Erken Giriş (UTC)", 190),
            "lead_gap": ("Lead Gap", 80), "m15_motion": ("15M Motion", 90),
            "h4_motion": ("4H Motion", 85), "btc_tsi": ("BTC TSI", 90),
            "btc_bb": ("BTC 4H BB", 95), "coin_bb": ("Coin 4H BB", 100),
            "dd48": ("48H Drawdown", 110),
        }
        self._configure_tree(self.signal_tree, signal_specs)
        signal_y = ttk.Scrollbar(signal_table_frame, orient="vertical", command=self.signal_tree.yview)
        signal_x = ttk.Scrollbar(signal_table_frame, orient="horizontal", command=self.signal_tree.xview)
        self.signal_tree.configure(yscrollcommand=signal_y.set, xscrollcommand=signal_x.set)
        self.signal_tree.grid(row=0, column=0, sticky="nsew")
        signal_y.grid(row=0, column=1, sticky="ns")
        signal_x.grid(row=1, column=0, sticky="ew")
        signal_table_frame.rowconfigure(0, weight=1)
        signal_table_frame.columnconfigure(0, weight=1)
        self.signal_tree.bind("<Double-1>", lambda _event: self.show_signal_detail())

        log_panel = ttk.Frame(self.scan_tab, style="Panel.TFrame", padding=14)
        log_panel.pack(fill="both", expand=True)
        log_header = ttk.Frame(log_panel, style="Panel.TFrame")
        log_header.pack(fill="x", pady=(0, 8))
        ttk.Label(log_header, text="Log Akışı", style="PanelTitle.TLabel").pack(side="left")
        ttk.Button(log_header, text="Log Kaydet", style="Secondary.TButton", command=self.save_log).pack(side="right", padx=(8, 0))
        ttk.Button(log_header, text="Log Temizle", style="Secondary.TButton", command=self.clear_log).pack(side="right")
        log_frame = ttk.Frame(log_panel, style="Panel.TFrame")
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame, height=8, bg="#070b14", fg=COLORS["text"], insertbackground=COLORS["text"],
            selectbackground=COLORS["selection"], relief="flat", padx=10, pady=8,
            font=("Cascadia Mono", 9), wrap="word", state="disabled",
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        self._append_log("Arayüz hazır. Tarama başlatılmayı bekliyor.")

    def _build_tracking_tab(self) -> None:
        controls = ttk.Frame(self.track_tab, style="Panel.TFrame", padding=16)
        controls.pack(fill="x", pady=(10, 10))
        self.update_all_button = ttk.Button(controls, text="Fiyatları Güncelle", style="Accent.TButton", command=self.update_all_prices)
        self.update_all_button.pack(side="left", padx=(0, 8))
        self.update_selected_button = ttk.Button(controls, text="Seçileni Güncelle", style="Secondary.TButton", command=self.update_selected_price)
        self.update_selected_button.pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Takipten Çıkar", style="Secondary.TButton", command=self.remove_selected_tracking).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Tümünü Temizle", style="Danger.TButton", command=self.clear_tracking).pack(side="left")
        ttk.Label(controls, textvariable=self.track_status_var, style="PanelTitle.TLabel").pack(side="right")

        panel = ttk.Frame(self.track_tab, style="Panel.TFrame", padding=14)
        panel.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(panel, text="Takip Edilen Sinyaller", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 10))
        table_frame = ttk.Frame(panel, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        track_columns = (
            "symbol", "signal_time", "signal_price", "current_price", "change_pct",
            "high_price", "low_price", "max_up_pct", "max_down_pct", "duration", "status",
        )
        self.track_tree = ttk.Treeview(table_frame, columns=track_columns, show="headings")
        track_specs = {
            "symbol": ("Symbol", 100), "signal_time": ("Sinyal Zamanı (UTC)", 190),
            "signal_price": ("Sinyal Fiyatı", 110), "current_price": ("Güncel Fiyat", 110),
            "change_pct": ("Değişim %", 90), "high_price": ("En Yüksek", 105),
            "low_price": ("En Düşük", 105), "max_up_pct": ("Maks. Yükseliş %", 115),
            "max_down_pct": ("Maks. Düşüş %", 115), "duration": ("Takip Süresi", 100),
            "status": ("Durum", 90),
        }
        self._configure_tree(self.track_tree, track_specs)
        self.track_tree.tag_configure("positive", foreground=COLORS["green"])
        self.track_tree.tag_configure("negative", foreground=COLORS["red"])
        self.track_tree.tag_configure("neutral", foreground=COLORS["text"])
        track_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.track_tree.yview)
        track_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.track_tree.xview)
        self.track_tree.configure(yscrollcommand=track_y.set, xscrollcommand=track_x.set)
        self.track_tree.grid(row=0, column=0, sticky="nsew")
        track_y.grid(row=0, column=1, sticky="ns")
        track_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def _stat_card(self, parent: ttk.Frame, title: str, variable: tk.StringVar) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel2.TFrame", padding=(14, 9))
        ttk.Label(frame, text=title, style="StatTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=variable, style="StatValue.TLabel").pack(anchor="w")
        return frame

    @staticmethod
    def _configure_tree(tree: ttk.Treeview, specs: dict[str, tuple[str, int]]) -> None:
        for key, (title, width) in specs.items():
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=70, anchor="center", stretch=True)

    def start_scan(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            return
        try:
            workers = max(1, min(32, int(self.workers_var.get())))
        except (ValueError, tk.TclError):
            workers = scanner.DEFAULT_WORKERS
            self.workers_var.set(workers)

        self.stop_event.clear()
        self.signal_by_iid.clear()
        for iid in self.signal_tree.get_children():
            self.signal_tree.delete(iid)
        self.scan_count_var.set("0")
        self.signal_count_var.set("0")
        self.error_count_var.set("0")
        self.total_count_var.set("0")
        self.progress_var.set(0)
        self.status_var.set("Taranıyor")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.workers_spin.configure(state="disabled")
        self._append_log(f"Tarama başlatıldı · workers={workers}")
        self.scan_thread = threading.Thread(target=self._scan_worker, args=(workers,), daemon=True)
        self.scan_thread.start()

    def stop_scan(self) -> None:
        if not (self.scan_thread and self.scan_thread.is_alive()):
            return
        self.stop_event.set()
        self.status_var.set("Durduruluyor")
        self.stop_button.configure(state="disabled")
        self._append_log("Durdurma istendi; çalışan API isteklerinin bitmesi bekleniyor.")

    def _scan_worker(self, workers: int) -> None:
        executor: ThreadPoolExecutor | None = None
        signals: list[dict[str, Any]] = []
        errors: list[tuple[str, str]] = []
        warmups: list[tuple[str, str]] = []
        scanned = 0
        try:
            self.events.put(("log", "Binance bağlantısı kuruluyor…"))
            symbols = scanner.spot_usdt_symbols()
            total = len(symbols)
            self.events.put(("universe", total))
            self.events.put(("log", f"Coin evreni hazırlandı: {total} coin taranacak."))
            if self.stop_event.is_set():
                self.events.put(("finished", {"status": "Durduruldu", "scanned": 0, "total": total, "signals": 0, "errors": 0}))
                return

            now_ms = scanner.server_time_ms()
            self.events.put(("log", "BTC 15M verileri alınıyor…"))
            btc15 = scanner.fetch_15m("BTCUSDT", now_ms=now_ms)
            self.events.put(("log", f"BTC verileri alındı: {len(btc15)} kapalı 15M mum."))

            executor = ThreadPoolExecutor(max_workers=workers)
            future_to_symbol = {
                executor.submit(scanner.scan_symbol, symbol, btc15, now_ms): symbol
                for symbol in symbols
            }
            pending = set(future_to_symbol)
            while pending:
                if self.stop_event.is_set():
                    for future in pending:
                        future.cancel()
                    break
                done, pending = wait(pending, timeout=0.20, return_when=FIRST_COMPLETED)
                for future in done:
                    symbol = future_to_symbol[future]
                    scanned += 1
                    self.events.put(("log", f"{symbol} tarandı."))
                    try:
                        rec = future.result()
                        if rec is not None:
                            signals.append(rec)
                            self.events.put(("signal", rec))
                            self.events.put(("log", f"SIGNAL: {symbol}"))
                    except scanner.WarmupPending as exc:
                        warmups.append((symbol, str(exc)))
                        self.events.put(("log", f"Warmup nedeniyle atlandı: {symbol}"))
                    except Exception as exc:
                        errors.append((symbol, repr(exc)))
                        self.events.put(("log", f"API/Tarama hatası · {symbol}: {exc!r}"))
                    self.events.put(("progress", {
                        "scanned": scanned, "total": total,
                        "signals": len(signals), "errors": len(errors),
                    }))

            stopped = self.stop_event.is_set()
            self._persist_scan_outputs(signals, errors, warmups)
            self.events.put(("finished", {
                "status": "Durduruldu" if stopped else "Tamamlandı",
                "scanned": scanned, "total": total,
                "signals": len(signals), "errors": len(errors),
                "warmups": len(warmups),
            }))
        except Exception as exc:
            self.events.put(("fatal", repr(exc)))
        finally:
            if executor is not None:
                executor.shutdown(wait=not self.stop_event.is_set(), cancel_futures=True)

    @staticmethod
    def _persist_scan_outputs(
        signals: list[dict[str, Any]],
        errors: list[tuple[str, str]],
        warmups: list[tuple[str, str]],
    ) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if signals:
            scanner.pd.DataFrame(signals).sort_values(
                ["decision_time_utc", "symbol"]
            ).to_csv(DATA_DIR / "tsi_bb_live_signals.csv", index=False)
        if errors:
            scanner.pd.DataFrame(errors, columns=["symbol", "error"]).to_csv(
                DATA_DIR / "tsi_bb_scan_errors.csv", index=False
            )
        if warmups:
            scanner.pd.DataFrame(warmups, columns=["symbol", "reason"]).to_csv(
                DATA_DIR / "tsi_bb_warmup_pending.csv", index=False
            )

    def _poll_events(self) -> None:
        try:
            while True:
                event_type, payload = self.events.get_nowait()
                if event_type == "log":
                    self._append_log(str(payload))
                elif event_type == "universe":
                    self.total_count_var.set(str(payload))
                elif event_type == "progress":
                    self._apply_progress(payload)
                elif event_type == "signal":
                    self._insert_signal(payload)
                elif event_type == "finished":
                    self._finish_scan(payload)
                elif event_type == "fatal":
                    self._handle_fatal(str(payload))
                elif event_type == "prices":
                    self._apply_price_results(payload)
                elif event_type == "price_error":
                    self._finish_price_error(str(payload))
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(100, self._poll_events)

    def _apply_progress(self, payload: dict[str, int]) -> None:
        scanned = int(payload["scanned"])
        total = max(1, int(payload["total"]))
        self.scan_count_var.set(str(scanned))
        self.signal_count_var.set(str(payload["signals"]))
        self.error_count_var.set(str(payload["errors"]))
        self.progress_var.set(scanned / total * 100.0)

    def _insert_signal(self, rec: dict[str, Any]) -> None:
        iid = f"signal_{len(self.signal_by_iid) + 1}"
        self.signal_by_iid[iid] = rec
        values = (
            rec.get("symbol"), rec.get("decision_time_utc"), fmt_price(rec.get("last_closed_15m_price")),
            rec.get("tested_entry_not_before_utc"), fmt_num(rec.get("lead_gap"), 1),
            rec.get("m15_motion_net"), rec.get("h4_motion_pos"), fmt_num(rec.get("btc1_tsi_d1"), 6),
            fmt_num(rec.get("btc4_bb_width"), 6), fmt_num(rec.get("coin4_bb_width"), 6),
            fmt_num(rec.get("causal_dd_high_48h_pct"), 3, "%"),
        )
        self.signal_tree.insert("", "end", iid=iid, values=values)
        self.signal_tree.see(iid)

    def _finish_scan(self, payload: dict[str, Any]) -> None:
        status = str(payload["status"])
        self.status_var.set(status)
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.workers_spin.configure(state="normal")
        self._apply_progress(payload)
        if status == "Tamamlandı":
            self.progress_var.set(100)
        self._append_log(
            f"Tarama {status.lower()}: {payload['scanned']}/{payload['total']} coin · "
            f"{payload['signals']} sinyal · {payload['errors']} hata · "
            f"{payload.get('warmups', 0)} warmup."
        )

    def _handle_fatal(self, error: str) -> None:
        self.status_var.set("Durduruldu")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.workers_spin.configure(state="normal")
        self._append_log(f"Tarama durdu: {error}")
        messagebox.showerror("Tarama Hatası", f"Tarama başlatılamadı veya kesildi:\n\n{error}")

    def follow_selected_signal(self) -> None:
        selected = self.signal_tree.selection()
        if not selected:
            messagebox.showinfo("Takibe Al", "Önce sinyal tablosundan bir satır seçin.")
            return
        added = 0
        duplicates = 0
        for iid in selected:
            rec = self.signal_by_iid.get(iid)
            if rec and self.store.add_signal(rec):
                added += 1
            else:
                duplicates += 1
        self._refresh_tracking_table()
        if added:
            self._append_log(f"{added} sinyal takip sistemine eklendi.")
            self.notebook.select(self.track_tab)
        if duplicates:
            messagebox.showinfo("Takip Sistemi", f"{duplicates} sinyal zaten takip listesinde.")

    def show_signal_detail(self) -> None:
        selected = self.signal_tree.selection()
        if not selected:
            messagebox.showinfo("Sinyal Detayı", "Önce bir sinyal satırı seçin.")
            return
        rec = self.signal_by_iid.get(selected[0])
        if not rec:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Sinyal Detayı · {rec.get('symbol', '')}")
        dialog.geometry("620x620")
        dialog.configure(bg=COLORS["bg"])
        text = tk.Text(
            dialog, bg=COLORS["panel"], fg=COLORS["text"], relief="flat",
            font=("Cascadia Mono", 10), padx=14, pady=14, wrap="word",
        )
        text.pack(fill="both", expand=True, padx=14, pady=14)
        text.insert("1.0", json.dumps(rec, indent=2, ensure_ascii=False, default=str))
        text.configure(state="disabled")

    def update_all_prices(self) -> None:
        if not self.store.records:
            messagebox.showinfo("Fiyat Güncelle", "Takip listesi boş.")
            return
        self._start_price_update(sorted({r["symbol"] for r in self.store.records.values()}))

    def update_selected_price(self) -> None:
        selected = self.track_tree.selection()
        if not selected:
            messagebox.showinfo("Seçileni Güncelle", "Önce takip tablosundan bir satır seçin.")
            return
        symbols = sorted({self.store.records[iid]["symbol"] for iid in selected if iid in self.store.records})
        if symbols:
            self._start_price_update(symbols)

    def _start_price_update(self, symbols: list[str]) -> None:
        if self.price_thread and self.price_thread.is_alive():
            return
        self.update_all_button.configure(state="disabled")
        self.update_selected_button.configure(state="disabled")
        self.track_status_var.set("Fiyatlar alınıyor…")
        self.price_thread = threading.Thread(target=self._price_worker, args=(symbols,), daemon=True)
        self.price_thread.start()

    def _price_worker(self, symbols: list[str]) -> None:
        try:
            wanted = set(symbols)
            payload = scanner.get_json("/api/v3/ticker/price")
            prices = {
                str(item["symbol"]): float(item["price"])
                for item in payload
                if str(item.get("symbol", "")) in wanted
            }
            missing = sorted(wanted - set(prices))
            self.events.put(("prices", {"prices": prices, "missing": missing}))
        except Exception as exc:
            self.events.put(("price_error", repr(exc)))

    def _apply_price_results(self, payload: dict[str, Any]) -> None:
        prices = payload["prices"]
        count = self.store.apply_prices(prices)
        self._refresh_tracking_table()
        self.update_all_button.configure(state="normal")
        self.update_selected_button.configure(state="normal")
        missing = payload.get("missing", [])
        self.track_status_var.set(f"{count} coin güncellendi · {datetime.now().strftime('%H:%M:%S')}")
        self._append_log(f"Takip fiyatları güncellendi: {count} coin.")
        if missing:
            self._append_log("Fiyat bulunamadı: " + ", ".join(missing))

    def _finish_price_error(self, error: str) -> None:
        self.update_all_button.configure(state="normal")
        self.update_selected_button.configure(state="normal")
        self.track_status_var.set("Fiyat güncelleme hatası")
        self._append_log(f"Fiyat güncelleme hatası: {error}")
        messagebox.showerror("Fiyat Güncelleme", error)

    def _refresh_tracking_table(self) -> None:
        selection = set(self.track_tree.selection()) if hasattr(self, "track_tree") else set()
        for iid in self.track_tree.get_children():
            self.track_tree.delete(iid)
        records = sorted(
            self.store.records.items(),
            key=lambda item: item[1].get("added_time", ""),
            reverse=True,
        )
        for key, rec in records:
            change = float(rec.get("change_pct", 0.0))
            tag = "positive" if change > 0 else "negative" if change < 0 else "neutral"
            values = (
                rec.get("symbol"), rec.get("signal_time"), fmt_price(rec.get("signal_price")),
                fmt_price(rec.get("current_price")), fmt_num(change, 2, "%"),
                fmt_price(rec.get("high_price")), fmt_price(rec.get("low_price")),
                fmt_num(rec.get("max_up_pct"), 2, "%"), fmt_num(rec.get("max_down_pct"), 2, "%"),
                fmt_duration(str(rec.get("added_time", ""))), rec.get("status", "Takipte"),
            )
            self.track_tree.insert("", "end", iid=key, values=values, tags=(tag,))
            if key in selection:
                self.track_tree.selection_add(key)
        self.track_status_var.set(f"{len(records)} sinyal takipte")

    def _refresh_tracking_durations(self) -> None:
        if not self._closing:
            self._refresh_tracking_table()
            self.root.after(60_000, self._refresh_tracking_durations)

    def remove_selected_tracking(self) -> None:
        selected = list(self.track_tree.selection())
        if not selected:
            messagebox.showinfo("Takipten Çıkar", "Önce bir veya daha fazla satır seçin.")
            return
        if not messagebox.askyesno("Takipten Çıkar", f"Seçili {len(selected)} kayıt takipten çıkarılsın mı?"):
            return
        self.store.remove(selected)
        self._refresh_tracking_table()

    def clear_tracking(self) -> None:
        if not self.store.records:
            return
        if not messagebox.askyesno("Tümünü Temizle", "Takip listesindeki bütün kayıtlar silinsin mi?"):
            return
        self.store.clear()
        self._refresh_tracking_table()

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def save_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Log Kaydet", defaultextension=".txt",
            filetypes=[("Metin dosyası", "*.txt"), ("Tüm dosyalar", "*.*")],
            initialfile=f"r2_scanner_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return
        Path(path).write_text(self.log_text.get("1.0", "end-1c"), encoding="utf-8")
        self._append_log(f"Log kaydedildi: {path}")

    def _on_close(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            if not messagebox.askyesno("Uygulamayı Kapat", "Tarama sürüyor. Durdurup uygulamayı kapatmak istiyor musunuz?"):
                return
            self._closing = True
            self.stop_event.set()
            self.status_var.set("Durduruluyor")
            self.root.after(200, self._close_when_idle)
            return
        self._closing = True
        self.root.destroy()

    def _close_when_idle(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            self.root.after(200, self._close_when_idle)
        else:
            self.root.destroy()


def self_test() -> None:
    assert scanner.CANDIDATE_VERSION == "2026-09-19-r2"
    with tempfile.TemporaryDirectory() as temp_dir:
        store = TrackingStore(Path(temp_dir) / "tracking.json")
        signal = {
            "symbol": "ETHUSDT",
            "decision_time_utc": "2026-09-21T12:00:00+00:00",
            "last_closed_15m_price": 100.0,
        }
        assert store.add_signal(signal) is True
        assert store.add_signal(signal) is False
        assert store.apply_prices({"ETHUSDT": 105.0}) == 1
        rec = next(iter(store.records.values()))
        assert abs(rec["change_pct"] - 5.0) < 1e-9
        assert abs(rec["max_up_pct"] - 5.0) < 1e-9
        assert rec["low_price"] == 100.0
        store2 = TrackingStore(store.path)
        assert len(store2.records) == 1
    print(json.dumps({"self_test": "ok", "scanner_version": scanner.CANDIDATE_VERSION}))


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    root = tk.Tk()
    R2ScannerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
