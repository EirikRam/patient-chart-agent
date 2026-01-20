"""
Phase 7 eval harness (seeded expectations + scoring).

Metrics:
- Risks precision/recall: set match on risk rule_id.
- Missing-info precision/recall: set match on missing_info[].id.
- Contradiction precision/recall: set match on contradictions[].id.
- Citation coverage:
  - Narrative: percent of citation keys with >=1 valid SourceRef doc_id.
  - Risks/timeline/contradictions: percent of items with non-empty evidence.

Phase 7.3 will expand this to more patients, seeded contradiction fixtures,
and red-herring expectations to stress precision.

allow_extra_* controls whether extra detections are tolerated or treated
as strict failures for precision.

Exit codes:
- 0: overall_pass is True
- 1: overall_pass is False (or failures when --fail-on-warn)
- 2: manifest load/parse error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from packages.core.llm import LLMClient, load_dotenv
from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.agents.verifier_agent import verify_result
from packages.pipeline.evidence_enrich import collect_result_evidence, enrich_result_evidence

REPO_ROOT = Path(__file__).resolve().parents[1]
LLM_SKIP_MESSAGE = "llm skipped: missing keys"


@dataclass(frozen=True)
class LLMOutcome:
    status: str
    reason: str | None = None
    errors: list[str] = field(default_factory=list)


def load_manifest(path: str | Path) -> dict:
    manifest_path = Path(path)
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def evaluate_manifest(
    path: str | Path,
    *,
    mode: str | None = None,
    require_llm: bool = False,
    llm_timeout_seconds: int = 60,
    llm_retries: int = 1,
) -> dict:
    manifest = load_manifest(path)
    patients = manifest.get("patients", [])
    if mode is None:
        mode = manifest.get("mode", "mock")
    enable_agents = bool(manifest.get("enable_agents", True))
    gates = _normalize_gates(manifest.get("gates"))
    llm_ok_rate = None
    llm_rate_failure = None
    llm_key_reason = None
    has_llm_keys = True
    if mode == "llm":
        has_llm_keys, llm_key_reason = _detect_llm_keys()
    if mode == "llm" and not has_llm_keys:
        outcome = _llm_outcome_skipped(reason=llm_key_reason)
        results = [
            _result_from_outcome(patient, outcome, require_llm=require_llm)
            for patient in patients
        ]
        llm_ok_rate = _llm_ok_rate(results)
        llm_ok_rate, llm_rate_failure = _apply_llm_ok_rate_gate(
            results, gates, llm_ok_rate=llm_ok_rate, apply_gate=(mode == "llm")
        )
        summary = _summarize(results)
        llm_counts = _llm_counts(results)
        overall_pass = all(item.get("patient_pass", True) for item in results)
        patients_failed = len(
            [item for item in results if not item.get("patient_pass", True)]
        )
        return {
            "version": manifest.get("version", "unknown"),
            "mode": mode,
            "enable_agents": enable_agents,
            "gates": gates,
            "patients": results,
            "summary": summary,
            "overall_pass": overall_pass,
            "patients_failed": patients_failed,
            "skipped_patients": llm_counts["skipped"],
            "skipped_reason": llm_key_reason,
            "llm_ok": llm_counts["ok"],
            "llm_skipped": llm_counts["skipped"],
            "llm_failed": llm_counts["failed"],
            "llm_ok_rate": llm_ok_rate,
            "llm_ok_rate_failure": llm_rate_failure,
            "llm_retried": 0,
            "require_llm": require_llm,
        }
    results = []
    llm_retried = 0
    for patient in patients:
        name = patient.get("name", "unknown")
        rel_path = patient.get("path", "")
        expects = patient.get("expects", {}) or {}
        path_obj = REPO_ROOT / rel_path
        if mode == "llm":
            outcome, metrics, retries_used = _run_llm_patient(
                path_obj,
                expects,
                enable_agents=enable_agents,
                timeout_seconds=llm_timeout_seconds,
                retries=llm_retries,
            )
            llm_retried += retries_used
            gate_result = {"patient_pass": True, "failures": []}
            if outcome.status == "ok" and metrics is not None:
                gate_result = evaluate_gates(metrics, gates)
            patient_metrics = metrics or _empty_metrics()
            patient_metrics["name"] = name
            patient_metrics["path"] = rel_path
            patient_metrics.update(gate_result)
            patient_metrics.update(_llm_fields(outcome))
            patient_metrics = _apply_llm_overrides(
                patient_metrics, outcome, require_llm=require_llm
            )
            results.append(patient_metrics)
        else:
            result = _run_pipeline(path_obj, mode=mode, enable_agents=enable_agents)
            metrics = _score_result(result, expects)
            gate_result = evaluate_gates(metrics, gates)
            metrics["name"] = name
            metrics["path"] = rel_path
            gate_result["failures"] = _sorted_failures(gate_result.get("failures") or [])
            metrics.update(gate_result)
            metrics["status"] = "ok"
            metrics["reason"] = None
            metrics["errors"] = []
            results.append(metrics)
    if mode == "llm":
        llm_ok_rate = _llm_ok_rate(results)
    llm_ok_rate, llm_rate_failure = _apply_llm_ok_rate_gate(
        results, gates, llm_ok_rate=llm_ok_rate, apply_gate=(mode == "llm")
    )
    summary = _summarize(results)
    overall_pass = all(item.get("patient_pass", True) for item in results)
    patients_failed = len([item for item in results if not item.get("patient_pass", True)])
    llm_counts = (
        _llm_counts(results) if mode == "llm" else {"ok": 0, "skipped": 0, "failed": 0}
    )
    return {
        "version": manifest.get("version", "unknown"),
        "mode": mode,
        "enable_agents": enable_agents,
        "gates": gates,
        "patients": results,
        "summary": summary,
        "overall_pass": overall_pass,
        "patients_failed": patients_failed,
        "skipped_patients": 0,
        "skipped_reason": None,
        "llm_ok": llm_counts["ok"],
        "llm_skipped": llm_counts["skipped"],
        "llm_failed": llm_counts["failed"],
        "llm_ok_rate": llm_ok_rate,
        "llm_ok_rate_failure": llm_rate_failure,
        "llm_retried": llm_retried,
        "require_llm": require_llm,
    }


def print_summary(report: dict) -> None:
    patients = report.get("patients", [])
    mode = report.get("mode", "unknown")
    print(f"Eval summary (mode={mode})")
    print("-" * 72)
    header = [
        "patient",
        "risk_p",
        "risk_r",
        "risk_tp",
        "risk_fp",
        "risk_fn",
        "missing_p",
        "missing_r",
        "miss_tp",
        "miss_fp",
        "miss_fn",
        "contr_p",
        "contr_r",
        "contr_tp",
        "contr_fp",
        "contr_fn",
        "narr_cite",
        "risk_cite",
        "tl_cite",
        "contr_cite",
    ]
    if mode == "llm":
        header.extend(["llm_status", "llm_reason"])
    print(" | ".join(header))
    for item in patients:
        status = item.get("llm_status")
        reason = item.get("llm_reason")
        is_ok = status in {None, "ok"}
        print(
            " | ".join(
                [
                    item.get("name", "unknown"),
                    _fmt_float(item.get("risk_precision", 0.0), is_ok=is_ok),
                    _fmt_float(item.get("risk_recall", 0.0), is_ok=is_ok),
                    _fmt_int(item.get("risk_tp", 0), is_ok=is_ok),
                    _fmt_int(item.get("risk_fp", 0), is_ok=is_ok),
                    _fmt_int(item.get("risk_fn", 0), is_ok=is_ok),
                    _fmt_float(item.get("missing_precision", 0.0), is_ok=is_ok),
                    _fmt_float(item.get("missing_recall", 0.0), is_ok=is_ok),
                    _fmt_int(item.get("missing_tp", 0), is_ok=is_ok),
                    _fmt_int(item.get("missing_fp", 0), is_ok=is_ok),
                    _fmt_int(item.get("missing_fn", 0), is_ok=is_ok),
                    _fmt_float(item.get("contradiction_precision", 0.0), is_ok=is_ok),
                    _fmt_float(item.get("contradiction_recall", 0.0), is_ok=is_ok),
                    _fmt_int(item.get("contradiction_tp", 0), is_ok=is_ok),
                    _fmt_int(item.get("contradiction_fp", 0), is_ok=is_ok),
                    _fmt_int(item.get("contradiction_fn", 0), is_ok=is_ok),
                    _fmt_float(item.get("narrative_citation_coverage", 0.0), is_ok=is_ok),
                    _fmt_float(item.get("risk_evidence_coverage", 0.0), is_ok=is_ok),
                    _fmt_float(item.get("timeline_evidence_coverage", 0.0), is_ok=is_ok),
                    _fmt_float(
                        item.get("contradiction_evidence_coverage", 0.0), is_ok=is_ok
                    ),
                    *( [str(status or ""), str(reason or "")] if mode == "llm" else [] ),
                ]
            )
        )
    print("-" * 72)
    summary = report.get("summary", {})
    summary_values = [
        _fmt_float(summary.get("risk_precision", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("risk_recall", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("missing_precision", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("missing_recall", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("contradiction_precision", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("contradiction_recall", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("narrative_citation_coverage", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("risk_evidence_coverage", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("timeline_evidence_coverage", 0.0), is_ok=bool(summary)),
        _fmt_float(summary.get("contradiction_evidence_coverage", 0.0), is_ok=bool(summary)),
    ]
    print(
        "macro avg | "
        + " | ".join(
            summary_values
        )
    )
    overall_pass = report.get("overall_pass", True)
    patients_failed = report.get("patients_failed", 0)
    print("-" * 72)
    print(f"overall_pass: {overall_pass} | patients_failed: {patients_failed}")
    patients_failed_list = _patients_failed_list(patients)
    failure_counts = _failure_counts(patients)
    print("patients_failed:", ", ".join(patients_failed_list) if patients_failed_list else "[]")
    if failure_counts:
        ordered = _failure_counts_sorted(failure_counts)
        counts_display = ", ".join([f"{name}={count}" for name, count in ordered])
        print(f"failure_counts: {counts_display}")


def _run_pipeline(
    path: Path, *, mode: str, enable_agents: bool
) -> PatientAnalysisResult | None:
    result = run_agent_pipeline(path, enable_agents=enable_agents, mode=mode)
    if mode == "llm" and not result:
        return None
    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)
    enrich_result_evidence(result, chart, str(path))
    result = verify_result(result)
    return result


def _score_result(result: PatientAnalysisResult, expects: dict) -> dict:
    expected_risks = _set_from_list(expects.get("risks"))
    expected_missing = _set_from_list(expects.get("missing_info_ids"))
    expected_contradictions = _set_from_list(expects.get("contradiction_ids"))

    allow_extra_risks = _allow_extra(expects, "allow_extra_risks")
    allow_extra_missing = _allow_extra(expects, "allow_extra_missing_info")
    allow_extra_contradictions = _allow_extra(expects, "allow_extra_contradictions")

    actual_risks = _extract_ids(result.risks, key="rule_id")
    actual_missing = _extract_ids(result.missing_info, key="id")
    actual_contradictions = _extract_ids(result.contradictions, key="id")

    risk_counts = _tp_fp_fn(actual_risks, expected_risks)
    missing_counts = _tp_fp_fn(actual_missing, expected_missing)
    contradiction_counts = _tp_fp_fn(actual_contradictions, expected_contradictions)

    risk_precision, risk_recall = _precision_recall_from_counts(
        risk_counts["tp"], risk_counts["fp"], risk_counts["fn"], expected_risks
    )
    missing_precision, missing_recall = _precision_recall_from_counts(
        missing_counts["tp"], missing_counts["fp"], missing_counts["fn"], expected_missing
    )
    contradiction_precision, contradiction_recall = _precision_recall_from_counts(
        contradiction_counts["tp"],
        contradiction_counts["fp"],
        contradiction_counts["fn"],
        expected_contradictions,
    )

    strict_fail_risks = (not allow_extra_risks) and bool(risk_counts["fp"])
    strict_fail_missing = (not allow_extra_missing) and bool(missing_counts["fp"])
    strict_fail_contradictions = (not allow_extra_contradictions) and bool(
        contradiction_counts["fp"]
    )

    if strict_fail_risks:
        risk_precision = 0.0
    if strict_fail_missing:
        missing_precision = 0.0
    if strict_fail_contradictions:
        contradiction_precision = 0.0

    evidence_sources = collect_result_evidence(result)
    valid_doc_ids = {source.doc_id for source in evidence_sources if source.doc_id}
    narrative_coverage = _narrative_citation_coverage(
        result.narrative, valid_doc_ids
    )
    risk_evidence_coverage = _evidence_coverage(result.risks)
    timeline_evidence_coverage = _evidence_coverage(result.timeline)
    contradiction_evidence_coverage = _evidence_coverage(result.contradictions)

    return {
        "expected_risks": sorted(expected_risks),
        "actual_risks": sorted(actual_risks),
        "risk_tp": risk_counts["tp"],
        "risk_fp": risk_counts["fp"],
        "risk_fn": risk_counts["fn"],
        "risk_precision": risk_precision,
        "risk_recall": risk_recall,
        "expected_missing_info_ids": sorted(expected_missing),
        "actual_missing_info_ids": sorted(actual_missing),
        "missing_tp": missing_counts["tp"],
        "missing_fp": missing_counts["fp"],
        "missing_fn": missing_counts["fn"],
        "missing_precision": missing_precision,
        "missing_recall": missing_recall,
        "expected_contradiction_ids": sorted(expected_contradictions),
        "actual_contradiction_ids": sorted(actual_contradictions),
        "contradiction_tp": contradiction_counts["tp"],
        "contradiction_fp": contradiction_counts["fp"],
        "contradiction_fn": contradiction_counts["fn"],
        "contradiction_precision": contradiction_precision,
        "contradiction_recall": contradiction_recall,
        "strict_fail_risks": strict_fail_risks,
        "strict_fail_missing_info": strict_fail_missing,
        "strict_fail_contradictions": strict_fail_contradictions,
        "narrative_citation_coverage": narrative_coverage,
        "risk_evidence_coverage": risk_evidence_coverage,
        "timeline_evidence_coverage": timeline_evidence_coverage,
        "contradiction_evidence_coverage": contradiction_evidence_coverage,
        "risk_count": len(actual_risks),
        "missing_info_count": len(actual_missing),
        "contradiction_count": len(actual_contradictions),
    }


def _summarize(results: list[dict]) -> dict:
    if not results:
        return {}
    filtered = [item for item in results if item.get("status", "ok") == "ok"]
    if not filtered:
        return {}
    keys = [
        "risk_precision",
        "risk_recall",
        "missing_precision",
        "missing_recall",
        "contradiction_precision",
        "contradiction_recall",
        "narrative_citation_coverage",
        "risk_evidence_coverage",
        "timeline_evidence_coverage",
        "contradiction_evidence_coverage",
    ]
    summary = {}
    for key in keys:
        values = [item.get(key, 0.0) for item in filtered]
        summary[key] = sum(values) / len(values)
    return summary


def _set_from_list(values: Any) -> set[str]:
    if not values:
        return set()
    if isinstance(values, list):
        return {str(value) for value in values if str(value).strip()}
    return set()


def _allow_extra(expects: dict, key: str) -> bool:
    value = expects.get(key, True)
    return True if value is None else bool(value)


def _tp_fp_fn(actual: set[str], expected: set[str]) -> dict:
    tp = actual & expected
    fp = actual - expected
    fn = expected - actual
    return {"tp": len(tp), "fp": len(fp), "fn": len(fn)}


def _precision_recall_from_counts(
    tp: int, fp: int, fn: int, expected: set[str]
) -> tuple[float, float]:
    predicted_count = tp + fp
    if predicted_count == 0:
        precision = 1.0 if not expected else 0.0
    else:
        precision = tp / predicted_count
    recall = 1.0 if not expected else (tp / (tp + fn))
    return precision, recall


def _extract_ids(items: Any, *, key: str) -> set[str]:
    values = set()
    for item in _safe_list(items):
        if isinstance(item, dict):
            value = item.get(key)
        else:
            value = getattr(item, key, None)
        if isinstance(value, str) and value.strip():
            values.add(value)
    return values


def _safe_list(items: Any) -> Iterable:
    return items if isinstance(items, list) else []


def _evidence_coverage(items: Any) -> float:
    values = list(_safe_list(items))
    if not values:
        return 1.0
    covered = 0
    for item in values:
        evidence = None
        if isinstance(item, dict):
            evidence = item.get("evidence")
        else:
            evidence = getattr(item, "evidence", None)
        if isinstance(evidence, list) and len(evidence) > 0:
            covered += 1
    return covered / len(values)


def _narrative_citation_coverage(narrative: Any, valid_doc_ids: set[str]) -> float:
    if narrative is None:
        return 1.0
    if isinstance(narrative, dict):
        citations = narrative.get("citations") or {}
    else:
        citations = getattr(narrative, "citations", None) or {}
    keys = list(citations.keys()) if isinstance(citations, dict) else []
    if not keys:
        return 1.0
    covered = 0
    for key in keys:
        values = citations.get(key) or []
        if any(cite in valid_doc_ids for cite in values if isinstance(cite, str)):
            covered += 1
    return covered / len(keys)


def _normalize_gates(gates: Any) -> dict:
    defaults = {
        "min_risk_precision": 0.0,
        "min_risk_recall": 1.0,
        "min_missing_precision": 0.0,
        "min_missing_recall": 1.0,
        "min_contradiction_precision": 0.0,
        "min_contradiction_recall": 1.0,
        "min_narrative_citation_coverage": 0.0,
        "min_risk_citation_coverage": 1.0,
        "min_timeline_citation_coverage": 1.0,
        "min_contradiction_citation_coverage": 1.0,
        "min_llm_ok_rate": None,
    }
    if not isinstance(gates, dict):
        return defaults
    merged = dict(defaults)
    for key, value in gates.items():
        if key in defaults and value is not None:
            merged[key] = float(value)
    return merged


def evaluate_gates(metrics: dict, gates: dict) -> dict:
    checks = [
        ("risk_precision", "min_risk_precision"),
        ("risk_recall", "min_risk_recall"),
        ("missing_precision", "min_missing_precision"),
        ("missing_recall", "min_missing_recall"),
        ("contradiction_precision", "min_contradiction_precision"),
        ("contradiction_recall", "min_contradiction_recall"),
        ("narrative_citation_coverage", "min_narrative_citation_coverage"),
        ("risk_evidence_coverage", "min_risk_citation_coverage"),
        ("timeline_evidence_coverage", "min_timeline_citation_coverage"),
        ("contradiction_evidence_coverage", "min_contradiction_citation_coverage"),
    ]
    failures = []
    for metric_key, gate_key in checks:
        metric_value = float(metrics.get(metric_key, 0.0))
        threshold = float(gates.get(gate_key, 0.0))
        if metric_value < threshold:
            failures.append(
                f"{metric_key} < {threshold:.2f} ({metric_value:.2f})"
            )
    return {"patient_pass": len(failures) == 0, "failures": failures}


def _build_json_payload(reports: list[dict], *, require_llm: bool) -> dict:
    per_patient = _build_per_patient(reports)
    patients_failed = [patient["name"] for patient in per_patient if not patient["patient_pass"]]
    failure_counts = _failure_counts_from_entries(per_patient)
    overall_pass = all(patient["patient_pass"] for patient in per_patient)
    return {
        "version": reports[0].get("version") if reports else None,
        "overall_pass": overall_pass,
        "patients_failed_count": len(patients_failed),
        "patients_failed": patients_failed,
        "failure_counts": _sorted_failure_counts_dict(failure_counts),
        "per_patient": per_patient,
        "require_llm": require_llm,
        "modes": {report.get("mode"): _mode_summary(report) for report in reports},
    }


def _print_quiet(report: dict) -> None:
    overall_pass = report.get("overall_pass", True)
    patients_failed = report.get("patients_failed", 0)
    print(f"overall_pass: {overall_pass} | patients_failed: {patients_failed}")
    if report.get("mode") == "llm" and report.get("llm_skipped", 0) > 0:
        print(LLM_SKIP_MESSAGE)
    for patient in report.get("patients", []):
        failures = patient.get("failures") or []
        if failures:
            name = patient.get("name", "unknown")
            print(f"FAIL {name}: {', '.join(failures)}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 7 eval harness.")
    parser.add_argument(
        "--manifest",
        default="eval/manifest.json",
        help="Path to eval manifest JSON.",
    )
    parser.add_argument(
        "--modes",
        default="mock",
        help="Comma-separated modes to run (e.g. mock,llm).",
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=int,
        default=60,
        help="Per-patient timeout for LLM mode.",
    )
    parser.add_argument(
        "--llm-retries",
        type=int,
        default=1,
        help="Number of retries for transient LLM failures.",
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if LLM mode is skipped.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print overall result and failures.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary to stdout.",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit non-zero if any patient failures.",
    )
    return parser.parse_args(argv)


def _llm_available() -> bool:
    has_keys, _ = _detect_llm_keys()
    return has_keys


def _llm_outcome_skipped(reason: str | None = None) -> LLMOutcome:
    return LLMOutcome(status="skipped", reason=reason or LLM_SKIP_MESSAGE, errors=[])


def _llm_outcome_failed(exc: Exception) -> LLMOutcome:
    reason = f"llm failed: {type(exc).__name__}"
    return LLMOutcome(status="failed", reason=reason, errors=sorted({type(exc).__name__}))


def _llm_outcome_ok() -> LLMOutcome:
    return LLMOutcome(status="ok", reason=None, errors=[])


def _llm_fields(outcome: LLMOutcome) -> dict:
    return {
        "llm_status": outcome.status,
        "llm_reason": outcome.reason,
        "llm_errors": list(outcome.errors),
        "status": outcome.status,
        "reason": outcome.reason,
        "errors": list(outcome.errors),
    }


def _result_from_outcome(
    patient: dict, outcome: LLMOutcome, *, require_llm: bool
) -> dict:
    name = patient.get("name", "unknown")
    rel_path = patient.get("path", "")
    result = {
        "name": name,
        "path": rel_path,
        "patient_pass": True,
        "failures": [],
        **_llm_fields(outcome),
    }
    return _apply_llm_overrides(result, outcome, require_llm=require_llm)


def _parse_modes(raw_modes: str) -> list[str]:
    modes = [mode.strip() for mode in raw_modes.split(",") if mode.strip()]
    return modes or ["mock"]


def _run_llm_patient(
    path_obj: Path,
    expects: dict,
    *,
    enable_agents: bool,
    timeout_seconds: int,
    retries: int,
) -> tuple[LLMOutcome, dict | None, int]:
    attempts = max(1, retries + 1)
    retries_used = 0
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            result = _run_llm_with_timeout(
                path_obj, enable_agents=enable_agents, timeout_seconds=timeout_seconds
            )
            if result is None:
                return _llm_outcome_skipped(), None, retries_used
            metrics = _score_result(result, expects)
            return _llm_outcome_ok(), metrics, retries_used
        except Exception as exc:
            last_exc = exc
            if _is_transient_llm_error(exc) and attempt < attempts - 1:
                retries_used += 1
                continue
            return _llm_outcome_failed(exc), None, retries_used
    if last_exc is None:
        return _llm_outcome_failed(RuntimeError("LLM retries exhausted")), None, retries_used
    return _llm_outcome_failed(last_exc), None, retries_used


def _apply_llm_overrides(
    metrics: dict, outcome: LLMOutcome, *, require_llm: bool
) -> dict:
    patient_pass = metrics.get("patient_pass", True)
    failures = list(metrics.get("failures") or [])
    if outcome.status == "failed":
        patient_pass = False
        failures.append("llm_failed")
    if outcome.status == "skipped" and require_llm:
        patient_pass = False
        failures.append("llm_required_but_skipped")
    metrics["patient_pass"] = patient_pass
    metrics["failures"] = _sorted_failures(failures)
    return metrics


def _empty_metrics() -> dict:
    return {
        "risk_precision": 0.0,
        "risk_recall": 0.0,
        "risk_tp": 0,
        "risk_fp": 0,
        "risk_fn": 0,
        "missing_precision": 0.0,
        "missing_recall": 0.0,
        "missing_tp": 0,
        "missing_fp": 0,
        "missing_fn": 0,
        "contradiction_precision": 0.0,
        "contradiction_recall": 0.0,
        "contradiction_tp": 0,
        "contradiction_fp": 0,
        "contradiction_fn": 0,
        "strict_fail_risks": False,
        "strict_fail_missing_info": False,
        "strict_fail_contradictions": False,
        "narrative_citation_coverage": 0.0,
        "risk_evidence_coverage": 0.0,
        "timeline_evidence_coverage": 0.0,
        "contradiction_evidence_coverage": 0.0,
        "risk_count": 0,
        "missing_info_count": 0,
        "contradiction_count": 0,
    }


def _llm_counts(results: list[dict]) -> dict:
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for item in results:
        status = item.get("llm_status")
        if status in counts:
            counts[status] += 1
    return counts


def _llm_ok_rate(results: list[dict]) -> float:
    attempted = 0
    ok = 0
    for item in results:
        status = item.get("llm_status")
        if status in {"ok", "failed"}:
            attempted += 1
            if status == "ok":
                ok += 1
    if attempted == 0:
        return 0.0
    return ok / attempted


def _apply_llm_ok_rate_gate(
    results: list[dict],
    gates: dict,
    *,
    llm_ok_rate: float | None,
    apply_gate: bool,
) -> tuple[float | None, str | None]:
    if not apply_gate:
        return None, None
    threshold = gates.get("min_llm_ok_rate")
    if threshold is None:
        return llm_ok_rate, None
    if llm_ok_rate is None:
        llm_ok_rate = _llm_ok_rate(results)
    failure = None
    if llm_ok_rate < float(threshold):
        failure = f"llm_ok_rate < {float(threshold):.2f} ({llm_ok_rate:.2f})"
        for item in results:
            failures = list(item.get("failures") or [])
            failures.append(failure)
            item["patient_pass"] = False
            item["failures"] = _sorted_failures(failures)
    return llm_ok_rate, failure


def _metrics_payload(patient: dict) -> dict | None:
    if patient.get("llm_status") != "ok":
        return None
    keys = [
        "risk_precision",
        "risk_recall",
        "risk_tp",
        "risk_fp",
        "risk_fn",
        "missing_precision",
        "missing_recall",
        "missing_tp",
        "missing_fp",
        "missing_fn",
        "contradiction_precision",
        "contradiction_recall",
        "contradiction_tp",
        "contradiction_fp",
        "contradiction_fn",
        "narrative_citation_coverage",
        "risk_evidence_coverage",
        "timeline_evidence_coverage",
        "contradiction_evidence_coverage",
    ]
    return {key: patient.get(key) for key in keys}


def _sorted_failures(failures: list[str]) -> list[str]:
    return sorted(str(item) for item in failures if str(item))


def _patients_failed_list(patients: list[dict]) -> list[str]:
    failed = []
    for patient in patients:
        if not patient.get("patient_pass", True):
            failed.append(patient.get("name", "unknown"))
    return failed


def _failure_counts(patients: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for patient in patients:
        for failure in patient.get("failures") or []:
            counts[failure] = counts.get(failure, 0) + 1
    return counts


def _failure_counts_sorted(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _sorted_failure_counts_dict(counts: dict[str, int]) -> dict[str, int]:
    return {key: counts[key] for key in sorted(counts)}


def _build_per_patient(reports: list[dict]) -> list[dict]:
    if not reports:
        return []
    base_patients = reports[0].get("patients", [])
    base_keys = [(patient.get("name"), patient.get("path")) for patient in base_patients]
    report_maps = []
    for report in reports:
        patient_map = {
            (patient.get("name"), patient.get("path")): patient
            for patient in report.get("patients", [])
        }
        report_maps.append((report.get("mode"), patient_map))
    per_patient = []
    for key in base_keys:
        name, path = key
        entry = {
            "name": name,
            "path": path,
            "patient_pass": True,
            "failures": [],
            "modes": {},
        }
        combined_failures: list[str] = []
        for mode, patient_map in report_maps:
            patient = patient_map.get(key)
            if patient is None:
                continue
            failures = _sorted_failures(patient.get("failures") or [])
            mode_entry = {
                "patient_pass": patient.get("patient_pass", True),
                "failures": failures,
            }
            if mode == "llm":
                mode_entry["llm_status"] = patient.get("llm_status")
                mode_entry["llm_reason"] = patient.get("llm_reason")
            entry["modes"][mode] = mode_entry
            if not patient.get("patient_pass", True):
                entry["patient_pass"] = False
            combined_failures.extend(failures)
        entry["failures"] = _sorted_failures(list(dict.fromkeys(combined_failures)))
        per_patient.append(entry)
    return per_patient


def _failure_counts_from_entries(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for failure in entry.get("failures") or []:
            counts[failure] = counts.get(failure, 0) + 1
    return counts


def _mode_summary(report: dict) -> dict:
    return {
        "mode": report.get("mode"),
        "overall_pass": report.get("overall_pass"),
        "patients_failed": report.get("patients_failed"),
        "llm_ok": report.get("llm_ok", 0),
        "llm_skipped": report.get("llm_skipped", 0),
        "llm_failed": report.get("llm_failed", 0),
        "llm_ok_rate": report.get("llm_ok_rate"),
        "llm_retried": report.get("llm_retried", 0),
        "require_llm": report.get("require_llm", False),
    }


def _detect_llm_keys() -> tuple[bool, str]:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        return True, "llm keys: openai"

    azure_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip() or os.getenv(
        "AZURE_OPENAI_BASE_URL", ""
    ).strip()
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip() or os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_NAME", ""
    ).strip()

    if azure_key and azure_endpoint and azure_deployment:
        return True, "llm keys: azure"
    if azure_key or azure_endpoint or azure_deployment:
        return False, "llm skipped: missing azure credentials"
    return False, LLM_SKIP_MESSAGE


def _load_env_if_available() -> None:
    if os.getenv("EVAL_LOAD_DOTENV") == "1":
        load_dotenv(REPO_ROOT / ".env")


def _run_llm_with_timeout(
    path_obj: Path, *, enable_agents: bool, timeout_seconds: int
) -> PatientAnalysisResult | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _run_pipeline, path_obj, mode="llm", enable_agents=enable_agents
        )
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            raise TimeoutError("LLM evaluation timed out") from exc


def _is_transient_llm_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, ConnectionError):
        return True
    try:
        import httpx  # type: ignore
    except Exception:
        httpx = None
    if httpx is not None:
        try:
            if isinstance(exc, httpx.TransportError):
                return True
        except Exception:
            pass
    name = type(exc).__name__.lower()
    if "ratelimit" in name:
        return True
    message = str(exc).lower()
    return "rate limit" in message


def _fmt_float(value: float, *, is_ok: bool) -> str:
    if not is_ok:
        return "NA"
    return f"{float(value):.2f}"


def _fmt_int(value: int, *, is_ok: bool) -> str:
    if not is_ok:
        return "NA"
    return str(int(value))


def main(argv: list[str] | None = None) -> int:
    _load_env_if_available()
    args = _parse_args(argv)
    modes = _parse_modes(args.modes)
    try:
        reports = [
            evaluate_manifest(
                args.manifest,
                mode=mode,
                require_llm=args.require_llm,
                llm_timeout_seconds=args.llm_timeout_seconds,
                llm_retries=args.llm_retries,
            )
            for mode in modes
        ]
    except Exception as exc:
        print(f"manifest_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = _build_json_payload(reports, require_llm=args.require_llm)
        print(json.dumps(payload, sort_keys=True))
    elif args.quiet:
        for report in reports:
            if len(reports) > 1:
                print(f"mode: {report.get('mode')}")
            _print_quiet(report)
    else:
        for report in reports:
            print_summary(report)
            if len(reports) > 1:
                print("")

    overall_pass = all(report.get("overall_pass", True) for report in reports)
    patients_failed = sum(report.get("patients_failed", 0) for report in reports)
    if args.fail_on_warn and patients_failed > 0:
        return 1
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
