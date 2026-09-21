# Early Reversal Refinement

Status: DEV_STABLE_REFINEMENT_HOLDOUT_EVALUATED
Events: 2,766 | Symbols: 406 | Features: 102 | Gates: 546

## Champion
{
  "gates": [
    {
      "feature": "stoch_spread",
      "op": "<=",
      "threshold": 22.222222222222328,
      "quantile": 0.8
    },
    {
      "feature": "ret_6p",
      "op": "<=",
      "threshold": 5.459877626737104,
      "quantile": 0.8
    }
  ],
  "gate_text": [
    "stoch_spread<=22.222222",
    "ret_6p<=5.4598776"
  ],
  "selection": {
    "score": 1.247004395064694,
    "plan": "TP5_SL3",
    "keep_discovery": 0.5862595419847328,
    "keep_calibration": 0.6998556998556998,
    "discovery": {
      "n": 384,
      "mean": 0.9657921435398441,
      "median": 4.5144522144522,
      "win": 52.864583333333336,
      "pf": 1.6452038641337476,
      "target_first": 50.0,
      "stop_first": 46.61458333333333
    },
    "calibration": {
      "n": 485,
      "mean": 1.1644293931361573,
      "median": 4.325547445255462,
      "win": 56.08247422680412,
      "pf": 1.8506374120674602,
      "target_first": 49.69072164948454,
      "stop_first": 41.649484536082475
    },
    "improvement_discovery": 0.7490657964910357,
    "improvement_calibration": 0.476688653029924
  },
  "evaluation": {
    "DISCOVERY": {
      "metrics": {
        "n": 384,
        "mean": 0.9657921435398441,
        "median": 4.5144522144522,
        "win": 52.864583333333336,
        "pf": 1.6452038641337476,
        "target_first": 50.0,
        "stop_first": 46.61458333333333
      },
      "frequency": {
        "signals": 384,
        "signals_per_day": 0.5253077975376197,
        "active_days": 227,
        "active_day_share_pct": 31.053351573187417,
        "median_on_active_day": 1.0,
        "p90_on_active_day": 2.0,
        "max_in_day": 74
      }
    },
    "CALIBRATION": {
      "metrics": {
        "n": 485,
        "mean": 1.1644293931361573,
        "median": 4.325547445255462,
        "win": 56.08247422680412,
        "pf": 1.8506374120674602,
        "target_first": 49.69072164948454,
        "stop_first": 41.649484536082475
      },
      "frequency": {
        "signals": 485,
        "signals_per_day": 1.3287671232876712,
        "active_days": 163,
        "active_day_share_pct": 44.657534246575345,
        "median_on_active_day": 1.0,
        "p90_on_active_day": 4.0,
        "max_in_day": 90
      }
    },
    "CROSS_HOLDOUT_PRE2026": {
      "metrics": {
        "n": 472,
        "mean": 0.9826494434247127,
        "median": 3.792324416971926,
        "win": 53.38983050847458,
        "pf": 1.6670767210196393,
        "target_first": 49.36440677966102,
        "stop_first": 45.76271186440678
      },
      "frequency": {
        "signals": 472,
        "signals_per_day": 0.4306569343065693,
        "active_days": 233,
        "active_day_share_pct": 21.259124087591243,
        "median_on_active_day": 1.0,
        "p90_on_active_day": 2.0,
        "max_in_day": 57
      }
    },
    "FINAL_HOLDOUT_2026": {
      "metrics": {
        "n": 90,
        "mean": -0.32106675314970984,
        "median": -3.2,
        "win": 35.55555555555556,
        "pf": 0.8377888278691922,
        "target_first": 34.44444444444444,
        "stop_first": 60.0
      },
      "frequency": {
        "signals": 90,
        "signals_per_day": 0.34615384615384615,
        "active_days": 73,
        "active_day_share_pct": 28.076923076923077,
        "median_on_active_day": 1.0,
        "p90_on_active_day": 2.0,
        "max_in_day": 5
      }
    },
    "ALL_2026": {
      "metrics": {
        "n": 382,
        "mean": -0.23531829447299057,
        "median": -3.2,
        "win": 37.696335078534034,
        "pf": 0.8785897547733965,
        "target_first": 34.81675392670157,
        "stop_first": 59.947643979057595
      },
      "frequency": {
        "signals": 382,
        "signals_per_day": 1.4692307692307693,
        "active_days": 186,
        "active_day_share_pct": 71.53846153846153,
        "median_on_active_day": 2.0,
        "p90_on_active_day": 4.0,
        "max_in_day": 11
      }
    }
  },
  "retained_events": 1723
}

