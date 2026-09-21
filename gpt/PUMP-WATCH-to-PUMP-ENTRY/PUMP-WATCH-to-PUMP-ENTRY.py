"""PUMP WATCH -> PUMP ENTRY research candidate.

Status: RESEARCH CANDIDATE, NOT production/final.
Source: Phase-2 1H motion WATCH research currently running.
This file is intentionally conservative: it stores the current motion-WATCH
feature and scoring logic, and is upgraded only after verified validation
improves. It does not use future candles to make a signal decision.
"""

def motion_watch(feature, params):
    """Return True when the current CLOSED 1H candle completes a WATCH setup.

    Expected feature keys are generated from candles at or before the decision
    timestamp: hl2, approach, dist, pb, touches, obva, maca, rvt, comp, es,
    trend. No forward high/low is an input.
    """
    score = 0
    score += feature["hl2"] >= params["hl"]
    score += feature["approach"] >= params["approach"] and feature["dist"] <= params["dist"]
    score += feature["pb"] <= params["pb"]
    score += feature["touches"] >= params["touches"]
    score += feature["obva"] > 0
    score += feature["maca"] >= params["maca"]
    score += feature["rvt"] >= params["rvt"]
    score += feature["comp"] <= params["comp"]

    return (
        score >= params["need"]
        and feature["es"] > 0
        and feature["trend"] > -0.06
    )


# Parameter values are deliberately NOT frozen here while Phase-2 is still
# running. A verified validation winner will be written here after the artifact
# is inspected. This prevents an unverified grid candidate being presented as
# the current best signal system.
BEST_PARAMS = None
