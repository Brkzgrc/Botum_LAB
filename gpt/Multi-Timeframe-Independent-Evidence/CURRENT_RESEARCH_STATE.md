# CURRENT RESEARCH STATE

Updated: 2026-09-21

## Purpose

This file is the durable handoff point for the GPT research thread.
A chat/session ending must NOT be treated as a research reset.
Before starting any new research workflow, read this file and the persisted output files referenced below.

## Fixed user objective

- Binance Spot LONG only.
- Preserve the quality of the current r2 premium setup.
- Increase practical opportunity frequency toward about 3 signals/day by adding independent validated setup families, not by weakening r2.
- Cost assumption: 0.20% round-trip.
- Main evaluation: signals/day, active-day coverage, +3/+4/+5 target-before-stop behavior, net expectancy, PF, MFE/MAE, symbol/year distribution, OOS/holdout robustness.
- A high win rate with very low coverage is not sufficient.
- Do not start expensive/new GitHub workflows without explicit user direction in the active conversation.

## Frozen premium reference

r2 remains untouched unless a new family is independently validated.
Persisted reference:
- gpt/Multi-Timeframe-Independent-Evidence/large_studies/r2_frozen_robustness/output/summary.json

Key r2 2026 reference:
- 110 signals
- 99 symbols
- mean 24h about +3.98%
- win 24h about 92.73%
- PF about 12.07%
- up3_before_dn2 about 80%

## Completed research — do not rerun blindly

### r2 movement expansion
Run: 35573311239
Conclusion: SUCCESS workflow, research result negative.
Output:
- gpt/Multi-Timeframe-Independent-Evidence/large_studies/r2_movement_expansion/output/summary.json

Result:
- Existing broad event pool could reach about 2-3/day but not with stable Discovery+Calibration quality.
- 2026-looking candidates were rejected because pre-2026/calibration did not support them.
- Do not loosen r2 using these movement scores.

### r2 nonlinear movement clusters
Run: 35573515541
Conclusion: SUCCESS workflow, research result negative.
Output:
- gpt/Multi-Timeframe-Independent-Evidence/large_studies/r2_movement_clusters/output/summary.json

Result:
- 160 movement features, PCA + k-means across k=8/12/16/20/24.
- No stable cluster subset preserved required quality while materially increasing frequency.
- Do not use this path to weaken r2.

### independent movement-signature families
Run: 35575114493
Conclusion: SUCCESS workflow, research result negative.
Output:
- gpt/Multi-Timeframe-Independent-Evidence/large_studies/independent_signature_families/output/summary.json

Population:
- 1,261,096 events
- 466 symbols
- 216 structural signatures

Result:
- 0 r2-parity individual signature candidates
- 0 strong-quality individual signature candidates
- NO_STABLE_SIGNATURE_FAMILY_SET

### independent price families v2
Run: 35575493314
Conclusion: SUCCESS workflow, all 66 jobs succeeded.
Output:
- gpt/Multi-Timeframe-Independent-Evidence/large_studies/independent_price_families_v2/output/summary.json

Population:
- 695,463 events
- 466 symbols
- 62 candidate rules
- Families: CONFIRMED_REVERSAL, SECOND_WAVE, BREAKOUT_HOLD, BEAR_TRAP_CONFIRM, PULLBACK_CONTINUATION

Result:
- NO_STABLE_INDEPENDENT_PRICE_FAMILIES
- champions = {}
- None of the 62 fixed rule variants met the Discovery+Calibration stability requirements.

## Earlier important evidence

Stage-6 sparse/local research from the previous Signal Phase project found that:
- C09 CONFIRMED_REVERSAL: confirmed local mechanism.
- C12 CONTINUATION: confirmed local mechanism.
- pooled OOS local-score=2 had roughly:
  - KNOWN rate3v2 53.04%, rate5v3 49.90%
  - HOLDOUT rate3v2 54.46%, rate5v3 52.08%
  - mean close24 about +1.76% KNOWN, +1.94% HOLDOUT
This evidence is promising but is NOT equivalent to r2 quality and must be re-tested against the current fixed objective/frequency framework before production use.

Conversation files containing the relevant old reports:
- PATTERN_DISCOVERY_REPORT.md
- STAGE3_VALIDATION_REPORT.md
- STAGE5_LOCAL_DISCOVERY_REPORT.md
- STAGE6_DECISION_REPORT.md

## Current conclusion

The following approaches have been falsified as a way to get ~3/day while preserving r2-level quality:
1. Relaxing r2 thresholds.
2. Linear movement-quality scoring within the old broad event pool.
3. Nonlinear PCA/k-means movement clusters within the old broad event pool.
4. Structural membership signatures from the first 48 movement-family rules.
5. The 62 fixed independent price-path variants in Independent Price Families v2.

Therefore:
- r2 stays as a premium setup.
- Frequency expansion must come from genuinely different setup mechanisms.
- Do not repeat the same threshold-grid variations under new names.

## Recommended next research direction

Rebuild and directly test the previously validated C09 CONFIRMED_REVERSAL and C12 CONTINUATION mechanisms under the current benchmark:
- exact causal entry timing
- 0.20% cost
- 2023-2025 selection only
- untouched 2026 evaluation
- +3/-2, +4/-2.5, +5/-3 first-touch plans
- frequency and active-day coverage
- OR-combination with frozen r2, with symbol/time dedupe

If C09/C12 fail current standards, move to outcome-first path discovery on actual +3/+5 rise episodes rather than another handcrafted threshold grid.

## Session-resume rule

On a new chat/session:
1. Read this file first.
2. Check latest GitHub Actions state before claiming anything is running.
3. Read the referenced persisted summaries.
4. Continue from the 'Recommended next research direction'.
5. Never report a workflow as successful until its result file exists and metrics are inspected.
