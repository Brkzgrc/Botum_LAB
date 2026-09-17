# Coin MTF Reversal Propagation — Causal/Tradable Validation

Bu testte setup için sabit RSI/KDJ/W%R/StochRSI seviyeleri kullanılmaz. Üst zaman dilimlerinde yalnızca TAMAMLANMIŞ mumlar kullanılır.

## Look-ahead kilidi
- 15M sinyali ancak 15 dakikalık mum kapandıktan sonra var sayılır.
- Giriş aynı kapanış sınırındaki yeni mum açılışından bile yapılmaz; sinyal kapanışından sonra TAM 1 adet 15M gecikme bırakılır ve sonraki mum açılışı kullanılır.
- 1H ve 4H bilgisi yalnızca ilgili mum kapandıktan sonra alt zaman dilimine taşınır.
- 1H teyidi giriş şartı olarak gelecekte bilinmiş sayılmaz; girişten SONRA oluşursa yönetim bilgisi olur.
- Ayrıca tamamen nedensel ikinci kol vardır: 1H teyidi beklenir, teyit mumu kapandıktan sonra bir 15M daha beklenir ve ancak sonraki açılışta giriş yapılır.

Seçili coin: 100 | Analiz edilen: 100 | Olay: 10360 | Hatalı/uygunsuz: 0

## Özet
- ALL: n=10337, symbols=100, gross12=0.043%, net12(cost0.20)=-0.157%, net-win=43.0%, MFE12=2.69%, MAE12=-2.42%, H1<=4h=64.1%, managed-net=-0.206%
- HOLDOUT_SYMBOLS: n=3281, symbols=32, gross12=0.012%, net12(cost0.20)=-0.188%, net-win=42.4%, MFE12=2.69%, MAE12=-2.47%, H1<=4h=63.9%, managed-net=-0.244%
- LATE_HOLDOUT: n=3040, symbols=100, gross12=0.025%, net12(cost0.20)=-0.175%, net-win=42.0%, MFE12=2.47%, MAE12=-2.21%, H1<=4h=65.4%, managed-net=-0.226%
- DOUBLE_HOLDOUT: n=976, symbols=32, gross12=-0.066%, net12(cost0.20)=-0.266%, net-win=39.9%, MFE12=2.43%, MAE12=-2.28%, H1<=4h=64.7%, managed-net=-0.301%
- H1_CONFIRMS_WITHIN4H: n=6626, symbols=100, gross12=0.552%, net12(cost0.20)=0.352%, net-win=50.4%, MFE12=3.21%, MAE12=-2.06%, H1<=4h=100.0%, managed-net=0.352%
- NO_H1_CONFIRM_WITHIN4H: n=3711, symbols=100, gross12=-0.866%, net12(cost0.20)=-1.066%, net-win=29.8%, MFE12=1.76%, MAE12=-3.05%, H1<=4h=0.0%, managed-net=-1.201%

## 1H teyidini BEKLEYEREK gerçek giriş (teyit kapanışı + 15M gecikme)
- ALL: n=6619, symbols=100, gross12=0.042%, net12(cost0.20)=-0.158%, net-win=42.7%, MFE12=2.78%, MAE12=-2.43%
- HOLDOUT_SYMBOLS: n=2094, symbols=32, gross12=-0.002%, net12(cost0.20)=-0.202%, net-win=41.1%, MFE12=2.79%, MAE12=-2.53%
- LATE_HOLDOUT: n=1987, symbols=100, gross12=-0.022%, net12(cost0.20)=-0.222%, net-win=41.1%, MFE12=2.53%, MAE12=-2.36%
- DOUBLE_HOLDOUT: n=632, symbols=32, gross12=-0.012%, net12(cost0.20)=-0.212%, net-win=38.0%, MFE12=2.58%, MAE12=-2.37%

Double-holdout'ta 1H teyit gelenler - gelmeyenler net12(cost0.20) farkı, symbol-cluster bootstrap: 1.286% [%95 GA 0.895, 1.716].