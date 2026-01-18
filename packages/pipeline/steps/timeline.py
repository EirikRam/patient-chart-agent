from __future__ import annotations

from datetime import datetime
from typing import Iterable

from packages.core.schemas.chart import (
    Allergy,
    Condition,
    Encounter,
    Medication,
    Note,
    Observation,
    PatientChart,
    SourceRef,
)


def _label_from_parts(*parts: str) -> str:
    for part in parts:
        if part:
            return part
    return "unknown"


def _event(date: datetime, kind: str, label: str, sources: list[SourceRef] | None) -> dict:
    return {"date": date, "kind": kind, "label": label, "sources": sources or []}


def _iter_events(chart: PatientChart) -> Iterable[dict]:
    for encounter in chart.encounters:
        date = encounter.start or encounter.end
        if date:
            label = _label_from_parts(encounter.type or "", encounter.reason or "", "encounter")
            yield _event(date, "encounter", label, encounter.sources)

    for condition in chart.conditions:
        date = condition.onset or condition.abatement
        if date:
            label = _label_from_parts(condition.display or "", condition.code or "", "condition")
            yield _event(date, "condition", label, condition.sources)

    for medication in chart.medications:
        date = medication.authored_on
        if date:
            label = _label_from_parts(medication.name or "", "medication")
            yield _event(date, "medication", label, medication.sources)

    for observation in chart.observations:
        date = observation.effective
        if date:
            value = observation.value_text or (str(observation.value) if observation.value is not None else "")
            label = _label_from_parts(observation.display or "", observation.code or "", value, "observation")
            yield _event(date, "observation", label, observation.sources)

    for note in chart.notes:
        date = note.authored
        if date:
            label = _label_from_parts(note.type or "", note.text or "", "note")
            yield _event(date, "note", label, note.sources)


def build_timeline(chart: PatientChart) -> list[dict]:
    """Build a minimal timeline of dated events with source attributions."""
    events = [event for event in _iter_events(chart) if isinstance(event.get("date"), datetime)]
    events.sort(key=lambda item: item["date"])
    return events