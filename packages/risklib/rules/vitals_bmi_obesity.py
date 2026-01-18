from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef

RULE_ID = "vitals_bmi_obesity"
SEVERITY = "medium"

LOINC_SYSTEM = "http://loinc.org"
BMI_CODE = "39156-5"

LAST_DEBUG_REASON: Optional[str] = None


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _obs_sources(obs) -> list[SourceRef]:
    return obs.sources or []


def run(chart: PatientChart) -> list[dict]:
    global LAST_DEBUG_REASON
    LAST_DEBUG_REASON = None

    candidates: list[tuple[datetime, float, object]] = []
    total = 0
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code != BMI_CODE:
            continue
        total += 1
        if obs.value is None:
            continue
        date = _obs_date(obs)
        if not date:
            continue
        candidates.append((date, float(obs.value), obs))

    if total == 0:
        LAST_DEBUG_REASON = "no BMI obs"
        return []
    if not candidates:
        LAST_DEBUG_REASON = "no numeric/date"
        return []

    candidates.sort(key=lambda item: item[0])
    date, value, obs = candidates[-1]

    if value >= 40:
        severity = "high"
        message = f"BMI in obesity class III: {value} on {date.date()}"
    elif value >= 30:
        severity = SEVERITY
        message = f"BMI in obesity range: {value} on {date.date()}"
    else:
        LAST_DEBUG_REASON = "normal"
        return []

    return [
        {
            "rule_id": RULE_ID,
            "severity": severity,
            "message": message,
            "evidence": _obs_sources(obs),
        }
    ]
