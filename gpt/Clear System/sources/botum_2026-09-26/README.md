# Botum kaynak anlık görüntüsü — 2026-09-26

Kaynak: özel `Brkzgrc/Botum` deposunun `main` dalı. Bu klasör yalnız tarihsel araştırma içindir; canlı sisteme dağıtılmaz ve komut olarak çalıştırılmaz. Dosyalar kendi yol ve adlarıyla birebir kopyalandı; Git blob SHA değerleri tekrar okunup doğrulandı. Botum'a yazılmadı.

| Dosya | Kaynak ve bu klasörde doğrulanan Git blob SHA |
| --- | --- |
| `spot_opportunity_scanner.py` | `f93655b474cdf2126bde8cc043689bbc5c270dac` |
| `tsi_bb_frozen_candidate.py` | `d98f9b164f1f7df10bd7f65f77e8267a451166ff` |
| `portfolio_tracker.py` | `8577806ad24b4829bcbe312870b84cf2e0aa1782` |
| `position_monitor.py` | `6ae28b7c63cef1060a21d38b88e02bb74e6d85c0` |
| `portfolio_snapshot.json` | `ccfffd5154b9f18b6050b58b33906588e202e5f7` |

`spot_opportunity_scanner.py`: PRESSURE/RETRIGGER ön eleme, 1D/4H/1H/15M karar, ilk taramada sinyal vermeme, aday sıralama ve günlük kota. `tsi_bb_frozen_candidate.py`: bağımsız frozen katmanı. `portfolio_tracker.py` ve `position_monitor.py`: kayıt, ücret, stop/hedef, 24 saat bitiş ve çıkış takibi. `portfolio_snapshot.json`: gerçek alım değil, 2026-09-26 16:50:40 tarihli 23 kapanışlı kağıt takip görüntüsü; ileri dönem seçiminde eğitim verisi sayılmayacak.

Araştırma protokolü ve deney kodu `../../research/pressure_confirmation/` altında tutulacak. Kaynak kopyalarını yeni geliştirmelerle değiştirme; yeni sürüm gerekiyorsa ayrı tarihli kaynak alt klasörü oluştur.
