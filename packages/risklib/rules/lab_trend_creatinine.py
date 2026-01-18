from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef

RULE_ID = "lab_trend_creatinine"
SEVERITY = "medium"

LOINC_SYSTEM = "http://loinc.org"
CREATININE_CODES = {"2160-0"}

LAST_DEBUG_REASON: Optional[str] = None


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _obs_unit(obs) -> Optional[str]:
    return obs.unit or None


def _obs_sources(obs) -> list[SourceRef]:
    return obs.sources or []


def run(chart: PatientChart) -> list[dict]:
    global LAST_DEBUG_REASON
    LAST_DEBUG_REASON = None

    candidates = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM:
            continue
        if obs.code not in CREATININE_CODES:
            continue
        if obs.value is None:
            continue
        date = _obs_date(obs)
        if not date:
            continue
        candidates.append((date, obs.value, _obs_unit(obs), obs))

    if not candidates:
        LAST_DEBUG_REASON = "no creatinine observations"
        return []

    candidates.sort(key=lambda item: item[0])
    if len(candidates) < 3:
        LAST_DEBUG_REASON = "insufficient dated numeric values"
        return []

    units = {unit for _, _, unit, _ in candidates}
    if len(units) > 1:
        LAST_DEBUG_REASON = "unit mismatch"
        return []

    first = candidates[0]
    last = candidates[-1]
    recent = candidates[-3:]

    increase_ratio = last[1] / first[1] if first[1] != 0 else None
    monotonic = recent[0][1] < recent[1][1] < recent[2][1]

    if (increase_ratio is not None and increase_ratio >= 1.25) or monotonic:
        evidence = _obs_sources(first[3]) + _obs_sources(recent[1][3]) + _obs_sources(last[3])
        message = (
            f"creatinine increased from {first[1]} on {first[0].date()} "
            f"to {last[1]} on {last[0].date()}"
        )
        return [
            {
                "rule_id": RULE_ID,
                "severity": SEVERITY,
                "message": message,
                "evidence": evidence,
            }
        ]

    LAST_DEBUG_REASON = "trend criteria not met"
    return []