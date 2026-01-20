from __future__ import annotations

from typing import Iterable

from packages.core.schemas.result import PatientAnalysisResult
from packages.pipeline.evidence_enrich import collect_result_evidence


def _safe_iter(items: object) -> Iterable:
    return items if isinstance(items, list) else []


def _has_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def verify_result(result: PatientAnalysisResult) -> PatientAnalysisResult:
    """Drop invalid agent artifacts and citations deterministically."""
    try:
        evidence_sources = collect_result_evidence(result)
        valid_doc_ids = {source.doc_id for source in evidence_sources if source.doc_id}
    except Exception:
        valid_doc_ids = set()

    narrative = result.narrative
    if narrative is not None:
        try:
            citations = narrative.citations or {}
            has_valid = False
            has_any = False
            for values in citations.values():
                for cite in values or []:
                    has_any = True
                    if cite in valid_doc_ids:
                        has_valid = True
                        break
                if has_valid:
                    break
            if has_any and not has_valid:
                result.narrative = None
        except Exception:
            result.narrative = None

    if result.contradictions is not None:
        filtered = []
        for item in _safe_iter(result.contradictions):
            try:
                evidence = item.evidence or []
                if len(evidence) < 2:
                    continue
                filtered.append(item)
            except Exception:
                continue
        result.contradictions = filtered

    if result.timeline is not None:
        filtered = []
        for entry in _safe_iter(result.timeline):
            try:
                if not (_has_text(entry.date) and _has_text(entry.type) and _has_text(entry.summary)):
                    continue
                filtered.append(entry)
            except Exception:
                continue
        result.timeline = filtered

    if result.missing_info is not None:
        filtered = []
        for item in _safe_iter(result.missing_info):
            try:
                if not (_has_text(item.id) and _has_text(item.severity) and _has_text(item.message)):
                    continue
                filtered.append(item)
            except Exception:
                continue
        result.missing_info = filtered

    return result


__all__ = ["verify_result"]
