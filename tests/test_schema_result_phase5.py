import json

from packages.core.schemas.chart import SourceRef
from packages.core.schemas.result import (
    ContradictionItem,
    MissingInfoItem,
    PatientAnalysisResult,
    TimelineEntry,
)


def _dump_json(result: PatientAnalysisResult) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    return result.json()


def _load_json(payload: str) -> PatientAnalysisResult:
    if hasattr(PatientAnalysisResult, "model_validate_json"):
        return PatientAnalysisResult.model_validate_json(payload)
    return PatientAnalysisResult.parse_raw(payload)


def test_patient_analysis_result_phase5_serialization() -> None:
    evidence = [
        SourceRef(doc_id="Observation/obs1", resource_type="Observation", resource_id="obs1")
    ]
    result = PatientAnalysisResult(
        snapshot="snapshot",
        risks=[],
        narrative=None,
        meta={"patient_id": "test"},
        timeline=[
            TimelineEntry(
                date="2025-01-01",
                type="LAB",
                summary="Lab observation recorded.",
                evidence=evidence,
            )
        ],
        missing_info=[
            MissingInfoItem(
                id="missing_hba1c_recent",
                severity="medium",
                message="No HbA1c Observation found in provided record.",
                evidence=[],
            )
        ],
        contradictions=[
            ContradictionItem(
                id="conflict_med_dose",
                severity="low",
                message="Conflicting medication dosages in record.",
                evidence=evidence,
            )
        ],
    )

    payload = _dump_json(result)
    parsed = _load_json(payload)
    assert parsed.timeline is not None
    assert parsed.missing_info is not None
    assert parsed.contradictions is not None

    data = json.loads(payload)
    assert "timeline" in data and data["timeline"]
    assert "missing_info" in data and data["missing_info"]
    assert "contradictions" in data and data["contradictions"]
