from __future__ import annotations

from typing import Dict, Iterable

from packages.core.schemas.chart import Observation, PatientChart, SourceRef


def build_observation_index(chart: PatientChart) -> Dict[str, Observation]:
    return {obs.id: obs for obs in chart.observations if obs.id}


def _iter_evidence(risks: Iterable[dict]) -> Iterable[SourceRef]:
    for risk in risks:
        evidence = risk.get("evidence") or []
        for item in evidence:
            if isinstance(item, SourceRef):
                yield item
            elif isinstance(item, dict):
                yield SourceRef(**item)


def enrich_evidence(risks: list[dict], chart: PatientChart, source_path: str) -> list[dict]:
    observation_index = build_observation_index(chart)
    for risk in risks:
        evidence = risk.get("evidence") or []
        enriched: list[SourceRef] = []
        for item in evidence:
            source = item if isinstance(item, SourceRef) else SourceRef(**item)
            source.file_path = source_path
            if source.resource_type == "Observation" and source.resource_id:
                obs = observation_index.get(source.resource_id)
                if obs:
                    source.timestamp = obs.effective_dt or obs.effective
            enriched.append(source)
        risk["evidence"] = enriched
    return risks


__all__ = ["build_observation_index", "enrich_evidence"]
