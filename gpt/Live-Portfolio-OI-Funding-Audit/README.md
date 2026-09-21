# Live Portfolio OI/Funding Audit

## Amaç
Canlı Portfolio'ya sinyal yansıtan iki bağımsız sinyal ailesinde BTC Open Interest ve Funding bilgisinin zararları azaltan nedensel bir veto olarak işe yarayıp yaramadığını ölçmek.

## Canlı referans
Araştırma eski backtest dosyalarından türetilmeyecek. Referans, 21 Eylül 2026'da kullanıcı tarafından sağlanan canlı dosyalardır:

1. `spot_opportunity_scanner.py`
   - Legacy v11 sinyal ailesi: RETRIGGER / PRESSURE
   - BTC mevcut rejimi yalnız fiyat/MACD tabanlıdır.
   - BTC RED hard veto değildir; kalite puanından 5 düşürür.
   - Günlük legacy sinyal kotası vardır.
2. `tsi_bb_frozen_candidate.py`
   - Legacy v11'den bağımsız TSI+BB Frozen sinyal ailesi.
   - Kendi BTC TSI/BB + motion gate'i ve 15M lead/lag mantığı vardır.
   - Karar bir tam 15M bar gecikmeyle eligible olur.
3. `portfolio_tracker.py`
   - spot-scanner kayıtlarını sanal olarak takip eder.
4. `position_monitor.py`
   - gerçek pozisyon yönetimi tarafıdır; sinyal üreticisi değildir.

## Kritik kural
Canlı sinyal kuralları OI/Funding araştırması sırasında değiştirilmeyecek. Önce aynı tarihsel sinyaller üretilecek, sonra OI/Funding yalnızca ex-post veto katmanı olarak uygulanacak.

## Ayrı raporlanacak aileler
- LEGACY_RETRIGGER
- LEGACY_PRESSURE
- TSI_BB_FROZEN
- COMBINED_PORTFOLIO

## Ölçümler
Her veto adayı için:
- baseline trade/sinyal sayısı
- veto edilen LOSS
- yanlış veto edilen WIN
- veto edilen expired
- net P&L farkı
- expectancy
- profit factor
- win rate
- max drawdown
- sinyal/gün
- büyük kazananların kaybı
- setup ailesi bazında aynı metrikler

## Causality / leakage kilidi
- OI ve funding yalnız sinyal karar anında veya ondan önce yayımlanmış değerlerden alınır.
- Gelecek funding settlement değeri kullanılamaz.
- OI raw nominal seviyeden çok değişim/z-score/percentile olarak test edilir.
- Eşikler tüm örneklemde optimize edilip aynı örneklemde başarı ilan edilmeyecek.
- Development / validation / final holdout ayrımı korunacak.

## Çıkış eşleşmesi
Eski replay'deki sabit %2.5 trailing doğrudan baseline kabul edilmeyecek. Canlı scanner'ın sinyalle taşıdığı çıkış politikası ve Portfolio'nun güncel spot takip davranışı esas alınacak.

## İlk bulgu
Repo'daki `gpt/retrigger_high_guard_2026/retrigger_high_guard_2026.py` kullanılabilir bir replay iskeleti içeriyor; ancak canlı baseline değildir:
- RETRIGGER yoluna `near_high20_pct <= 1.0` eklenmiş.
- eski replay çıkışı TP1 sonrası sabit %2.5 trailing kullanıyor.
Bu nedenle dosya yalnız replay altyapısı olarak kullanılabilir; karar/çıkış kuralları canlı referansla yeniden eşitlenmelidir.

## Fazlar
1. Canlı kaynak eşleme ve fark denetimi.
2. İki sinyal ailesinin causal historical replay'i.
3. Baseline sonuçlarının canlı Portfolio kontratıyla doğrulanması.
4. BTC OI/Funding tarihsel veri setinin causal join'i.
5. Tek değişken ve kombinasyon veto taraması.
6. Walk-forward + final holdout.
7. Ancak robust iyileşme varsa canlı entegrasyon adayı.

Durum: FAZ 1 BAŞLADI.
