from __future__ import annotations

import argparse
import sys
from pathlib import Path

import re

from packages.core.llm import LLMClient
from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.steps.narrative import generate_narrative
from packages.pipeline.evidence_enrich import enrich_evidence
from packages.pipeline.steps.risks import run_risk_rules
from packages.pipeline.steps.snapshot import build_snapshot_from_chart


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate grounded narrative.")
    parser.add_argument("path", type=Path, help="Path to patient JSON bundle.")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser.parse_args()


def _print_narrative(narrative) -> None:
    print(f"patient_id: {narrative.patient_id}")
    print("Summary:")
    for bullet in narrative.summary_bullets:
        print(f"- {bullet}")
        match = re.search(r"\[(S\d+)\]", bullet)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")
    print("Risks:")
    for bullet in narrative.risk_bullets:
        print(f"- {bullet}")
        match = re.search(r"\[(R\d+)\]", bullet)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")
    print("Follow-up questions:")
    for question in narrative.followup_questions:
        print(f"- {question}")
        match = re.search(r"\[(F\d+)\]", question)
        if match:
            cites = narrative.citations.get(match.group(1), [])
            for cite in cites:
                print(f"  - src: {cite}")


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


def _result_to_json(result: PatientAnalysisResult) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def main() -> int:
    args = parse_args()
    if not args.path.exists():
        print(f"File not found: {args.path}", file=sys.stderr)
        return 1

    resources = load_patient_dir(args.path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    snapshot_text = build_snapshot_from_chart(chart)
    patient_id = chart.patient_id
    llm = LLMClient() if args.mode == "llm" else None
    if llm is not None:
        print(f"LLM mode enabled: model={llm.model} base_url={llm.base_url}")
    try:
        narrative = generate_narrative(snapshot_text, patient_id, llm)
    except Exception as exc:
        print(f"LLM failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Falling back to mock mode.", file=sys.stderr)
        narrative = generate_narrative(snapshot_text, patient_id, None)
    if args.json:
        risks = run_risk_rules(chart)
        enrich_evidence(risks, chart, str(args.path))
        result = PatientAnalysisResult(
            snapshot=snapshot_text,
            risks=_serialize_risks(risks),
            narrative=narrative,
            meta={"patient_id": patient_id, "source_path": str(args.path), "mode": "narrative"},
        )
        print(_result_to_json(result))
        return 0

    _print_narrative(narrative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
