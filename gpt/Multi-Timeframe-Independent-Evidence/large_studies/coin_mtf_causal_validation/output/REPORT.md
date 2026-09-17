# Coin MTF Reversal Propagation — Causal/Tradable Validation

Bu testte setup için sabit RSI/KDJ/W%R/StochRSI seviyeleri kullanılmaz. Üst zaman dilimlerinde yalnızca TAMAMLANMIŞ mumlar kullanılır.

## Look-ahead kilidi
- 15M sinyali ancak 15 dakikalık mum kapandıktan sonra var sayılır.
- Giriş aynı mum kapanışından geçmişe dönük yapılmaz; bir sonraki 15M mumun açılışı kullanılır.
- 1H ve 4H bilgisi yalnızca ilgili mum kapandıktan sonra alt zaman dilimine taşınır.
- 1H teyidi giriş şartı olarak gelecekte bilinmiş sayılmaz; girişten SONRA oluşursa yönetim bilgisi olur.
- 1H teyidi 4 saat içinde gelmezse +4h açılışında çıkış; gelirse +12h açılışına kadar tutma ayrıca test edilir.

Seçili coin: 100 | Analiz edilen: 100 | Olay: 10360 | Hatalı/uygunsuz: 0

## Özet
- ALL: n=10337, symbols=100, gross12=0.014%, net12(cost0.20)=-0.186%, net-win=42.2%, MFE12=2.66%, MAE12=-2.45%, H1<=4h=64.1%, managed-net=-0.226%
- HOLDOUT_SYMBOLS: n=3281, symbols=32, gross12=-0.017%, net12(cost0.20)=-0.217%, net-win=41.4%, MFE12=2.66%, MAE12=-2.50%, H1<=4h=63.9%, managed-net=-0.265%
- LATE_HOLDOUT: n=3040, symbols=100, gross12=0.035%, net12(cost0.20)=-0.165%, net-win=41.2%, MFE12=2.47%, MAE12=-2.22%, H1<=4h=65.4%, managed-net=-0.211%
- DOUBLE_HOLDOUT: n=976, symbols=32, gross12=-0.019%, net12(cost0.20)=-0.219%, net-win=39.0%, MFE12=2.45%, MAE12=-2.27%, H1<=4h=64.7%, managed-net=-0.245%
- H1_CONFIRMS_WITHIN4H: n=6626, symbols=100, gross12=0.579%, net12(cost0.20)=0.379%, net-win=50.0%, MFE12=3.21%, MAE12=-2.06%, H1<=4h=100.0%, managed-net=0.379%
- NO_H1_CONFIRM_WITHIN4H: n=3711, symbols=100, gross12=-0.995%, net12(cost0.20)=-1.195%, net-win=28.3%, MFE12=1.69%, MAE12=-3.15%, H1<=4h=0.0%, managed-net=-1.305%

Double-holdout'ta 1H teyit gelenler - gelmeyenler net12(cost0.20) farkı, symbol-cluster bootstrap: 1.444% [%95 GA 1.045, 1.868].