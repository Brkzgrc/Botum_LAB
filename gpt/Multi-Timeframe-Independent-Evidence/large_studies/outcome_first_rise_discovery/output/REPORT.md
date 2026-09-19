# Outcome-First Rise Discovery

Önce yükseliş olayları bulundu; sonra sinyal kuralı dayatmadan bu olayların öncesindeki fiyat/indikatör davranışı matched non-rise kontrollerle karşılaştırıldı.

Rows=337612 | rise=276782 | controls=60830 | symbols=464

## Rise archetypes
- DELAYED_RECOVERY_5PCT_72H: {'n': 91026, 'symbols': 463, 'mfe24_mean': 2.8979248801059296, 'mae24_mean': -5.031651687835432, 'mfe72_mean': 9.009281205979892, 'mae72_mean': -6.628922765760915}
- IMMEDIATE_CLEAN_3PCT_12H: {'n': 63664, 'symbols': 463, 'mfe24_mean': 4.505780543990255, 'mae24_mean': -2.7323742690062613, 'mfe72_mean': 5.333872225934653, 'mae72_mean': -7.205492240102723}
- IMPULSE_8PCT_72H: {'n': 79594, 'symbols': 456, 'mfe24_mean': 9.692473390350619, 'mae24_mean': -1.518141142575536, 'mfe72_mean': 18.987213255080153, 'mae72_mean': -1.735554485242445}
- TREND_CLEAN_5PCT_24H: {'n': 42498, 'symbols': 459, 'mfe24_mean': 7.6040201222897466, 'mae24_mean': -1.1545598967017232, 'mfe72_mean': 8.44084296429508, 'mae72_mean': -6.250324383854887}

## Stable precursor features across discovery/calibration/cross-holdout/final
- pre_dd_from_high_8h: effects -0.838, -0.755, -0.786, -0.758
- pre_dd_from_high_12h: effects -0.850, -0.780, -0.799, -0.747
- h1_bb_width: effects 0.907, 0.871, 0.862, 0.734
- pre_dd_from_high_4h: effects -0.818, -0.727, -0.771, -0.759
- pre_dd_from_high_24h: effects -0.839, -0.805, -0.796, -0.716
- pre_dd_from_high_2h: effects -0.773, -0.688, -0.725, -0.726
- pre_dd_from_high_48h: effects -0.823, -0.802, -0.787, -0.682
- pre_dd_from_high_1h: effects -0.714, -0.647, -0.691, -0.668
- m15_bb_width: effects 0.795, 0.616, 0.698, 0.702
- h4_bb_width: effects 0.915, 0.885, 0.888, 0.611
- btc1_atr_pct: effects 0.958, 0.581, 0.803, 0.635
- btc4_atr_pct: effects 1.020, 0.489, 0.829, 0.651
- btc4_adx: effects 0.539, 0.494, 0.455, 0.529
- btc4_bb_width: effects 0.693, 0.441, 0.630, 0.500
- btc1_bb_width: effects 0.619, 0.420, 0.554, 0.424
- h4_adx: effects 0.379, 0.637, 0.416, 0.435
- h1_stoch_raw: effects -0.360, -0.393, -0.383, -0.429
- h4_mfi: effects 0.458, 0.357, 0.440, 0.489
- pre_ret_1h: effects -0.328, -0.336, -0.328, -0.349
- h1_tsi_d1: effects -0.326, -0.351, -0.347, -0.348
- h1_motion_neg: effects 0.320, 0.349, 0.346, 0.369
- h1_rsi_d3: effects -0.318, -0.320, -0.339, -0.338
- h1_motion_net: effects -0.317, -0.353, -0.344, -0.365
- m15_tsi_d3: effects -0.321, -0.315, -0.333, -0.337
- h1_rsi_d1: effects -0.310, -0.317, -0.320, -0.322
- h4_chop14: effects -0.449, -0.447, -0.428, -0.310
- m15_stoch_k: effects -0.309, -0.329, -0.324, -0.336
- m15_bb_pctb: effects -0.309, -0.408, -0.345, -0.356
- m15_stoch_raw: effects -0.305, -0.364, -0.337, -0.344
- m15_tsi_d1: effects -0.304, -0.337, -0.329, -0.329