# Outcome Second Family Population Validation

{
  "purpose": "Population validation of the frozen independent second-family screen champion. Threshold is fixed before this run; no selection or tuning occurs here.",
  "rule": {
    "h1_atr_pct_min": 1.58953710752988,
    "entry": "next 15m open",
    "exit": "24h later open",
    "round_trip_cost_pct": 0.2
  },
  "universe": "active Binance Spot USDT, exact stable/fiat base exclusions, BTC excluded",
  "primary_policy": "24h per-symbol cooldown to match independent event logic; raw hourly trigger is diagnostic only",
  "events_raw": 1853978,
  "events_cooldown24": 99410,
  "symbols": 456,
  "periods": {
    "CALIBRATION_2025": {
      "raw_hourly": {
        "metrics": {
          "n": 1180234,
          "symbols": 374,
          "mean24": -0.39938217383687397,
          "median24": -0.6285714285714448,
          "win24": 45.113087743616944,
          "pf24": 0.852252169517301,
          "up3_before_dn2": 37.88358918655114,
          "danger_dn2_first": 60.03343404782442,
          "mfe24": 5.875690893206805,
          "mae24": -5.488815644618211
        },
        "frequency": {
          "calendar_days": 365,
          "signals": 1180234,
          "signals_per_day": 3233.5178082191783,
          "active_days": 365,
          "active_day_share_pct": 100.0,
          "median_on_active_day": 2649.0,
          "p90_on_active_day": 6141.6,
          "max_in_day": 8568
        }
      },
      "cooldown24": {
        "metrics": {
          "n": 62030,
          "symbols": 374,
          "mean24": -0.5267592635967471,
          "median24": -0.7176430027313494,
          "win24": 44.391423504755764,
          "pf24": 0.8057785455159134,
          "up3_before_dn2": 37.47380299854909,
          "danger_dn2_first": 60.24343059809769,
          "mfe24": 5.651832079867151,
          "mae24": -5.542625347793911
        },
        "frequency": {
          "calendar_days": 365,
          "signals": 62030,
          "signals_per_day": 169.94520547945206,
          "active_days": 365,
          "active_day_share_pct": 100.0,
          "median_on_active_day": 151.0,
          "p90_on_active_day": 287.0,
          "max_in_day": 366
        }
      }
    },
    "OOS_2026": {
      "raw_hourly": {
        "metrics": {
          "n": 673744,
          "symbols": 455,
          "mean24": -0.4912370226999285,
          "median24": -0.9611798287345428,
          "win24": 41.539516492911254,
          "pf24": 0.824018632324357,
          "up3_before_dn2": 37.63714407846304,
          "danger_dn2_first": 59.748064546771474,
          "mfe24": 6.490191799529298,
          "mae24": -5.284750151312188
        },
        "frequency": {
          "calendar_days": 260,
          "signals": 673744,
          "signals_per_day": 2591.3230769230768,
          "active_days": 260,
          "active_day_share_pct": 100.0,
          "median_on_active_day": 2132.5,
          "p90_on_active_day": 4029.999999999999,
          "max_in_day": 9035
        }
      },
      "cooldown24": {
        "metrics": {
          "n": 37380,
          "symbols": 455,
          "mean24": -0.4398284847519251,
          "median24": -0.9024902452171688,
          "win24": 41.77367576243981,
          "pf24": 0.8341981503864785,
          "up3_before_dn2": 36.88336008560727,
          "danger_dn2_first": 60.24344569288389,
          "mfe24": 6.24666623548524,
          "mae24": -5.050343763789055
        },
        "frequency": {
          "calendar_days": 260,
          "signals": 37380,
          "signals_per_day": 143.76923076923077,
          "active_days": 260,
          "active_day_share_pct": 100.0,
          "median_on_active_day": 121.0,
          "p90_on_active_day": 241.09999999999994,
          "max_in_day": 389
        }
      }
    }
  },
  "oos2026_symbol_cluster_bootstrap_mean24": {
    "mean": -0.43983017884326436,
    "ci_low": -0.5145216822544738,
    "ci_high": -0.36355435319605006,
    "p_gt_0": 0.0
  }
}