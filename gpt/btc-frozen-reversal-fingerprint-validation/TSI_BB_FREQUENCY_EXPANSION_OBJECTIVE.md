# TSI+BB Frequency Expansion — Research Objective

## Why this branch exists
The BTC frozen fingerprint did not transfer well to ETH/SOL. The current priority is therefore the stronger LAB candidate: frozen TSI+BB.

A high win rate is not sufficient by itself. Every candidate must be judged jointly by:
- signal frequency,
- win rate,
- average net P&L per signal,
- median net P&L,
- profit factor,
- drawdown / downside concentration,
- robustness across symbols and time.

A configuration with high win rate but trivial net P&L (for example ~+0.10% per trade) is not considered successful.

## Existing 2026 baseline from LAB
Frozen TSI+BB:
- 150 signals in 2026 sample,
- win24: 84.0%,
- mean net24: +3.2568%,
- median net24: +3.1996%,
- profit factor 24h: 6.126,
- round-trip cost already included: 0.20%.

This corresponds to roughly 4 signals/week through the 2026 study window.

## Expansion target
Primary operational target:
- minimum 5 signals/week,
- preferred 10–15 signals/week,
- preserve win rate as much as possible,
- P&L must remain economically meaningful.

## Evaluation discipline
Do not optimize on 2026 outcomes directly.

Expansion candidates must be selected using pre-2026 discovery/calibration data only. 2026 remains the evaluation set.

For each candidate report:
- signals/week,
- win24,
- mean net24,
- median net24,
- PF24,
- p10 net24,
- symbol concentration,
- monthly stability,
- comparison versus frozen TSI+BB.

No candidate is promoted solely because of win rate.
