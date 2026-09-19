# r2 Concurrent Signal Ranking

{
  "purpose": "Rank simultaneous frozen-r2 signals using only causal pre-entry features. Selection uses Discovery+Calibration.",
  "competition_group_counts": {
    "DISCOVERY": 4,
    "CALIBRATION": 5,
    "CROSS_HOLDOUT_PRE2026": 6,
    "FINAL_HOLDOUT_2026": 3
  },
  "features": 362,
  "stable_rules": 0,
  "champion_selected_without_holdouts": null,
  "top20": [
    {
      "feature": "m15_ppo_hist",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 3.631368436009512,
        "selected_median": 3.2739454094292686,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.16384152371409755
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.070043001680992,
        "selected_median": 1.547719336238873,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.9751213754010983
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.8572856509651614,
        "selected_median": 3.049630723781393,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.9494968158898227
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "m15_ppo_hist_acc",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 6.6057807476653725,
        "selected_median": 2.9319910514541414,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 3.138253835369958
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.6273193597220645,
        "selected_median": 1.3438868417461114,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.4178450173600257
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 5.745352986170538,
        "selected_median": 4.221600198166953,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -0.061429480684446425
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "m15_tsi_acc",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 3.856565455006455,
        "selected_median": 4.175569735642659,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.3890385427110403
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.609030636468691,
        "selected_median": 0.9829380411507385,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.4361337406133992
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.996119263485486,
        "selected_median": 4.112056737588654,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.810663203369498
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_atr_pct_d1",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 4.371188265490988,
        "selected_median": 4.175569735642659,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.9036613531955737
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.6321286812301683,
        "selected_median": 1.3438868417461114,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.413035695851922
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.2502055713952287,
        "selected_median": 1.6132366273798884,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -3.5565768954597554
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_bb_width_d1",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 6.4093869225344235,
        "selected_median": 5.5420494699646605,
        "selected_win": 60.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 2.941860010239009
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 3.022606734306377,
        "selected_median": 1.922160966878672,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.022557642775713038
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 1.3273273264131673,
        "selected_median": 1.6132366273798884,
        "selected_win": 66.66666666666666,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -4.479455140441817
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_bb_width_d3",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 6.651570189441517,
        "selected_median": 5.5420494699646605,
        "selected_win": 60.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 3.1840432771461025
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 3.3062701878041323,
        "selected_median": 2.8965377855128533,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": 0.2611058107220421
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 1.0078154021868218,
        "selected_median": 0.6547008547008517,
        "selected_win": 66.66666666666666,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -4.798967064668163
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_bb_pctb_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 4.3066949252894915,
        "selected_median": 3.2739454094292686,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.8391680129940768
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.6051116924471778,
        "selected_median": 1.2006379344403297,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.4400526846349124
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.1661902727876243,
        "selected_median": 3.2383954154727723,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.64059219406736
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_bb_pctb_acc",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 7.935099781365153,
        "selected_median": 4.519999999999991,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 4.4675728690697385
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.6661488619399354,
        "selected_median": 1.2006379344403297,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.3790155151421548
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.693616306841367,
        "selected_median": 4.112056737588654,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.113166160013617
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_vwap_dist_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 7.503011830283019,
        "selected_median": 5.105039787798416,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 4.0354849179876044
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.0510946243733734,
        "selected_median": 1.8751505238987831,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.9940697527087168
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.5793505986463647,
        "selected_median": 2.8864197530864333,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -3.2274318682086194
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_roc4_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 4.518249744953567,
        "selected_median": 3.2739454094292686,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 1.0507228326581526
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.8298486925955237,
        "selected_median": 1.3438868417461114,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.21531568448656646
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.5523983952555405,
        "selected_median": 4.646938775510212,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.2543840715994437
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_ppo_hist_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 7.414191294422163,
        "selected_median": 4.660937108494134,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 3.946664382126748
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.070043001680992,
        "selected_median": 1.547719336238873,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.9751213754010983
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.259838674420019,
        "selected_median": 2.8864197530864333,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -3.546943792434965
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_tsi_acc",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 8.961894711251992,
        "selected_median": 7.403872529245681,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 5.494367798956577
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.7449825296613024,
        "selected_median": 1.7585745468349565,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.3001818474207878
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.1661902727876243,
        "selected_median": 3.2383954154727723,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.64059219406736
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_cmo_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 7.852508050372917,
        "selected_median": 4.730232558139536,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 4.384981138077502
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.549441156843727,
        "selected_median": 1.4993816160421396,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.4957232202383632
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.0282661787587686,
        "selected_median": 2.3210084033613576,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.7785162880962155
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_cmo_acc",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 6.91342757386671,
        "selected_median": 4.730232558139536,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 3.4459006615712955
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.7517617005739474,
        "selected_median": 1.7789120595728907,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.2934026765081428
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.0282661787587686,
        "selected_median": 2.3210084033613576,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.7785162880962155
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h1_donch_pos_d1",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 8.089517783702142,
        "selected_median": 4.660937108494134,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 4.6219908714067275
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.6051116924471778,
        "selected_median": 1.2006379344403297,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.4400526846349124
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.428499584035748,
        "selected_median": 1.6132366273798884,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -3.378282882819236
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "h4_donch_pos_d3",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 5.780995849352429,
        "selected_median": 5.105039787798416,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 2.3134689370570145
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.50729090961484,
        "selected_median": 2.899155987251345,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.5378734674672501
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 6.025537841846311,
        "selected_median": 4.646938775510212,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": 0.2187553749913267
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "causal_dd_high_2h",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 3.5815484239955437,
        "selected_median": 3.2739454094292686,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.11402151170012909
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 1.700072846061089,
        "selected_median": 1.547719336238873,
        "selected_win": 100.0,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -1.3450915310210012
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.920207214862288,
        "selected_median": 3.2383954154727723,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.886575251992696
      },
      "stable_train_cal": false,
      "train_score": -0.12384395171312201
    },
    {
      "feature": "causal_dd_high_24h",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.4973365777270726,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.12384395171312201
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 3.339663926315913,
        "selected_median": 3.2739454094292686,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": -0.12786298597950152
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.051288663037941,
        "selected_median": 1.846463017840683,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.9938757140441492
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 3.2101592551509497,
        "selected_median": 3.069754768392352,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -2.5966232117040344
      },
      "stable_train_cal": false,
      "train_score": -0.12786298597950152
    },
    {
      "feature": "h1_adx",
      "side": "HIGH",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.3971495320575973,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.22403099738259735
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 4.369733248516781,
        "selected_median": 3.998473282442738,
        "selected_win": 100.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": 0.9022063362213659
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.182777045605722,
        "selected_median": 2.1259934613714337,
        "selected_win": 83.33333333333334,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.8623873314763681
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 2.5612732832867615,
        "selected_median": 2.807518796992481,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -3.2455091835682226
      },
      "stable_train_cal": false,
      "train_score": -0.22403099738259735
    },
    {
      "feature": "h4_roc12",
      "side": "LOW",
      "DISCOVERY": {
        "groups": 4,
        "selected_mean": 3.3971495320575973,
        "selected_median": 3.3915454109583076,
        "selected_win": 100.0,
        "all_group_event_mean": 3.6211805294401946,
        "delta_mean": -0.22403099738259735
      },
      "CALIBRATION": {
        "groups": 5,
        "selected_mean": 3.4450226515393894,
        "selected_median": 3.2739454094292686,
        "selected_win": 80.0,
        "all_group_event_mean": 3.4675269122954147,
        "delta_mean": -0.022504260756025296
      },
      "CROSS_HOLDOUT_PRE2026": {
        "groups": 6,
        "selected_mean": 2.3718798763267146,
        "selected_median": 0.9829380411507385,
        "selected_win": 66.66666666666666,
        "all_group_event_mean": 3.04516437708209,
        "delta_mean": -0.6732845007553756
      },
      "FINAL_HOLDOUT_2026": {
        "groups": 3,
        "selected_mean": 4.5617524685616235,
        "selected_median": 3.047794707297502,
        "selected_win": 100.0,
        "all_group_event_mean": 5.806782466854984,
        "delta_mean": -1.2450299982933606
      },
      "stable_train_cal": false,
      "train_score": -0.22403099738259735
    }
  ]
}