## Winner/Loser profile
[
  {
    "feature": "h4_trend_score",
    "winner_median": 0.0,
    "loser_median": 2.0,
    "median_delta_iqr": -0.6666666666666666,
    "abs_delta": 0.6666666666666666
  },
  {
    "feature": "mom_accel_15m",
    "winner_median": 4.0,
    "loser_median": 2.0,
    "median_delta_iqr": 0.5,
    "abs_delta": 0.5
  },
  {
    "feature": "h4_rsi",
    "winner_median": 42.86325521219962,
    "loser_median": 54.25925909542499,
    "median_delta_iqr": -0.4406365310088701,
    "abs_delta": 0.4406365310088701
  },
  {
    "feature": "h4_ema50_dist_pct",
    "winner_median": -5.727964651027939,
    "loser_median": 4.550113008854884,
    "median_delta_iqr": -0.42497560682737223,
    "abs_delta": 0.42497560682737223
  },
  {
    "feature": "h4_ema50_d1",
    "winner_median": -0.2332491519207002,
    "loser_median": 0.1860644551769263,
    "median_delta_iqr": -0.42435685580813354,
    "abs_delta": 0.42435685580813354
  },
  {
    "feature": "h4_di_spread",
    "winner_median": -4.345834252739788,
    "loser_median": 11.513884438769509,
    "median_delta_iqr": -0.41053280345127297,
    "abs_delta": 0.41053280345127297
  },
  {
    "feature": "h4_ema20_dist_pct",
    "winner_median": -3.1783416678980325,
    "loser_median": 1.976424171768354,
    "median_delta_iqr": -0.369110492300872,
    "abs_delta": 0.369110492300872
  },
  {
    "feature": "h4_ema20_d1",
    "winner_median": -0.3334466939666769,
    "loser_median": 0.2084783777704713,
    "median_delta_iqr": -0.36831177481143523,
    "abs_delta": 0.36831177481143523
  },
  {
    "feature": "mom_accel_4h",
    "winner_median": -1.0,
    "loser_median": 0.0,
    "median_delta_iqr": -0.3333333333333333,
    "abs_delta": 0.3333333333333333
  },
  {
    "feature": "h1_di_spread",
    "winner_median": -5.917383622065518,
    "loser_median": 2.4575727487631838,
    "median_delta_iqr": -0.30319653493798776,
    "abs_delta": 0.30319653493798776
  },
  {
    "feature": "stoch_spread_d3",
    "winner_median": 13.191434006443885,
    "loser_median": 19.22795393905865,
    "median_delta_iqr": -0.291281767504865,
    "abs_delta": 0.291281767504865
  },
  {
    "feature": "dd_12h_prev",
    "winner_median": -6.8837475007140885,
    "loser_median": -8.532718362640523,
    "median_delta_iqr": 0.27484199249638563,
    "abs_delta": 0.27484199249638563
  },
  {
    "feature": "stoch_spread",
    "winner_median": 13.994544829230197,
    "loser_median": 17.530035781501944,
    "median_delta_iqr": -0.2722038838234235,
    "abs_delta": 0.2722038838234235
  },
  {
    "feature": "ret_3p",
    "winner_median": 3.472222222222232,
    "loser_median": 4.286892003297615,
    "median_delta_iqr": -0.2636820182435842,
    "abs_delta": 0.2636820182435842
  },
  {
    "feature": "h1_ema50_dist_pct",
    "winner_median": -2.4531642940601173,
    "loser_median": 0.2653167416757807,
    "median_delta_iqr": -0.2621368919367168,
    "abs_delta": 0.2621368919367168
  },
  {
    "feature": "h1_ema50_d1",
    "winner_median": -0.1000289966706313,
    "loser_median": 0.0108304276168702,
    "median_delta_iqr": -0.26200642016436576,
    "abs_delta": 0.26200642016436576
  },
  {
    "feature": "h1_di_spread_d3",
    "winner_median": -2.3132588700782284,
    "loser_median": -4.794174676504408,
    "median_delta_iqr": 0.2583360229132858,
    "abs_delta": 0.2583360229132858
  },
  {
    "feature": "h4_mom_score",
    "winner_median": 1.0,
    "loser_median": 2.0,
    "median_delta_iqr": -0.25,
    "abs_delta": 0.25
  },
  {
    "feature": "h1_stoch_spread",
    "winner_median": -1.8103077898352993,
    "loser_median": -4.215970503872319,
    "median_delta_iqr": 0.21185250203651484,
    "abs_delta": 0.21185250203651484
  },
  {
    "feature": "di_spread_d3",
    "winner_median": 13.687879225037316,
    "loser_median": 16.51382985003083,
    "median_delta_iqr": -0.2062446851078529,
    "abs_delta": 0.2062446851078529
  },
  {
    "feature": "h1_rsi",
    "winner_median": 45.323492404766775,
    "loser_median": 48.60028845631247,
    "median_delta_iqr": -0.18685728537989466,
    "abs_delta": 0.18685728537989466
  },
  {
    "feature": "ret_2h_prev",
    "winner_median": -2.6798307475317307,
    "loser_median": -2.5123849964614364,
    "median_delta_iqr": -0.18526612973229656,
    "abs_delta": 0.18526612973229656
  },
  {
    "feature": "close_loc",
    "winner_median": 0.9142857142857136,
    "loser_median": 0.8865671641791039,
    "median_delta_iqr": 0.18057769355846598,
    "abs_delta": 0.18057769355846598
  },
  {
    "feature": "ema50_dist_pct",
    "winner_median": 1.7652213591604404,
    "loser_median": 2.522970296875915,
    "median_delta_iqr": -0.17715955225958663,
    "abs_delta": 0.17715955225958663
  },
  {
    "feature": "ema50_d1",
    "winner_median": 0.0721018006345053,
    "loser_median": 0.1030845342471664,
    "median_delta_iqr": -0.17710407598315997,
    "abs_delta": 0.17710407598315997
  }
]