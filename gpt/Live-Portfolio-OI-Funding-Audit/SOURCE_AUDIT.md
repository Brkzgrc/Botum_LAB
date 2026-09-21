# SOURCE AUDIT — 2026-09-21

## Sonuç
Eski `backtest_standalone_v5.py` adına bağımlılık kaldırıldı. Araştırmanın otoritesi canlı dosyalar olacak.

## Repo'da bulunan replay iskeleti
`gpt/retrigger_high_guard_2026/retrigger_high_guard_2026.py`:
- v11 kod gövdesi + tarihsel 15M replay içeriyor.
- state/watch ve günlük kota mekanizmasını tarihsel olarak simüle ediyor.
- sinyal anı feature snapshot'ı kaydediyor.
- fakat canlıdan sapmış bir deney: RETRIGGER için `1H near_high20_pct <= 1.0` guard eklenmiş.
- çıkış simülasyonu eski sabit %2.5 trailing kullanıyor.

## Canlıyla eşitlenecek noktalar
1. RETRIGGER guard kaldırılacak; canlı legacy karar mantığı birebir alınacak.
2. JUP/SYRUP ve canlı universe istisnaları birebir eşlenecek.
3. Legacy günlük kota ve watch-state davranışı korunacak.
4. Frozen TSI+BB ayrı motor olarak replay'e eklenecek; legacy kurallarıyla birleştirilmeyecek.
5. Aynı sembol/aynı scan çakışma davranışı canlı orchestrator ile eşlenecek.
6. Scanner payload'ındaki güncel exit policy tarihsel sonuca uygulanacak.
7. Portfolio tarafındaki gerçekçi kapanış/fee davranışı baseline'a yansıtılacak.
8. Baseline dondurulmadan hiçbir OI/Funding eşiği denenmeyecek.

## OI/Funding araştırma ilkesi
Amaç OI/Funding'in sinyal üretmesi değil, mevcut iki bağımsız sinyal ailesinde kötü koşulları veto edip etmediğini ölçmektir.
