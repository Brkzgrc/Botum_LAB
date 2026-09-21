# Reconstructed feature specification (frozen before 2026 fingerprint readout)

The original scratchpad code was never committed, so the exact implementation cannot be recovered from Git. This file freezes the reconstruction **before** reading the 2026 fingerprint result.

## Frozen reconstruction

### 1. `4h_dip100_uzaklik_d3`

1. On closed 4H bars:
   `dip100_uzaklik = 100 * (close / rolling_min(low, 100) - 1)`
2. `d3 = dip100_uzaklik[t] - dip100_uzaklik[t-3]`
3. Convert `d3` to a causal coin-internal percentile against the **previous 500 completed 4H bars**, excluding the current bar:
   `100 * mean(history <= current)`
4. For an event at time T, rule input is the mean percentile over `T-24h <= bar_time < T-12h`.
5. Condition stays frozen: `<= 36.6`.

Rationale: the legacy name says distance-to-100-bar-dip plus `d3`; the surviving LAB feature convention uses `_d3 = diff(3)`.

### 2. `4h_RSI2_ivme`

1. Compute Wilder RSI on close with period 2.
2. Define normalized one-bar speed:
   `hiz = RSI2.diff(1) / SMA(abs(RSI2.diff(1)), 20)`
3. Define acceleration:
   `ivme = hiz - hiz.shift(1)`
4. Convert `ivme` to the same causal previous-500-bar percentile.
5. For an event at T, rule input is the mean percentile over `T-48h <= bar_time < T-24h`.
6. Condition stays frozen: `>= 48.4`.

Rationale: the surviving Claude LAB code uses exactly this `hiz -> ivme` naming and formula.

## Important status

This is a **reconstruction**, not a recovered original. Therefore any 2026 readout using it is labeled **reconstruction validation / exploratory fidelity check**, not the independent confirmatory p-value for the original frozen scratchpad implementation.

No formula, window, threshold, or event-generator change is allowed after the 2026 fingerprint readout is seen.
