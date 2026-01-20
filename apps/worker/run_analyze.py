from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.core.render.markdown import render_patient_report_md
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


def _result_to_json(result: PatientAnalysisResult) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def _write_markdown_report(path: Path, result: PatientAnalysisResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_patient_report_md(result), encoding="utf-8")


def _normalize_patient_path(path: Path) -> Path:
    if path.exists() and path.is_file():
        return path.parent
    if not path.exists():
        raise FileNotFoundError(
            f"Patient path not found: {path}. Expected a directory or a patient JSON file."
        )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run risk analysis.")
    parser.add_argument("path", type=Path, help="Path to patient JSON bundle.")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--out", type=Path, help="Output path for markdown report.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--phase5", action="store_true", help="Enable phase 5 agents.")
    parser.add_argument("--llm-debug", action="store_true", help="Emit LLM diagnostics.")
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if LLM narrative is unavailable.",
    )
    args = parser.parse_args()

    path = _normalize_patient_path(args.path)
    output_format = args.format
    if args.json:
        output_format = "json"
    if output_format == "md" and args.out is None:
        print("Error: --out is required when --format md is used.", file=sys.stderr)
        return 2

    if args.require_llm and args.mode != "llm":
        print("Error: --require-llm requires --mode llm.", file=sys.stderr)
        return 2

    if args.require_llm and not args.phase5:
        print("Error: --require-llm requires --phase5 to generate a narrative.", file=sys.stderr)
        return 2

    if args.phase5:
        result = run_agent_pipeline(
            path,
            enable_agents=True,
            mode=args.mode,
            llm_debug=args.llm_debug,
            require_llm=args.require_llm,
        )
        resources = load_patient_dir(path)
        grouped = parse_fhir_resources(resources)
        chart = normalize_to_patient_chart(grouped)
        enrich_result_evidence(result, chart, str(path))
        if output_format == "json":
            print(_result_to_json(result))
            return 0
        if output_format == "md":
            _write_markdown_report(args.out, result)
            print(f"Markdown report written to {args.out}")
        return 0

    resources = load_patient_dir(path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)

    risks = run_risk_rules(chart)
    enrich_evidence(risks, chart, str(path))
    snapshot_text = build_snapshot_from_chart(chart)
    result = PatientAnalysisResult(
        snapshot=snapshot_text,
        risks=_serialize_risks(risks),
        narrative=None,
        meta={"patient_id": chart.patient_id, "source_path": str(path), "mode": args.mode},
    )
    if output_format == "json":
        print(_result_to_json(result))
        return 0
    if output_format == "md":
        _write_markdown_report(args.out, result)
        print(f"Markdown report written to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())