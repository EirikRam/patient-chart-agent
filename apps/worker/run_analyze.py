from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.evidence_enrich import enrich_evidence, enrich_result_evidence
from packages.pipeline.steps.risks import run_risk_rules
from packages.pipeline.steps.snapshot import build_snapshot_from_chart


def _serialize_risks(risks: list[dict]) -> list[dict]:
    serialized = []
    for risk in risks:
        evidence = risk.get("evidence") or []
        evidence_out = []
        for source in evidence:
            evidence_out.append(
                {
                    "doc_id": getattr(source, "doc_id", None),
                    "resource_type": getattr(source, "resource_type", None),
                    "resource_id": getattr(source, "resource_id", None),
                    "file_path": getattr(source, "file_path", None),
                    "timestamp": getattr(source, "timestamp", None),
                }
            )
        serialized.append(
            {
                "rule_id": risk.get("rule_id", "unknown"),
                "severity": risk.get("severity", "medium"),
                "message": risk.get("message", ""),
                "evidence": evidence_out,
            }
        )
    return serialized


def _source_fields(source: object) -> tuple[object, object]:
    if isinstance(source, dict):
        return source.get("resource_type"), source.get("resource_id")
    return getattr(source, "resource_type", None), getattr(source, "resource_id", None)


def _result_to_json(result: PatientAnalysisResult) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run risk analysis.")
    parser.add_argument("path", type=Path, help="Path to patient JSON bundle.")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--phase5", action="store_true", help="Enable phase 5 agents.")
    args = parser.parse_args()

    path = args.path
    if args.phase5:
        result = run_agent_pipeline(path, enable_agents=True, mode=args.mode)
        resources = load_patient_dir(path)
        grouped = parse_fhir_resources(resources)
        chart = normalize_to_patient_chart(grouped)
        enrich_result_evidence(result, chart, str(path))
        if args.json:
            print(_result_to_json(result))
            return 0

        patient_id = result.meta.get("patient_id", "unknown")
        risks = result.risks or []
        print(f"patient_id: {patient_id}")
        print(f"total risks found: {len(risks)}")
        if not risks:
            return 0
        for risk in risks:
            rule_id = risk.get("rule_id", "unknown")
            severity = risk.get("severity", "medium")
            message = risk.get("message", "")
            print(f"{rule_id} | {severity} | {message}")
            evidence = risk.get("evidence") or []
            for source in evidence[:5]:
                resource_type, resource_id = _source_fields(source)
                resource_type = resource_type or "unknown"
                resource_id = resource_id or "unknown"
                print(f"  - src: {resource_type}/{resource_id}")
        return 0

    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    risks = run_risk_rules(chart)
    if args.json:
        enrich_evidence(risks, chart, str(path))
        snapshot_text = build_snapshot_from_chart(chart)
        result = PatientAnalysisResult(
            snapshot=snapshot_text,
            risks=_serialize_risks(risks),
            narrative=None,
            meta={"patient_id": chart.patient_id, "source_path": str(path), "mode": args.mode},
        )
        print(_result_to_json(result))
        return 0

    print(f"patient_id: {chart.patient_id}")
    print(f"total risks found: {len(risks)}")
    if not risks:
        return 0
    for risk in risks:
        rule_id = risk.get("rule_id", "unknown")
        severity = risk.get("severity", "medium")
        message = risk.get("message", "")
        print(f"{rule_id} | {severity} | {message}")
        evidence = risk.get("evidence") or []
        for source in evidence[:5]:
            resource_type, resource_id = _source_fields(source)
            resource_type = resource_type or "unknown"
            resource_id = resource_id or "unknown"
            print(f"  - src: {resource_type}/{resource_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())