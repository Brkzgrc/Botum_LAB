# r2 BTC Regime Filter

{
  "purpose": "BTC-only regime gate discovery on frozen r2. Selection uses Discovery+Calibration; holdouts diagnostic only.",
  "features": 134,
  "rules": 1072,
  "stable_rules": 39,
  "base": {
    "DISCOVERY": {
      "n": 27,
      "mean24": 3.400172271386731,
      "median24": 4.024854162983904,
      "win24": 88.88888888888889,
      "q10": 0.24009324009325128,
      "danger": 33.33333333333333
    },
    "CALIBRATION": {
      "n": 48,
      "mean24": 3.4795206061411186,
      "median24": 3.2987176711575805,
      "win24": 85.41666666666666,
      "q10": -0.7475557917109562,
      "danger": 27.083333333333332
    },
    "CROSS_HOLDOUT_PRE2026": {
      "n": 40,
      "mean24": 2.7599377848894653,
      "median24": 3.1100111978474283,
      "win24": 80.0,
      "q10": -1.3878101252645934,
      "danger": 45.0
    },
    "FINAL_HOLDOUT_2026": {
      "n": 36,
      "mean24": 5.806782466854984,
      "median24": 3.489224799467172,
      "win24": 97.22222222222221,
      "q10": 1.5117030594526628,
      "danger": 16.666666666666664
    }
  },
  "champion_selected_without_holdouts": {
    "feature": "btc1_di_spread",
    "q": 0.9,
    "threshold": 4.790830741816574,
    "side": "KEEP_BELOW",
    "DISCOVERY": {
      "n": 23,
      "mean24": 4.363109485349092,
      "median24": 4.698074745186864,
      "win24": 100.0,
      "q10": 2.234965304136791,
      "danger": 34.78260869565217
    },
    "DISCOVERY_keep": 0.8518518518518519,
    "CALIBRATION": {
      "n": 38,
      "mean24": 4.107559651967565,
      "median24": 3.60194892232355,
      "win24": 92.10526315789474,
      "q10": 0.3556087551299505,
      "danger": 10.526315789473683
    },
    "CALIBRATION_keep": 0.7916666666666666,
    "CROSS_HOLDOUT_PRE2026": {
      "n": 34,
      "mean24": 3.1587181086328173,
      "median24": 3.2783470092797806,
      "win24": 88.23529411764706,
      "q10": -0.32490769212402193,
      "danger": 41.17647058823529
    },
    "CROSS_HOLDOUT_PRE2026_keep": 0.85,
    "FINAL_HOLDOUT_2026": {
      "n": 36,
      "mean24": 5.806782466854984,
      "median24": 3.489224799467172,
      "win24": 97.22222222222221,
      "q10": 1.5117030594526628,
      "danger": 16.666666666666664
    },
    "FINAL_HOLDOUT_2026_keep": 1.0,
    "stable_train_cal": true,
    "train_score": 1.097027218352522,
    "name": "btc1_di_spread:KEEP_BELOW:Q90"
  },
  "top20": [
    {
      "feature": "btc1_di_spread",
      "q": 0.9,
      "threshold": 4.790830741816574,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 23,
        "mean24": 4.363109485349092,
        "median24": 4.698074745186864,
        "win24": 100.0,
        "q10": 2.234965304136791,
        "danger": 34.78260869565217
      },
      "DISCOVERY_keep": 0.8518518518518519,
      "CALIBRATION": {
        "n": 38,
        "mean24": 4.107559651967565,
        "median24": 3.60194892232355,
        "win24": 92.10526315789474,
        "q10": 0.3556087551299505,
        "danger": 10.526315789473683
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 34,
        "mean24": 3.1587181086328173,
        "median24": 3.2783470092797806,
        "win24": 88.23529411764706,
        "q10": -0.32490769212402193,
        "danger": 41.17647058823529
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.85,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 1.097027218352522,
      "name": "btc1_di_spread:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc4_ppo_hist",
      "q": 0.9,
      "threshold": -0.06526960085781977,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 24,
        "mean24": 4.16540416588379,
        "median24": 4.6750728755520115,
        "win24": 95.83333333333334,
        "q10": 1.2822046916087375,
        "danger": 33.33333333333333
      },
      "DISCOVERY_keep": 0.8888888888888888,
      "CALIBRATION": {
        "n": 38,
        "mean24": 4.107559651967565,
        "median24": 3.60194892232355,
        "win24": 92.10526315789474,
        "q10": 0.3556087551299505,
        "danger": 10.526315789473683
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 33,
        "mean24": 3.625015060271373,
        "median24": 3.3405449502365903,
        "win24": 90.9090909090909,
        "q10": 0.23228590464270413,
        "danger": 39.39393939393939
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.825,
      "FINAL_HOLDOUT_2026": {
        "n": 15,
        "mean24": 9.005837553865312,
        "median24": 4.539336492891,
        "win24": 93.33333333333333,
        "q10": 2.1640439241758096,
        "danger": 26.666666666666668
      },
      "FINAL_HOLDOUT_2026_keep": 0.4166666666666667,
      "stable_train_cal": true,
      "train_score": 0.9736541848001563,
      "name": "btc4_ppo_hist:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc1_di_spread",
      "q": 0.8,
      "threshold": -4.99115371238803,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 20,
        "mean24": 4.344473086777691,
        "median24": 4.706949830505891,
        "win24": 100.0,
        "q10": 1.986727069176515,
        "danger": 35.0
      },
      "DISCOVERY_keep": 0.7407407407407407,
      "CALIBRATION": {
        "n": 37,
        "mean24": 3.9421817970380344,
        "median24": 3.5708484408992103,
        "win24": 91.8918918918919,
        "q10": 0.31532147742817446,
        "danger": 10.81081081081081
      },
      "CALIBRATION_keep": 0.7708333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 33,
        "mean24": 3.625015060271373,
        "median24": 3.3405449502365903,
        "win24": 90.9090909090909,
        "q10": 0.23228590464270413,
        "danger": 39.39393939393939
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.825,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.9193244825625798,
      "name": "btc1_di_spread:KEEP_BELOW:Q80"
    },
    {
      "feature": "btc1_rvol20_d1",
      "q": 0.2,
      "threshold": 0.0228742316570938,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 20,
        "mean24": 4.329935969659783,
        "median24": 4.706949830505891,
        "win24": 100.0,
        "q10": 1.986727069176515,
        "danger": 40.0
      },
      "DISCOVERY_keep": 0.7407407407407407,
      "CALIBRATION": {
        "n": 37,
        "mean24": 3.9421817970380344,
        "median24": 3.5708484408992103,
        "win24": 91.8918918918919,
        "q10": 0.31532147742817446,
        "danger": 10.81081081081081
      },
      "CALIBRATION_keep": 0.7708333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 31,
        "mean24": 3.375401199565741,
        "median24": 3.216149068322971,
        "win24": 90.32258064516128,
        "q10": 0.1904644471845353,
        "danger": 38.70967741935484
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.775,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.9193244825625798,
      "name": "btc1_rvol20_d1:KEEP_ABOVE:Q20"
    },
    {
      "feature": "btc4_adx_acc",
      "q": 0.9,
      "threshold": 0.13268011426467882,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 24,
        "mean24": 4.004187025817052,
        "median24": 4.6750728755520115,
        "win24": 95.83333333333334,
        "q10": 1.2822046916087375,
        "danger": 37.5
      },
      "DISCOVERY_keep": 0.8888888888888888,
      "CALIBRATION": {
        "n": 39,
        "mean24": 3.986400305597577,
        "median24": 3.5708484408992103,
        "win24": 89.74358974358975,
        "q10": 0.01887824897401487,
        "danger": 12.82051282051282
      },
      "CALIBRATION_keep": 0.8125,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 35,
        "mean24": 2.6997785542057544,
        "median24": 3.11262939958592,
        "win24": 82.85714285714286,
        "q10": -1.0925025305794396,
        "danger": 42.857142857142854
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.875,
      "FINAL_HOLDOUT_2026": {
        "n": 19,
        "mean24": 7.772003805491675,
        "median24": 4.112056737588654,
        "win24": 94.73684210526315,
        "q10": 1.2590757641605201,
        "danger": 21.052631578947366
      },
      "FINAL_HOLDOUT_2026_keep": 0.5277777777777778,
      "stable_train_cal": true,
      "train_score": 0.7499370447334187,
      "name": "btc4_adx_acc:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc4_er10",
      "q": 0.1,
      "threshold": 0.0866874132490491,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 24,
        "mean24": 3.951473154921364,
        "median24": 4.6750728755520115,
        "win24": 91.66666666666666,
        "q10": 1.2822046916087375,
        "danger": 37.5
      },
      "DISCOVERY_keep": 0.8888888888888888,
      "CALIBRATION": {
        "n": 35,
        "mean24": 4.013763086106507,
        "median24": 3.5708484408992103,
        "win24": 88.57142857142857,
        "q10": -0.09056087551299251,
        "danger": 14.285714285714285
      },
      "CALIBRATION_keep": 0.7291666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 31,
        "mean24": 2.7741141883526543,
        "median24": 3.216149068322971,
        "win24": 80.64516129032258,
        "q10": -1.4569832402234637,
        "danger": 48.38709677419355
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.775,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.6972231738377305,
      "name": "btc4_er10:KEEP_ABOVE:Q10"
    },
    {
      "feature": "btc1_adx_acc",
      "q": 0.1,
      "threshold": -0.4997990293396199,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 23,
        "mean24": 4.363109485349092,
        "median24": 4.698074745186864,
        "win24": 100.0,
        "q10": 2.234965304136791,
        "danger": 34.78260869565217
      },
      "DISCOVERY_keep": 0.8518518518518519,
      "CALIBRATION": {
        "n": 38,
        "mean24": 3.8112471883440504,
        "median24": 3.5463792766293856,
        "win24": 89.47368421052632,
        "q10": -0.008481532147737003,
        "danger": 13.157894736842104
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 37,
        "mean24": 3.0334185755087093,
        "median24": 3.216149068322971,
        "win24": 83.78378378378379,
        "q10": -0.9102621757574278,
        "danger": 40.54054054054054
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.925,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.6884230130629441,
      "name": "btc1_adx_acc:KEEP_ABOVE:Q10"
    },
    {
      "feature": "btc1_adx_acc",
      "q": 0.2,
      "threshold": -0.11769799257001373,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 21,
        "mean24": 4.151069902675587,
        "median24": 4.652071005917158,
        "win24": 100.0,
        "q10": 2.104147465437811,
        "danger": 33.33333333333333
      },
      "DISCOVERY_keep": 0.7777777777777778,
      "CALIBRATION": {
        "n": 38,
        "mean24": 3.8112471883440504,
        "median24": 3.5463792766293856,
        "win24": 89.47368421052632,
        "q10": -0.008481532147737003,
        "danger": 13.157894736842104
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 36,
        "mean24": 2.9399204558417393,
        "median24": 3.1643892339544455,
        "win24": 83.33333333333334,
        "q10": -1.0013823531684338,
        "danger": 41.66666666666667
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.9,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.6884230130629441,
      "name": "btc1_adx_acc:KEEP_ABOVE:Q20"
    },
    {
      "feature": "btc1_rvol20_d1",
      "q": 0.1,
      "threshold": -0.1007668430999272,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 23,
        "mean24": 4.363109485349092,
        "median24": 4.698074745186864,
        "win24": 100.0,
        "q10": 2.234965304136791,
        "danger": 34.78260869565217
      },
      "DISCOVERY_keep": 0.8518518518518519,
      "CALIBRATION": {
        "n": 38,
        "mean24": 3.8112471883440504,
        "median24": 3.5463792766293856,
        "win24": 89.47368421052632,
        "q10": -0.008481532147737003,
        "danger": 13.157894736842104
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 35,
        "mean24": 3.1442942212779865,
        "median24": 3.216149068322971,
        "win24": 85.71428571428571,
        "q10": -0.36838729686393196,
        "danger": 40.0
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.875,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.6884230130629441,
      "name": "btc1_rvol20_d1:KEEP_ABOVE:Q10"
    },
    {
      "feature": "btc4_rvol20_d1",
      "q": 0.8,
      "threshold": 0.006057158252842,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 20,
        "mean24": 4.07321875650487,
        "median24": 4.706949830505891,
        "win24": 95.0,
        "q10": 1.986727069176515,
        "danger": 45.0
      },
      "DISCOVERY_keep": 0.7407407407407407,
      "CALIBRATION": {
        "n": 34,
        "mean24": 3.8188085074263576,
        "median24": 3.5463792766293856,
        "win24": 88.23529411764706,
        "q10": -0.11792065663474438,
        "danger": 14.705882352941178
      },
      "CALIBRATION_keep": 0.7083333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 32,
        "mean24": 3.5236502074152254,
        "median24": 3.5611750891154093,
        "win24": 84.375,
        "q10": -0.501432923801036,
        "danger": 46.875
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.8,
      "FINAL_HOLDOUT_2026": {
        "n": 4,
        "mean24": 3.145127249090546,
        "median24": 1.5117030594526628,
        "win24": 100.0,
        "q10": 0.8813414457482274,
        "danger": 0.0
      },
      "FINAL_HOLDOUT_2026_keep": 0.1111111111111111,
      "stable_train_cal": true,
      "train_score": 0.6508766930063636,
      "name": "btc4_rvol20_d1:KEEP_BELOW:Q80"
    },
    {
      "feature": "btc1_roc12_acc",
      "q": 0.8,
      "threshold": -0.5123205763146177,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 19,
        "mean24": 4.009133896882222,
        "median24": 4.715824915824918,
        "win24": 89.47368421052632,
        "q10": 0.6302881393790452,
        "danger": 36.84210526315789
      },
      "DISCOVERY_keep": 0.7037037037037037,
      "CALIBRATION": {
        "n": 30,
        "mean24": 3.97834223581058,
        "median24": 3.4833849627218365,
        "win24": 90.0,
        "q10": 0.04623803009576675,
        "danger": 13.333333333333334
      },
      "CALIBRATION_keep": 0.625,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 28,
        "mean24": 3.52043872429674,
        "median24": 3.7442865975936823,
        "win24": 82.14285714285714,
        "q10": -0.8191419983464217,
        "danger": 39.285714285714285
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.7,
      "FINAL_HOLDOUT_2026": {
        "n": 4,
        "mean24": 3.145127249090546,
        "median24": 1.5117030594526628,
        "win24": 100.0,
        "q10": 0.8813414457482274,
        "danger": 0.0
      },
      "FINAL_HOLDOUT_2026_keep": 0.1111111111111111,
      "stable_train_cal": true,
      "train_score": 0.6343690264052816,
      "name": "btc1_roc12_acc:KEEP_BELOW:Q80"
    },
    {
      "feature": "btc1_chop14",
      "q": 0.8,
      "threshold": 47.85989017803526,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 21,
        "mean24": 3.8749190138398757,
        "median24": 4.698074745186864,
        "win24": 90.47619047619048,
        "q10": 0.9299435028248484,
        "danger": 38.095238095238095
      },
      "DISCOVERY_keep": 0.7777777777777778,
      "CALIBRATION": {
        "n": 34,
        "mean24": 3.6996571217049556,
        "median24": 3.60194892232355,
        "win24": 94.11764705882352,
        "q10": 0.6588505126821212,
        "danger": 8.823529411764707
      },
      "CALIBRATION_keep": 0.7083333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 30,
        "mean24": 4.016600580565172,
        "median24": 3.364911275663507,
        "win24": 90.0,
        "q10": 0.11683985585474164,
        "danger": 40.0
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.75,
      "FINAL_HOLDOUT_2026": {
        "n": 0
      },
      "FINAL_HOLDOUT_2026_keep": 0.0,
      "stable_train_cal": true,
      "train_score": 0.5412882235708928,
      "name": "btc1_chop14:KEEP_BELOW:Q80"
    },
    {
      "feature": "btc4_er10",
      "q": 0.2,
      "threshold": 0.1627641607060111,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 21,
        "mean24": 3.8749190138398757,
        "median24": 4.698074745186864,
        "win24": 90.47619047619048,
        "q10": 0.9299435028248484,
        "danger": 38.095238095238095
      },
      "DISCOVERY_keep": 0.7777777777777778,
      "CALIBRATION": {
        "n": 35,
        "mean24": 4.013763086106507,
        "median24": 3.5708484408992103,
        "win24": 88.57142857142857,
        "q10": -0.09056087551299251,
        "danger": 14.285714285714285
      },
      "CALIBRATION_keep": 0.7291666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 31,
        "mean24": 2.7741141883526543,
        "median24": 3.216149068322971,
        "win24": 80.64516129032258,
        "q10": -1.4569832402234637,
        "danger": 48.38709677419355
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.775,
      "FINAL_HOLDOUT_2026": {
        "n": 36,
        "mean24": 5.806782466854984,
        "median24": 3.489224799467172,
        "win24": 97.22222222222221,
        "q10": 1.5117030594526628,
        "danger": 16.666666666666664
      },
      "FINAL_HOLDOUT_2026_keep": 1.0,
      "stable_train_cal": true,
      "train_score": 0.5412882235708928,
      "name": "btc4_er10:KEEP_ABOVE:Q20"
    },
    {
      "feature": "btc1_roc12_acc",
      "q": 0.9,
      "threshold": -0.2624061985072479,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 23,
        "mean24": 3.8389658554727455,
        "median24": 4.698074745186864,
        "win24": 91.30434782608695,
        "q10": 0.8926404763076514,
        "danger": 39.130434782608695
      },
      "DISCOVERY_keep": 0.8518518518518519,
      "CALIBRATION": {
        "n": 30,
        "mean24": 3.97834223581058,
        "median24": 3.4833849627218365,
        "win24": 90.0,
        "q10": 0.04623803009576675,
        "danger": 13.333333333333334
      },
      "CALIBRATION_keep": 0.625,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 31,
        "mean24": 3.275986715692271,
        "median24": 3.3892776010904235,
        "win24": 83.87096774193549,
        "q10": -0.545781466113404,
        "danger": 45.16129032258064
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.775,
      "FINAL_HOLDOUT_2026": {
        "n": 4,
        "mean24": 3.145127249090546,
        "median24": 1.5117030594526628,
        "win24": 100.0,
        "q10": 0.8813414457482274,
        "danger": 0.0
      },
      "FINAL_HOLDOUT_2026_keep": 0.1111111111111111,
      "stable_train_cal": true,
      "train_score": 0.4823465095897642,
      "name": "btc1_roc12_acc:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc4_cmo_d1",
      "q": 0.8,
      "threshold": 2.3628846476896825,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 20,
        "mean24": 3.913761387600574,
        "median24": 4.6750728755520115,
        "win24": 95.0,
        "q10": 0.8604533331806044,
        "danger": 25.0
      },
      "DISCOVERY_keep": 0.7407407407407407,
      "CALIBRATION": {
        "n": 31,
        "mean24": 3.6761498811559474,
        "median24": 3.444859813084112,
        "win24": 87.09677419354838,
        "q10": -0.2,
        "danger": 16.129032258064516
      },
      "CALIBRATION_keep": 0.6458333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 27,
        "mean24": 3.818505605628268,
        "median24": 3.7555006180469697,
        "win24": 85.18518518518519,
        "q10": -0.2796902122391962,
        "danger": 40.74074074074074
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.675,
      "FINAL_HOLDOUT_2026": {
        "n": 15,
        "mean24": 9.005837553865312,
        "median24": 4.539336492891,
        "win24": 93.33333333333333,
        "q10": 2.1640439241758096,
        "danger": 26.666666666666668
      },
      "FINAL_HOLDOUT_2026_keep": 0.4166666666666667,
      "stable_train_cal": true,
      "train_score": 0.47045494948605227,
      "name": "btc4_cmo_d1:KEEP_BELOW:Q80"
    },
    {
      "feature": "btc4_cmo_d1",
      "q": 0.9,
      "threshold": 2.835978117575828,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 24,
        "mean24": 3.7544648351985095,
        "median24": 4.3384625844505305,
        "win24": 95.83333333333334,
        "q10": 0.897303354622301,
        "danger": 33.33333333333333
      },
      "DISCOVERY_keep": 0.8888888888888888,
      "CALIBRATION": {
        "n": 31,
        "mean24": 3.6761498811559474,
        "median24": 3.444859813084112,
        "win24": 87.09677419354838,
        "q10": -0.2,
        "danger": 16.129032258064516
      },
      "CALIBRATION_keep": 0.6458333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 30,
        "mean24": 3.53609850860383,
        "median24": 3.5611750891154093,
        "win24": 86.66666666666667,
        "q10": -0.1466445853020922,
        "danger": 46.666666666666664
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.75,
      "FINAL_HOLDOUT_2026": {
        "n": 15,
        "mean24": 9.005837553865312,
        "median24": 4.539336492891,
        "win24": 93.33333333333333,
        "q10": 2.1640439241758096,
        "danger": 26.666666666666668
      },
      "FINAL_HOLDOUT_2026_keep": 0.4166666666666667,
      "stable_train_cal": true,
      "train_score": 0.47045494948605227,
      "name": "btc4_cmo_d1:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc1_chop14",
      "q": 0.9,
      "threshold": 55.01093720095294,
      "side": "KEEP_BELOW",
      "DISCOVERY": {
        "n": 24,
        "mean24": 3.7366279071764037,
        "median24": 4.3384625844505305,
        "win24": 91.66666666666666,
        "q10": 0.897303354622301,
        "danger": 33.33333333333333
      },
      "DISCOVERY_keep": 0.8888888888888888,
      "CALIBRATION": {
        "n": 36,
        "mean24": 4.073808366210008,
        "median24": 3.719596505278522,
        "win24": 94.44444444444444,
        "q10": 0.7804371289800163,
        "danger": 8.333333333333332
      },
      "CALIBRATION_keep": 0.75,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 34,
        "mean24": 3.1825335007410644,
        "median24": 3.2783470092797806,
        "win24": 85.29411764705883,
        "q10": -1.1836227079904456,
        "danger": 38.23529411764706
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.85,
      "FINAL_HOLDOUT_2026": {
        "n": 17,
        "mean24": 3.6103586177904456,
        "median24": 3.2383954154727723,
        "win24": 100.0,
        "q10": 2.7110298828051382,
        "danger": 11.76470588235294
      },
      "FINAL_HOLDOUT_2026_keep": 0.4722222222222222,
      "stable_train_cal": true,
      "train_score": 0.46789765869548283,
      "name": "btc1_chop14:KEEP_BELOW:Q90"
    },
    {
      "feature": "btc1_rvol20_acc",
      "q": 0.2,
      "threshold": 0.1806933863428621,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 19,
        "mean24": 3.708997568856596,
        "median24": 4.698074745186864,
        "win24": 89.47368421052632,
        "q10": 0.4473970473970626,
        "danger": 26.31578947368421
      },
      "DISCOVERY_keep": 0.7037037037037037,
      "CALIBRATION": {
        "n": 33,
        "mean24": 3.9658431086615002,
        "median24": 3.5708484408992103,
        "win24": 90.9090909090909,
        "q10": 0.27575898291896583,
        "danger": 12.121212121212121
      },
      "CALIBRATION_keep": 0.6875,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 24,
        "mean24": 3.8816426550882146,
        "median24": 3.7442865975936823,
        "win24": 87.5,
        "q10": -0.26217550593676875,
        "danger": 37.5
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.6,
      "FINAL_HOLDOUT_2026": {
        "n": 32,
        "mean24": 6.139489369075539,
        "median24": 3.531933152664857,
        "win24": 96.875,
        "q10": 2.36965944272447,
        "danger": 18.75
      },
      "FINAL_HOLDOUT_2026_keep": 0.8888888888888888,
      "stable_train_cal": true,
      "train_score": 0.45554921682536437,
      "name": "btc1_rvol20_acc:KEEP_ABOVE:Q20"
    },
    {
      "feature": "btc1_di_spread_d3",
      "q": 0.2,
      "threshold": -4.517862311523126,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 21,
        "mean24": 3.6568362235460135,
        "median24": 4.652071005917158,
        "win24": 90.47619047619048,
        "q10": 0.6547008547008739,
        "danger": 28.57142857142857
      },
      "DISCOVERY_keep": 0.7777777777777778,
      "CALIBRATION": {
        "n": 34,
        "mean24": 4.29033319918267,
        "median24": 3.60194892232355,
        "win24": 91.17647058823529,
        "q10": 0.3768395687696895,
        "danger": 11.76470588235294
      },
      "CALIBRATION_keep": 0.7083333333333334,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 26,
        "mean24": 3.9807268330257792,
        "median24": 3.7442865975936823,
        "win24": 84.61538461538461,
        "q10": -0.32403875455156417,
        "danger": 34.61538461538461
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.65,
      "FINAL_HOLDOUT_2026": {
        "n": 21,
        "mean24": 3.521743118990465,
        "median24": 3.1898305084745893,
        "win24": 100.0,
        "q10": 1.4101694915254372,
        "danger": 9.523809523809524
      },
      "FINAL_HOLDOUT_2026_keep": 0.5833333333333334,
      "stable_train_cal": true,
      "train_score": 0.41101404650937856,
      "name": "btc1_di_spread_d3:KEEP_ABOVE:Q20"
    },
    {
      "feature": "btc1_cmf_d3",
      "q": 0.1,
      "threshold": -0.0890031421024102,
      "side": "KEEP_ABOVE",
      "DISCOVERY": {
        "n": 22,
        "mean24": 3.602486015490007,
        "median24": 4.6750728755520115,
        "win24": 90.9090909090909,
        "q10": 0.6775622411986217,
        "danger": 31.818181818181817
      },
      "DISCOVERY_keep": 0.8148148148148148,
      "CALIBRATION": {
        "n": 38,
        "mean24": 3.6903722918879978,
        "median24": 3.60194892232355,
        "win24": 89.47368421052632,
        "q10": -0.008481532147737003,
        "danger": 13.157894736842104
      },
      "CALIBRATION_keep": 0.7916666666666666,
      "CROSS_HOLDOUT_PRE2026": {
        "n": 29,
        "mean24": 3.5947470415486618,
        "median24": 3.3892776010904235,
        "win24": 86.20689655172413,
        "q10": -0.1909931276144602,
        "danger": 37.93103448275862
      },
      "CROSS_HOLDOUT_PRE2026_keep": 0.725,
      "FINAL_HOLDOUT_2026": {
        "n": 32,
        "mean24": 6.139489369075539,
        "median24": 3.531933152664857,
        "win24": 96.875,
        "q10": 2.36965944272447,
        "danger": 18.75
      },
      "FINAL_HOLDOUT_2026_keep": 0.8888888888888888,
      "stable_train_cal": true,
      "train_score": 0.3125348170516229,
      "name": "btc1_cmf_d3:KEEP_ABOVE:Q10"
    }
  ]
}