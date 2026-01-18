from __future__ import annotations

from typing import Callable

from packages.core.schemas.chart import PatientChart, SourceRef
from packages.risklib.rules import (
    duplicate_therapy,
    followup_missing,
    lab_trend_creatinine,
    lab_trend_potassium,
    med_allergy_conflict,
)

_RULE_MODULES = [
    duplicate_therapy,
    followup_missing,
    lab_trend_creatinine,
    lab_trend_potassium,
    med_allergy_conflict,
]

_SEVERITIES = {"low", "medium", "high"}


def _get_runner(module: object) -> Callable[[PatientChart], object] | None:
    for name in ("run", "evaluate", "check", "detect"):
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    return None


def _as_sourceref(value: object) -> SourceRef | None:
    if isinstance(value, SourceRef):
        return value
    if isinstance(value, dict):
        payload = {
            "doc_id": value.get("doc_id"),
            "resource_type": value.get("resource_type"),
            "resource_id": value.get("resource_id"),
            "file_path": value.get("file_path"),
            "timestamp": value.get("timestamp"),
        }
        return SourceRef(**payload)
    return None


def _normalize_results(module: object, raw: object) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        items = [{"message": str(raw)}]

    results: list[dict] = []
    default_rule_id = getattr(module, "RULE_ID", module.__name__.split(".")[-1])
    default_severity = getattr(module, "SEVERITY", "medium")
    for item in items:
        if not isinstance(item, dict):
            item = {"message": str(item)}
        rule_id = item.get("rule_id") or default_rule_id
        severity = item.get("severity") if item.get("severity") in _SEVERITIES else default_severity
        if severity not in _SEVERITIES:
            severity = "medium"
        message = item.get("message") or item.get("summary") or "risk detected"
        evidence_list = item.get("evidence") or item.get("sources") or []
        evidence: list[SourceRef] = []
        if isinstance(evidence_list, list):
            for entry in evidence_list:
                source = _as_sourceref(entry)
                if source:
                    evidence.append(source)
        results.append(
            {
                "rule_id": str(rule_id),
                "severity": str(severity),
                "message": str(message),
                "evidence": evidence,
            }
        )
    return results


def run_risk_rules(chart: PatientChart) -> list[dict]:
    results: list[dict] = []
    for module in _RULE_MODULES:
        runner = _get_runner(module)
        if not runner:
            continue
        try:
            raw = runner(chart)
        except Exception:
            continue
        results.extend(_normalize_results(module, raw))
    return results