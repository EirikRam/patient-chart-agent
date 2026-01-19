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
import sys
from pathlib import Path
from typing import Any, Iterable

from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.agents.verifier_agent import verify_result
from packages.pipeline.evidence_enrich import collect_result_evidence, enrich_result_evidence

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_manifest(path: str | Path) -> dict:
    manifest_path = Path(path)
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def evaluate_manifest(path: str | Path) -> dict:
    manifest = load_manifest(path)
    patients = manifest.get("patients", [])
    mode = manifest.get("mode", "mock")
    enable_agents = bool(manifest.get("enable_agents", True))
    gates = _normalize_gates(manifest.get("gates"))
    results = []
    for patient in patients:
        name = patient.get("name", "unknown")
        rel_path = patient.get("path", "")
        expects = patient.get("expects", {}) or {}
        path_obj = REPO_ROOT / rel_path
        result = _run_pipeline(path_obj, mode=mode, enable_agents=enable_agents)
        metrics = _score_result(result, expects)
        gate_result = evaluate_gates(metrics, gates)
        metrics["name"] = name
        metrics["path"] = rel_path
        metrics.update(gate_result)
        results.append(metrics)
    summary = _summarize(results)
    overall_pass = all(item.get("patient_pass", True) for item in results)
    patients_failed = len([item for item in results if not item.get("patient_pass", True)])
    return {
        "version": manifest.get("version", "unknown"),
        "mode": mode,
        "enable_agents": enable_agents,
        "gates": gates,
        "patients": results,
        "summary": summary,
        "overall_pass": overall_pass,
        "patients_failed": patients_failed,
    }


def print_summary(report: dict) -> None:
    patients = report.get("patients", [])
    print("Phase 7 eval summary")
    print("-" * 72)
    header = (
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
    )
    print(" | ".join(header))
    for item in patients:
        print(
            " | ".join(
                [
                    item.get("name", "unknown"),
                    f"{item.get('risk_precision', 0.0):.2f}",
                    f"{item.get('risk_recall', 0.0):.2f}",
                    str(item.get("risk_tp", 0)),
                    str(item.get("risk_fp", 0)),
                    str(item.get("risk_fn", 0)),
                    f"{item.get('missing_precision', 0.0):.2f}",
                    f"{item.get('missing_recall', 0.0):.2f}",
                    str(item.get("missing_tp", 0)),
                    str(item.get("missing_fp", 0)),
                    str(item.get("missing_fn", 0)),
                    f"{item.get('contradiction_precision', 0.0):.2f}",
                    f"{item.get('contradiction_recall', 0.0):.2f}",
                    str(item.get("contradiction_tp", 0)),
                    str(item.get("contradiction_fp", 0)),
                    str(item.get("contradiction_fn", 0)),
                    f"{item.get('narrative_citation_coverage', 0.0):.2f}",
                    f"{item.get('risk_evidence_coverage', 0.0):.2f}",
                    f"{item.get('timeline_evidence_coverage', 0.0):.2f}",
                    f"{item.get('contradiction_evidence_coverage', 0.0):.2f}",
                ]
            )
        )
    print("-" * 72)
    summary = report.get("summary", {})
    print(
        "macro avg | "
        + " | ".join(
            [
                f"{summary.get('risk_precision', 0.0):.2f}",
                f"{summary.get('risk_recall', 0.0):.2f}",
                f"{summary.get('missing_precision', 0.0):.2f}",
                f"{summary.get('missing_recall', 0.0):.2f}",
                f"{summary.get('contradiction_precision', 0.0):.2f}",
                f"{summary.get('contradiction_recall', 0.0):.2f}",
                f"{summary.get('narrative_citation_coverage', 0.0):.2f}",
                f"{summary.get('risk_evidence_coverage', 0.0):.2f}",
                f"{summary.get('timeline_evidence_coverage', 0.0):.2f}",
                f"{summary.get('contradiction_evidence_coverage', 0.0):.2f}",
            ]
        )
    )
    overall_pass = report.get("overall_pass", True)
    patients_failed = report.get("patients_failed", 0)
    print("-" * 72)
    print(f"overall_pass: {overall_pass} | patients_failed: {patients_failed}")


def _run_pipeline(path: Path, *, mode: str, enable_agents: bool) -> PatientAnalysisResult:
    result = run_agent_pipeline(path, enable_agents=enable_agents, mode=mode)
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
        values = [item.get(key, 0.0) for item in results]
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


def _json_summary(report: dict) -> dict:
    return {
        "version": report.get("version"),
        "overall_pass": report.get("overall_pass"),
        "patients_failed": report.get("patients_failed"),
        "summary": report.get("summary", {}),
        "patients": [
            {
                "name": patient.get("name"),
                "patient_pass": patient.get("patient_pass"),
                "failures": patient.get("failures"),
            }
            for patient in report.get("patients", [])
        ],
    }


def _print_quiet(report: dict) -> None:
    overall_pass = report.get("overall_pass", True)
    patients_failed = report.get("patients_failed", 0)
    print(f"overall_pass: {overall_pass} | patients_failed: {patients_failed}")
    for patient in report.get("patients", []):
        failures = patient.get("failures") or []
        if failures:
            name = patient.get("name", "unknown")
            print(f"FAIL {name}: {', '.join(failures)}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 7 eval harness.")
    parser.add_argument(
        "--manifest",
        default="eval/manifest_phase7.json",
        help="Path to eval manifest JSON.",
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = evaluate_manifest(args.manifest)
    except Exception as exc:
        print(f"manifest_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_json_summary(report), sort_keys=True))
    elif args.quiet:
        _print_quiet(report)
    else:
        print_summary(report)

    overall_pass = report.get("overall_pass", True)
    patients_failed = report.get("patients_failed", 0)
    if args.fail_on_warn and patients_failed > 0:
        return 1
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
