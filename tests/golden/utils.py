from __future__ import annotations

import json
import difflib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.agents.verifier_agent import verify_result
from packages.pipeline.evidence_enrich import collect_result_evidence, enrich_result_evidence
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources


def _needs_evidence_enrichment(result: Any) -> bool:
    try:
        sources = collect_result_evidence(result)
    except Exception:
        return True
    if not sources:
        return False
    return any(source.file_path in (None, "") for source in sources)


def _ensure_evidence_enriched(result: Any, path_obj: Path) -> None:
    if not _needs_evidence_enrichment(result):
        return
    resources = load_patient_dir(path_obj)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)
    enrich_result_evidence(result, chart, str(path_obj))


def generate_result_json(path: str | Path) -> dict:
    path_obj = Path(path)
    result = run_agent_pipeline(path_obj, enable_agents=True, mode="mock")
    _ensure_evidence_enriched(result, path_obj)
    result = verify_result(result)
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return json.loads(result.json())


def _normalize_paths(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if key in ("file_path", "source_path") and isinstance(item, str):
                normalized[key] = item.replace("\\", "/")
            elif key == "timestamp" and item is not None:
                normalized[key] = _normalize_timestamp(item)
            else:
                normalized[key] = _normalize_paths(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_paths(item) for item in value]
    return value


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        text = value.isoformat()
    else:
        text = value if isinstance(value, str) else str(value)
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def _sort_timeline(entries: list[dict]) -> list[dict]:
    sorted_entries = list(entries)
    sorted_entries.sort(key=lambda item: (item.get("type") or "", item.get("summary") or ""))
    sorted_entries.sort(key=lambda item: item.get("date") or "", reverse=True)
    return sorted_entries


def _sort_risks(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda item: item.get("rule_id") or "")


def normalize_result(obj: dict) -> dict:
    data = deepcopy(obj)
    data = _normalize_paths(data)
    timeline = data.get("timeline")
    if isinstance(timeline, list):
        data["timeline"] = _sort_timeline(timeline)
    risks = data.get("risks")
    if isinstance(risks, list):
        data["risks"] = _sort_risks(risks)
    return data


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json_pretty(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _json_lines(payload: dict) -> list[str]:
    return json.dumps(payload, indent=2, sort_keys=True).splitlines()


def compare_json(expected: dict, actual: dict, *, max_lines: int = 200) -> tuple[bool, str]:
    if expected == actual:
        return True, ""
    diff_iter: Iterable[str] = difflib.unified_diff(
        _json_lines(expected),
        _json_lines(actual),
        fromfile="expected",
        tofile="actual",
        lineterm="",
    )
    diff_lines = list(diff_iter)
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + ["... diff truncated ..."]
    return False, "\n".join(diff_lines)


def write_golden_files(cases: list[tuple[Path, Path]]) -> None:
    """One-off helper to (re)generate golden JSON fixtures."""
    for patient_path, golden_path in cases:
        result = generate_result_json(patient_path)
        normalized = normalize_result(result)
        write_json_pretty(golden_path, normalized)
