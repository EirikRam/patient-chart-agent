from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from packages.core.llm import LLMClient
from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agents.contradiction_agent import run_contradiction_agent
from packages.pipeline.agents.missing_info_agent import run_missing_info_agent
from packages.pipeline.agents.timeline_agent import run_timeline_agent
from packages.pipeline.agents.verifier_agent import verify_result
from packages.pipeline.evidence_enrich import enrich_evidence, enrich_result_evidence
from packages.pipeline.steps.narrative import generate_narrative
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


def run_agent_pipeline(
    path: str | Path,
    *,
    mode: Literal["mock", "llm"] = "mock",
    enable_agents: bool = False,
    llm_client: Optional[LLMClient] = None,
    llm_debug: bool = False,
    require_llm: bool = False,
) -> PatientAnalysisResult:
    path_obj = Path(path)
    resources = load_patient_dir(path_obj)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)
    snapshot_text = build_snapshot_from_chart(chart)
    risks = run_risk_rules(chart)
    enrich_evidence(risks, chart, str(path_obj))
    llm = llm_client or (LLMClient() if mode == "llm" else None)
    narrative = generate_narrative(
        snapshot_text,
        chart.patient_id,
        llm,
        require_llm=require_llm,
        llm_debug=llm_debug,
    )

    timeline = None
    missing_info = None
    contradictions = None
    if enable_agents:
        timeline = run_timeline_agent(chart)
        missing_info = run_missing_info_agent(chart)
        contradictions = run_contradiction_agent(chart)
        result = PatientAnalysisResult(
            snapshot=snapshot_text,
            risks=_serialize_risks(risks),
            narrative=narrative,
            meta={"patient_id": chart.patient_id, "source_path": str(path_obj), "mode": mode},
            timeline=timeline,
            missing_info=missing_info,
            contradictions=contradictions,
        )
        enrich_result_evidence(result, chart, str(path_obj))
        return verify_result(result)

    return PatientAnalysisResult(
        snapshot=snapshot_text,
        risks=_serialize_risks(risks),
        narrative=narrative,
        meta={"patient_id": chart.patient_id, "source_path": str(path_obj), "mode": mode},
        timeline=timeline,
        missing_info=missing_info,
        contradictions=contradictions,
    )


__all__ = ["run_agent_pipeline"]
