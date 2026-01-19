from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from packages.core.llm import LLMClient
from packages.core.schemas.result import PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.evidence_enrich import enrich_evidence
from packages.pipeline.steps.narrative import generate_narrative
from packages.pipeline.steps.risks import run_risk_rules
from packages.pipeline.steps.snapshot import build_snapshot_from_chart

router = APIRouter(prefix="/v1")


class AnalyzeRequest(BaseModel):
    path: str
    mode: Literal["mock", "llm"] = "mock"


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


def _error(status: int, code: str, message: str, detail: Optional[dict] = None) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "detail": detail or {}}}
    return JSONResponse(status_code=status, content=payload)


@router.post("/analyze", response_model=PatientAnalysisResult)
def analyze(request: AnalyzeRequest) -> JSONResponse:
    path = Path(request.path)
    if not request.path:
        return _error(400, "invalid_input", "path is required")
    if not path.exists():
        return _error(404, "not_found", "file not found", {"path": request.path})
    if not path.is_file():
        return _error(400, "invalid_input", "path must be a file", {"path": request.path})

    try:
        resources = load_patient_dir(path)
        grouped = parse_fhir_resources(resources)
        chart = normalize_to_patient_chart(grouped)
        snapshot_text = build_snapshot_from_chart(chart)
        risks = run_risk_rules(chart)
        enrich_evidence(risks, chart, request.path)
        llm = LLMClient() if request.mode == "llm" else None
        narrative = generate_narrative(snapshot_text, chart.patient_id, llm)
        result = PatientAnalysisResult(
            snapshot=snapshot_text,
            risks=_serialize_risks(risks),
            narrative=narrative,
            meta={"patient_id": chart.patient_id, "source_path": request.path, "mode": request.mode},
        )
        return JSONResponse(status_code=200, content=jsonable_encoder(result))
    except RuntimeError as exc:
        return _error(500, "runtime_error", str(exc))
    except Exception as exc:
        return _error(500, "internal_error", "unexpected error", {"error": str(exc)})