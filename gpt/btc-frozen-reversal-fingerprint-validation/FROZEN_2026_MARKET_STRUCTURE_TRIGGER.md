# 2026 mechanical candidate generator — frozen before fingerprint readout

This is the candidate generator already used for the baseline 2026 outcome calculation. It is now frozen; it must not be tuned after fingerprint results are seen.

- Market: BTCUSDT spot.
- 1H, 4H and 1D swings use a symmetric 2-left / 2-right pivot.
- A pivot becomes knowable only when its two right-side bars have closed.
- 1H bullish trigger:
  - latest confirmed 1H swing low is a higher low than the previous confirmed 1H swing low; and
  - current 1H close crosses above the latest confirmed 1H swing high.
- Candidate set used for the fingerprint test:
  - the 1H bullish trigger occurs while the latest confirmed 4H structure is **bear** (latest two confirmed swing highs lower, latest two confirmed swing lows lower).
- Same trigger logic produced 43 raw candidates in 2026 through 2026-09-21.
- A separate 14-day fixed-span episode view is also reported; episode start is the first raw candidate and no episode span may exceed 14 days.

Outcome definition remains separate from candidate generation:
- within 30 days, +10% before -10%;
- if neither is reached and a full 30 days are available, close at day 30 for descriptive P&L;
- immature late-2026 candidates are censored.

This generator was examined with outcomes before the fingerprint reconstruction was executed, so it is **not** a pristine preregistered event definition. It is a fixed exploratory 2026 candidate stream for testing whether the frozen fingerprint adds separation on top of market structure.
