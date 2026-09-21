# PUMP WATCH → PUMP ENTRY Research

## Objective
Develop a Binance Spot USDT LONG signal system with high out-of-sample win rate and high cost-adjusted P&L. Signal count does not need to be large; quality takes priority.

## Locked scope
- Test period: 2026-01-01 through 2026-09-21.
- Binance Spot, USDT quote.
- Exact stablecoin and fiat base-asset exclusions; no substring exclusion.
- FORCE_INCLUDE: JUP, SYRUP.
- Spot only, LONG only.
- Round-trip trading cost: 0.20%.
- No look-ahead: every decision uses only fully closed candles.
- A generated signal enters at the NEXT candle OPEN. Same-candle future high/low must never be used to create the signal.
- Future high/low may be used only for outcome/episode labels after the signal timestamp.

## Architecture under research
1. PUMP WATCH = early warning / accumulation-compression motion.
2. PUMP ENTRY = tradable confirmation after WATCH.
3. 4H context, 1H setup/motion, 15M ignition/entry timing.
4. Static-threshold baseline must be compared with motion-based and hybrid families.

## Motion candidates
- Higher-low progression and ATR-normalized slope.
- Pullback magnitude/duration decay.
- Repeated resistance tests, touch imbalance, shrinking distance to resistance.
- ADX slope/acceleration and DI spread evolution.
- Normalized MACD histogram slope/acceleration.
- OBV slope/acceleration.
- RVOL trajectory rather than only a fixed threshold.
- BB Width and ATR/range contraction → expansion.
- 4H trend/regime and BTC context.

## Required evaluation
Discovery and validation must be separated. Prefer walk-forward/monthly stability rather than selecting thresholds on the entire sample.
Report:
- signals/trades
- win rate
- net P&L after 0.20% cost
- average and median trade return
- Profit Factor
- expectancy
- max drawdown / loss streak
- MFE and MAE
- +5/+8/+10/+15/+20/+25 hit rates
- 6h/12h/24h/48h/72h forward behavior
- median WATCH→ENTRY lead time
- false WATCH alerts
- monthly/regime stability
- unique symbols

Do not promote a candidate merely because its in-sample win rate is high.
