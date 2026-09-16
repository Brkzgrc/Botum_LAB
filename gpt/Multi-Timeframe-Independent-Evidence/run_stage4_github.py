# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "stage4_v4_1_1.py.zlib.b64"
MONITOR = ROOT / "04_SHADOW_FORWARD_MONITOR.py"
UNIVERSE = ROOT / "frozen_universe.json"
MODEL = ROOT / "reports" / "stage2" / "regime_model.json"
EXPECTED_SHA256 = "45fbce1e258c387eff246fe42202a6e02e22bf71983dc0f9089ee5138b33c4b1"


def ensure_monitor() -> None:
    raw = zlib.decompress(base64.b64decode("".join(PAYLOAD.read_text(encoding="utf-8").split())))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Stage4 payload SHA256 uyuşmuyor: {digest}")
    if not MONITOR.exists() or hashlib.sha256(MONITOR.read_bytes()).hexdigest() != EXPECTED_SHA256:
        MONITOR.write_bytes(raw)


def ensure_frozen_universe() -> int:
    obj = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    symbols = obj.get("symbols", [])
    if len(symbols) != 401:
        raise SystemExit(f"Frozen universe 401 sembol olmalı; bulundu={len(symbols)}")
    d = ROOT / "data" / "discovery_events"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.parquet"):
        old.unlink()
    for symbol in symbols:
        (d / f"{symbol}.parquet").touch()
    return len(symbols)


def main() -> None:
    ensure_monitor()
    n = ensure_frozen_universe()
    if not MODEL.exists():
        raise SystemExit(
            "Eksik frozen bağımlılık: reports/stage2/regime_model.json. "
            "Stage 2'de kullanılan dosyanın aynısı gerekir; yeniden fit edilmeyecek."
        )
    print(f"[DEPLOY] exact Stage4 v4.1.1 sha256={EXPECTED_SHA256[:16]}…")
    print(f"[DEPLOY] frozen universe={n}")
    subprocess.run(
        [sys.executable, str(MONITOR), "--once", "--workers", "5"],
        cwd=str(ROOT),
        check=True,
    )


if __name__ == "__main__":
    main()
