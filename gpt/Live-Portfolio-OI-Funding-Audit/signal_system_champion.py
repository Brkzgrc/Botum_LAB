# -*- coding: utf-8 -*-
"""Research champion signal gate.

This file is the single evolving research candidate for the OI/Funding project.
It does NOT replace or modify production. A rule is promoted here only after
causal validation/holdout evidence is recorded in README.md.

Input: a baseline signal dict already produced by the live-parity replay.
Output: keep/veto decision plus an auditable reason.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

CHAMPION_VERSION = "2026-09-21-baseline"
STATUS = "BASELINE_NO_OI_FUNDING_VETO"

@dataclass(frozen=True)
class Decision:
    keep: bool
    reason: str
    version: str = CHAMPION_VERSION

def signal_decision(signal: dict[str, Any]) -> Decision:
    """Current champion: preserve every production-baseline signal.

    OI/Funding thresholds are deliberately NOT enabled yet. The active research
    must first demonstrate robust improvement on validation + untouched final
    holdout. This prevents an in-sample threshold from silently becoming the
    'best signal system'.
    """
    return Decision(
        keep=True,
        reason="BASELINE: no validated OI/Funding veto promoted yet",
    )

def apply(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[]
    for s in signals:
        d=signal_decision(s)
        row=dict(s)
        row["research_champion_keep"]=d.keep
        row["research_champion_reason"]=d.reason
        row["research_champion_version"]=d.version
        if d.keep:
            out.append(row)
    return out
