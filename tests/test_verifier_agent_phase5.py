from pathlib import Path

import pytest

from packages.core.schemas.chart import SourceRef
from packages.core.schemas.output import NarrativeSummary
from packages.core.schemas.result import ContradictionItem, PatientAnalysisResult
from packages.ingest.synthea.loader import load_patient_dir
from packages.ingest.synthea.normalizer import normalize_to_patient_chart
from packages.ingest.synthea.parser import parse_fhir_resources
from packages.pipeline.agent_pipeline import run_agent_pipeline
from packages.pipeline.agents.verifier_agent import verify_result
from packages.pipeline.evidence_enrich import enrich_result_evidence


def test_verifier_drops_invalid_narrative_citations() -> None:
    narrative = NarrativeSummary(
        patient_id="test",
        summary_bullets=["Test summary [S1]"],
        risk_bullets=[],
        followup_questions=[],
        citations={"S1": ["Observation/does-not-exist"]},
    )
    result = PatientAnalysisResult(
        snapshot="snapshot",
        risks=[
            {
                "rule_id": "lab_a1c_elevated",
                "severity": "medium",
                "message": "test",
                "evidence": [SourceRef(doc_id="Observation/obs1", resource_type="Observation")],
            }
        ],
        narrative=narrative,
        meta={"patient_id": "test"},
    )

    verified = verify_result(result)
    assert verified.narrative is None


def test_verifier_drops_invalid_contradiction_items() -> None:
    result = PatientAnalysisResult(
        snapshot="snapshot",
        risks=[],
        narrative=None,
        meta={"patient_id": "test"},
        contradictions=[
            ContradictionItem(
                id="conflicting_condition_onset",
                severity="low",
                message="Conflicting onset dates.",
                evidence=[SourceRef(doc_id="Condition/cond-1", resource_type="Condition")],
            )
        ],
    )

    verified = verify_result(result)
    assert verified.contradictions == []


def test_verifier_keeps_valid_result() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    result = run_agent_pipeline(sample_path, enable_agents=True, mode="mock")
    resources = load_patient_dir(sample_path)
    grouped = parse_fhir_resources(resources)
    chart = normalize_to_patient_chart(grouped)
    enrich_result_evidence(result, chart, str(sample_path))

    verified = verify_result(result)
    if verified.narrative is not None:
        assert verified.narrative == result.narrative
    assert isinstance(verified.timeline, list)
    assert isinstance(verified.missing_info, list)
    assert isinstance(verified.contradictions, list)
