# BTC Frozen Reversal Fingerprint Validation

Purpose: isolate the frozen BTC reversal-fingerprint research from the live `Botum` repository and continue all validation only inside `Botum_LAB`.

## Frozen hypothesis

- `4h_dip100_uzaklik_d3|24-12s|ort <= 36.6`
- AND `4h_RSI2_ivme|48-24s|ort >= 48.4`

The thresholds and features are frozen. Validation must not tune thresholds, add a third condition, change features, or reopen broad search.

## Source provenance

Research notes were copied from `Brkzgrc/Botum` at commit `aedb91d5a0be831d0c27ddc65aa2147813618493`.
Relevant audit-chain commits preserved in the notes include:
- `645c0abd9c12bac89fa90bacd28bbc77e6866a12` — candidate selection / preregistration
- `828f66c5ed5d8fd012f7a01344f26a4e925c8380` — empirical-p audit
- `8b83ac63a0d02962efb82bc33e2bdd785a8078ca` — permutation fix / protocol freeze
- `624b956dfe5c7cc1620977a033f41ff4521fea73` — PASS/FAIL preregistration
- `aedb91d5a0be831d0c27ddc65aa2147813618493` — power correction + blind replay protocol

## Important migration limitation

The historical notes explicitly describe the research tools as **scratchpad, not committed to the repository**. Git history was checked for these paths and no commits exist:
`nihai_test.py`, `ozellik_fabrikasi.py`, `yapi_fabrikasi.py`, `zor_negatif.py`, `parmak_izi.py`, `aday_secim.py`, `audit.py`, `guc_analizi.py`.

Therefore the exact legacy feature implementation is **not recoverable from Git**. The preserved snapshot contains the frozen rule, audit results, normalization rules, episode logic, power criteria, and validation protocol. Any reconstruction of the feature code must happen here in Botum_LAB and be clearly versioned as a reconstruction rather than claimed as the original scratchpad.

## Repository safety boundary

- `Botum`: live system; source-only during this migration.
- `Botum_LAB`: all future research code, data transforms, backtests, and validation.
- No future research should require writes to `Botum`.
