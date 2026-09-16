# Multi-Timeframe Independent Evidence — Stage 4 Forward Monitor

Bu klasör GPT tarafındaki Signal Phase Research / Multi-Timeframe Independent Evidence forward-shadow takibi içindir.

## Amaç
Stage 3'te PROMOTE_FORWARD statüsü alan C02 / C09 / C12 dondurulmuş kurallarını Binance Spot üzerinde ileri-zaman (shadow) olarak takip etmek.

- Gerçek emir yok.
- Telegram yok.
- Retroaktif sinyal yok.
- Kurallar/eşikler forward sırasında değiştirilmez.
- Yalnız kapanmış mumlar kullanılır.
- 3/6/12/24 saat outcome bilgisi sinyal üretildikten sonra eklenir.

## GitHub Actions
Workflow her saat tek tur çalışır. Daemon kullanılmaz. State dosyaları bu klasör altında korunup repoya geri commit edilir.

Ana monitor: `04_SHADOW_FORWARD_MONITOR.py` (Stage 4 v4.1.1)

Sabit evren: `frozen_universe.json` (401 Stage-2 sembolü)

Zorunlu frozen bağımlılık: `reports/stage2/regime_model.json`
