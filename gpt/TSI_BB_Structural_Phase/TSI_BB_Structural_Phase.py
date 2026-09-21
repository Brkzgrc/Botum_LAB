"""Canonical TSI+BB Structural Phase signal-system definition.

This file is the single promoted signal definition for this research project.
Update it only when research produces a demonstrably better accepted system.

Current promoted system: frozen TSI+BB r2.
Phase 11 is recorded as the best expansion candidate so far, but is NOT
promoted because 2026 frequency is 3.74 signals/week (< 5/week target).

All percentage inputs below use percentage points, exactly as research data.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Any

SYSTEM_VERSION = "2026-09-21-r2"
SYSTEM_STATUS = "PROMOTED_CORE"
ROUND_TRIP_COST_PCT = 0.20

# Frozen parent + r2 thresholds. Do not retune using 2026.
BTC1_TSI_D1_MAX = -0.211069
BTC4_BB_WIDTH_MIN = 0.0942267
ALT4_BB_WIDTH_MIN = 0.19233492
CAUSAL_DD_HIGH_48H_MAX = -7.3594696

# Best research expansion so far. Kept here for provenance, not live promotion.
PHASE11_CANDIDATE = {
    "status": "RESEARCH_ONLY_NOT_PROMOTED",
    "workflow_run": 35647958921,
    "selected_families": [
        "TSI_DEEP_LB48_P168_Q950",
        "TSI_DEEP_LB48_P12_Q925",
        "TSI_DEEP_LB48_P72_Q950",
        "TSI_DEEP_LB48_P72_Q925",
        "TSI_DEEP_LB48_P48_Q900",
    ],
    "signals_per_week_2026": 3.742307692307692,
    "win24": 85.61151079136691,
    "mean24": 3.325016553432881,
    "median24": 3.2055727554179514,
    "pf24": 5.77039257843987,
    "win48": 84.89208633093526,
    "mean48": 4.9701186317128885,
    "median48": 4.614814814814805,
    "pf48": 8.019959732424324,
}

@dataclass(frozen=True)
class SignalDecision:
    signal: bool
    system: str
    reason: str


def is_r2_signal(
    btc1_tsi_d1: float,
    btc4_bb_width: float,
    alt4_bb_width: float,
    causal_dd_high_48h: float,
) -> bool:
    """Return True only when the frozen promoted r2 entry conditions pass."""
    return (
        btc1_tsi_d1 <= BTC1_TSI_D1_MAX
        and btc4_bb_width >= BTC4_BB_WIDTH_MIN
        and alt4_bb_width >= ALT4_BB_WIDTH_MIN
        and causal_dd_high_48h <= CAUSAL_DD_HIGH_48H_MAX
    )


def evaluate(features: Mapping[str, Any]) -> SignalDecision:
    """Evaluate one already-causal feature row.

    Required keys:
      btc1_tsi_d1
      btc4_bb_width
      h4_bb_width
      causal_dd_high_48h

    Feature construction must use only information available at decision time.
    """
    required = (
        "btc1_tsi_d1",
        "btc4_bb_width",
        "h4_bb_width",
        "causal_dd_high_48h",
    )
    missing = [k for k in required if k not in features]
    if missing:
        raise KeyError("Missing required causal features: " + ", ".join(missing))

    ok = is_r2_signal(
        float(features["btc1_tsi_d1"]),
        float(features["btc4_bb_width"]),
        float(features["h4_bb_width"]),
        float(features["causal_dd_high_48h"]),
    )
    return SignalDecision(
        signal=ok,
        system=SYSTEM_VERSION,
        reason="frozen_tsi_bb_r2_pass" if ok else "frozen_tsi_bb_r2_fail",
    )


if __name__ == "__main__":
    print(
        f"{SYSTEM_VERSION} | {SYSTEM_STATUS} | "
        f"TSI<={BTC1_TSI_D1_MAX} | BTC4_BB>={BTC4_BB_WIDTH_MIN} | "
        f"ALT4_BB>={ALT4_BB_WIDTH_MIN} | DD48<={CAUSAL_DD_HIGH_48H_MAX}"
    )
