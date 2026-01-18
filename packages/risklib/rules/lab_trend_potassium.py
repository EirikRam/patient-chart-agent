from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef

RULE_ID = "lab_trend_potassium"
SEVERITY = "medium"

LOINC_SYSTEM = "http://loinc.org"
POTASSIUM_CODES = {"6298-4"}

LAST_DEBUG_REASON: Optional[str] = None


def _obs_date(obs) -> Optional[datetime]:
    return obs.effective_dt or obs.effective


def _obs_unit(obs) -> Optional[str]:
    return obs.unit or None


def _obs_sources(obs) -> list[SourceRef]:
    return obs.sources or []


def _unit_matches(unit: Optional[str], token: str) -> bool:
    if not unit:
        return False
    return token in unit.lower()


def _collect_candidates(chart: PatientChart) -> tuple[list[tuple[datetime, float, Optional[str], object]], int]:
    total = 0
    usable: list[tuple[datetime, float, Optional[str], object]] = []
    for obs in chart.observations:
        if obs.code_system != LOINC_SYSTEM:
            continue
        if obs.code not in POTASSIUM_CODES:
            continue
        total += 1
        if obs.value is None:
            continue
        date = _obs_date(obs)
        if not date:
            continue
        usable.append((date, obs.value, _obs_unit(obs), obs))
    return usable, total


def _unit_set(items: list[tuple[datetime, float, Optional[str], object]]) -> set[str]:
    units = {unit for _, _, unit, _ in items if unit}
    return units


def _evidence_three(items: list[tuple[datetime, float, Optional[str], object]], index: int) -> list[SourceRef]:
    if not items:
        return []
    indices = {index}
    if index - 1 >= 0:
        indices.add(index - 1)
    if index + 1 < len(items):
        indices.add(index + 1)
    while len(indices) < 3 and indices:
        if min(indices) > 0:
            indices.add(min(indices) - 1)
        if len(indices) < 3 and max(indices) + 1 < len(items):
            indices.add(max(indices) + 1)
    evidence: list[SourceRef] = []
    for idx in sorted(indices)[:3]:
        evidence.extend(_obs_sources(items[idx][3]))
    return evidence


def run(chart: PatientChart) -> list[dict]:
    global LAST_DEBUG_REASON
    LAST_DEBUG_REASON = None

    candidates, total = _collect_candidates(chart)
    if total == 0:
        LAST_DEBUG_REASON = "no potassium observations"
        return []

    candidates.sort(key=lambda item: item[0])
    if len(candidates) < 3:
        LAST_DEBUG_REASON = f"insufficient dated numeric values (total={total}, usable={len(candidates)})"
        return []

    units = _unit_set(candidates)
    if len(units) > 1:
        LAST_DEBUG_REASON = f"unit mismatch (units={sorted(units)})"
        return []

    unit = candidates[0][2]

    # Abnormal threshold in mmol/L.
    if _unit_matches(unit, "mmol"):
        for idx, (_, value, _, _) in enumerate(candidates):
            if value < 3.0 or value > 5.5:
                evidence = _evidence_three(candidates, idx)
                message = f"potassium out of range: {value} {unit or ''}".strip()
                return [
                    {
                        "rule_id": RULE_ID,
                        "severity": "high",
                        "message": message,
                        "evidence": evidence,
                    }
                ]

    first = candidates[0]
    last = candidates[-1]
    recent = candidates[-3:]

    if abs(last[1] - first[1]) >= 0.8:
        evidence = _obs_sources(first[3]) + _obs_sources(recent[1][3]) + _obs_sources(last[3])
        message = (
            f"potassium changed from {first[1]} on {first[0].date()} "
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

    mono_inc = recent[0][1] < recent[1][1] < recent[2][1]
    mono_dec = recent[0][1] > recent[1][1] > recent[2][1]
    if mono_inc or mono_dec:
        evidence = _obs_sources(recent[0][3]) + _obs_sources(recent[1][3]) + _obs_sources(recent[2][3])
        message = (
            f"potassium trend from {recent[0][1]} on {recent[0][0].date()} "
            f"to {recent[2][1]} on {recent[2][0].date()}"
        )
        return [
            {
                "rule_id": RULE_ID,
                "severity": SEVERITY,
                "message": message,
                "evidence": evidence,
            }
        ]

    LAST_DEBUG_REASON = (
        f"trend criteria not met (total={total}, usable={len(candidates)})"
    )
    return []