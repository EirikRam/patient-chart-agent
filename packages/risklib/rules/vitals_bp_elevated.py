from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef

RULE_ID = "vitals_bp_elevated"
SEVERITY = "medium"

LOINC_SYSTEM = "http://loinc.org"
BP_PANEL_CODE = "85354-9"
SYSTOLIC_CODE = "8480-6"
DIASTOLIC_CODE = "8462-4"

LAST_DEBUG_REASON: Optional[str] = None


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _obs_sources(obs) -> list[SourceRef]:
    return obs.sources or []


def _parse_component_value(components: list[dict], code: str) -> Optional[float]:
    for component in components or []:
        if component.get("code_system") != LOINC_SYSTEM:
            continue
        if component.get("code") != code:
            continue
        value = component.get("value")
        return value if isinstance(value, (int, float)) else None
    return None


def _parse_bp_from_value_text(value_text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not value_text or "/" not in value_text:
        return None, None
    parts = value_text.split("/")
    if len(parts) < 2:
        return None, None
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None, None


def run(chart: PatientChart) -> list[dict]:
    global LAST_DEBUG_REASON
    LAST_DEBUG_REASON = None

    candidates: list[tuple[datetime, float, float, object]] = []
    total = 0
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM or obs.code != BP_PANEL_CODE:
            continue
        total += 1
        date = _obs_date(obs)
        if not date:
            continue
        systolic = _parse_component_value(obs.components, SYSTOLIC_CODE)
        diastolic = _parse_component_value(obs.components, DIASTOLIC_CODE)
        if systolic is None or diastolic is None:
            s_text, d_text = _parse_bp_from_value_text(obs.value_text)
            systolic = systolic if systolic is not None else s_text
            diastolic = diastolic if diastolic is not None else d_text
        if systolic is None or diastolic is None:
            continue
        candidates.append((date, float(systolic), float(diastolic), obs))

    if total == 0:
        LAST_DEBUG_REASON = "no BP obs"
        return []
    if not candidates:
        LAST_DEBUG_REASON = "cannot parse systolic/diastolic"
        return []

    candidates.sort(key=lambda item: item[0])
    date, systolic, diastolic, obs = candidates[-1]

    severity = None
    if systolic >= 180 or diastolic >= 120:
        severity = "high"
    elif systolic >= 140 or diastolic >= 90:
        severity = "medium"

    if not severity:
        LAST_DEBUG_REASON = "normal"
        return []

    message = f"elevated BP: {systolic:.0f}/{diastolic:.0f} on {date.date()}"
    return [
        {
            "rule_id": RULE_ID,
            "severity": severity,
            "message": message,
            "evidence": _obs_sources(obs),
        }
    ]
