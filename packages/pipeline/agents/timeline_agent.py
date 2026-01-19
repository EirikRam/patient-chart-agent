from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from packages.core.schemas.chart import Encounter, Observation, PatientChart
from packages.core.schemas.result import Evidence, TimelineEntry


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso_date(value: Optional[datetime | str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        parsed = _parse_datetime(value)
        return value if parsed else None
    return None


def _category_label(observation: Observation) -> str:
    category = (observation.category or "").lower()
    if "vital" in category:
        return "VITAL"
    if "lab" in category or "laboratory" in category:
        return "LAB"
    return "OBSERVATION"


def _observation_summary(observation: Observation) -> str:
    label = observation.display or observation.code or "observation"
    value = observation.value_text or (
        f"{observation.value}" if observation.value is not None else ""
    )
    unit = observation.unit or ""
    if value:
        unit_text = f" {unit}".rstrip()
        return f"{label}: {value}{unit_text}".strip()
    return f"{label} observation recorded"


def _encounter_summary(encounter: Encounter) -> str:
    label = encounter.type or encounter.reason or "encounter"
    return f"{label} recorded"


def _evidence(resource_type: str, resource_id: Optional[str]) -> list[Evidence]:
    if resource_id:
        return [
            Evidence(
                doc_id=f"{resource_type}/{resource_id}",
                resource_type=resource_type,
                resource_id=resource_id,
            )
        ]
    return []


def _iter_encounter_entries(
    encounters: Iterable[Encounter],
) -> Iterable[tuple[datetime, TimelineEntry]]:
    for encounter in encounters:
        date_value = encounter.start or encounter.end
        iso_date = _iso_date(date_value)
        if not date_value or not iso_date:
            continue
        date_dt = date_value if isinstance(date_value, datetime) else _parse_datetime(iso_date)
        if not date_dt:
            continue
        summary = _encounter_summary(encounter)
        evidence = encounter.sources or _evidence("Encounter", encounter.id)
        if not evidence:
            continue
        yield (
            date_dt,
            TimelineEntry(
                date=iso_date,
                type="ENCOUNTER",
                summary=summary,
                evidence=list(evidence),
            ),
        )


def _iter_observation_entries(
    observations: Iterable[Observation],
) -> Iterable[tuple[datetime, TimelineEntry]]:
    for observation in observations:
        date_value = observation.effective_dt or observation.effective
        iso_date = _iso_date(date_value)
        if not date_value or not iso_date:
            continue
        date_dt = date_value if isinstance(date_value, datetime) else _parse_datetime(iso_date)
        if not date_dt:
            continue
        summary = _observation_summary(observation)
        entry_type = _category_label(observation)
        evidence = observation.sources or _evidence("Observation", observation.id)
        if not evidence:
            continue
        yield (
            date_dt,
            TimelineEntry(
                date=iso_date,
                type=entry_type,
                summary=summary,
                evidence=list(evidence),
            ),
        )


def run_timeline_agent(chart: PatientChart, *, max_entries: int = 20) -> list[TimelineEntry]:
    """Return deterministic timeline entries from chart encounters/observations."""
    entries: list[tuple[datetime, TimelineEntry]] = []
    entries.extend(list(_iter_encounter_entries(chart.encounters)))
    entries.extend(list(_iter_observation_entries(chart.observations)))
    entries.sort(
        key=lambda item: (
            item[0],
            item[1].type,
            item[1].summary,
            item[1].evidence[0].resource_id or item[1].evidence[0].doc_id,
        ),
        reverse=True,
    )
    return [entry for _, entry in entries[:max_entries]]


__all__ = ["run_timeline_agent"]
