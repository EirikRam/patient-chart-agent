from __future__ import annotations

import importlib
from typing import Callable

from packages.core.schemas.chart import PatientChart, SourceRef
from packages.risklib.rules import discover_rules

_SEVERITIES = {"low", "medium", "high"}


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


def _normalize_results(default_rule_id: str, default_severity: str, raw: object) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        items = [{"message": str(raw)}]

    results: list[dict] = []
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


def run_risk_rules(chart: PatientChart, debug: bool = False) -> list[dict] | tuple[list[dict], dict]:
    results: list[dict] = []
    debug_info: dict[str, str] = {}
    runners = discover_rules()
    for rule_id, runner in sorted(runners.items()):
        module = importlib.import_module(runner.__module__)
        default_severity = getattr(module, "SEVERITY", "medium")
        try:
            raw = runner(chart)
        except Exception as exc:
            if debug:
                debug_info[rule_id] = f"error: {exc}"
            continue
        normalized = _normalize_results(rule_id, default_severity, raw)
        if debug:
            if normalized:
                debug_info[rule_id] = f"executed, hits={len(normalized)}"
            else:
                reason = getattr(module, "LAST_DEBUG_REASON", None)
                debug_info[rule_id] = reason or "executed, no hits"
        results.extend(normalized)
    if debug:
        return results, debug_info
    return results