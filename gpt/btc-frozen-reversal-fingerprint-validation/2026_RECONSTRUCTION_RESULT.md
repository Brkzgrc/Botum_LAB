# 2026 reconstruction readout

**Status:** encouraging direction, not confirmatory.

The legacy scratchpad feature implementation was not recoverable, so the two frozen features were reconstructed and frozen in `RECONSTRUCTED_FEATURE_SPEC.md` before this readout. The 2026 market-structure candidate generator was also frozen before the fingerprint readout.

## Raw candidates

| metric | all mature | fingerprint fires | no fire |
|---|---:|---:|---:|
| candidates | 34 | 8 | 26 |
| +10 before -10 within 30d | 17 | 6 | 11 |
| success rate | 50.0% | **75.0%** | 42.3% |
| average descriptive P&L | +3.88% | **+6.54%** | +3.07% |

Fixed-subset one-sided hypergeometric tail for 6 or more successes among 8 fires, given 17 successes among 34 mature candidates: **p = 0.1123**.

## 14-day episode view

| metric | all mature episodes | fingerprint fires | no fire |
|---|---:|---:|---:|
| episodes | 12 | 3 | 9 |
| +10 before -10 within 30d | 6 | **3** | 3 |
| success rate | 50.0% | **100.0%** | 33.3% |
| average descriptive P&L | +3.07% | **+10.00%** | +0.76% |

Fixed-subset one-sided hypergeometric tail for all 3 fired episodes being successes, given 6 successes among 12 mature episodes: **p = 0.0909**.

## Interpretation

The reconstructed fingerprint points in the expected direction and materially enriches the candidate stream in this partial-2026 sample. However the independent episode count is too small for a confirmatory claim, and the exact legacy feature code is unavailable. Therefore this run is **exploratory reconstruction validation**, not a PASS for the original preregistered hypothesis.

## Pending fired candidates

These fingerprint fires were still immature at the 2026-09-21 cutoff and must remain untouched until their 30-day outcome is known:

- 2026-08-27 08:00 UTC
- 2026-09-03 12:00 UTC
- 2026-09-03 19:00 UTC
- 2026-09-09 04:00 UTC

No formula, threshold, event definition, or episode rule should be changed before those pending outcomes mature.

## P&L caveat

P&L uses +10% TP / -10% stop, otherwise the 30-day close. Fees and slippage are excluded. Candidates overlap in time, so summed percentages are fixed-notional descriptive totals, not portfolio returns.
