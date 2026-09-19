# r2 Portfolio Realism

{
  "purpose": "Translate frozen r2 event returns into constrained portfolio behavior without changing signal thresholds.",
  "events": 225,
  "symbols": 159,
  "overlap_24h": {
    "median": 0.0,
    "p90": 0.0,
    "max": 74,
    "pct_entries_with_existing_position": 5.777777777777778,
    "pct_entries_with_3plus_existing": 4.888888888888889
  },
  "all_period_stats": {
    "day": {
      "periods": 30,
      "signals_median": 1.5,
      "signals_p90": 22.000000000000014,
      "max_signals": 75,
      "positive_period_pct": 63.33333333333333
    },
    "week": {
      "periods": 21,
      "signals_median": 3.0,
      "signals_p90": 32.0,
      "max_signals": 77,
      "positive_period_pct": 76.19047619047619
    },
    "month": {
      "periods": 16,
      "signals_median": 4.5,
      "signals_p90": 36.0,
      "max_signals": 77,
      "positive_period_pct": 87.5
    }
  },
  "split_results": {
    "DISCOVERY": {
      "events": 27,
      "period_stats": {
        "day": {
          "periods": 9,
          "signals_median": 2.0,
          "signals_p90": 5.200000000000002,
          "max_signals": 14,
          "positive_period_pct": 77.77777777777779
        },
        "week": {
          "periods": 8,
          "signals_median": 2.0,
          "signals_p90": 6.299999999999998,
          "max_signals": 14,
          "positive_period_pct": 75.0
        },
        "month": {
          "periods": 7,
          "signals_median": 2.0,
          "signals_p90": 8.200000000000005,
          "max_signals": 16,
          "positive_period_pct": 85.71428571428571
        }
      },
      "scenarios": [
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 9,
          "skipped_slots": 18,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 131.39509834819287,
          "total_return_pct": 31.395098348192874,
          "max_drawdown_pct": -4.251029543419871
        },
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 9,
          "skipped_slots": 18,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 131.39509834819287,
          "total_return_pct": 31.395098348192874,
          "max_drawdown_pct": -4.251029543419871
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 14,
          "skipped_slots": 13,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 118.10638480874015,
          "total_return_pct": 18.10638480874014,
          "max_drawdown_pct": -2.2769065193038007
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 14,
          "skipped_slots": 13,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 118.10638480874015,
          "total_return_pct": 18.10638480874014,
          "max_drawdown_pct": -2.2769065193038007
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 16,
          "skipped_slots": 11,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 114.78295584318457,
          "total_return_pct": 14.782955843184563,
          "max_drawdown_pct": -1.5195903979090541
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 16,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 11,
          "final_equity": 114.78295584318457,
          "total_return_pct": 14.782955843184563,
          "max_drawdown_pct": -1.5195903979090541
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 18,
          "skipped_slots": 9,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 111.15906355527625,
          "total_return_pct": 11.15906355527625,
          "max_drawdown_pct": -0.9125490996590435
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 16,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 11,
          "final_equity": 108.6993109010239,
          "total_return_pct": 8.699310901023916,
          "max_drawdown_pct": -0.9125490996590435
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 23,
          "skipped_slots": 4,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.81059646327276,
          "total_return_pct": 7.8105964632727565,
          "max_drawdown_pct": -4.279438341439334
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 16,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 11,
          "final_equity": 104.28648115924848,
          "total_return_pct": 4.286481159248479,
          "max_drawdown_pct": -0.456573077720801
        }
      ]
    },
    "CALIBRATION": {
      "events": 48,
      "period_stats": {
        "day": {
          "periods": 9,
          "signals_median": 2.0,
          "signals_p90": 11.600000000000003,
          "max_signals": 26,
          "positive_period_pct": 77.77777777777779
        },
        "week": {
          "periods": 8,
          "signals_median": 3.5,
          "signals_p90": 13.399999999999997,
          "max_signals": 26,
          "positive_period_pct": 75.0
        },
        "month": {
          "periods": 5,
          "signals_median": 8.0,
          "signals_p90": 19.200000000000003,
          "max_signals": 26,
          "positive_period_pct": 80.0
        }
      },
      "scenarios": [
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 9,
          "skipped_slots": 39,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 131.3405942370406,
          "total_return_pct": 31.340594237040587,
          "max_drawdown_pct": -6.367261343978726
        },
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 9,
          "skipped_slots": 39,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 131.3405942370406,
          "total_return_pct": 31.340594237040587,
          "max_drawdown_pct": -6.367261343978726
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 14,
          "skipped_slots": 34,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 137.1585833993966,
          "total_return_pct": 37.15858339939659,
          "max_drawdown_pct": -3.197553858948776
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 14,
          "skipped_slots": 34,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 137.1585833993966,
          "total_return_pct": 37.15858339939659,
          "max_drawdown_pct": -3.197553858948776
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 18,
          "skipped_slots": 30,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 129.54959177861235,
          "total_return_pct": 29.54959177861236,
          "max_drawdown_pct": -6.817403983586501
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 18,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 129.54959177861235,
          "total_return_pct": 29.54959177861236,
          "max_drawdown_pct": -6.817403983586501
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 24,
          "skipped_slots": 24,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 121.59495912941452,
          "total_return_pct": 21.594959129414516,
          "max_drawdown_pct": -4.222581173458728
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 18,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 117.01615161834205,
          "total_return_pct": 17.016151618342047,
          "max_drawdown_pct": -4.222581173458739
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 32,
          "skipped_slots": 16,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 111.09078214767729,
          "total_return_pct": 11.090782147677292,
          "max_drawdown_pct": -1.187788820610125
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 18,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 108.24927931115641,
          "total_return_pct": 8.249279311156421,
          "max_drawdown_pct": -2.1637134863024543
        }
      ]
    },
    "CROSS_HOLDOUT_PRE2026": {
      "events": 40,
      "period_stats": {
        "day": {
          "periods": 14,
          "signals_median": 1.5,
          "signals_p90": 6.100000000000003,
          "max_signals": 12,
          "positive_period_pct": 64.28571428571429
        },
        "week": {
          "periods": 12,
          "signals_median": 2.0,
          "signals_p90": 6.700000000000001,
          "max_signals": 12,
          "positive_period_pct": 66.66666666666666
        },
        "month": {
          "periods": 10,
          "signals_median": 2.5,
          "signals_p90": 7.6999999999999975,
          "max_signals": 14,
          "positive_period_pct": 60.0
        }
      },
      "scenarios": [
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 13,
          "skipped_slots": 27,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.28710129983229,
          "total_return_pct": 7.287101299832277,
          "max_drawdown_pct": -21.92466046288243
        },
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 13,
          "skipped_slots": 27,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.28710129983229,
          "total_return_pct": 7.287101299832277,
          "max_drawdown_pct": -21.92466046288243
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 20,
          "skipped_slots": 20,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 119.77655853777121,
          "total_return_pct": 19.776558537771205,
          "max_drawdown_pct": -10.346441295286702
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 20,
          "skipped_slots": 20,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 119.77655853777121,
          "total_return_pct": 19.776558537771205,
          "max_drawdown_pct": -10.346441295286702
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 25,
          "skipped_slots": 15,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 117.63019053796933,
          "total_return_pct": 17.630190537969327,
          "max_drawdown_pct": -6.958875042035606
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 25,
          "skipped_slots": 1,
          "skipped_symbol": 0,
          "skipped_daily": 14,
          "final_equity": 117.63019053796933,
          "total_return_pct": 17.630190537969327,
          "max_drawdown_pct": -6.958875042035606
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 31,
          "skipped_slots": 9,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 115.13274327981583,
          "total_return_pct": 15.13274327981582,
          "max_drawdown_pct": -4.583723827555608
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 26,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 14,
          "final_equity": 110.95635452307684,
          "total_return_pct": 10.95635452307684,
          "max_drawdown_pct": -4.204723830906709
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 38,
          "skipped_slots": 2,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 110.73277429607116,
          "total_return_pct": 10.732774296071156,
          "max_drawdown_pct": -5.03887276715671
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 26,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 14,
          "final_equity": 105.39612535177359,
          "total_return_pct": 5.396125351773584,
          "max_drawdown_pct": -2.1133864675853653
        }
      ]
    },
    "FINAL_HOLDOUT_2026": {
      "events": 36,
      "period_stats": {
        "day": {
          "periods": 2,
          "signals_median": 18.0,
          "signals_p90": 20.4,
          "max_signals": 21,
          "positive_period_pct": 100.0
        },
        "week": {
          "periods": 2,
          "signals_median": 18.0,
          "signals_p90": 20.4,
          "max_signals": 21,
          "positive_period_pct": 100.0
        },
        "month": {
          "periods": 2,
          "signals_median": 18.0,
          "signals_p90": 20.4,
          "max_signals": 21,
          "positive_period_pct": 100.0
        }
      },
      "scenarios": [
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 2,
          "skipped_slots": 34,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 105.9427684765829,
          "total_return_pct": 5.942768476582905,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 1,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 2,
          "skipped_slots": 34,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 105.9427684765829,
          "total_return_pct": 5.942768476582905,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 4,
          "skipped_slots": 32,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.66422299338932,
          "total_return_pct": 7.664222993389314,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 2,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 4,
          "skipped_slots": 32,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.66422299338932,
          "total_return_pct": 7.664222993389314,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 6,
          "skipped_slots": 30,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.36034056900029,
          "total_return_pct": 7.360340569000279,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 3,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 6,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 107.36034056900029,
          "total_return_pct": 7.360340569000279,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 10,
          "skipped_slots": 26,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.32545214039578,
          "total_return_pct": 7.325452140395772,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 5,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 6,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 104.38488918866094,
          "total_return_pct": 4.384889188660934,
          "max_drawdown_pct": 0.0
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": null,
          "accepted": 20,
          "skipped_slots": 16,
          "skipped_symbol": 0,
          "skipped_daily": 0,
          "final_equity": 107.74011397177391,
          "total_return_pct": 7.740113971773899,
          "max_drawdown_pct": -3.056388536632637
        },
        {
          "max_slots": 10,
          "hold_h": 24,
          "daily_entry_cap": 3,
          "accepted": 6,
          "skipped_slots": 0,
          "skipped_symbol": 0,
          "skipped_daily": 30,
          "final_equity": 102.18070141205327,
          "total_return_pct": 2.1807014120532653,
          "max_drawdown_pct": 0.0
        }
      ]
    }
  }
}