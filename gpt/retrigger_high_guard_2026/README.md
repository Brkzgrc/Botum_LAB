# RETRIGGER High Guard 2026

Amaç: Mevcut spot scanner karar akışında yalnız RETRIGGER yoluna
`1H near_high20_pct <= 1.0` koruma şartını eklemek.

Evren: 478 aktif USDT spot kripto paritesi.
Hariç: yalnız 15 stable/fiat tabanı.
Dahil: JUP, SYRUP, WBTC, PAXG, XAUT.

Durum:
- Eski tek-parça replay geçersizdir; 5 saat limitinde yarıda kesildi.
- Devam çalışması, coin-parçalarında aday olayları çıkarıp sonunda tek küresel
  günlük-limit/pozisyon motorunda birleştirecek.
- Parça çıktıları tek başına performans sonucu sayılmaz.
