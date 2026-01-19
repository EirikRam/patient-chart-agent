from __future__ import annotations

from typing import Dict, Iterable, List

from packages.core.schemas.chart import Observation, PatientChart, SourceRef
from packages.core.schemas.result import PatientAnalysisResult


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


def _enrich_sources(sources: Iterable[SourceRef], chart: PatientChart, source_path: str) -> None:
    observation_index = build_observation_index(chart)
    for source in sources:
        source.file_path = source_path
        if source.resource_type == "Observation" and source.resource_id:
            obs = observation_index.get(source.resource_id)
            if obs:
                source.timestamp = obs.effective_dt or obs.effective


def _normalize_evidence_list(evidence: Iterable[object]) -> list[SourceRef]:
    normalized: list[SourceRef] = []
    for item in evidence:
        source = item if isinstance(item, SourceRef) else SourceRef(**item)
        normalized.append(source)
    return normalized


def enrich_evidence(risks: list[dict], chart: PatientChart, source_path: str) -> list[dict]:
    for risk in risks:
        evidence = risk.get("evidence") or []
        enriched = _normalize_evidence_list(evidence)
        _enrich_sources(enriched, chart, source_path)
        risk["evidence"] = enriched
    return risks


def collect_result_evidence(result: PatientAnalysisResult) -> List[SourceRef]:
    sources: list[SourceRef] = []
    for risk in result.risks or []:
        evidence = risk.get("evidence") or []
        enriched = _normalize_evidence_list(evidence)
        sources.extend(enriched)
        risk["evidence"] = enriched

    for entry in result.timeline or []:
        if not entry.evidence:
            continue
        entry.evidence = _normalize_evidence_list(entry.evidence)
        sources.extend(entry.evidence)
    for item in result.missing_info or []:
        if not item.evidence:
            continue
        item.evidence = _normalize_evidence_list(item.evidence)
        sources.extend(item.evidence)
    for item in result.contradictions or []:
        if not item.evidence:
            continue
        item.evidence = _normalize_evidence_list(item.evidence)
        sources.extend(item.evidence)
    return sources


def enrich_result_evidence(
    result: PatientAnalysisResult, chart: PatientChart, source_path: str
) -> PatientAnalysisResult:
    sources = collect_result_evidence(result)
    if sources:
        _enrich_sources(sources, chart, source_path)
    return result


__all__ = [
    "build_observation_index",
    "collect_result_evidence",
    "enrich_evidence",
    "enrich_result_evidence",
]
