# Legacy scratchpad availability audit

The old research notes name the following tools as scratchpad scripts:

- `nihai_test.py`
- `zor_negatif.py`
- `yapi_fabrikasi.py`
- `ozellik_fabrikasi.py`
- `parmak_izi.py`
- `etkilesim_avcisi.py`
- `iz_avcisi.py`
- `kural_madenci.py`
- `cikis_lab.py`
- `aday_secim.py`
- `audit.py`
- `guc_analizi.py`
- `_zayif_etki.py`
- `_zincir_kalibre.py`

The source notes themselves say these were **scratchpad / not committed**. Git history checks for the principal files returned no commits. This means the exact original implementation of `4h_dip100_uzaklik_d3` and `4h_RSI2_ivme` cannot be copied from Git because that code is not present in repository history.

What *was* preserved and migrated:
- frozen feature names and thresholds;
- time windows and aggregation;
- causal 500-bar coin-internal percentile normalization;
- corrected 14-day episode logic;
- permutation-audit conclusions;
- discovery p-value provenance;
- power / PASS-FAIL-SONUCSUZ rules;
- blind replay and outcome definition.

Next implementation work in this folder must be marked as **reconstructed implementation** and validated against all recoverable historical invariants before it is used for confirmatory results.
