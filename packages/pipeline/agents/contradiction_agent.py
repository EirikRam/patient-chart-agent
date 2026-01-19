from __future__ import annotations

from datetime import datetime
from typing import Optional

from packages.core.schemas.chart import PatientChart, SourceRef
from packages.core.schemas.result import ContradictionItem, Evidence


def _condition_label(condition) -> Optional[str]:
    label = condition.display or condition.code
    if isinstance(label, str) and label.strip():
        return label.strip()
    return None


def _condition_key(condition) -> Optional[str]:
    label = _condition_label(condition)
    return label.lower() if label else None


def _condition_onset(condition) -> Optional[datetime]:
    return condition.onset


def _evidence_for_condition(condition) -> list[Evidence]:
    sources = condition.sources or []
    evidence = [src for src in sources if src.doc_id or src.resource_id]
    return evidence


def run_contradiction_agent(chart: PatientChart) -> list[ContradictionItem]:
    """Return deterministic contradictions from chart content."""
    grouped: dict[str, list[tuple[datetime, str, list[SourceRef]]]] = {}
    for condition in chart.conditions:
        key = _condition_key(condition)
        if not key:
            continue
        onset = _condition_onset(condition)
        if not onset:
            continue
        evidence = _evidence_for_condition(condition)
        if not evidence:
            continue
        label = _condition_label(condition) or key
        grouped.setdefault(key, []).append((onset, label, evidence))

    for _, entries in grouped.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda item: item[0])
        first = entries[0]
        for candidate in entries[1:]:
            if candidate[0].date() != first[0].date():
                evidence = list(first[2]) + list(candidate[2])
                if len(evidence) < 2:
                    continue
                return [
                    ContradictionItem(
                        id="conflicting_condition_onset",
                        severity="low",
                        message=(
                            f"The condition '{first[1]}' appears multiple times in the record "
                            "with conflicting onset dates."
                        ),
                        evidence=evidence,
                    )
                ]

    return []


__all__ = ["run_contradiction_agent"]
