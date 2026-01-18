from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef

RULE_ID = "lab_a1c_elevated"
SEVERITY = "medium"

LOINC_SYSTEM = "http://loinc.org"
A1C_CODES = {"4548-4"}

LAST_DEBUG_REASON: Optional[str] = None


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _obs_sources(obs) -> list[SourceRef]:
    return obs.sources or []


def run(chart: PatientChart) -> list[dict]:
    global LAST_DEBUG_REASON
    LAST_DEBUG_REASON = None

    candidates: list[tuple[datetime, float, Optional[str], object]] = []
    total = 0
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM:
            continue
        if obs.code not in A1C_CODES:
            continue
        total += 1
        if obs.value is None:
            continue
        date = _obs_date(obs)
        if not date:
            continue
        candidates.append((date, obs.value, obs.unit, obs))

    if total == 0:
        LAST_DEBUG_REASON = "no a1c observations"
        return []
    if not candidates:
        LAST_DEBUG_REASON = "no dated numeric values"
        return []

    candidates.sort(key=lambda item: item[0])
    date, value, unit, obs = candidates[-1]
    evidence = _obs_sources(obs)
    unit_text = f" {unit}" if unit else ""

    if value >= 6.5:
        return [
            {
                "rule_id": RULE_ID,
                "severity": "high",
                "message": f"A1c in diabetes range: {value}{unit_text} on {date.date()}",
                "evidence": evidence,
            }
        ]
    if 5.7 <= value < 6.5:
        return [
            {
                "rule_id": RULE_ID,
                "severity": SEVERITY,
                "message": f"A1c in prediabetes range: {value}{unit_text} on {date.date()}",
                "evidence": evidence,
            }
        ]

    LAST_DEBUG_REASON = "value normal"
    return []
